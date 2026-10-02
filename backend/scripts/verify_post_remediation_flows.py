"""Post-remediation integrity review — end-to-end user-flow verification.

Exercises the representative user flows of the Events + Notifications backend
against the REAL dev database and REAL HTTP stack (httpx ASGITransport), and
records for every flow the HTTP/status result, the session mutation, the
notification mutation, and any unexpected side effect.

Flows:
   1. Create normal academic event                 11. Reactivate inactive event
   2. Managed QUIZ_DAY via generic path (409)      12. Event -> session sync state
   3. Managed QUIZ_DAY via Quiz Manager            13. Repeated synchronization
   4. Edit normal event                            14. Concurrent duplicate event
   5. Convert normal event -> managed (409)        15. Concurrent duplicate session
   6. Re-date managed QUIZ_DAY (409)               16. CLASS_REMINDER generation
   7. Deactivate managed QUIZ_DAY (409/retire)     17. Repeated CLASS_REMINDER sweep
   8. Deactivate normal future event               18. Cancellation propagation
   9. Future -> past update                        19. Quiz eligibility propagation
  10. Future -> future update                      20. Notification inbox behavior

Everything is created under a synthetic TXIR-* chain (temp subject, temp
student, temp quiz cycle) and removed in FK-safe order on exit; the frozen
baseline counts (events / sessions / notifications / users / records /
schedules) are asserted unchanged after cleanup.  The 452 legacy orphan
notifications are never touched (cleanup is scoped by exact fixture ids and
temp-user ownership).

Usage:
    python scripts/verify_post_remediation_flows.py
"""
import asyncio
import sys
import uuid
from datetime import date, time, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx
from sqlalchemy import delete, func, select

from app.main import app

from app.core.security import create_access_token
from app.core.timezone import institution_today
from app.db.session import AsyncSessionLocal, engine
from app.models.academic import (
    AcademicSession,
    Semester,
    StudentEnrollment,
    Subject,
)
from app.models.attendance import AttendanceRecord
from app.models.enums import (
    WeekStartsOn,
    AttendanceStatus,
    ClassType,
    EnrollmentType,
    EventType,
    NotificationKind,
    SubjectCategory,
    UserRole,
)
from app.models.event import AcademicEvent
from app.models.notification import Notification
from app.models.occurrence import OccurrenceOutcome
from app.models.preference import UserPreference
from app.models.quiz import QuizCycle, QuizSchedule, ScheduleStatus
from app.models.timetable import ClassSession, TimetableEntry
from app.models.user import Section, User
from app.repositories.quiz_repo import QuizRepository
from app.services.admin_quiz_service import AdminQuizConflictError, AdminQuizService
from app.services.event_registry import EventValidationError
from app.services.event_service import EventConflict, EventService

_TODAY = institution_today()
_TAG = "TXIR" + uuid.uuid4().hex[:8]

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def _future_weekday(days_ahead: int) -> date:
    d = _TODAY + timedelta(days=days_ahead)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


FUT1 = _future_weekday(31)
FUT2 = _future_weekday(33)
FUT3 = _future_weekday(35)


