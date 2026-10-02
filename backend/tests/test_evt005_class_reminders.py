"""EVT-005 (Events Backend Remediation) — CLASS_REMINDER production scheduler.

Audit defect (docs/EVENTS_BACKEND_DEEP_AUDIT_REPORT.md EVT-005 / H-4d):
CLASS_REMINDER generation was unreachable in production. The only producer
was the explicit sweep ``NotificationService.regenerate_user_notifications``
with NO production caller — no scheduler existed anywhere (no lifespan, no
background task, no worker) — so the documented ``class_reminders`` user
preference silently did nothing.

Fix under test (``app/services/notification_scheduler.py`` + the FastAPI
lifespan in ``app/main.py``):

  - ``run_class_reminder_sweep_once()`` regenerates the canonical
    projections for every user opted into class reminders (the sweep IS the
    existing projection builders — identical date semantics from
    ``institution_today()``, cancelled/marked sessions excluded);
  - the emission is the canonical ``emit()`` boundary: repeated sweeps
    refresh in place (ON CONFLICT on (user_id, kind, occurrence_key)) and
    never re-push;
  - the periodic task starts idempotently (never started twice) from the
    lifespan, honours CLASS_REMINDER_SWEEP_ENABLED, and stops cleanly.

Tests run the REAL sweep against the REAL database inside a SAVEPOINT-style
sandbox: the sweep's per-user sessions all bind to ONE outer transaction via
the injected ``session_factory``; ``commit()`` becomes a flush and everything
rolls back at the end (same convention as the EVT-001/002 suite). Pushes are
observed through the injected ``push_sink`` seam (temp users have no push
subscriptions, but the seam proves exactly-once delivery semantics).
"""
import asyncio
import uuid
from datetime import time, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.timezone import institution_today
from app.db.session import AsyncSessionLocal, engine
from app.models.academic import StudentEnrollment, Subject
from app.models.attendance import AttendanceRecord
from app.models.enums import (
    AttendanceStatus,
    ClassType,
    EnrollmentType,
    NotificationKind,
    SubjectCategory,
    UserRole,
    WeekStartsOn,
)
from app.models.notification import Notification
from app.models.preference import UserPreference
from app.models.timetable import ClassSession
from app.models.user import User
from app.services.notification_scheduler import (
    run_class_reminder_sweep_once,
    start_class_reminder_scheduler,
    stop_class_reminder_scheduler,
)

_TODAY = institution_today()
_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


@pytest.fixture(scope="module", autouse=True)
def _loop_lifecycle():
    yield
    try:
        _LOOP.run_until_complete(engine.dispose())
    except Exception:
        pass


