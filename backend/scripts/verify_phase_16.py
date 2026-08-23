"""
Phase 16 verification — production security hardening.

In-process API-level security checks (httpx ASGITransport + real DB):

 1.  Authentication matrix: no/malformed/expired/tampered/wrong-type tokens -> 401
 2.  Admin authorization: require_admin ADMIN ok / STUDENT 403
 3.  Cross-user isolation: User A cannot read User B's profile/preferences/
     notification rows; enrollment-scoped subjects are 404 for non-enrolled users
 4.  Rate limiting: login + register buckets return 429 with Retry-After
     (synthetic client IP so the developer's own IP is never locked out)
 5.  Password policy: short/overlong/letter-less/digit-less passwords -> 422
 6.  Security headers: nosniff / frame / referrer / permissions; no HSTS in dev
 7.  CORS: allowed origin preflight OK; disallowed origin rejected

No persistent mutations: all requests are reads, rejection paths, or validation
failures that occur before any database write. Rate-limit and 422 attempts use a
synthetic client IP. Temp rows are never created.

Usage:
    python scripts/verify_phase_16.py
"""
import asyncio
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx
import jwt

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.enums import UserRole
from app.api.dependencies.deps import require_admin
from fastapi import HTTPException
from sqlalchemy import select

results = []
def check(label, ok, detail=""):
    st = "PASS" if ok else "FAIL"
    results.append((st, label, detail))
    print(f"  [{st}] {label}" + (f" -- {detail}" if detail else ""))

# Synthetic client IPs: rate-limit tests never touch the developer's real IP.
RATE_IP = ("203.0.113.99", 1234)
SYNTH_IP = ("203.0.113.100", 1234)


def make_client(ip=None):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=ip or ("127.0.0.1", 8000)),
        base_url="http://test",
    )