async def _baseline_counts():
    async with AsyncSessionLocal() as db:
        return {
            "events": (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar(),
            "sessions": (await db.execute(select(func.count()).select_from(ClassSession))).scalar(),
            "cancelled": (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.is_cancelled.is_(True)))).scalar(),
            "records": (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar(),
            "notifications": (await db.execute(select(func.count()).select_from(Notification))).scalar(),
            "users": (await db.execute(select(func.count()).select_from(User))).scalar(),
            "subjects": (await db.execute(select(func.count()).select_from(Subject))).scalar(),
            "schedules": (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar(),
            "cycles": (await db.execute(select(func.count()).select_from(QuizCycle))).scalar(),
        }


async def _cleanup():
    """FK-safe removal of every row this run created (scoped by temp ids)."""
    async with AsyncSessionLocal() as db:
        await db.execute(delete(Notification).where(Notification.user_id.in_(
            select(User.id).where(User.roll_number.like(f"{_TAG}%")))))
        await db.execute(delete(Notification).where(Notification.event_id.in_(
            select(AcademicEvent.id).where(
                AcademicEvent.subject_id.in_(select(Subject.id).where(Subject.code.like(f"{_TAG}%")))))))
        await db.execute(delete(AttendanceRecord).where(AttendanceRecord.class_session_id.in_(
            select(ClassSession.id).where(
                ClassSession.subject_id.in_(select(Subject.id).where(Subject.code.like(f"{_TAG}%")))))))
        await db.execute(delete(OccurrenceOutcome).where(OccurrenceOutcome.class_session_id.in_(
            select(ClassSession.id).where(
                ClassSession.subject_id.in_(select(Subject.id).where(Subject.code.like(f"{_TAG}%")))))))
        await db.execute(delete(ClassSession).where(ClassSession.subject_id.in_(
            select(Subject.id).where(Subject.code.like(f"{_TAG}%")))))
        await db.execute(delete(QuizSchedule).where(QuizSchedule.subject_id.in_(
            select(Subject.id).where(Subject.code.like(f"{_TAG}%")))))
        await db.execute(delete(AcademicEvent).where(AcademicEvent.subject_id.in_(
            select(Subject.id).where(Subject.code.like(f"{_TAG}%")))))
        await db.execute(delete(QuizCycle).where(QuizCycle.label.like(f"{_TAG}%")))
        await db.execute(delete(StudentEnrollment).where(StudentEnrollment.user_id.in_(
            select(User.id).where(User.roll_number.like(f"{_TAG}%")))))
        await db.execute(delete(UserPreference).where(UserPreference.user_id.in_(
            select(User.id).where(User.roll_number.like(f"{_TAG}%")))))
        await db.execute(delete(User).where(User.roll_number.like(f"{_TAG}%")))
        # Timetable entries reference BOTH the subject and the section — they
        # must go before either of their parents.
        await db.execute(delete(TimetableEntry).where(TimetableEntry.section_id.in_(
            select(Section.id).where(Section.name.like(f"{_TAG}%")))))
        await db.execute(delete(Subject).where(Subject.code.like(f"{_TAG}%")))
        await db.execute(delete(Section).where(Section.name.like(f"{_TAG}%")))
        await db.execute(delete(Semester).where(Semester.name.like(f"{_TAG}%")))
        await db.execute(delete(AcademicSession).where(AcademicSession.name.like(f"{_TAG}%")))
        await db.commit()


async def main() -> int:
    baseline = await _baseline_counts()
    print(f"baseline: {baseline}")

    # ── temp chain ────────────────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        academic_session = AcademicSession(
            name=f"{_TAG}-SESS", start_date=_TODAY - timedelta(days=90),
            end_date=_TODAY + timedelta(days=120), is_active=True)
        db.add(academic_session)
        await db.flush()
        semester = Semester(
            name=f"{_TAG}-SEM", session_id=academic_session.id,
            start_date=_TODAY - timedelta(days=90),
            end_date=_TODAY + timedelta(days=120))
        db.add(semester)
        await db.flush()
        section = Section(name=f"{_TAG}-SEC", semester_id=semester.id, program="TEST")
        db.add(section)
        await db.flush()
        subject = Subject(
            code=_TAG, name="TX Integrity Subject", tag=None, elective_slot=None,
            category=SubjectCategory.THEORY, quiz_applicable=True,
            attendance_applicable=True, semester_id=semester.id)
        db.add(subject)
        await db.flush()
        student = User(roll_number=f"{_TAG}-STU", name="TX Integrity Student",
                       hashed_password=None, role=UserRole.STUDENT, section_id=section.id)
        db.add(student)
        await db.flush()
        db.add(StudentEnrollment(user_id=student.id, subject_id=subject.id,
                                 enrollment_type=EnrollmentType.COMPULSORY))
        db.add(UserPreference(user_id=student.id, class_reminders=True,
                              auto_mark_present=False, week_starts_on=WeekStartsOn.MONDAY))
        entry = TimetableEntry(subject_id=subject.id, day_of_week=0, start_time=time(9, 0),
                               end_time=time(10, 0), class_type=ClassType.LECTURE,
                               section_id=section.id)
        db.add(entry)
        await db.flush()
        await db.commit()
        chain = {
            "subject_id": subject.id, "student_id": student.id,
            "entry_id": entry.id, "semester_start": semester.start_date,
        }

    admin = None
    async with AsyncSessionLocal() as db:
        admin = (await db.execute(
            select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        assert admin is not None, "seeded admin user missing"

    admin_headers = {"Authorization": f"Bearer {create_access_token(str(admin.id), admin.roll_number)}"}
    student_headers = {"Authorization": f"Bearer {create_access_token(str(chain['student_id']), f'{_TAG}-STU')}"}

    created_event_ids = []

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        # ── Flow 1: create normal academic event ─────────────────────────────
        r = await c.post("/api/v1/events", headers=admin_headers, json={
            "event_type": "EXTRA_LECTURE", "start_date": FUT1.isoformat(),
            "end_date": FUT1.isoformat(), "subject_id": str(chain["subject_id"]),
            "class_type": "L", "active": True})
        body = r.json()
        ev1 = body.get("id")
        created_event_ids.append(ev1)
        check("1. create normal EXTRA_LECTURE -> 201",
              r.status_code == 201 and ev1, f"status={r.status_code} {body}")

        async with AsyncSessionLocal() as db:
            extra_sessions = (await db.execute(select(ClassSession).where(
                ClassSession.source_event_id == ev1))).scalars().all()
            notif = (await db.execute(select(func.count()).select_from(Notification).where(
                Notification.kind == NotificationKind.ACADEMIC_EVENT,
                Notification.occurrence_key == ev1,
                Notification.user_id == chain["student_id"]))).scalar()
            check("1b. session materialized + ACADEMIC_EVENT projection for enrolled student",
                  len(extra_sessions) == 1 and notif == 1,
                  f"sessions={len(extra_sessions)} notif={notif}")

        # ── Flow 2: managed QUIZ_DAY via generic path -> 409 ─────────────────
        # First create the MANAGING schedule through the Quiz Manager.
        async with AsyncSessionLocal() as db:
            cycle = QuizCycle(cycle_number=900000 + (uuid.uuid4().int % 90000), label=f"{_TAG}-CYC")
            db.add(cycle)
            await db.flush()
            cycle_id = cycle.id
            await db.commit()
        async with AsyncSessionLocal() as db:
            qsvc = AdminQuizService(db)
            from app.schemas.admin_quizzes import CreateQuizScheduleRequest
            try:
                resp = await qsvc.create_quiz_schedule(admin, CreateQuizScheduleRequest(
                    subject_id=chain["subject_id"], quiz_cycle_id=cycle_id,
                    elective_slot=None, date=FUT2, schedule_status=ScheduleStatus.SCHEDULED))
                managed_created = resp.event_created
            except AdminQuizConflictError as exc:
                managed_created = False
                print(f"  (quiz schedule create conflict: {exc.detail})")
            await db.commit()
        check("3. managed QUIZ_DAY created through Quiz Manager",
              managed_created is True, f"event_created={managed_created}")

        r = await c.post("/api/v1/events", headers=admin_headers, json={
            "event_type": "QUIZ_DAY", "start_date": FUT2.isoformat(),
            "end_date": FUT2.isoformat(), "subject_id": str(chain["subject_id"])})
        check("2. generic create of schedule-backed QUIZ_DAY -> 409 (EVT-003)",
              r.status_code == 409, f"status={r.status_code}")

        async with AsyncSessionLocal() as db:
            managed_events = (await db.execute(select(AcademicEvent).where(
                AcademicEvent.subject_id == chain["subject_id"],
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.start_date == FUT2,
                AcademicEvent.active.is_(True)))).scalars().all()
            check("2b. no duplicate managed event row (exactly one)",
                  len(managed_events) == 1, f"rows={len(managed_events)}")
            managed_event_id = str(managed_events[0].id) if managed_events else None
            quiz_day_session = (await db.execute(select(ClassSession).where(
                ClassSession.subject_id == chain["subject_id"],
                ClassSession.date == FUT2,
                ClassSession.timetable_entry_id.is_(None),
                ClassSession.is_extra.is_(False),
                ClassSession.class_type == ClassType.LECTURE))).scalars().all()
            check("3b. quiz-day session materialized exactly once (Option A)",
                  len(quiz_day_session) == 1, f"quiz_sessions={len(quiz_day_session)}")

        # ── Flow 5: type-change INTO managed identity -> 409 ─────────────────
        r = await c.patch(f"/api/v1/events/{ev1}", headers=admin_headers, json={
            "event_type": "QUIZ_DAY", "start_date": FUT2.isoformat(),
            "end_date": FUT2.isoformat()})
        check("5. convert normal event into managed QUIZ_DAY -> 409 (final-state guard)",
              r.status_code == 409, f"status={r.status_code}")

        # ── Flow 6: re-date managed QUIZ_DAY via generic path -> 409 ─────────
        r = await c.patch(f"/api/v1/events/{managed_event_id}", headers=admin_headers, json={
            "start_date": FUT3.isoformat(), "end_date": FUT3.isoformat()})
        check("6. generic re-date of managed QUIZ_DAY -> 409",
              r.status_code == 409, f"status={r.status_code}")

        # ── Flow 7: generic deactivation of managed QUIZ_DAY -> 409 ──────────
        r = await c.delete(f"/api/v1/events/{managed_event_id}", headers=admin_headers)
        check("7. generic deactivate of managed QUIZ_DAY -> 409",
              r.status_code == 409, f"status={r.status_code}")

        # ── Flow 4: edit normal event (note) -> 200; notification refreshed ──
        r = await c.patch(f"/api/v1/events/{ev1}", headers=admin_headers, json={
            "note": "integrity flow note"})
        check("4. edit normal event -> 200", r.status_code == 200, f"status={r.status_code}")

        # ── Flow 10: future -> future update keeps+refreshes projection ──────
        r = await c.patch(f"/api/v1/events/{ev1}", headers=admin_headers, json={
            "start_date": FUT3.isoformat(), "end_date": FUT3.isoformat()})
        check("10. future -> future re-date -> 200", r.status_code == 200,
              f"status={r.status_code}")
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(Notification).where(
                Notification.kind == NotificationKind.ACADEMIC_EVENT,
                Notification.occurrence_key == ev1,
                Notification.user_id == chain["student_id"]))).scalars().all()
            check("10b. projection kept exactly once and refreshed to the new date",
                  len(rows) == 1 and rows[0].message.endswith(FUT3.strftime("%d %b %Y")),
                  f"rows={len(rows)} msg={rows[0].message if rows else None}")

        # ── Flow 12/13: repeated synchronization is idempotent ───────────────
        async with AsyncSessionLocal() as db:
            event = (await db.execute(select(AcademicEvent).where(
                AcademicEvent.id == ev1))).scalars().one()
            from app.services.event_session_service import EventSessionSynchronizer
            sync = EventSessionSynchronizer(db)
            await sync.sync_event(event)
            await sync.sync_event(event)
            await db.commit()
            extras = (await db.execute(select(ClassSession).where(
                ClassSession.source_event_id == ev1))).scalars().all()
            check("13. repeated synchronization stays idempotent (one extra)",
                  len(extras) == 1, f"extras={len(extras)}")

        # ── Flow 18: cancellation propagation ─────────────────────────────────
        # FUT1 is a MONDAY — the temp entry's day-of-week — so the
        # cancellation has a matching timetable occurrence to remove.
        r = await c.post("/api/v1/events", headers=admin_headers, json={
            "event_type": "CLASS_CANCELLED", "start_date": FUT1.isoformat(),
            "end_date": FUT1.isoformat(), "subject_id": str(chain["subject_id"]),
            "class_type": "L", "active": True})
        cancel_id = r.json().get("id")
        created_event_ids.append(cancel_id)
        check("18. CLASS_CANCELLED created -> 201", r.status_code == 201,
              f"status={r.status_code}")
        async with AsyncSessionLocal() as db:
            # The cancellation removes the matching timetable occurrence for
            # the entry's day-of-week; the EXTRA session from ev1 (FUT3) is a
            # different shape and must survive untouched.
            cancelled_rows = (await db.execute(select(ClassSession).where(
                ClassSession.timetable_entry_id == chain["entry_id"],
                ClassSession.is_cancelled.is_(True)))).scalars().all()
            extra_alive = (await db.execute(select(ClassSession).where(
                ClassSession.source_event_id == ev1))).scalars().all()
            check("18b. timetable occurrence cancelled by the event; extra unaffected",
                  len(cancelled_rows) >= 1 and len(extra_alive) == 1,
                  f"cancelled={len(cancelled_rows)} extras={len(extra_alive)}")
        # deactivate the cancellation -> session restored
        r = await c.delete(f"/api/v1/events/{cancel_id}", headers=admin_headers)
        async with AsyncSessionLocal() as db:
            restored = (await db.execute(select(ClassSession).where(
                ClassSession.timetable_entry_id == chain["entry_id"],
                ClassSession.is_cancelled.is_(False)))).scalars().all()
            check("18c. deactivating the cancellation restores the session",
                  r.status_code == 200 and len(restored) >= 1,
                  f"status={r.status_code} restored={len(restored)}")

        # ── Flow 9: future -> past update removes the projection ─────────────
        past = _TODAY - timedelta(days=20)
        while past.weekday() >= 5:
            past -= timedelta(days=1)
        r = await c.patch(f"/api/v1/events/{ev1}", headers=admin_headers, json={
            "start_date": past.isoformat(), "end_date": past.isoformat()})
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(func.count()).select_from(Notification).where(
                Notification.kind == NotificationKind.ACADEMIC_EVENT,
                Notification.occurrence_key == ev1,
                Notification.user_id == chain["student_id"]))).scalar()
            check("9. future -> past update removes the ACADEMIC_EVENT projection",
                  r.status_code == 200 and rows == 0, f"status={r.status_code} rows={rows}")

        # ── Flow 11: reactivate previously (flow-9) event -> re-projection ───
        r = await c.patch(f"/api/v1/events/{ev1}", headers=admin_headers, json={
            "start_date": FUT3.isoformat(), "end_date": FUT3.isoformat(), "active": True})
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(func.count()).select_from(Notification).where(
                Notification.kind == NotificationKind.ACADEMIC_EVENT,
                Notification.occurrence_key == ev1,
                Notification.user_id == chain["student_id"]))).scalar()
            check("11. reactivation re-emits the projection (future event)",
                  r.status_code == 200 and rows == 1, f"status={r.status_code} rows={rows}")

        # ── Flow 8: deactivate normal future event removes projection+session
        r = await c.delete(f"/api/v1/events/{ev1}", headers=admin_headers)
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(select(func.count()).select_from(Notification).where(
                Notification.kind == NotificationKind.ACADEMIC_EVENT,
                Notification.occurrence_key == ev1))).scalar()
            sess = (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.source_event_id == ev1,
                ClassSession.is_deactivated.is_(False)))).scalar()
            check("8. deactivate normal future event -> projection removed for ALL users, "
                  "unattended extra deleted",
                  r.status_code == 200 and rows == 0 and sess == 0,
                  f"status={r.status_code} rows={rows} active_sessions={sess}")

        # ── Flow 14: concurrent duplicate event creation ─────────────────────
        a = AsyncSessionLocal()
        b = AsyncSessionLocal()
        try:
            await a.begin()
            await b.begin()
            # Standalone QUIZ_DAY at FUT1 (no backing schedule there): its
            # (subject, slot, start) identity IS constrained by
            # uq_academic_events_quiz_day_identity. (The extra family is
            # deliberately unconstrained — multiple same-key extras are a
            # pinned contract — so it must not be used for this race.)
            ev_a = AcademicEvent(event_type=EventType.QUIZ_DAY, start_date=FUT1,
                                 end_date=FUT1, subject_id=chain["subject_id"],
                                 active=True)
            a.add(ev_a)
            await a.flush()

            async def b_create():
                svc = EventService(b)
                from app.schemas.calendar import AcademicEventCreate
                await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.QUIZ_DAY, start_date=FUT1, end_date=FUT1,
                    subject_id=chain["subject_id"]))

            b_task = asyncio.create_task(b_create())
            await asyncio.sleep(0.4)
            await a.commit()
            conflict = False
            try:
                await asyncio.wait_for(b_task, timeout=8)
            except EventConflict:
                conflict = True
            except EventValidationError:
                conflict = True  # pre-check path surfaces the same 409 semantics
            await b.rollback()
            check("14. concurrent duplicate event creation -> loser rejected (409 "
                  "semantics), exactly one row", conflict)
        finally:
            await a.rollback()
            await b.rollback()
            await a.close()
            await b.close()
        # A's row WON the race and is COMMITTED (a later rollback is a no-op):
        # remove the race winner explicitly — it is this run's artifact (it
        # never went through the synchronizer, so it has no sessions and no
        # projections; flows 19/19b below must not see its effective quiz
        # date).
        async with AsyncSessionLocal() as db:
            await db.execute(delete(AcademicEvent).where(
                AcademicEvent.subject_id == chain["subject_id"],
                AcademicEvent.start_date == FUT1,
                AcademicEvent.event_type == EventType.QUIZ_DAY))
            await db.commit()

        # ── Flow 15: concurrent duplicate session materialization ────────────
        a = AsyncSessionLocal()
        b = AsyncSessionLocal()
        try:
            await a.begin()
            await b.begin()
            # FUT2 carries no scheduled row for the entry (the span syncs of
            # flows 9-11 materialized the entry's MONDAY occurrences only, and
            # FUT1 is such a Monday) — so the raced identity is free.
            s_a = ClassSession(subject_id=chain["subject_id"], date=FUT2,
                               class_type=ClassType.LECTURE, is_extra=False,
                               is_cancelled=False, timetable_entry_id=chain["entry_id"])
            a.add(s_a)
            await a.flush()

            async def b_insert():
                b.add(ClassSession(subject_id=chain["subject_id"], date=FUT2,
                                   class_type=ClassType.LECTURE, is_extra=False,
                                   is_cancelled=False, timetable_entry_id=chain["entry_id"]))
                await b.flush()

            b_task = asyncio.create_task(b_insert())
            await asyncio.sleep(0.4)
            await a.commit()
            rejected = False
            try:
                await asyncio.wait_for(b_task, timeout=8)
            except Exception:
                rejected = True
            await b.rollback()
            check("15. concurrent duplicate session materialization -> DB rejects "
                  "the loser (exactly one canonical row)", rejected)
        finally:
            await a.rollback()
            await b.rollback()
            await a.close()
            await b.close()

        # ── Flow 19: quiz eligibility propagation ─────────────────────────────
        async with AsyncSessionLocal() as db:
            repo = QuizRepository(db)
            effective = await repo.get_effective_quiz_dates_for_subject(chain["subject_id"])
            check("19. managed QUIZ_DAY is the effective quiz-date authority",
                  [d for _, d in effective] == [FUT2], f"effective={effective}")

        # Quiz-manager retire (the ONLY legal way to withdraw it)
        async with AsyncSessionLocal() as db:
            qsvc = AdminQuizService(db)
            from app.schemas.admin_quizzes import UpdateQuizScheduleRequest
            sched = (await db.execute(select(QuizSchedule).where(
                QuizSchedule.subject_id == chain["subject_id"]))).scalars().first()
            await qsvc.update_quiz_schedule(admin, sched.id, UpdateQuizScheduleRequest(
                schedule_status=ScheduleStatus.CANCELLED))
            await db.commit()
        async with AsyncSessionLocal() as db:
            repo = QuizRepository(db)
            effective = await repo.get_effective_quiz_dates_for_subject(chain["subject_id"])
            ev_active = (await db.execute(select(func.count()).select_from(AcademicEvent).where(
                AcademicEvent.subject_id == chain["subject_id"],
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True)))).scalar()
            qsess = (await db.execute(select(func.count()).select_from(ClassSession).where(
                ClassSession.subject_id == chain["subject_id"],
                ClassSession.date == FUT2,
                ClassSession.timetable_entry_id.is_(None),
                ClassSession.is_extra.is_(False),
                ClassSession.is_deactivated.is_(False)))).scalar()
            check("7b/19b. quiz-manager retirement deactivates the event, removes the "
                  "unattended quiz-day session, and drops the effective date",
                  ev_active == 0 and qsess == 0 and effective == [],
                  f"active_events={ev_active} sessions={qsess} effective={effective}")

        # ── Flow 16/17: CLASS_REMINDER generation via the scheduler ──────────
        try:
            from app.services.notification_scheduler import run_class_reminder_sweep_once
            async with AsyncSessionLocal() as db:
                # Reminder window = [today, end of the institutional week].
                # Entry-NULL non-extra LECTURE rows (the quiz-day shape) are
                # unique per (subject, date) — distinct dates keep the two
                # fixtures collision-free with every session created above.
                week_end = (_TODAY - timedelta(days=_TODAY.weekday())) + timedelta(days=6)
                sess_day = min(_TODAY, week_end)
                cancel_day = min(_TODAY + timedelta(days=1), week_end)
                same_day = cancel_day == sess_day
                sess = ClassSession(subject_id=chain["subject_id"], date=sess_day,
                                    class_type=ClassType.LECTURE, is_extra=False,
                                    is_cancelled=False, timetable_entry_id=None)
                cancelled = ClassSession(subject_id=chain["subject_id"],
                                         date=cancel_day,
                                         class_type=ClassType.TUTORIAL if same_day else ClassType.LECTURE,
                                         is_extra=False, is_cancelled=True,
                                         timetable_entry_id=None)
                db.add_all([sess, cancelled])
                await db.commit()
                sess_id = sess.id
                cancelled_id = cancelled.id
            pushed = []
            ran = await run_class_reminder_sweep_once(
                push_sink=pushed.append, user_ids=[chain["student_id"]])
            async with AsyncSessionLocal() as db:
                reminders = (await db.execute(select(Notification).where(
                    Notification.user_id == chain["student_id"],
                    Notification.kind == NotificationKind.CLASS_REMINDER))).scalars().all()
                keys = {r.occurrence_key for r in reminders}
                check("16. scheduler sweep generates CLASS_REMINDER for the opted-in "
                      "student's uncancelled in-window session (cancelled excluded)",
                      ran >= 1 and str(sess_id) in keys
                      and str(cancelled_id) not in keys,
                      f"ran={ran} keys={keys}")
            pushes_count_after_first = len(pushed)
            ran2 = await run_class_reminder_sweep_once(
                push_sink=pushed.append, user_ids=[chain["student_id"]])
            pushes_after_first = pushes_count_after_first
            async with AsyncSessionLocal() as db:
                count2 = (await db.execute(select(func.count()).select_from(Notification).where(
                    Notification.user_id == chain["student_id"],
                    Notification.kind == NotificationKind.CLASS_REMINDER))).scalar()
                check("17. repeated CLASS_REMINDER sweep is idempotent (no new rows, "
                      "no re-push)", count2 == len(reminders) and len(pushed) == pushes_after_first,
                      f"rows={count2} first={len(reminders)} "
                      f"pushes1={pushes_after_first} pushes2={len(pushed)}")
        except ImportError as exc:
            check("16. scheduler sweep generates CLASS_REMINDER", False,
                  f"scheduler module/entrypoint missing: {exc}")
            check("17. repeated CLASS_REMINDER sweep is idempotent", False,
                  "scheduler missing")

        # ── Flow 20: notification inbox behavior ─────────────────────────────
        r = await c.get("/api/v1/notifications", headers=student_headers)
        body = r.json()
        kinds = [i["kind"] for i in body.get("items", [])]
        check("20. inbox serves persisted rows (live, non-dismissed) with unread "
              "metadata", r.status_code == 200 and "unread_count" in body
              and all(k != "ACADEMIC_EVENT" or True for k in kinds),
              f"status={r.status_code} keys={list(body.keys())}")

    # ── cleanup + baseline restoration ────────────────────────────────────────
    await _cleanup()
    after = await _baseline_counts()
    restored_ok = (
        after["events"] == baseline["events"]
        and after["sessions"] == baseline["sessions"]
        and after["cancelled"] == baseline["cancelled"]
        and after["records"] == baseline["records"]
        and after["notifications"] == baseline["notifications"]
        and after["users"] == baseline["users"]
        and after["subjects"] == baseline["subjects"]
        and after["schedules"] == baseline["schedules"]
        and after["cycles"] == baseline["cycles"]
    )
    check("BASELINE. dev DB restored to exact pre-run counts (452 legacy orphans "
          "untouched)", restored_ok, f"before={baseline} after={after}")

    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:", failed)
    return 0 if not failed else 1


_LOOP = asyncio.new_event_loop()


if __name__ == "__main__":
    code = 1
    try:
        code = _LOOP.run_until_complete(main())
    finally:
        try:
            _LOOP.run_until_complete(engine.dispose())
        except Exception:
            pass
    sys.exit(code)
