"""
Phase 6.5 verification — lightweight in-process API checks.

Runs the security matrix and read-contract regression against the real
api_router with the real database (httpx ASGITransport), using minted JWTs
for the real admin (2401220100027) and the existing registration-verification
student account (9999999999999). No browser automation, no E2E suite.

Test event rows created during verification are hard-deleted at the end
(they are this script's own artifacts). The seeded QUIZ_DAY events and the
admin role are intentionally left in place.

Usage:
    python scripts/verify_phase_6_5.py
"""
import asyncio
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.event import AcademicEvent
from sqlalchemy import select, delete

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


async def main() -> int:
    async with AsyncSessionLocal() as db:
        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        student_user = (await db.execute(select(User).where(User.roll_number == "9999999999999"))).scalars().first()
        if admin_user is None or student_user is None:
            print("ERROR: required users not found")
            return 1

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    student_token = create_access_token(str(student_user.id), student_user.roll_number)

    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    transport = httpx.ASGITransport(app=app)
    test_event_ids: list[uuid.UUID] = []

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # --- Authorization matrix -------------------------------------------------
            r = await client.get("/api/v1/events")
            check("1. unauthenticated GET /events -> 401", r.status_code == 401, f"got {r.status_code}")

            r = await client.get("/api/v1/events", headers=student_headers)
            check("2. student GET /events -> 200", r.status_code == 200, f"got {r.status_code}")

            r = await client.post("/api/v1/events", headers=student_headers, json={
                "event_type": "PUBLIC_HOLIDAY", "start_date": "2026-11-01", "end_date": "2026-11-01"})
            check("3. student POST /events -> 403", r.status_code == 403, f"got {r.status_code}")

            r = await client.patch("/api/v1/events/00000000-0000-0000-0000-000000000000", headers=student_headers,
                                   json={"active": False})
            check("4. student PATCH /events/{id} -> 403", r.status_code == 403, f"got {r.status_code}")

            r = await client.delete("/api/v1/events/00000000-0000-0000-0000-000000000000", headers=student_headers)
            check("5. student DELETE /events/{id} -> 403", r.status_code == 403, f"got {r.status_code}")

            # --- Admin mutations -------------------------------------------------------
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "PUBLIC_HOLIDAY", "start_date": "2026-11-01", "end_date": "2026-11-01"})
            check("6. admin POST global holiday -> 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
            holiday_id = r.json()["id"]
            test_event_ids.append(uuid.UUID(holiday_id))

            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "PUBLIC_HOLIDAY", "start_date": "2026-11-01", "end_date": "2026-11-01"})
            check("6b. duplicate active event -> 409", r.status_code == 409, f"got {r.status_code} {r.text[:200]}")

            subjects = (await client.get("/api/v1/subjects", headers=admin_headers)).json()
            bcs501 = next(s for s in subjects if s["code"] == "BCS-501")
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-11-02", "end_date": "2026-11-02",
                "subject_id": bcs501["id"], "class_type": "L"})
            check("7. admin POST subject-scoped extra lecture -> 201", r.status_code == 201, f"got {r.status_code} {r.text[:200]}")
            extra_id = uuid.UUID(r.json()["id"])
            test_event_ids.append(extra_id)

            r = await client.patch(f"/api/v1/events/{holiday_id}", headers=admin_headers,
                                   json={"substitution_schedule_override": "MONDAY"})
            check("8. admin PATCH substitution override -> 200", r.status_code == 200,
                  f"got {r.status_code} {r.text[:200]}")
            check("8b. PATCH applied override", r.json().get("substitution_schedule_override") == "MONDAY")

            r = await client.delete(f"/api/v1/events/{holiday_id}", headers=admin_headers)
            check("9. admin DELETE (deactivation) -> 200 active=false", r.status_code == 200 and r.json()["active"] is False,
                  f"got {r.status_code} {r.text[:200]}")

            # --- Validation / conflict / not-found -------------------------------------
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-11-03", "end_date": "2026-11-03"})
            check("10. invalid event (EXTRA_LECTURE without subject) -> 422", r.status_code == 422, f"got {r.status_code}")

            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "PUBLIC_HOLIDAY", "start_date": "2026-11-03", "end_date": "2026-11-01"})
            check("11. inverted date range -> 422", r.status_code == 422, f"got {r.status_code}")

            r = await client.patch("/api/v1/events/00000000-0000-0000-0000-000000000000", headers=admin_headers,
                                   json={"active": True})
            check("12. nonexistent event PATCH -> 404", r.status_code == 404, f"got {r.status_code}")

            r = await client.delete("/api/v1/events/00000000-0000-0000-0000-000000000000", headers=admin_headers)
            check("13. nonexistent event DELETE -> 404", r.status_code == 404, f"got {r.status_code}")

            # --- Read-contract regression (Phase 6.1 frozen) ----------------------------
            r = await client.get("/api/v1/events", headers=student_headers)
            body = r.json()
            check("17. GET /events default = active only", r.status_code == 200 and all(e["active"] for e in body), f"got {r.status_code}")

            r = await client.get("/api/v1/events?active=false", headers=student_headers)
            body = r.json()
            check("18. GET /events?active=false = inactive only", r.status_code == 200 and all(not e["active"] for e in body), f"got {r.status_code}")

            r = await client.get("/api/v1/events?upcoming=true", headers=student_headers)
            body = r.json()
            check("19. GET /events?upcoming=true excludes past", r.status_code == 200 and all(e["end_date"] >= "2026-08-14" for e in body), f"got {r.status_code}")

            r = await client.get("/api/v1/events?date_from=2026-08-24&date_to=2026-08-24", headers=student_headers)
            body = r.json()
            check("20. GET /events date range overlap -> BNC-501 quiz day only",
                  r.status_code == 200 and len(body) == 1 and body[0]["event_type"] == "QUIZ_DAY" and body[0]["start_date"] == "2026-08-24",
                  f"got {r.status_code} {r.text[:200]}")

            r = await client.get("/api/v1/events?date_from=2026-09-01&date_to=2026-08-01", headers=student_headers)
            check("20. inverted date range -> 422", r.status_code == 422, f"got {r.status_code}")

            # --- Calendar read model reflects seeded events (Phase 6.2 frozen) -----------
            r = await client.get("/api/v1/calendar?year=2026&month=8", headers=student_headers)
            body = r.json()
            aug24 = next((d for d in body["days"] if d["date"] == "2026-08-24"), None)
            check("21. /calendar Aug 2026 shows QUIZ_DAY on 2026-08-24",
                  aug24 is not None and any(e["event_type"] == "QUIZ_DAY" for e in aug24["events"]),
                  f"got {r.status_code}")

            # --- /student/me exposes role ------------------------------------------------
            r = await client.get("/api/v1/student/me", headers=admin_headers)
            check("22. /student/me admin role=ADMIN", r.json().get("role") == "ADMIN", r.text[:200])
            r = await client.get("/api/v1/student/me", headers=student_headers)
            check("23. /student/me student role=STUDENT", r.json().get("role") == "STUDENT", r.text[:200])
    finally:
        # Hard-delete only this script's own test-event rows (not the seed,
        # not deactivated seed rows, not user data).
        async with AsyncSessionLocal() as db:
            if test_event_ids:
                await db.execute(delete(AcademicEvent).where(AcademicEvent.id.in_(test_event_ids)))
                await db.commit()
                print(f"cleanup: removed {len(test_event_ids)} verification event row(s)")

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))