class _RollbackSession:
    """Binds every sweep session to ONE real session inside ONE outer
    transaction; ``commit()`` becomes a flush, so the sweep's writes stay
    uncommitted and the outer rollback discards everything."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    async def commit(self):
        await self._real.flush()

    async def rollback(self):
        await self._real.rollback()


class _SharedTxFactory:
    """session_factory seam: hands out wrapper sessions that all share the
    one real (outer-transaction) session."""

    def __init__(self, real):
        self._real = real

    def __call__(self):
        return _RollbackSessionCtx(self._real)


class _RollbackSessionCtx:
    def __init__(self, real):
        self._wrapper = _RollbackSession(real)

    async def __aenter__(self):
        return self._wrapper

    async def __aexit__(self, *exc):
        return False


@pytest.fixture()
def sandbox():
    """One real session inside one outer transaction + the factory seam."""

    async def _setup():
        real = AsyncSessionLocal()
        await real.begin()
        return real

    real = _run(_setup())
    try:
        yield real, _SharedTxFactory(real)
    finally:
        _run(real.rollback())
        _run(real.close())


async def _make_chain(db, *, tag, with_pref, session_shapes):
    """Temp subject + student (+ optional preference) + sessions. All rows
    live only inside the sandbox transaction."""
    from app.models.academic import AcademicSession, Semester
    from app.models.user import Section

    academic_session = AcademicSession(
        name=f"{tag}-SESS", start_date=_TODAY - timedelta(days=90),
        end_date=_TODAY + timedelta(days=120), is_active=True)
    db.add(academic_session)
    await db.flush()
    semester = Semester(
        name=f"{tag}-SEM", session_id=academic_session.id,
        start_date=_TODAY - timedelta(days=90),
        end_date=_TODAY + timedelta(days=120))
    db.add(semester)
    await db.flush()
    section = Section(name=f"{tag}-SEC", semester_id=semester.id, program="TEST")
    db.add(section)
    await db.flush()
    subject = Subject(
        code=tag, name="TX Reminder Subject", tag=None, elective_slot=None,
        category=SubjectCategory.THEORY, quiz_applicable=False,
        attendance_applicable=True, semester_id=semester.id)
    db.add(subject)
    await db.flush()
    student = User(roll_number=f"{tag}-STU", name="TX Reminder Student",
                   hashed_password=None, role=UserRole.STUDENT, section_id=section.id)
    db.add(student)
    await db.flush()
    db.add(StudentEnrollment(user_id=student.id, subject_id=subject.id,
                             enrollment_type=EnrollmentType.COMPULSORY))
    if with_pref:
        db.add(UserPreference(user_id=student.id, class_reminders=True,
                              auto_mark_present=False, week_starts_on=WeekStartsOn.MONDAY))
    # Reminder window = [today, end of the institutional week] (the builder's
    # own semantics), so fixture sessions must stay inside it — clamped, NOT
    # weekend-shifted (a working-Saturday session is a legitimate reminder).
    week_end = (_TODAY - timedelta(days=_TODAY.weekday())) + timedelta(days=6)
    session_ids = {}
    for name, (offset, cancelled, marked) in session_shapes.items():
        day = min(_TODAY + timedelta(days=offset), week_end)
        # Only ONE entry-NULL non-extra LECTURE session per (subject, date)
        # may exist (uq_class_sessions_quiz_day_subject_date — the quiz-day
        # shape); the cancelled/marked fixture variants are TUTORIAL, which
        # the reminder semantics treat identically.
        class_type = ClassType.TUTORIAL if name != "inweek" else ClassType.LECTURE
        sess = ClassSession(subject_id=subject.id, date=day,
                            class_type=class_type, is_extra=False,
                            is_cancelled=cancelled, timetable_entry_id=None)
        db.add(sess)
        await db.flush()
        session_ids[name] = sess.id
        if marked:
            db.add(AttendanceRecord(user_id=student.id, class_session_id=sess.id,
                                    status=AttendanceStatus.ATTENDED))
    await db.flush()
    return {"student_id": student.id, "subject_id": subject.id,
            "session_ids": session_ids}


# ═══════════════════════════════ T1 + T2 ════════════════════════════════════

def test_t1_t2_sweep_generates_reminders_for_opted_in_only(sandbox):
    """An opted-in user's unmarked, uncancelled in-window session gets exactly
    one CLASS_REMINDER row (keyed by session id); a user without the
    preference gets none — the preference finally does something."""
    real, factory = sandbox

    async def scenario():
        opted = await _make_chain(
            real, tag=f"TXE5A{uuid.uuid4().hex[:6]}", with_pref=True,
            session_shapes={"inweek": (1, False, False)})
        not_opted = await _make_chain(
            real, tag=f"TXE5B{uuid.uuid4().hex[:6]}", with_pref=False,
            session_shapes={"inweek": (1, False, False)})
        await real.flush()
        pushed = []
        swept = await run_class_reminder_sweep_once(
            push_sink=pushed.append, session_factory=factory)
        assert swept >= 1
        rows = (await real.execute(
            select(Notification).where(
                Notification.kind == NotificationKind.CLASS_REMINDER))).scalars().all()
        by_user = {str(r.user_id): r for r in rows}
        assert str(opted["student_id"]) in by_user, "opted-in user has a reminder"
        assert str(not_opted["student_id"]) not in by_user, "no preference -> no reminder"
        reminder = by_user[str(opted["student_id"])]
        assert reminder.occurrence_key == str(opted["session_ids"]["inweek"])
        assert reminder.session_id == opted["session_ids"]["inweek"]
        # exactly one push, for the opted-in user's new row only
        assert len(pushed) == 1 and str(pushed[0][0]) == str(opted["student_id"])
        return True

    assert _run(scenario()) is True


# ═══════════════════════════════ T3 ════════════════════════════════════════

def test_t3_repeated_sweep_is_idempotent_and_never_repushes(sandbox):
    real, factory = sandbox

    async def scenario():
        chain = await _make_chain(
            real, tag=f"TXE5C{uuid.uuid4().hex[:6]}", with_pref=True,
            session_shapes={"inweek": (1, False, False)})
        await real.flush()
        pushed = []
        await run_class_reminder_sweep_once(push_sink=pushed.append,
                                            session_factory=factory)
        await run_class_reminder_sweep_once(push_sink=pushed.append,
                                            session_factory=factory)
        n = (await real.execute(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == chain["student_id"],
                Notification.kind == NotificationKind.CLASS_REMINDER))).scalar()
        assert n == 1, f"repeat sweep duplicated the reminder: {n}"
        assert len(pushed) == 1, f"repeat sweep re-pushed: {len(pushed)}"
        return True

    assert _run(scenario()) is True


# ═══════════════════════════════ T4 ════════════════════════════════════════

def test_t4_cancelled_and_marked_sessions_excluded(sandbox):
    real, factory = sandbox

    async def scenario():
        chain = await _make_chain(
            real, tag=f"TXE5D{uuid.uuid4().hex[:6]}", with_pref=True,
            session_shapes={
                "cancelled": (1, True, False),
                "marked": (2, False, True),
                "clean": (3, False, False),
            })
        await real.flush()
        await run_class_reminder_sweep_once(session_factory=factory)
        rows = (await real.execute(
            select(Notification).where(
                Notification.user_id == chain["student_id"],
                Notification.kind == NotificationKind.CLASS_REMINDER))).scalars().all()
        keys = {r.occurrence_key for r in rows}
        assert keys == {str(chain["session_ids"]["clean"])}, \
            f"only the clean unmarked session may remind: {keys}"
        return True

    assert _run(scenario()) is True


# ═══════════════════════════════ T5 ════════════════════════════════════════

def test_t5_start_stop_lifecycle_idempotent_and_flag_gated(monkeypatch):
    """start_class_reminder_scheduler never starts twice; stop cancels; the
    disabled configuration starts nothing."""

    async def scenario():
        def stop_ok(t):
            return t.cancelled() or t.done()

        stop_class_reminder_scheduler()  # ensure a clean slate
        task = start_class_reminder_scheduler()
        assert task is not None, "enabled by default -> task created"
        again = start_class_reminder_scheduler()
        assert again is task, "second start must return the SAME task"
        await stop_class_reminder_scheduler()
        assert stop_ok(task)

        monkeypatch.setattr(settings, "CLASS_REMINDER_SWEEP_ENABLED", False)
        assert start_class_reminder_scheduler() is None, \
            "disabled configuration must start nothing"
        await stop_class_reminder_scheduler()
        return True

    assert _run(scenario()) is True


# ═══════════════════════════════ T6 ════════════════════════════════════════

def test_t6_lifespan_starts_and_stops_the_scheduler():
    """The FastAPI lifespan wiring: entering the app lifespan starts the
    scheduler inside this process; exiting stops it — the production
    deployment contract (uvicorn app.main:app runs this lifespan)."""

    from app.main import app
    import app.services.notification_scheduler as sched

    async def scenario():
        assert sched._scheduler_task is None
        async with app.router.lifespan_context(app):
            assert sched._scheduler_task is not None, \
                "lifespan startup must start the scheduler task"
            assert sched._scheduler_task is start_class_reminder_scheduler(), \
                "double start (import + lifespan) must be idempotent"
        assert sched._scheduler_task is None, \
            "lifespan shutdown must stop the scheduler task"
        return True

    assert _run(scenario()) is True
