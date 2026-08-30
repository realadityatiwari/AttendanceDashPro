"""
Phase 24.11 — Admin & Scope Management verifier.

Proves the admin-management contract end-to-end against the LOCAL development
DB: admin list/detail, scope assign/deactivate/reactivate, authorization
matrix (HEAD_ADMIN only), spoof resistance, and baseline restoration.

The `admin_scopes` table (Phase 23.11) is the authoritative scope store —
reused as-is, no schema change.

LOCALITY GUARD (hard): forces + asserts DATABASE_URI is the local dev DB.
"""
import asyncio, os, sys, uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

LOCAL_URI = "postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/attendancedash"
os.environ["DATABASE_URI"] = LOCAL_URI
from app.core.config import settings
_effective = settings.DATABASE_URI
if "127.0.0.1:55432" not in _effective and "localhost:55432" not in _effective:
    print(f"LOCALITY GUARD ABORT ({_effective})"); sys.exit(2)
if "attendancedash" not in _effective:
    print(f"LOCALITY GUARD ABORT: not attendancedash ({_effective})"); sys.exit(2)

from sqlalchemy import delete, func, select, text, update
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.db.session import AsyncSessionLocal
from app.models.user import User, Section
from app.models.admin_scope import AdminScope
from app.models.academic import Subject, AcademicSession
from app.models.enums import AdminRole, UserRole
from app.core.security import create_access_token

results = []; _BASELINE = {}; _ACTIVE_SESSION_ID = None

def check(n, ok, d=""): results.append((n, ok)); print(f"{'PASS' if ok else 'FAIL'}  {n}" + (f"  -- {d}" if not ok else ""))

async def counts(db):
    out = {}
    for t in ["users", "admin_scopes", "academic_sessions", "semesters", "sections",
              "subsections", "subjects", "academic_events", "class_sessions",
              "attendance_records", "student_elective_choices", "timetable_entries",
              "occurrence_outcomes", "quiz_schedules"]:
        out[t] = (await db.execute(select(func.count()).select_from(text(f'"{t}"')))).scalar_one()
    return out

