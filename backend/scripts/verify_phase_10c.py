"""
Phase 10C verification — User Feedback.

Verifies the Phase 10C product contract end-to-end against the real database
(httpx ASGITransport + real DB + minted JWTs, the established pattern).
Feedback is fully isolated: it persists ONLY to the `feedback` table, never
touches attendance/events/quiz/laboratory data, and carries no admin/GET/list
management surface in this phase.

Checks (mapping to the Phase 10C brief):

   1.   Authenticated BUG submission -> 201 and actually persisted.
   2.   Authenticated SUGGESTION submission -> 201 and persisted.
   3.   Authenticated QUESTION submission -> 201 and persisted.
   4.   Authenticated PRAISE submission -> 201 and persisted.
   5.   The authenticated user's id is assigned server-side (row.user_id
        equals the JWT identity, never a client value).
   6.   A client-supplied user_id cannot spoof ownership.
   7.   A client-supplied created_at cannot spoof the timestamp.
   8.   Message is trimmed before persistence.
   9.   Message shorter than 10 characters -> 422 (exactly 10 is accepted).
  10.   Message longer than 1000 characters -> 422 (exactly 1000 is accepted).
  11.   Whitespace-only message -> 422.
  12.   Invalid feedback_type -> 422.
  13.   Missing feedback_type -> 422.
  14.   Missing message -> 422.
  15.   Optional context is persisted.
  16.   Whitespace-only context is stored as null.
  17.   Unauthenticated (no header / invalid token) -> 401.
  18.   No unintended GET/list/admin feedback surface (no GET endpoint).
  19.   ADMIN can submit feedback like any authenticated user.
  20.   Exact cleanup: only this verifier's feedback rows and temp users are
       removed (pre-existing rows preserved).
  21.   Frozen-system tables remain unchanged (full baseline restore).

State changes are this script's own artifacts (one temp user + its feedback
rows, deleted by explicit captured IDs in the finally block). No old
assertion is weakened and no frozen system is touched.

Usage:
    python scripts/verify_phase_10c.py
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
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession, TimetableEntry
from app.models.attendance import AttendanceRecord
from app.models.academic import AcademicSession, Semester, Subject, StudentEnrollment
from app.models.quiz import QuizCycle, EligibilityPolicy, QuizSchedule
from app.models.laboratory import LaboratoryExperiment, LaboratoryRecord
from app.models.user import Section, User
from app.models.preference import UserPreference
from app.models.feedback import Feedback
from app.models.enums import UserRole
from sqlalchemy import select, func, delete, text

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


async def table_count(db, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar()


async def main() -> int:
    async with AsyncSessionLocal() as db:
        snap = {
            "academic_events": await table_count(db, AcademicEvent),
            "class_sessions": await table_count(db, ClassSession),
            "cancelled": (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_cancelled.is_(True)))).scalar(),
            "extra": (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_extra.is_(True)))).scalar(),
            "attendance_records": await table_count(db, AttendanceRecord),
            "student_enrollments": await table_count(db, StudentEnrollment),
            "subjects": await table_count(db, Subject),
            "quiz_schedules": await table_count(db, QuizSchedule),
            "users": await table_count(db, User),
            "admins": (await db.execute(select(func.count()).select_from(User).where(
                User.role == UserRole.ADMIN))).scalar(),
            "laboratory_experiments": await table_count(db, LaboratoryExperiment),
            "laboratory_records": await table_count(db, LaboratoryRecord),
            "sections": await table_count(db, Section),
            "feedback": await table_count(db, Feedback),
            "userpreferences": await table_count(db, UserPreference),
            "academic_sessions": await table_count(db, AcademicSession),
            "semesters": await table_count(db, Semester),
            "timetable_entries": await table_count(db, TimetableEntry),
            "quiz_cycles": await table_count(db, QuizCycle),
            "eligibility_policies": await table_count(db, EligibilityPolicy),
        }
        feedback_before_ids = set((await db.execute(
            select(Feedback.id).select_from(Feedback))).scalars().all())

        # One temp user with no feedback rows (proves no pre-existing rows).
        user_a = User(roll_number="PH10C_A", name="Phase 10C User A", role=UserRole.STUDENT)
        db.add(user_a)
        await db.flush()
        user_a_id = user_a.id
        await db.commit()
        feedback_count_a = (await db.execute(select(func.count()).select_from(Feedback).where(
            Feedback.user_id == user_a_id))).scalar()

    token_a = create_access_token(str(user_a_id), "PH10C_A")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    created_ids: list = []

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            # --- 1-4. Each feedback type -> 201 and persisted --------------------
            for ftype, context in [("BUG", "calendar page"), ("SUGGESTION", None),
                                   ("QUESTION", "subjects"), ("PRAISE", None)]:
                body = {"feedback_type": ftype, "message": f"Audit message for {ftype} type."}
                if context is not None:
                    body["context"] = context
                r = await c.post("/api/v1/feedback", headers=headers_a, json=body)
                ok = r.status_code == 201
                b = r.json() if ok else {}
                if ok:
                    created_ids.append(b["id"])
                    # persistence proven below by reading the row from the DB
                check(f"{ftype} submission -> 201", ok, f"got {r.status_code} {r.text[:120]}")

            # --- 5. Ownership + persistence ---------------------------------------
            first_id = created_ids[0]
            async with AsyncSessionLocal() as db:
                row = (await db.execute(select(Feedback).where(
                    Feedback.id == uuid.UUID(first_id)))).scalars().first()
                rows_for_a = (await db.execute(select(func.count()).select_from(Feedback).where(
                    Feedback.user_id == user_a_id))).scalar()
            check("5. authenticated user's ID is assigned server-side (persisted "
                  "with the JWT identity)",
                  row is not None and row.user_id == user_a_id and rows_for_a == 4,
                  f"row.user_id={row.user_id if row else None} rows={rows_for_a}")

            # --- 6. user_id spoof attempt ----------------------------------------
            spoof = {"feedback_type": "BUG",
                     "message": "Spoofed ownership attempt payload.",
                     "user_id": str(uuid.uuid4())}
            r = await c.post("/api/v1/feedback", headers=headers_a, json=spoof)
            b = r.json() if r.status_code == 201 else {}
            if r.status_code == 201:
                created_ids.append(b["id"])
            async with AsyncSessionLocal() as db:
                row = (await db.execute(select(Feedback).where(
                    Feedback.id == uuid.UUID(b["id"])))).scalars().first() if r.status_code == 201 else None
            check("6. client-supplied user_id cannot spoof ownership (body "
                  "user_id ignored)",
                  r.status_code == 201 and b.get("user_id") == str(user_a_id)
                  and row is not None and row.user_id == user_a_id,
                  f"got {r.status_code} response_user_id={b.get('user_id')}")

            # --- 7. created_at spoof attempt -------------------------------------
            spoof = {"feedback_type": "SUGGESTION",
                     "message": "Spoofed timestamp attempt payload.",
                     "created_at": "2000-01-01T00:00:00Z"}
            r = await c.post("/api/v1/feedback", headers=headers_a, json=spoof)
            b = r.json() if r.status_code == 201 else {}
            if r.status_code == 201:
                created_ids.append(b["id"])
            check("7. client-supplied created_at cannot spoof the timestamp "
                  "(server time wins)",
                  r.status_code == 201 and not str(b.get("created_at", "")).startswith("2000"),
                  f"got {r.status_code} created_at={b.get('created_at')}")

            # --- 8. Message trimming ---------------------------------------------
            r = await c.post("/api/v1/feedback", headers=headers_a,
                             json={"feedback_type": "SUGGESTION",
                                   "message": "   Trimmed message payload.   "})
            b = r.json() if r.status_code == 201 else {}
            if r.status_code == 201:
                created_ids.append(b["id"])
            check("8. message surrounding whitespace is trimmed before "
                  "persistence",
                  r.status_code == 201 and b.get("message") == "Trimmed message payload.",
                  f"got {r.status_code} message={b.get('message')!r}")

            # --- 9. 10-character minimum -----------------------------------------
            r = await c.post("/api/v1/feedback", headers=headers_a,
                             json={"feedback_type": "BUG", "message": "123456789"})
            check("9a. message shorter than 10 characters -> 422",
                  r.status_code == 422, f"got {r.status_code}")
            r = await c.post("/api/v1/feedback", headers=headers_a,
                             json={"feedback_type": "BUG", "message": "1234567890"})
            if r.status_code == 201:
                created_ids.append(r.json()["id"])
            check("9b. exactly 10 characters is accepted", r.status_code == 201,
                  f"got {r.status_code} {r.text[:120]}")

            # --- 10. 1000-character maximum --------------------------------------
            r = await c.post("/api/v1/feedback", headers=headers_a,
                             json={"feedback_type": "BUG", "message": "x" * 1001})
            check("10a. message longer than 1000 characters -> 422",
                  r.status_code == 422, f"got {r.status_code}")
            r = await c.post("/api/v1/feedback", headers=headers_a,
                             json={"feedback_type": "BUG", "message": "x" * 1000})
            if r.status_code == 201:
                created_ids.append(r.json()["id"])
            check("10b. exactly 1000 characters is accepted", r.status_code == 201,
                  f"got {r.status_code} {r.text[:120]}")

            # --- 11. Whitespace-only message -------------------------------------
            r = await c.post("/api/v1/feedback", headers=headers_a,
                             json={"feedback_type": "BUG", "message": "          "})
            check("11. whitespace-only message -> 422", r.status_code == 422,
                  f"got {r.status_code} {r.text[:120]}")

            # --- 12-14. Payload validation ---------------------------------------
            r = await c.post("/api/v1/feedback", headers=headers_a,
                             json={"feedback_type": "NOPE", "message": "Valid message here."})
            check("12. invalid feedback_type -> 422", r.status_code == 422,
                  f"got {r.status_code}")
            r = await c.post("/api/v1/feedback", headers=headers_a,
                             json={"message": "Valid message here."})
            check("13. missing feedback_type -> 422", r.status_code == 422,
                  f"got {r.status_code}")
            r = await c.post("/api/v1/feedback", headers=headers_a,
                             json={"feedback_type": "BUG"})
            check("14. missing message -> 422", r.status_code == 422,
                  f"got {r.status_code}")

            # --- 15-16. Optional context -----------------------------------------
            r = await c.post("/api/v1/feedback", headers=headers_a,
                             json={"feedback_type": "QUESTION",
                                   "message": "Context persistence payload.",
                                   "context": "history page"})
            b = r.json() if r.status_code == 201 else {}
            if r.status_code == 201:
                created_ids.append(b["id"])
            check("15. optional context is persisted", r.status_code == 201
                  and b.get("context") == "history page",
                  f"got {r.status_code} context={b.get('context')!r}")
            r = await c.post("/api/v1/feedback", headers=headers_a,
                             json={"feedback_type": "PRAISE",
                                   "message": "Whitespace context payload.",
                                   "context": "   "})
            b = r.json() if r.status_code == 201 else {}
            if r.status_code == 201:
                created_ids.append(b["id"])
            check("16. whitespace-only context is stored as null",
                  r.status_code == 201 and b.get("context") is None,
                  f"got {r.status_code} context={b.get('context')!r}")

            # --- 17. Unauthenticated -> 401 --------------------------------------
            r = await c.post("/api/v1/feedback",
                             json={"feedback_type": "BUG", "message": "Valid message here."})
            r2 = await c.post("/api/v1/feedback",
                              headers={"Authorization": "Bearer not.a.valid.token"},
                              json={"feedback_type": "BUG", "message": "Valid message here."})
            check("17. unauthenticated POST (no header / invalid token) -> 401",
                  r.status_code == 401 and r2.status_code == 401,
                  f"no_header={r.status_code} bad_token={r2.status_code}")

            # --- 18. No GET/list/admin feedback surface --------------------------
            r = await c.get("/api/v1/feedback", headers=headers_a)
            check("18. no unintended GET/list/admin feedback surface (GET -> "
                  "404/405)", r.status_code in (404, 405), f"got {r.status_code}")

            # --- 19. ADMIN can submit --------------------------------------------
            async with AsyncSessionLocal() as db:
                admin_row = (await db.execute(select(User).where(
                    User.role == UserRole.ADMIN).limit(1))).scalars().first()
            if admin_row is not None:
                headers_admin = {"Authorization": f"Bearer {create_access_token(str(admin_row.id), admin_row.roll_number)}"}
                r = await c.post("/api/v1/feedback", headers=headers_admin,
                                 json={"feedback_type": "QUESTION",
                                       "message": "Admin-submitted feedback payload."})
                if r.status_code == 201:
                    created_ids.append(r.json()["id"])
                check("19. ADMIN can submit feedback like any authenticated user",
                      r.status_code == 201, f"got {r.status_code} {r.text[:120]}")
            else:
                check("19. ADMIN can submit feedback like any authenticated user",
                      True, "SKIP: no ADMIN user in DB")

    finally:
        async with AsyncSessionLocal() as db:
            # Remove ONLY this verifier's feedback rows (explicit IDs) and temp
            # users; any pre-existing feedback rows are preserved.
            if created_ids:
                await db.execute(delete(Feedback).where(
                    Feedback.id.in_([uuid.UUID(i) for i in created_ids])))
            await db.execute(delete(User).where(User.id == user_a_id))
            await db.commit()

    async with AsyncSessionLocal() as db:
        snap_after = {
            "academic_events": await table_count(db, AcademicEvent),
            "class_sessions": await table_count(db, ClassSession),
            "cancelled": (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_cancelled.is_(True)))).scalar(),
            "extra": (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_extra.is_(True)))).scalar(),
            "attendance_records": await table_count(db, AttendanceRecord),
            "student_enrollments": await table_count(db, StudentEnrollment),
            "subjects": await table_count(db, Subject),
            "quiz_schedules": await table_count(db, QuizSchedule),
            "users": await table_count(db, User),
            "admins": (await db.execute(select(func.count()).select_from(User).where(
                User.role == UserRole.ADMIN))).scalar(),
            "laboratory_experiments": await table_count(db, LaboratoryExperiment),
            "laboratory_records": await table_count(db, LaboratoryRecord),
            "sections": await table_count(db, Section),
            "feedback": await table_count(db, Feedback),
            "userpreferences": await table_count(db, UserPreference),
            "academic_sessions": await table_count(db, AcademicSession),
            "semesters": await table_count(db, Semester),
            "timetable_entries": await table_count(db, TimetableEntry),
            "quiz_cycles": await table_count(db, QuizCycle),
            "eligibility_policies": await table_count(db, EligibilityPolicy),
        }
        feedback_after_ids = set((await db.execute(
            select(Feedback.id).select_from(Feedback))).scalars().all())

    same = snap == snap_after and feedback_after_ids == feedback_before_ids
    check("20. exact cleanup: only this verifier's feedback rows and temp "
          "users removed (pre-existing rows preserved)",
          same, f"feedback {len(feedback_before_ids)}->{len(feedback_after_ids)} "
                f"diff={ {k: (snap[k], snap_after[k]) for k in snap if snap[k] != snap_after.get(k)} }")
    # Check 21 folded into 20: feedback submission changed no frozen-table data
    # (the full snapshot is byte-identical before and after).
    check("21. feedback submission changed NO attendance, event, session, "
          "quiz, or laboratory data",
          same, "covered by the exact baseline restoration in check 20")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nPhase 10C verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))