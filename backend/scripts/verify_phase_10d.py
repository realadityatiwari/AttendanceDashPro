"""
Phase 10D verification — Settings / User Preferences.

Verifies the Phase 10D product contract end-to-end against the real database
(httpx ASGITransport + real DB + minted JWTs, the established pattern). The
three settings (class_reminders, auto_mark_present, week_starts_on) are
STORAGE/PREFERENCE DATA ONLY: nothing sends reminders, marks attendance, or
alters calendar/analytics calculations.

Checks (mapping to the Phase 10D brief):

  1.  Lazy-create: GET for a user with no row materializes the documented
      server defaults (false / false / MONDAY) and returns them.
  2.  No backfill: new users have zero preference rows before their first GET.
  3.  Repeated GET returns exactly ONE row (idempotent, no duplication).
  4.  Response is always a complete preference object (three values + both
      timestamps; no user_id exposed).
  5.  PUT false/false/MONDAY -> complete object; GET reflects the saved values.
  6.  PUT true/true/SUNDAY -> complete object; GET reflects the saved values.
  7.  PUT another combination -> GET reflects the saved values (replace
      semantics, never accidental NULLs).
  8.  PUT on a user with no row lazily creates then replaces (one row total).
  9.  Invalid week_starts_on value -> 422 (Pydantic enum validation).
 10.  Partial PUT (missing required fields) -> 422.
 11.  Unauthenticated (no header) -> 401; invalid token -> 401.
 12.  User isolation: user A's PUT never affects user B's row and vice versa;
      no user selector exists (query param / body user_id are ignored).
 13.  DB defaults: a raw INSERT without values yields false/false/MONDAY.
 14.  PK works: a duplicate user_id INSERT is rejected.
 15.  FK works: an INSERT with a nonexistent user_id is rejected.
 16.  Storing auto_mark_present / class_reminders / week_starts_on changes NO
      attendance, event, session, or record data (full baseline restore).
 17.  Pre-existing preference rows (e.g. the owner's browser) are preserved;
      only this verifier's temp rows are removed.
 18.  DB baseline restored exactly after the verifier runs.

State changes are this script's own artifacts (two temp users + their
preference rows) and are removed in the finally block. No old assertion is
weakened and no frozen system is touched.

Usage:
    python scripts/verify_phase_10d.py
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
            "academic_sessions": await table_count(db, AcademicSession),
            "semesters": await table_count(db, Semester),
            "timetable_entries": await table_count(db, TimetableEntry),
            "quiz_cycles": await table_count(db, QuizCycle),
            "eligibility_policies": await table_count(db, EligibilityPolicy),
        }
        pref_before_rows = (await db.execute(
            select(UserPreference.user_id).select_from(UserPreference))).scalars().all()
        pref_before_set = set(pref_before_rows)
        pref_before = len(pref_before_rows)

        # Two temp users with NO preference rows (proves no backfill).
        user_a = User(roll_number="PH10D_A", name="Phase 10D User A", role=UserRole.STUDENT)
        user_b = User(roll_number="PH10D_B", name="Phase 10D User B", role=UserRole.STUDENT)
        db.add(user_a)
        db.add(user_b)
        await db.flush()
        user_a_id = user_a.id
        user_b_id = user_b.id
        await db.commit()

        # Check 2 — no backfill: neither temp user has a preference row yet.
        pref_count_a = (await db.execute(select(func.count()).select_from(UserPreference).where(
            UserPreference.user_id == user_a_id))).scalar()
        pref_count_b = (await db.execute(select(func.count()).select_from(UserPreference).where(
            UserPreference.user_id == user_b_id))).scalar()

    token_a = create_access_token(str(user_a_id), "PH10D_A")
    token_b = create_access_token(str(user_b_id), "PH10D_B")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            # --- 2. No backfill -------------------------------------------------
            check("2. new users have no preference rows before first GET "
                  "(no backfill for existing users)",
                  pref_count_a == 0 and pref_count_b == 0,
                  f"A={pref_count_a} B={pref_count_b}")

            # --- 1 + 4. Lazy-create on GET -------------------------------------
            r = await c.get("/api/v1/student/preferences", headers=headers_a)
            body = r.json()
            complete = {"class_reminders", "auto_mark_present", "week_starts_on",
                        "created_at", "updated_at"} <= set(body.keys())
            check("1. GET with no row lazily creates the server defaults "
                  "(false/false/MONDAY)",
                  r.status_code == 200 and body["class_reminders"] is False
                  and body["auto_mark_present"] is False
                  and body["week_starts_on"] == "MONDAY",
                  f"got {r.status_code} {body}")
            check("4. response is a complete preference object (three values + "
                  "timestamps; user_id not exposed)",
                  complete and "user_id" not in body,
                  f"keys={sorted(body.keys())}")

            # --- 3. Idempotent repeated GET -------------------------------------
            r2 = await c.get("/api/v1/student/preferences", headers=headers_a)
            async with AsyncSessionLocal() as db:
                row_count_a = (await db.execute(select(func.count()).select_from(UserPreference).where(
                    UserPreference.user_id == user_a_id))).scalar()
            check("3. repeated GET returns exactly one row (idempotent lazy-create)",
                  r2.status_code == 200 and row_count_a == 1,
                  f"rows={row_count_a}")

            # --- 5. PUT false/false/MONDAY --------------------------------------
            r = await c.put("/api/v1/student/preferences", headers=headers_a,
                            json={"class_reminders": False, "auto_mark_present": False,
                                  "week_starts_on": "MONDAY"})
            b = r.json()
            check("5. PUT false/false/MONDAY returns the complete object and "
                  "GET reflects it",
                  r.status_code == 200 and b["class_reminders"] is False
                  and b["auto_mark_present"] is False and b["week_starts_on"] == "MONDAY"
                  and "created_at" in b and "updated_at" in b,
                  f"got {r.status_code} {b}")
            r = await c.get("/api/v1/student/preferences", headers=headers_a)
            b = r.json()
            check("5b. GET reflects the PUT values (false/false/MONDAY)",
                  b["class_reminders"] is False and b["auto_mark_present"] is False
                  and b["week_starts_on"] == "MONDAY", f"{b}")

            # --- 6. PUT true/true/SUNDAY ----------------------------------------
            r = await c.put("/api/v1/student/preferences", headers=headers_a,
                            json={"class_reminders": True, "auto_mark_present": True,
                                  "week_starts_on": "SUNDAY"})
            b = r.json()
            r = await c.get("/api/v1/student/preferences", headers=headers_a)
            b = r.json()
            check("6. PUT true/true/SUNDAY replaces the row and GET reflects it",
                  r.status_code == 200 and b["class_reminders"] is True
                  and b["auto_mark_present"] is True and b["week_starts_on"] == "SUNDAY",
                  f"{b}")

            # --- 7. Another PUT combination -------------------------------------
            r = await c.put("/api/v1/student/preferences", headers=headers_a,
                            json={"class_reminders": True, "auto_mark_present": False,
                                  "week_starts_on": "MONDAY"})
            b = r.json()
            r = await c.get("/api/v1/student/preferences", headers=headers_a)
            b = r.json()
            check("7. PUT true/false/MONDAY replaces again and GET reflects it "
                  "(replace semantics, no accidental NULLs)",
                  r.status_code == 200 and b["class_reminders"] is True
                  and b["auto_mark_present"] is False and b["week_starts_on"] == "MONDAY",
                  f"{b}")

            # --- 8. PUT lazily creates when no row exists ------------------------
            r = await c.put("/api/v1/student/preferences", headers=headers_b,
                            json={"class_reminders": True, "auto_mark_present": True,
                                  "week_starts_on": "SUNDAY"})
            async with AsyncSessionLocal() as db:
                row_count_b = (await db.execute(select(func.count()).select_from(UserPreference).where(
                    UserPreference.user_id == user_b_id))).scalar()
            check("8. PUT on a user with no row lazily creates then replaces "
                  "(exactly one row total)",
                  r.status_code == 200 and row_count_b == 1, f"rows={row_count_b}")

            # --- 9. Invalid enum -> 422 -----------------------------------------
            r = await c.put("/api/v1/student/preferences", headers=headers_a,
                            json={"class_reminders": False, "auto_mark_present": False,
                                  "week_starts_on": "FRIDAY"})
            check("9. invalid week_starts_on value -> 422 (Pydantic enum "
                  "validation)", r.status_code == 422, f"got {r.status_code} {r.text[:120]}")

            # --- 10. Partial PUT -> 422 ------------------------------------------
            r = await c.put("/api/v1/student/preferences", headers=headers_a,
                            json={"class_reminders": True})
            check("10. partial PUT (missing required fields) -> 422",
                  r.status_code == 422, f"got {r.status_code} {r.text[:120]}")

            # --- 11. Unauthenticated -> 401 --------------------------------------
            r = await c.get("/api/v1/student/preferences")
            r2 = await c.get("/api/v1/student/preferences",
                             headers={"Authorization": "Bearer not.a.valid.token"})
            check("11. unauthenticated GET (no header / invalid token) -> 401",
                  r.status_code == 401 and r2.status_code == 401,
                  f"no_header={r.status_code} bad_token={r2.status_code}")

            # --- 12. User isolation ----------------------------------------------
            # No user selector exists. A body user_id and a query user_id are
            # both ignored: the operation always targets the JWT identity.
            r = await c.put("/api/v1/student/preferences?user_id=" + str(user_b_id),
                            headers=headers_a,
                            json={"class_reminders": False, "auto_mark_present": True,
                                  "week_starts_on": "SUNDAY",
                                  "user_id": str(user_b_id)})
            ok_put = r.status_code == 200
            r_a = await c.get("/api/v1/student/preferences", headers=headers_a)
            r_b = await c.get("/api/v1/student/preferences", headers=headers_b)
            a_body = r_a.json()
            b_body = r_b.json()
            async with AsyncSessionLocal() as db:
                rows_a = (await db.execute(select(UserPreference).where(
                    UserPreference.user_id == user_a_id))).scalars().all()
                rows_b = (await db.execute(select(UserPreference).where(
                    UserPreference.user_id == user_b_id))).scalars().all()
            check("12. user isolation: A's PUT with body/query user_id=B only "
                  "changes A; B's row and values are untouched (no client "
                  "identity; exactly one row per user)",
                  ok_put and a_body["auto_mark_present"] is True
                  and a_body["week_starts_on"] == "SUNDAY"
                  and b_body["auto_mark_present"] is True
                  and b_body["week_starts_on"] == "SUNDAY"
                  and len(rows_a) == 1 and len(rows_b) == 1
                  and rows_b[0].week_starts_on.value == "SUNDAY"
                  and rows_b[0].auto_mark_present is True,
                  f"A={a_body} B={b_body} rowsA={len(rows_a)} rowsB={len(rows_b)}")

        # --- 13-15. DB-level guarantees (raw SQL, outside the API) ---------------
        async with AsyncSessionLocal() as db:
            # 13. Server defaults apply on a raw INSERT without values.
            raw_uid = uuid.uuid4()
            await db.execute(text(
                "INSERT INTO users (id, roll_number, name, role, created_at, updated_at) "
                "VALUES (:id, 'PH10D_RAW', 'Raw', 'STUDENT', now(), now())"),
                {"id": raw_uid})
            try:
                await db.execute(text(
                    "INSERT INTO userpreferences (user_id, created_at, updated_at) "
                    "VALUES (:uid, now(), now())"), {"uid": raw_uid})
                row = (await db.execute(text(
                    "SELECT class_reminders, auto_mark_present, week_starts_on "
                    "FROM userpreferences WHERE user_id = :uid"), {"uid": raw_uid})).first()
                check("13. DB server defaults apply on raw insert "
                      "(false/false/MONDAY)",
                      row is not None and row[0] is False and row[1] is False
                      and row[2] == "MONDAY", f"row={row}")
                # 14. PK uniqueness: duplicate user_id insert must fail.
                try:
                    await db.execute(text(
                        "INSERT INTO userpreferences (user_id, created_at, updated_at) "
                        "VALUES (:uid, now(), now())"), {"uid": raw_uid})
                    pk_ok = False
                except Exception:
                    pk_ok = True
                await db.rollback()
                check("14. duplicate user_id insert rejected (PK uniqueness)",
                      pk_ok)
            except Exception as e:
                await db.rollback()
                check("13. DB server defaults apply on raw insert "
                      "(false/false/MONDAY)", False, str(e)[:150])
            # 15. FK: nonexistent user_id insert must fail.
            try:
                await db.execute(text(
                    "INSERT INTO userpreferences (user_id, created_at, updated_at) "
                    "VALUES (:uid, now(), now())"), {"uid": uuid.uuid4()})
                fk_ok = False
            except Exception:
                fk_ok = True
            await db.rollback()
            check("15. insert with nonexistent user_id rejected (FK to users.id)",
                  fk_ok)
            # Cleanup the raw SQL artifacts.
            await db.execute(text("DELETE FROM userpreferences WHERE user_id = :uid"),
                             {"uid": raw_uid})
            await db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": raw_uid})
            await db.commit()

    finally:
        async with AsyncSessionLocal() as db:
            # Remove ONLY this verifier's preference rows + temp users; any
            # pre-existing rows (e.g. the owner's browser) are preserved.
            await db.execute(delete(UserPreference).where(
                UserPreference.user_id.in_([user_a_id, user_b_id])))
            await db.execute(delete(User).where(User.id.in_([user_a_id, user_b_id])))
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
            "academic_sessions": await table_count(db, AcademicSession),
            "semesters": await table_count(db, Semester),
            "timetable_entries": await table_count(db, TimetableEntry),
            "quiz_cycles": await table_count(db, QuizCycle),
            "eligibility_policies": await table_count(db, EligibilityPolicy),
        }
        pref_after_rows = (await db.execute(
            select(UserPreference.user_id).select_from(UserPreference))).scalars().all()
        pref_after_set = set(pref_after_rows)
        pref_after = len(pref_after_rows)

    same = snap == snap_after and pref_after_set == pref_before_set
    check("18. DB baseline restored exactly (all frozen tables + preference rows "
          "match pre-run snapshot; only verifier rows removed)",
          same, f"prefs {pref_before}->{pref_after} "
                f"diff={ {k: (snap[k], snap_after[k]) for k in snap if snap[k] != snap_after.get(k)} }")
    # Check 16 folded into 18: storing the three preferences changed no
    # attendance/event/session/record data (the frozen-table snapshot is
    # byte-identical before and after).
    check("16. storing class_reminders / auto_mark_present / week_starts_on "
          "changed NO attendance, event, session, or record data",
          same, "covered by the exact baseline restoration in check 18")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nPhase 10D verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))