async def main() -> int:
    global _BASELINE, _ACTIVE_SESSION_ID
    print("=" * 64)
    print("Phase 24.11 — Admin & Scope Management")
    print(f"Locality guard: {settings.DATABASE_URI}")
    print("=" * 64)
    fx = {}
    try:
        async with AsyncSessionLocal() as db:
            active = (await db.execute(select(AcademicSession).where(AcademicSession.is_active.is_(True)))).scalars().first()
            if active is None: check("0. active session", False); return 1
            _ACTIVE_SESSION_ID = active.id
            admin = (await db.execute(select(User).where(User.role == UserRole.ADMIN))).scalars().first()
            if admin is None: check("0. admin user", False); return 1
            _BASELINE = await counts(db)
            print(f"baseline: {_BASELINE}")

            section = (await db.execute(select(Section))).scalars().first()
            bcs58 = (await db.execute(select(Subject).where(Subject.code == "BCS-058"))).scalars().first()
            bcs501 = (await db.execute(select(Subject).where(Subject.code == "BCS-501"))).scalars().first()
            if not all([section, bcs58, bcs501]):
                check("0. section + subjects found", False); return 1
            fx["section"] = section.id; fx["bcs58"] = bcs58.id; fx["bcs501"] = bcs501.id

            # Fixture target user (STUDENT; will receive a scope) + scoped admins
            target = User(roll_number=f"2401350{uuid.uuid4().hex[:6]}", name="Ph2411 Target", hashed_password="x", section_id=section.id)
            classAdmin = User(roll_number=f"2401351{uuid.uuid4().hex[:6]}", name="Ph2411 CLASS", hashed_password="x", section_id=section.id)
            elecAdmin = User(roll_number=f"2401352{uuid.uuid4().hex[:6]}", name="Ph2411 ELEC", hashed_password="x", section_id=section.id)
            stu = User(roll_number=f"2401353{uuid.uuid4().hex[:6]}", name="Ph2411 STU", hashed_password="x", section_id=section.id)
            db.add_all([target, classAdmin, elecAdmin, stu]); await db.flush()
            fx["target"] = target.id; fx["classAdmin"] = classAdmin.id
            fx["elecAdmin"] = elecAdmin.id; fx["stu"] = stu.id
            db.add_all([
                AdminScope(user_id=classAdmin.id, role=AdminRole.CLASS_ADMIN, section_id=section.id),
                AdminScope(user_id=elecAdmin.id, role=AdminRole.ELECTIVE_ADMIN, subject_id=bcs58.id),
            ])
            await db.commit()

        transport = ASGITransport(app=app)
        A = "/api/v1/admin/admins"
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            async def tok(uid):
                u = (await db.execute(select(User).where(User.id == uid))).scalars().first()
                return create_access_token(subject=str(u.id), roll_number=u.roll_number)
            async with AsyncSessionLocal() as db:
                t_head = await tok(admin.id)
                t_class = await tok(fx["classAdmin"])
                t_elec = await tok(fx["elecAdmin"])
                t_stu = await tok(fx["stu"])
            h = {"Authorization": f"Bearer {t_head}"}

            # A. unauth -> 401
            r = await c.get(A); check("A1. unauth GET -> 401", r.status_code == 401)
            r = await c.post(f"{A}/{fx['target']}/scopes", json={}); check("A2. unauth POST -> 401", r.status_code == 401)

            # B. STUDENT -> 403
            r = await c.get(A, headers={"Authorization": f"Bearer {t_stu}"})
            check("B1. STUDENT GET -> 403", r.status_code == 403, str(r.status_code))

            # B2. scoped admins (CLASS / ELECTIVE) -> 403 (matrix FULL | NO | NO | NO)
            r = await c.get(A, headers={"Authorization": f"Bearer {t_class}"})
            check("B2. CLASS_ADMIN GET -> 403", r.status_code == 403, str(r.status_code))
            r = await c.get(A, headers={"Authorization": f"Bearer {t_elec}"})
            check("B3. ELECTIVE_ADMIN GET -> 403", r.status_code == 403, str(r.status_code))
            r = await c.post(f"{A}/{fx['target']}/scopes",
                             json={"role": "CLASS_ADMIN", "section_id": str(fx["section"])},
                             headers={"Authorization": f"Bearer {t_class}"})
            check("B4. CLASS_ADMIN assign -> 403", r.status_code == 403, str(r.status_code))

            # C. HEAD list -> all admin users (legacy ADMIN + scoped fixtures)
            r = await c.get(A, headers=h)
            check("C1. HEAD list -> 200", r.status_code == 200)
            items = r.json()["items"]
            check("C2. list includes legacy ADMIN (global)",
                  any(i["is_global"] for i in items), str([i["display_name"] for i in items]))
            check("C3. list includes fixture CLASS_ADMIN + ELECTIVE_ADMIN",
                  any(i["display_name"] == "Ph2411 CLASS" and i["active_scope_count"] == 1 for i in items)
                  and any(i["display_name"] == "Ph2411 ELEC" and i["active_scope_count"] == 1 for i in items),
                  str([(i["display_name"], i["active_scope_count"]) for i in items]))

            # D. HEAD detail with scopes
            r = await c.get(f"{A}/{fx['classAdmin']}", headers=h)
            check("D1. detail -> 200", r.status_code == 200, str(r.status_code))
            d = r.json()
            check("D2. detail roles include CLASS_ADMIN", "CLASS_ADMIN" in d["roles"], str(d["roles"]))
            check("D3. detail scope row resolved (section name)",
                  len(d["scopes"]) == 1 and d["scopes"][0]["section_name"] is not None,
                  str(d["scopes"]))

            # E. Nonexistent user -> 404
            r = await c.get(f"{A}/{uuid.uuid4()}", headers=h)
            check("E1. nonexistent admin detail -> 404", r.status_code == 404, str(r.status_code))

            # F. Assign CLASS_ADMIN scope to the target user (valid)
            r = await c.post(f"{A}/{fx['target']}/scopes",
                             json={"role": "CLASS_ADMIN", "section_id": str(fx["section"])}, headers=h)
            check("F1. assign CLASS_ADMIN -> 201", r.status_code == 201, str(r.status_code))
            fx["scope1"] = r.json()["scope"]["id"] if r.status_code == 201 else None
            check("F2. assigned scope active", r.json()["scope"]["active"] is True)

            # F3. Assign ELECTIVE_ADMIN to target (second scope, different role)
            r = await c.post(f"{A}/{fx['target']}/scopes",
                             json={"role": "ELECTIVE_ADMIN", "subject_id": str(fx["bcs58"])}, headers=h)
            check("F3. assign ELECTIVE_ADMIN -> 201", r.status_code == 201, str(r.status_code))
            fx["scope2"] = r.json()["scope"]["id"] if r.status_code == 201 else None

            # G. Duplicate active scope (same user/role/target) -> 409
            r = await c.post(f"{A}/{fx['target']}/scopes",
                             json={"role": "CLASS_ADMIN", "section_id": str(fx["section"])}, headers=h)
            check("G1. duplicate CLASS_ADMIN scope -> 409", r.status_code == 409, str(r.status_code))

            # H. Invalid role-shape -> 422
            r = await c.post(f"{A}/{fx['target']}/scopes",
                             json={"role": "CLASS_ADMIN", "subject_id": str(fx["bcs58"])}, headers=h)
            check("H1. CLASS_ADMIN with subject instead of section -> 422", r.status_code == 422, str(r.status_code))
            r = await c.post(f"{A}/{fx['target']}/scopes",
                             json={"role": "ELECTIVE_ADMIN", "section_id": str(fx["section"])}, headers=h)
            check("H2. ELECTIVE_ADMIN with section instead of subject -> 422", r.status_code == 422, str(r.status_code))

            # I. HEAD_ADMIN scope row cannot be created -> 409
            r = await c.post(f"{A}/{fx['target']}/scopes", json={"role": "HEAD_ADMIN"}, headers=h)
            check("I1. HEAD_ADMIN scope row rejected -> 409", r.status_code == 409, str(r.status_code))

            # J. Nonexistent target (section/subject) -> 404
            r = await c.post(f"{A}/{fx['target']}/scopes",
                             json={"role": "CLASS_ADMIN", "section_id": str(uuid.uuid4())}, headers=h)
            check("J1. nonexistent section -> 404", r.status_code == 404, str(r.status_code))
            r = await c.post(f"{A}/{fx['target']}/scopes",
                             json={"role": "ELECTIVE_ADMIN", "subject_id": str(uuid.uuid4())}, headers=h)
            check("J2. nonexistent subject -> 404", r.status_code == 404, str(r.status_code))

            # K. Revoke (deactivate) a scope -> row preserved, active=false
            r = await c.patch(f"{A}/{fx['target']}/scopes/{fx['scope1']}", json={"active": False}, headers=h)
            check("K1. revoke scope1 -> 200", r.status_code == 200, str(r.status_code))
            check("K2. revoked scope inactive (row preserved)", r.json()["scope"]["active"] is False)
            r = await c.get(f"{A}/{fx['target']}", headers=h)
            d = r.json()
            check("K3. inactive scope still listed in detail",
                  any(s["id"] == fx["scope1"] and s["active"] is False for s in d["scopes"]), str(d["scopes"]))

            # L. Reactivate scope1
            r = await c.patch(f"{A}/{fx['target']}/scopes/{fx['scope1']}", json={"active": True}, headers=h)
            check("L1. reactivate scope1 -> 200", r.status_code == 200 and r.json()["scope"]["active"] is True,
                  str(r.status_code))

            # M. Cross-user scope ID -> 404 (no leak)
            r = await c.patch(f"{A}/{fx['stu']}/scopes/{fx['scope2']}", json={"active": False}, headers=h)
            check("M1. scope ID from another user -> 404", r.status_code == 404, str(r.status_code))

            # N. Spoofing: role/scope query params cannot elevate scoped admins
            r = await c.get(A, params={"role": "HEAD_ADMIN"}, headers={"Authorization": f"Bearer {t_class}"})
            check("N1. query role cannot elevate CLASS_ADMIN -> 403", r.status_code == 403, str(r.status_code))
            r = await c.post(f"{A}/{fx['target']}/scopes",
                             json={"role": "HEAD_ADMIN", "section_id": str(fx["section"])},
                             params={"scope": "global"}, headers={"Authorization": f"Bearer {t_stu}"})
            check("N2. spoofed scope param cannot elevate STUDENT -> 403", r.status_code == 403, str(r.status_code))

        passed = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.11 verifier (core): {passed}/{len(results)} PASS")
        return 0 if passed == len(results) else 1

    finally:
        async with AsyncSessionLocal() as db:
            try:
                # Clean fixture scopes + users (target received scopes during the run).
                if fx.get("target"):
                    await db.execute(delete(AdminScope).where(AdminScope.user_id == fx["target"]))
                if fx.get("section"):
                    for k in ("classAdmin", "elecAdmin", "target", "stu"):
                        if fx.get(k):
                            await db.execute(delete(AdminScope).where(AdminScope.user_id == fx[k]))
                            await db.execute(delete(User).where(User.id == fx[k]))
                if _ACTIVE_SESSION_ID:
                    await db.execute(update(AcademicSession).where(
                        AcademicSession.id == _ACTIVE_SESSION_ID).values(is_active=True))
                await db.commit()
            except Exception as e: print(f"cleanup: {e}"); await db.rollback()

async def post_cleanup():
    async with AsyncSessionLocal() as db:
        after = await counts(db)
        check("O1. baseline restored", after == _BASELINE, f"before={_BASELINE} after={after}")
        a = (await db.execute(select(AcademicSession).where(AcademicSession.is_active.is_(True)))).scalars().first()
        check("O2. active session unchanged", a is not None and a.id == _ACTIVE_SESSION_ID)

if __name__ == "__main__":
    async def _run():
        c = await main()
        await post_cleanup()
        p = sum(1 for _, ok in results if ok)
        print(f"\nPhase 24.11 verifier: {p}/{len(results)} PASS")
        return 0 if p == len(results) else 1
    sys.exit(asyncio.run(_run()))