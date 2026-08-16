"""
Attendance specification alignment verification.

Verifies the attendance-spec changes against the real application (httpx
ASGITransport + real DB, minted JWTs for the real admin, the registration-
verification student, and a temporary partial-enrollment student):

  1.  Quiz-day sessions: every SCHEDULED quiz date for a quiz-applicable
      subject has a non-cancelled class session (quiz-day attendance is a
      real attendance event).
  2.  Quiz-day sessions sit OUTSIDE every eligibility window
      (window_end == quiz_date - 1), so eligibility is untouched.
  3.  Quiz-day sessions follow the future-date rule: a FUTURE quiz-day session
      is view-only (mutation rejected 400, still visible in the daily read);
      the subject summary counts it once its date is reached (as_of
      semantics).
  4.  Student-controlled events (spec): subject-scoped extras on the
      student's OWN enrollments -> 201/200/200 (create/patch/delete);
      global/closure events -> 403; a subject the student is NOT enrolled
      in -> 403.
  5.  Synchronizer guard: a CLASS_CANCELLED event on a quiz-day date never
      cancels the quiz-day session.
  6.  Additive summary fields: required_pct == 75 and status is the canonical
      engine band (SAFE/WATCH/CRITICAL/None).
  7.  Exact database baseline restoration (events/sessions/cancelled/extra/
      records/users/enrollments).

All state changes are this script's own artifacts and are removed in the
finally block (hard-delete events + attendance records + temp user, restore
cancelled sessions, delete unattended extras on its test window).

Usage:
    python scripts/verify_attendance_spec_alignment.py
"""
import asyncio
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
from app.models.user import User
from app.models.event import AcademicEvent
from app.models.attendance import AttendanceRecord
from app.models.academic import StudentEnrollment, Subject
from app.models.quiz import QuizSchedule, ScheduleStatus
from app.models.timetable import ClassSession
from app.models.enums import UserRole
from app.services.event_registry import EVENT_TYPE_RULES
from app.engines.attendance_engine import classify_attendance_status
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

        # Baseline snapshot (exact restoration asserted at the end).
        from sqlalchemy import func
        events_before = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        sessions_before = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
        cancelled_before = (await db.execute(select(func.count()).select_from(ClassSession).where(ClassSession.is_cancelled.is_(True)))).scalar()
        extra_before = (await db.execute(select(func.count()).select_from(ClassSession).where(ClassSession.is_extra.is_(True)))).scalar()
        records_before = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        users_before = (await db.execute(select(func.count()).select_from(User))).scalar()
        enrollments_before = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
        subject_ids = {s.code: s.id for s in (await db.execute(select(Subject))).scalars().all()}
        # All SCHEDULED quiz schedules with dates for quiz-applicable subjects
        # (eagerly loaded, precomputed here so later checks never lazy-load
        # detached ORM attributes).
        from sqlalchemy.orm import selectinload
        schedules = (await db.execute(
            select(QuizSchedule)
            .options(selectinload(QuizSchedule.subject))
            .where(
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED,
                QuizSchedule.date.isnot(None),
            )
        )).scalars().all()
        code_by_id = {s.id: s.code for s in (await db.execute(select(Subject))).scalars().all()}
        quiz_day_plans = [
            (qs.subject_id, qs.date)
            for qs in schedules
            if qs.subject is not None and qs.subject.quiz_applicable
        ]
        print(f"baseline: events={events_before} sessions={sessions_before} cancelled={cancelled_before} "
              f"extra={extra_before} records={records_before} users={users_before} enrollments={enrollments_before}")

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    student_token = create_access_token(str(student_user.id), student_user.roll_number)

    test_event_ids: list[uuid.UUID] = []
    test_record_ids: list[uuid.UUID] = []
    temp_user_id: uuid.UUID | None = None
    # Sessions this run's CLASS_CANCELLED cancelled (exact ids, Option A: the
    # cancellation targets the covering timetable lecture on a covered quiz
    # date) — restored in the finally block, never by date/shape sweeps.
    my_cancelled_ids: set = set()
    temp_enrollment_id: uuid.UUID | None = None

    try:
        # --- 1. Quiz-day sessions exist on every scheduled quiz date ----------
        async with AsyncSessionLocal() as db:
            missing = 0
            for subject_id, quiz_date in quiz_day_plans:
                has = (await db.execute(
                    select(ClassSession.id).where(
                        ClassSession.subject_id == subject_id,
                        ClassSession.date == quiz_date,
                        ClassSession.is_cancelled.is_(False),
                    )
                )).scalars().first()
                if has is None:
                    missing += 1
            check("1. every SCHEDULED quiz date has a recordable session (quiz-day attendance)",
                  missing == 0, f"{missing} missing")

        # --- 2. Quiz-day sessions are outside every eligibility window ---------
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            by_code = {}
            for subject_id, quiz_date in quiz_day_plans:
                by_code.setdefault(code_by_id[subject_id], []).append(quiz_date)
            # Cycle order follows quiz date order (Quiz I is the earliest
            # scheduled quiz), so enumerate() maps dates to cycles correctly.
            for code in by_code:
                by_code[code].sort()
            all_ok = True
            detail = ""
            for code, dates in by_code.items():
                for cycle, quiz_date in enumerate(dates, start=1):
                    r = await client.get(f"/api/v1/quiz-eligibility/{code}/{cycle}", headers=student_token_headers(student_token))
                    if r.status_code != 200:
                        all_ok = False
                        detail += f"{code}/{cycle}:{r.status_code} "
                        continue
                    body = r.json()
                    w_end = date.fromisoformat(body["window_end"])
                    if w_end != quiz_date - timedelta(days=1):
                        all_ok = False
                        detail += f"{code}/{cycle}:window_end={w_end} quiz-1={quiz_date - timedelta(days=1)} "
            check("2. quiz-day sessions excluded from eligibility (window_end == quiz_date - 1)",
                  all_ok, detail)

            # --- 3. Quiz-day sessions follow the future-date rule -----------------
            async with AsyncSessionLocal() as db:
                # Earliest quiz-day-only session (timetable_entry_id NULL). All
                # scheduled quiz days are ahead of today, so this session is a
                # FUTURE date: it stays visible (view-only) but cannot be marked.
                target = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.timetable_entry_id.is_(None),
                        ClassSession.is_extra.is_(False),
                    ).order_by(ClassSession.date)
                )).scalars().first()
            target_code = None
            async with AsyncSessionLocal() as db:
                subj = (await db.execute(select(Subject).where(Subject.id == target.subject_id))).scalars().first()
                target_code = subj.code
            r = await client.post("/api/v1/attendance", headers=student_token_headers(student_token), json={
                "class_session_id": str(target.id), "status": "Attended"})
            r_daily = await client.get(f"/api/v1/attendance/daily/{target.date.isoformat()}",
                                       headers=student_token_headers(student_token))
            check("3. future quiz-day session is view-only: attendance mutation "
                  "rejected (400, future date), session still visible in the daily "
                  "read (recordable once its date is reached via the canonical "
                  "mutation)",
                  r.status_code == 400 and r_daily.status_code == 200
                  and any(s["id"] == str(target.id) for s in r_daily.json()["sessions"]),
                  f"got {r.status_code} {r.text[:150]}")
            if r.status_code == 200:
                test_record_ids.append(uuid.UUID(r.json()["id"]))

            # Subject summary counts it once its date is reached (as_of semantics).
            before_day = (target.date - timedelta(days=1)).isoformat()
            on_day = target.date.isoformat()
            rb = await client.get(f"/api/v1/attendance/summary/{target_code}?as_of_date={before_day}", headers=student_token_headers(student_token))
            ra = await client.get(f"/api/v1/attendance/summary/{target_code}?as_of_date={on_day}", headers=student_token_headers(student_token))
            lec_before = rb.json().get("lecture", {}).get("total")
            lec_on = ra.json().get("lecture", {}).get("total")
            # Option A (separate occurrence): the earliest quiz-day session now
            # sits on 2026-08-24 (BNC-501), a date that carries BOTH the normal
            # lecture AND the independent quiz-day session — crossing the as_of
            # boundary adds both (+2). Both are canonical lecture-class rows
            # counted in subject attendance.
            check("3b. quiz-day session counts toward subject attendance on its date "
                  "(as_of; +2 = normal lecture + independent quiz-day occurrence)",
                  rb.status_code == 200 and ra.status_code == 200 and lec_on == lec_before + 2,
                  f"as_of {before_day} L={lec_before} -> as_of {on_day} L={lec_on}")

            # Additive summary fields (attendance UI refinement).
            summary = ra.json()
            expected_status = classify_attendance_status(summary.get("current_avg_pct"))
            check("4. summary exposes required_pct == 75 and canonical status band",
                  summary.get("required_pct") == 75.0
                  and summary.get("status") == expected_status
                  and summary.get("status") in (None, "SAFE", "WATCH", "CRITICAL"),
                  f"required_pct={summary.get('required_pct')} status={summary.get('status')} expected={expected_status}")

            # --- 4. Student-controlled events (spec) ----------------------------
            # Temp student with ONE enrollment (BCS-501) to prove the
            # enrollment boundary both ways.
            async with AsyncSessionLocal() as db:
                temp_user = User(roll_number="SPEC_AUDIT_TMP", name="Spec Audit Temp", role=UserRole.STUDENT)
                db.add(temp_user)
                await db.flush()
                db.add(StudentEnrollment(user_id=temp_user.id, subject_id=subject_ids["BCS-501"]))
                await db.commit()
                temp_user_id = temp_user.id
            temp_token = create_access_token(str(temp_user_id), "SPEC_AUDIT_TMP")

            # Temp user: enrolled subject -> 201; non-enrolled subject -> 403.
            r = await client.post("/api/v1/events", headers=token_headers(temp_token), json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-11-09", "end_date": "2026-11-09",
                "subject_id": str(subject_ids["BCS-501"]), "class_type": "L"})
            check("5. student POST subject-scoped extra for ENROLLED subject -> 201",
                  r.status_code == 201, f"got {r.status_code} {r.text[:150]}")
            if r.status_code == 201:
                test_event_ids.append(uuid.UUID(r.json()["id"]))

            r = await client.post("/api/v1/events", headers=token_headers(temp_token), json={
                "event_type": "EXTRA_LECTURE", "start_date": "2026-11-10", "end_date": "2026-11-10",
                "subject_id": str(subject_ids["BCS-058"]), "class_type": "L"})
            check("5b. student POST subject-scoped extra for NON-enrolled subject -> 403",
                  r.status_code == 403, f"got {r.status_code} {r.text[:150]}")

            r = await client.post("/api/v1/events", headers=token_headers(temp_token), json={
                "event_type": "PUBLIC_HOLIDAY", "start_date": "2026-11-11", "end_date": "2026-11-11"})
            check("5c. student POST global/closure event -> 403", r.status_code == 403, f"got {r.status_code}")

            # Real student: PATCH + DELETE their own subject-scoped event.
            r = await client.post("/api/v1/events", headers=student_token_headers(student_token), json={
                "event_type": "EXTRA_TUTORIAL", "start_date": "2026-11-12", "end_date": "2026-11-12",
                "subject_id": str(subject_ids["BCS-501"]), "class_type": "T"})
            own_ok = r.status_code == 201
            if own_ok:
                own_id = uuid.UUID(r.json()["id"])
                test_event_ids.append(own_id)
                r2 = await client.patch(f"/api/v1/events/{own_id}", headers=student_token_headers(student_token),
                                        json={"is_working_day": False})
                check("6. student PATCH own subject-scoped event -> 200", r2.status_code == 200, f"got {r2.status_code}")
                r3 = await client.delete(f"/api/v1/events/{own_id}", headers=student_token_headers(student_token))
                check("6b. student DELETE own subject-scoped event -> 200 (safe deactivation)",
                      r3.status_code == 200 and r3.json()["active"] is False, f"got {r3.status_code}")

            # Admin-created global event: student PATCH/DELETE -> 403.
            r = await client.post("/api/v1/events", headers=admin_headers(admin_token), json={
                "event_type": "PUBLIC_HOLIDAY", "start_date": "2026-11-13", "end_date": "2026-11-13"})
            global_id = uuid.UUID(r.json()["id"]) if r.status_code == 201 else None
            if global_id:
                test_event_ids.append(global_id)
                r2 = await client.patch(f"/api/v1/events/{global_id}", headers=student_token_headers(student_token),
                                        json={"active": False})
                check("6c. student PATCH global event -> 403", r2.status_code == 403, f"got {r2.status_code}")
                r3 = await client.delete(f"/api/v1/events/{global_id}", headers=student_token_headers(student_token))
                check("6d. student DELETE global event -> 403", r3.status_code == 403, f"got {r3.status_code}")

            # --- 5. Synchronizer guard: CLASS_CANCELLED never cancels quiz-day ----
            async with AsyncSessionLocal() as db:
                quiz_session = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.timetable_entry_id.is_(None),
                        ClassSession.is_extra.is_(False),
                        ClassSession.date >= date(2026, 8, 24),
                    ).order_by(ClassSession.date)
                )).scalars().first()
            if quiz_session is not None:
                r = await client.post("/api/v1/events", headers=admin_headers(admin_token), json={
                    "event_type": "CLASS_CANCELLED", "start_date": quiz_session.date.isoformat(),
                    "end_date": quiz_session.date.isoformat(),
                    "subject_id": str(quiz_session.subject_id), "class_type": quiz_session.class_type.value})
                check("7. admin POST CLASS_CANCELLED on quiz-day date -> 201", r.status_code == 201, f"got {r.status_code}")
                if r.status_code == 201:
                    cancel_id = uuid.UUID(r.json()["id"])
                    test_event_ids.append(cancel_id)
                async with AsyncSessionLocal() as db:
                    after = (await db.execute(
                        select(ClassSession).where(ClassSession.id == quiz_session.id))).scalars().first()
                    # Option A: the earliest quiz-day session sits on the covered
                    # 08-24 (BNC-501), so CLASS_CANCELLED cancels the real
                    # timetable lecture (its intent) while the quiz-day session
                    # stays protected. Capture the cancelled lecture id so the
                    # finally block restores the exact baseline.
                    cancelled_lec = (await db.execute(
                        select(ClassSession).where(
                            ClassSession.subject_id == quiz_session.subject_id,
                            ClassSession.date == quiz_session.date,
                            ClassSession.timetable_entry_id.isnot(None),
                            ClassSession.is_cancelled.is_(True)))).scalars().first()
                    if cancelled_lec is not None:
                        my_cancelled_ids.add(cancelled_lec.id)
                check("7b. synchronizer guard: quiz-day session NOT cancelled by event sync "
                      "(the covering timetable lecture is cancelled instead)",
                      after is not None and not after.is_cancelled,
                      f"is_cancelled={after.is_cancelled if after else 'missing'}")
            else:
                check("7. quiz-day session found for synchronizer guard test", False, "no quiz-day session found")

    finally:
        # Remove every artifact this script created (events, attendance
        # records, temp user + enrollment, orphan extras / cancelled rows on
        # its test window).
        async with AsyncSessionLocal() as db:
            from sqlalchemy import func as _f
            if test_event_ids:
                await db.execute(delete(AcademicEvent).where(AcademicEvent.id.in_(test_event_ids)))
            if test_record_ids:
                await db.execute(delete(AttendanceRecord).where(AttendanceRecord.id.in_(test_record_ids)))
            if temp_user_id is not None:
                await db.execute(delete(StudentEnrollment).where(StudentEnrollment.user_id == temp_user_id))
                await db.execute(delete(User).where(User.id == temp_user_id))
            # Restore sessions my events touched: delete unattended extras,
            # un-cancel unattended cancelled sessions, on the test window.
            window_start, window_end = date(2026, 11, 9), date(2026, 11, 13)
            stale = (await db.execute(
                select(ClassSession).where(
                    ClassSession.date >= window_start, ClassSession.date <= window_end))).scalars().all()
            from app.repositories.session_repo import SessionRepository
            attended_ids = await SessionRepository(db).get_session_ids_with_attendance([s.id for s in stale])
            for s in stale:
                if s.id in attended_ids:
                    continue
                if s.is_extra:
                    await db.delete(s)
                elif s.is_cancelled:
                    s.is_cancelled = False
            if my_cancelled_ids:
                await db.execute(
                    ClassSession.__table__.update()
                    .where(ClassSession.id.in_(my_cancelled_ids),
                           ClassSession.is_cancelled.is_(True))
                    .values(is_cancelled=False)
                )
            await db.commit()

        async with AsyncSessionLocal() as db:
            from sqlalchemy import func
            events_after = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
            sessions_after = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
            cancelled_after = (await db.execute(select(func.count()).select_from(ClassSession).where(ClassSession.is_cancelled.is_(True)))).scalar()
            extra_after = (await db.execute(select(func.count()).select_from(ClassSession).where(ClassSession.is_extra.is_(True)))).scalar()
            records_after = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
            users_after = (await db.execute(select(func.count()).select_from(User))).scalar()
            enrollments_after = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
        check("8. database restored to the exact baseline "
              "(events/sessions/cancelled/extra/records/users/enrollments)",
              (events_after, sessions_after, cancelled_after, extra_after, records_after, users_after, enrollments_after)
              == (events_before, sessions_before, cancelled_before, extra_before, records_before, users_before, enrollments_before),
              f"events {events_before}->{events_after} sessions {sessions_before}->{sessions_after} "
              f"cancelled {cancelled_before}->{cancelled_after} extra {extra_before}->{extra_after} "
              f"records {records_before}->{records_after} users {users_before}->{users_after} "
              f"enrollments {enrollments_before}->{enrollments_after}")

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


def token_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def admin_headers(token: str) -> dict:
    return token_headers(token)


def student_token_headers(token: str) -> dict:
    return token_headers(token)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
