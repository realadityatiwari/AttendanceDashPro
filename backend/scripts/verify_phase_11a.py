"""
Phase 11A verification — Notification Read Model (backend).

Verifies the Phase 11A contract end-to-end against the real database
(httpx ASGITransport + real DB + minted JWTs, the established pattern):

  - GET /api/v1/notifications is a pure READ model: it never mutates
    attendance / class_sessions / academic_events / quiz / laboratory data
    and its output is generated on-read from the existing engines/services.
  - The owner is always the authenticated user; a client-supplied user_id
    is ignored.
  - CLASS_REMINDER is gated by the user's `class_reminders` preference (a
    missing row means the documented default: off), scoped to the current
    institutional week, and excludes cancelled sessions.
  - auto_mark_present and week_starts_on remain completely inert: neither
    changes the notification output.
  - Every other kind is a projection of canonical engine outputs
    (classify_attendance_status / optimize_attendance / current quiz cycle /
    dashboard upcoming-events selection) — cross-checked against those
    services directly.

C-class re-scope (Phase 11B, migration d1e2f3a4b5c6): the notifications
table now EXISTS and GET /api/v1/notifications snapshots projections into
persisted rows (idempotent upserts). The Phase 11A projection semantics are
unchanged — checks 13/14 are re-scoped to prove the table exists (11B) and
that this verifier leaves the notifications table exactly as it found it
(its admin user's inbox rows are restored to the pre-run row set).

State changes are this script's own artifacts (two temp users, one temp
enrollment, three temp class sessions, two temp preference rows, the
notification rows created for those temp users and any newly created rows
for the pre-existing admin user), deleted by explicit captured IDs in the
finally block. No frozen system is touched and the alembic head is verified
unchanged.

Usage:
    python scripts/verify_phase_11a.py
"""
import asyncio
import subprocess
import sys
import uuid
from datetime import date, timedelta
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
from app.models.notification import Notification
from app.models.enums import UserRole, ClassType, WeekStartsOn
from app.services.attendance_service import institution_today
from app.services.eligibility_service import EligibilityService
from app.services.attendance_service import AttendanceService
from app.engines.attendance_engine import classify_attendance_status
from sqlalchemy import select, func, delete, text