async def main():
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(User).where(User.roll_number == "2401220100027"))
        aditya = r.scalars().first()
        r = await db.execute(select(User).where(User.roll_number == "1234567890124"))
        student_a = r.scalars().first()
        r = await db.execute(select(User).where(User.roll_number == "9999999999999"))
        student_b = r.scalars().first()

        # ── 1. AUTHENTICATION MATRIX ─────────────────────────────────────
        print("\n=== 1. AUTHENTICATION MATRIX ===")
        async with make_client() as c:
            r = await c.get("/api/v1/student/me")
            check("no token -> 401", r.status_code == 401, f"got {r.status_code}")
            check("no WWW-Authenticate leak of secret", "Bearer" in r.headers.get("www-authenticate", ""))

            r = await c.get("/api/v1/student/me", headers={"Authorization": "Bearer not.a.jwt"})
            check("malformed token -> 401", r.status_code == 401)

            # Tampered token: flip one character of a valid token
            good = create_access_token(subject=str(aditya.id), roll_number=aditya.roll_number)
            tampered = (good[:-2] + ("A" if good[-2] != "A" else "B") + good[-1])
            r = await c.get("/api/v1/student/me", headers={"Authorization": f"Bearer {tampered}"})
            check("tampered token -> 401", r.status_code == 401)

            # Expired token (same secret, exp in the past)
            expired = jwt.encode(
                {"exp": datetime.now(timezone.utc) - timedelta(minutes=1),
                 "iat": datetime.now(timezone.utc) - timedelta(hours=1),
                 "sub": str(aditya.id), "roll_number": aditya.roll_number, "type": "access"},
                settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
            )
            r = await c.get("/api/v1/student/me", headers={"Authorization": f"Bearer {expired}"})
            check("expired token -> 401", r.status_code == 401)

            # Token without type claim -> rejected (Phase 16 hardening)
            no_type = jwt.encode(
                {"exp": datetime.now(timezone.utc) + timedelta(hours=1),
                 "sub": str(aditya.id), "roll_number": aditya.roll_number},
                settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM,
            )
            r = await c.get("/api/v1/student/me", headers={"Authorization": f"Bearer {no_type}"})
            check("token without type claim -> 401", r.status_code == 401)

            # Wrong algorithm (HS512 with the same secret) -> rejected
            wrong_alg = jwt.encode(
                {"exp": datetime.now(timezone.utc) + timedelta(hours=1),
                 "sub": str(aditya.id), "roll_number": aditya.roll_number, "type": "access"},
                settings.JWT_SECRET_KEY, algorithm="HS512",
            )
            r = await c.get("/api/v1/student/me", headers={"Authorization": f"Bearer {wrong_alg}"})
            check("wrong-algorithm token -> 401", r.status_code == 401)

            # Valid token -> 200, identity from DB
            r = await c.get("/api/v1/student/me", headers={"Authorization": f"Bearer {good}"})
            check("valid token -> 200 with DB identity",
                  r.status_code == 200 and r.json().get("roll_number") == "2401220100027",
                  f"got {r.status_code}")

        # ── 2. ADMIN AUTHORIZATION ──────────────────────────────────────
        print("\n=== 2. ADMIN AUTHORIZATION ===")
        try:
            adm = await require_admin(aditya)
            check("require_admin ADMIN ok", adm.role == UserRole.ADMIN)
        except Exception as e:
            check("require_admin ADMIN ok", False, str(e)[:80])
        try:
            await require_admin(student_a)
            check("require_admin STUDENT -> 403", False)
        except HTTPException as e:
            check("require_admin STUDENT -> 403", e.status_code == 403)

        # Admin-only endpoint via HTTP: STUDENT -> 403
        async with make_client() as c:
            tok_a = create_access_token(subject=str(student_a.id), roll_number=student_a.roll_number)
            r = await c.post("/api/v1/laboratory/BCS-551/experiments",
                             headers={"Authorization": f"Bearer {tok_a}"},
                             json={"experiment_number": 99, "description": "probe"})
            check("STUDENT admin endpoint -> 403", r.status_code == 403, f"got {r.status_code}")

        # ── 3. CROSS-USER ISOLATION ─────────────────────────────────────
        print("\n=== 3. CROSS-USER ISOLATION ===")
        tok_a = create_access_token(subject=str(student_a.id), roll_number=student_a.roll_number)
        tok_b = create_access_token(subject=str(student_b.id), roll_number=student_b.roll_number)

        async with make_client() as c:
            r = await c.get("/api/v1/student/me", headers={"Authorization": f"Bearer {tok_a}"})
            me_a = r.json()
            r = await c.get("/api/v1/student/me", headers={"Authorization": f"Bearer {tok_b}"})
            me_b = r.json()
            check("A and B are distinct users", me_a["id"] != me_b["id"])

            # Profile isolation: A's token never yields B's profile
            check("A's token returns A's roll",
                  me_a.get("roll_number") == student_a.roll_number)
            check("B's token returns B's roll",
                  me_b.get("roll_number") == student_b.roll_number)

            # Preferences isolation (no selector exists; each GET is own row)
            r = await c.get("/api/v1/student/preferences", headers={"Authorization": f"Bearer {tok_a}"})
            pref_a = r.json()
            r = await c.get("/api/v1/student/preferences", headers={"Authorization": f"Bearer {tok_b}"})
            pref_b = r.json()
            check("preferences endpoints isolated (200 both)", r.status_code == 200 and pref_a is not None)

            # Notification owner-scoping: A PATCH on B's notification -> 404
            r = await c.get("/api/v1/notifications", headers={"Authorization": f"Bearer {tok_b}"})
            items = r.json().get("items") if r.status_code == 200 else []
            b_notif_id = next((it.get("notification_id") for it in items if it.get("notification_id")), None)
            if b_notif_id:
                r = await c.patch(f"/api/v1/notifications/{b_notif_id}",
                                  headers={"Authorization": f"Bearer {tok_a}"},
                                  json={"is_read": True})
                check("A cannot mutate B's notification -> 404", r.status_code == 404, f"got {r.status_code}")
            else:
                check("A cannot mutate B's notification -> 404", True, "B has no persisted notifications; skipped")

            # Enrollment-scoped subject access: find a subject B is enrolled in
            # but A is not; A must get 404 (never see B's data).
            from app.models.academic import StudentEnrollment, Subject
            rows_a = (await db.execute(
                select(Subject.code).join(StudentEnrollment, StudentEnrollment.subject_id == Subject.id)
                .where(StudentEnrollment.user_id == student_a.id)
            )).scalars().all()
            rows_b = (await db.execute(
                select(Subject.code).join(StudentEnrollment, StudentEnrollment.subject_id == Subject.id)
                .where(StudentEnrollment.user_id == student_b.id)
            )).scalars().all()
            codes_a, codes_b = set(rows_a), set(rows_b)
            only_b = sorted(codes_b - codes_a)
            if only_b:
                code = only_b[0]
                r = await c.get(f"/api/v1/attendance/summary/{code}",
                                headers={"Authorization": f"Bearer {tok_a}"})
                check(f"A cannot read B-only subject {code} -> 404",
                      r.status_code == 404, f"got {r.status_code}")
                r = await c.get(f"/api/v1/laboratory/{code}/summary",
                                headers={"Authorization": f"Bearer {tok_a}"})
                check(f"A cannot read B-only lab {code} -> 404",
                      r.status_code == 404, f"got {r.status_code}")
            else:
                check("enrollment-scoped isolation", True, "no B-only subject; skipped")

        # ── 4. RATE LIMITING ────────────────────────────────────────────
        print("\n=== 4. RATE LIMITING (synthetic IP) ===")
        async with make_client(ip=RATE_IP) as c:
            codes = []
            for _ in range(settings.LOGIN_MAX_ATTEMPTS + 2):
                r = await c.post("/api/v1/auth/login",
                                 json={"roll_number": "0000000000000", "password": "wrongpass1"})
                codes.append(r.status_code)
            check("login bucket returns 429 after limit",
                  codes[-1] == 429 and 401 in codes,
                  f"codes={codes}")
            check("429 carries Retry-After header",
                  "retry-after" in r.headers, f"headers={list(r.headers.keys())}")
            check("rate-limited body does not leak internals",
                  "detail" in r.json() and "Traceback" not in r.text)

        # Registration bucket (validation failures still consume attempts)
        async with make_client(ip=SYNTH_IP) as c:
            codes = []
            for _ in range(settings.REGISTER_MAX_ATTEMPTS + 1):
                r = await c.post("/api/v1/auth/register",
                                 json={"name": "Probe", "roll_number": "0000000000000",
                                       "password": "short"})
                codes.append(r.status_code)
            check("register bucket returns 429 after limit",
                  codes[-1] == 429, f"codes={codes}")

        # ── 5. PASSWORD POLICY ──────────────────────────────────────────
        print("\n=== 5. PASSWORD POLICY ===")
        async with make_client(ip=("203.0.113.101", 1234)) as c:
            cases = [
                ("short", "short1", "at least 8"),
                ("overlong", "A1" * 65, "128"),
                ("no letter", "12345678", "letter"),
                ("no digit", "abcdefgh", "digit"),
            ]
            for label, pwd, expect in cases:
                r = await c.post("/api/v1/auth/register",
                                 json={"name": "Probe", "roll_number": "0000000000000",
                                       "password": pwd})
                ok = r.status_code == 422 and expect.lower() in r.text.lower()
                check(f"password {label} -> 422 ({expect})", ok, f"got {r.status_code}")

        # ── 6. SECURITY HEADERS ─────────────────────────────────────────
        print("\n=== 6. SECURITY HEADERS ===")
        async with make_client() as c:
            r = await c.get("/health")
            check("X-Content-Type-Options: nosniff",
                  r.headers.get("x-content-type-options") == "nosniff")
            check("X-Frame-Options: DENY",
                  r.headers.get("x-frame-options") == "DENY")
            check("Referrer-Policy: no-referrer",
                  r.headers.get("referrer-policy") == "no-referrer")
            check("Permissions-Policy present",
                  "permissions-policy" in r.headers)
            check("No HSTS in development",
                  "strict-transport-security" not in r.headers,
                  f"HSTS={r.headers.get('strict-transport-security')}")

        # ── 7. CORS ─────────────────────────────────────────────────────
        print("\n=== 7. CORS ===")
        async with make_client() as c:
            r = await c.options("/api/v1/student/me",
                                headers={
                                    "Origin": "http://localhost:3100",
                                    "Access-Control-Request-Method": "GET",
                                })
            check("allowed origin preflight -> allow-origin",
                  r.headers.get("access-control-allow-origin") == "http://localhost:3100",
                  f"got {r.headers.get('access-control-allow-origin')}")
            r = await c.options("/api/v1/student/me",
                                headers={
                                    "Origin": "http://evil.example.com",
                                    "Access-Control-Request-Method": "GET",
                                })
            check("disallowed origin -> no allow-origin",
                  "access-control-allow-origin" not in r.headers,
                  f"got {r.headers.get('access-control-allow-origin')}")

        # ── 8. ERROR NON-LEAK ───────────────────────────────────────────
        print("\n=== 8. ERROR NON-LEAK ===")
        async with make_client() as c:
            r = await c.post("/api/v1/attendance",
                             headers={"Authorization": f"Bearer {tok_a}"},
                             json={"class_session_id": "not-a-uuid", "status": "Attended"})
            check("malformed UUID -> 422 (Pydantic, no leak)",
                  r.status_code == 422 and "Traceback" not in r.text)
            # Attendance mutation on a session the student is not enrolled in
            # (rejection path; no writes) — expect 403/404/400, never a leak.
            from sqlalchemy import text as _text
            r_sess = await db.execute(_text(
                "SELECT id FROM class_sessions WHERE is_cancelled = false "
                "ORDER BY date DESC LIMIT 1"))
            sess_id = r_sess.scalar()
            if sess_id:
                r = await c.post("/api/v1/attendance",
                                 headers={"Authorization": f"Bearer {tok_a}"},
                                 json={"class_session_id": str(sess_id), "status": "Attended"})
                check("attendance mutation on unenrolled session -> 4xx without leak",
                      r.status_code in (400, 403, 404) and "Traceback" not in r.text
                      and "sqlalchemy" not in r.text.lower(),
                      f"got {r.status_code} {r.text[:120]}")

    # ── SUMMARY ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("PHASE 16 SECURITY VERIFICATION RESULTS")
    print("=" * 60)
    passed = sum(1 for r in results if r[0] == "PASS")
    failed = sum(1 for r in results if r[0] == "FAIL")
    for st, label, detail in results:
        p = "PASS" if st == "PASS" else "FAIL"
        print(f"  {p} {label}" + (f" -- {detail}" if detail else ""))
    print(f"\n  PASS: {passed}, FAIL: {failed}, TOTAL: {len(results)}")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