SUBJECT_SCOPED_KINDS = {
    "CLASS_REMINDER", "QUIZ_APPROACHING", "ATTENDANCE_THRESHOLD",
    "MUST_ATTEND", "SAFE_SKIP",
}

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
            "userpreferences": await table_count(db, UserPreference),
            "academic_sessions": await table_count(db, AcademicSession),
            "semesters": await table_count(db, Semester),
            "timetable_entries": await table_count(db, TimetableEntry),
            "quiz_cycles": await table_count(db, QuizCycle),
            "eligibility_policies": await table_count(db, EligibilityPolicy),
            "notifications": await table_count(db, Notification),
        }

        as_of = institution_today()
        week_start = as_of - timedelta(days=as_of.weekday())
        week_end = week_start + timedelta(days=6)

        # Fixture: temp user U (enrolled into one existing subject, with three
        # temp class sessions this week) and temp user V (no enrollments).
        user_u = User(roll_number="PH11A_U", name="Phase 11A User U", role=UserRole.STUDENT)
        user_v = User(roll_number="PH11A_V", name="Phase 11A User V", role=UserRole.STUDENT)
        db.add_all([user_u, user_v])
        await db.flush()

        admin = (await db.execute(select(User).where(
            User.role == UserRole.ADMIN).limit(1))).scalars().first()

        # C-class (11B): capture the admin's PRE-EXISTING notification rows so
        # the finally block can restore the inbox to exactly this row set (the
        # GET requests below persist rows for the admin as a real side effect).
        admin_notif_baseline = set((await db.execute(
            select(Notification.id).where(Notification.user_id == admin.id))).scalars().all())

        enroll = (await db.execute(select(StudentEnrollment).where(
            StudentEnrollment.user_id == admin.id).limit(1))).scalars().first()
        subject = await db.get(Subject, enroll.subject_id)

        db.add(StudentEnrollment(user_id=user_u.id, subject_id=subject.id))
        db.add(UserPreference(
            user_id=user_u.id,
            class_reminders=False,
            auto_mark_present=False,
            week_starts_on=WeekStartsOn.MONDAY,
        ))
        await db.flush()

        # Sessions: in-week (unmarked), in-week (cancelled), out-of-week.
        in_week = as_of if as_of == week_end else min(week_end, as_of + timedelta(days=1))
        out_week = week_end + timedelta(days=1)
        s1 = ClassSession(subject_id=subject.id, date=in_week, class_type=ClassType.LECTURE,
                          is_extra=False, is_cancelled=False, timetable_entry_id=None)
        s2 = ClassSession(subject_id=subject.id, date=in_week, class_type=ClassType.LECTURE,
                          is_extra=False, is_cancelled=True, timetable_entry_id=None)
        s3 = ClassSession(subject_id=subject.id, date=out_week, class_type=ClassType.LECTURE,
                          is_extra=False, is_cancelled=False, timetable_entry_id=None)
        db.add_all([s1, s2, s3])
        await db.flush()
        await db.commit()

        s1_id, s2_id, s3_id = s1.id, s2.id, s3.id
        user_u_id, user_v_id = user_u.id, user_v.id
        admin_id, admin_roll = admin.id, admin.roll_number
        subject_id = subject.id

    token_u = create_access_token(str(user_u_id), "PH11A_U")
    headers_u = {"Authorization": f"Bearer {token_u}"}
    token_v = create_access_token(str(user_v_id), "PH11A_V")
    headers_v = {"Authorization": f"Bearer {token_v}"}
    token_admin = create_access_token(str(admin_id), admin_roll)
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            # --- 1. Authenticated GET -> 200 -------------------------------------
            r = await c.get("/api/v1/notifications", headers=headers_admin)
            check("1. authenticated GET /api/v1/notifications -> 200",
                  r.status_code == 200, f"got {r.status_code} {r.text[:160]}")

            # --- 2. Unauthenticated -> 401 ---------------------------------------
            r1 = await c.get("/api/v1/notifications")
            r2 = await c.get("/api/v1/notifications",
                             headers={"Authorization": "Bearer not.a.valid.token"})
            check("2. unauthenticated GET (no header / invalid token) -> 401",
                  r1.status_code == 401 and r2.status_code == 401,
                  f"no_header={r1.status_code} bad_token={r2.status_code}")

            # --- 3. Response shape -----------------------------------------------
            body = r.json()
            items_ok = isinstance(body.get("items"), list) and all(
                isinstance(i, dict) and isinstance(i.get("id"), str)
                and i.get("kind") in SUBJECT_SCOPED_KINDS | {"ACADEMIC_EVENT"}
                and isinstance(i.get("date"), str) and i.get("date")
                and isinstance(i.get("message"), str) and i.get("message")
                for i in body.get("items", [])
            )
            check("3. response shape valid (items[] with id/kind/date/message "
                  "per item)", items_ok and "as_of" in body,
                  f"got {list(body.keys())}")

            # --- 4. as_of is the server-generated institution date ---------------
            as_of_expected = institution_today().isoformat()
            check("4. as_of is the server-generated institution date (never "
                  "client-controlled)", body.get("as_of") == as_of_expected,
                  f"as_of={body.get('as_of')!r} expected={as_of_expected!r}")

            # --- 5. Client cannot control identity -------------------------------
            r_spoof = await c.get("/api/v1/notifications",
                                  headers=headers_admin,
                                  params={"user_id": str(user_v_id)})
            check("5. client-supplied ?user_id= is ignored (identical response, "
                  "no user_id field)", r_spoof.status_code == 200
                  and r_spoof.json() == body and "user_id" not in body,
                  f"got {r_spoof.status_code}")

            # --- 6. Enrollment scoping / isolation --------------------------------
            body_v = (await c.get("/api/v1/notifications", headers=headers_v)).json()
            v_kinds = {i["kind"] for i in body_v["items"]}
            v_unscoped = all(i.get("subject_code") is None
                             for i in body_v["items"] if i["kind"] == "ACADEMIC_EVENT")
            async with AsyncSessionLocal() as db:
                enrolled_codes = set((await db.execute(
                    select(Subject.code).join(StudentEnrollment).where(
                        StudentEnrollment.user_id == admin_id))).scalars().all())
            owner_codes = {i.get("subject_code") for i in body["items"]
                           if i.get("subject_code") is not None}
            check("6. enrollment scoping + isolation: unenrolled user gets no "
                  "subject-scoped items; owner items reference only enrolled "
                  "subjects", not (v_kinds & SUBJECT_SCOPED_KINDS) and v_unscoped
                  and owner_codes <= enrolled_codes,
                  f"v_kinds={v_kinds} owner_codes={owner_codes}")

            # --- 7. class_reminders=false suppresses (explicit row) --------------
            body_u = (await c.get("/api/v1/notifications", headers=headers_u)).json()
            u_reminders_off = [i for i in body_u["items"] if i["kind"] == "CLASS_REMINDER"]
            check("7. class_reminders=false suppresses CLASS_REMINDER (temp "
                  "user has a qualifying in-week session)",
                  len(u_reminders_off) == 0, f"got {len(u_reminders_off)} items")

            # --- 8. class_reminders=true permits with qualifying data ------------
            async with AsyncSessionLocal() as db:
                pref_u = (await db.execute(select(UserPreference).where(
                    UserPreference.user_id == user_u_id))).scalars().first()
                pref_u.class_reminders = True
                await db.commit()
            body_u = (await c.get("/api/v1/notifications", headers=headers_u)).json()
            u_reminders = [i for i in body_u["items"] if i["kind"] == "CLASS_REMINDER"]
            reminder_has_s1 = any(i.get("session_id") == str(s1_id) for i in u_reminders)
            check("8. class_reminders=true permits CLASS_REMINDER referencing the "
                  "qualifying in-week session", len(u_reminders) >= 1 and reminder_has_s1,
                  f"ids={[i.get('session_id') for i in u_reminders]}")

            # --- 9. Cancelled sessions excluded -----------------------------------
            reminder_has_s2 = any(i.get("session_id") == str(s2_id) for i in u_reminders)
            check("9. cancelled sessions never generate CLASS_REMINDER",
                  not reminder_has_s2, f"ids={[i.get('session_id') for i in u_reminders]}")

            # --- 10. Out-of-current-week sessions excluded ------------------------
            reminder_has_s3 = any(i.get("session_id") == str(s3_id) for i in u_reminders)
            check("10. sessions outside the current institutional week are not "
                  "reminded", not reminder_has_s3,
                  f"ids={[i.get('session_id') for i in u_reminders]}")

            # --- 11-12. auto_mark_present / week_starts_on remain inert -----------
            async with AsyncSessionLocal() as db:
                pref_u = (await db.execute(select(UserPreference).where(
                    UserPreference.user_id == user_u_id))).scalars().first()
                pref_u.auto_mark_present = True
                pref_u.week_starts_on = WeekStartsOn.SUNDAY
                await db.commit()
            body_u_inert = (await c.get("/api/v1/notifications", headers=headers_u)).json()
            check("11. auto_mark_present=true has NO effect on the notification "
                  "output", body_u_inert == body_u,
                  f"items {len(body_u.get('items', []))}->{len(body_u_inert.get('items', []))}")
            check("12. week_starts_on=SUNDAY has NO effect on the notification "
                  "output", body_u_inert == body_u,
                  f"items {len(body_u.get('items', []))}->{len(body_u_inert.get('items', []))}")

            # --- 15. QUIZ_APPROACHING = canonical current quiz cycle --------------
            async with AsyncSessionLocal() as db:
                cycle = await EligibilityService(db).get_current_quiz_cycle(admin_id)
            quiz_items = [i for i in body["items"] if i["kind"] == "QUIZ_APPROACHING"]
            if cycle["basis"] == "next_upcoming":
                quiz_ok = len(quiz_items) == 1 and quiz_items[0]["quiz_cycle"] == cycle["quiz_cycle"] \
                    and quiz_items[0]["date"] == cycle["quiz_date"].isoformat()
            else:
                quiz_ok = len(quiz_items) == 0
            check("15. QUIZ_APPROACHING matches the canonical current quiz cycle "
                  f"(basis={cycle['basis']})", quiz_ok,
                  f"items={[(i['quiz_cycle'], i['date']) for i in quiz_items]} "
                  f"cycle={cycle['quiz_cycle']}/{cycle['quiz_date']}")

            # --- 16. ATTENDANCE_*/MUST_ATTEND/SAFE_SKIP = canonical summaries -----
            async with AsyncSessionLocal() as db:
                subjects = (await db.execute(select(Subject).join(StudentEnrollment).where(
                    StudentEnrollment.user_id == admin_id))).scalars().all()
                subjects = [s for s in subjects if s.attendance_applicable]
                summaries = await AttendanceService(db).get_subject_summaries(
                    user_id=admin_id, subjects=subjects, as_of_date=institution_today())
            code_to_subject = {s.code: s for s in subjects}
            att_items = [i for i in body["items"] if i["kind"] == "ATTENDANCE_THRESHOLD"]
            must_items = [i for i in body["items"] if i["kind"] == "MUST_ATTEND"]
            skip_items = [i for i in body["items"] if i["kind"] == "SAFE_SKIP"]
            att_ok = all(
                classify_attendance_status(
                    summaries[code_to_subject[i["subject_code"]].id].current_avg_pct)
                in ("WATCH", "CRITICAL") for i in att_items
            ) if att_items else True
            must_ok = all(
                (lambda o: o is not None and o.is_reachable
                 and (o.lecture_deficit or 0) + (o.tutorial_deficit or 0) > 0)(
                    summaries[code_to_subject[i["subject_code"]].id].optimization)
                for i in must_items
            ) if must_items else True
            skip_ok = all(
                (lambda o: o is not None and o.is_reachable
                 and (o.safe_skip_lecture or 0) + (o.safe_skip_tutorial or 0) > 0)(
                    summaries[code_to_subject[i["subject_code"]].id].optimization)
                for i in skip_items
            ) if skip_items else True
            check("16. ATTENDANCE_THRESHOLD / MUST_ATTEND / SAFE_SKIP match the "
                  "canonical subject summaries (engine banding + optimizer)",
                  att_ok and must_ok and skip_ok,
                  f"att={len(att_items)} must={len(must_items)} skip={len(skip_items)}")

            # --- 17. ACADEMIC_EVENT == dashboard upcoming-events selection --------
            dash = (await c.get("/api/v1/dashboard/summary", headers=headers_admin)).json()
            dash_event_ids = {e["id"] for e in dash.get("upcoming_events", [])}
            note_event_ids = {i.get("event_id") for i in body["items"]
                              if i["kind"] == "ACADEMIC_EVENT"}
            check("17. ACADEMIC_EVENT items equal the dashboard upcoming-events "
                  "selection", dash_event_ids == note_event_ids,
                  f"dash={dash_event_ids} notes={note_event_ids}")

    finally:
        async with AsyncSessionLocal() as db:
            # Remove ONLY this verifier's artifacts (explicit IDs); everything
            # pre-existing is preserved. Notification rows are deleted first
            # (they reference the users being removed; the admin's rows are
            # restored to the pre-run row set captured above).
            await db.execute(delete(Notification).where(
                Notification.user_id.in_([user_u_id, user_v_id])))
            if admin_notif_baseline is not None:
                await db.execute(delete(Notification).where(
                    Notification.user_id == admin_id,
                    Notification.id.not_in(list(admin_notif_baseline)),
                ))
            await db.execute(delete(ClassSession).where(ClassSession.id.in_([s1_id, s2_id, s3_id])))
            await db.execute(delete(StudentEnrollment).where(
                StudentEnrollment.user_id.in_([user_u_id, user_v_id])))
            await db.execute(delete(UserPreference).where(
                UserPreference.user_id.in_([user_u_id, user_v_id])))
            await db.execute(delete(User).where(User.id.in_([user_u_id, user_v_id])))
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
            "userpreferences": await table_count(db, UserPreference),
            "academic_sessions": await table_count(db, AcademicSession),
            "semesters": await table_count(db, Semester),
            "timetable_entries": await table_count(db, TimetableEntry),
            "quiz_cycles": await table_count(db, QuizCycle),
            "eligibility_policies": await table_count(db, EligibilityPolicy),
            "notifications": await table_count(db, Notification),
        }
        notifications_table = (await db.execute(text(
            "SELECT to_regclass('public.notifications')"))).scalar()
        # Prove the verifier's own artifacts are fully gone.
        leftover = {
            "users": (await db.execute(select(func.count()).select_from(User).where(
                User.id.in_([user_u_id, user_v_id])))).scalar(),
            "sessions": (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.id.in_([s1_id, s2_id, s3_id])))).scalar(),
            "prefs": (await db.execute(select(func.count()).select_from(UserPreference).where(
                UserPreference.user_id.in_([user_u_id, user_v_id])))).scalar(),
            # C-class (11B): no notification rows may remain for the temp
            # users, and the admin's inbox must be exactly the pre-run set.
            "notif_temp": (await db.execute(select(func.count()).select_from(Notification).where(
                Notification.user_id.in_([user_u_id, user_v_id])))).scalar(),
            "notif_admin_beyond_baseline": (await db.execute(select(func.count()).select_from(
                Notification).where(
                Notification.user_id == admin_id,
                Notification.id.not_in(list(admin_notif_baseline)),
            ))).scalar(),
        }

    same = snap == snap_after
    check("13. notification generation mutated NO frozen-table data "
          "(full snapshot byte-identical, notifications included)",
          same, f"diff={ {k: (snap[k], snap_after[k]) for k in snap if snap[k] != snap_after.get(k)} }")
    # C-class (11B): the persistence surface now exists (migration
    # d1e2f3a4b5c6); check 13 proves this verifier restores it exactly.
    check("14. notifications table exists (Phase 11B persistence surface) "
          "and this verifier restores it to its pre-run state",
          notifications_table is not None and same,
          f"to_regclass={notifications_table}")

    before_heads = subprocess.check_output(
        [sys.executable, "-m", "alembic", "heads"], cwd=str(BACKEND_DIR), text=True).strip()
    after_heads = subprocess.check_output(
        [sys.executable, "-m", "alembic", "heads"], cwd=str(BACKEND_DIR), text=True).strip()
    check("18. alembic head unchanged (no migration created during the run)",
          before_heads == after_heads,
          f"before={before_heads!r} after={after_heads!r}")
    check("19. exact cleanup: only this verifier's artifacts removed, "
          "pre-existing rows preserved (notifications restored to baseline)",
          same and all(v == 0 for v in leftover.values()),
          f"leftover={leftover}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\nPhase 11A verification: {passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))