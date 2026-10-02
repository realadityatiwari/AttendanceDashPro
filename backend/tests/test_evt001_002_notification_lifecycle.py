"""EVT-001 + EVT-002 (Events Backend Remediation Phase 2) — ACADEMIC_EVENT
notification projections follow the lifecycle of their source AcademicEvent.

Audit defects:
  - EVT-001: deactivate_event() never touched the event's ACADEMIC_EVENT
    notification projection — soft-deactivated events left stale "… on
    <date>" rows live in every recipient's inbox (the H-4a read filter only
    hides rows whose event row no longer EXISTS; soft-deleted rows exist).
  - EVT-002: update_event() moving an event future → past made the
    post-commit emission trigger early-return, so the previously generated
    future-event notification stayed live with its old date.

Fix under test: `NotificationService.reconcile_event_notification(event)` —
one shared stale predicate (`event_is_stale_for_notification`: inactive OR
no longer future) governs BOTH the emission trigger's early-return and the
new in-transaction reconciliation, which removes every recipient's
projection row for the event (idempotent; other events' rows and other
notification kinds untouched; no replacement created). EventService calls it
inside the mutation transaction (deactivation, and updates whose FINAL state
is stale), and quiz-manager retirement reconciles too — the event change and
its notification reconciliation commit or roll back together.

Scenarios run the REAL production services inside a SAVEPOINT sandbox (same
pattern as the Phase 1 EVT-003 tests): EventService.commit() and the
notification writes become flushes inside an outer transaction and everything
rolls back. Synthetic TX-* fixtures isolate notification recipients (no push
subscriptions -> no real pushes; the enrolled recipient is the synthetic
student only).

T1  deactivate future event -> its ACADEMIC_EVENT row removed
T2  deactivate event with no projection -> safe, idempotent
T3  deactivate twice -> idempotent, unrelated rows untouched
T4  future -> past update -> row removed
T5  future -> future update -> row kept and refreshed
T6  past -> past update -> no row created
T7  deactivated event -> no live row regains through a normal update
T8  unrelated notification kinds for the same user untouched
T9  another event's notification untouched
T10 event + notification reconcile visible in the SAME transaction
T11 EVT-003 guard intact + rejected mutations mutate zero notifications
T12 Quiz Manager lifecycle works; retirement reconciles an adopted projection
"""
import asyncio
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.core.timezone import institution_today
from app.db.session import AsyncSessionLocal, engine
from app.models.academic import (
    AcademicSession,
    Semester,
    StudentEnrollment,
    Subject,
)
from app.models.enums import (
    ClassType,
    EnrollmentType,
    EventType,
    NotificationKind,
    SubjectCategory,
    UserRole,
)
from app.models.event import AcademicEvent
from app.models.notification import Notification
from app.models.quiz import QuizCycle, QuizSchedule, ScheduleStatus
from app.models.timetable import ClassSession
from app.models.user import Section, User
from app.repositories.event_repo import EventConflict
from app.schemas.calendar import AcademicEventCreate, AcademicEventUpdate
from app.services.admin_quiz_service import AdminQuizService
from app.services.event_service import EventService
from app.services.notification_service import NotificationService

# Fixture dates derive from the live institutional clock so the tests never
# silently rot as "today" advances.
_TODAY = institution_today()
FUT1 = _TODAY + timedelta(days=39)
FUT2 = _TODAY + timedelta(days=41)
PAST1 = _TODAY - timedelta(days=17)
PAST2 = _TODAY - timedelta(days=15)
_SPAN_START = _TODAY - timedelta(days=90)
_SPAN_END = _TODAY + timedelta(days=120)


class _RollbackSession:
    """Wraps the real AsyncSession: `commit()` becomes a flush inside an
    outer transaction; everything is rolled back when the wrapper closes."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    async def commit(self):
        await self._real.flush()

    async def rollback(self):
        await self._real.rollback()


# ONE loop for the whole module (asyncpg connections bind to their creating
# loop; the registration e2e module documents the same Windows constraint).
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
    _LOOP.close()


async def _chain(db, tag):
    """Synthetic academic chain + quiz-bearing theory subject + admin +
    enrolled student (the notification recipient). Returns (subject, admin,
    student)."""
    academic_session = AcademicSession(
        name=f"TX-SESS-{tag}", start_date=_SPAN_START,
        end_date=_SPAN_END, is_active=True)
    db.add(academic_session)
    await db.flush()
    semester = Semester(
        name=f"TX-SEM-{tag}", session_id=academic_session.id,
        start_date=_SPAN_START, end_date=_SPAN_END)
    db.add(semester)
    await db.flush()
    section = Section(name=f"TX-SEC-{tag}", semester_id=semester.id, program="TEST")
    db.add(section)
    await db.flush()
    subject = Subject(
        code="TX-EVT12", name="TX EVT-001/002 Subject", tag=None,
        elective_slot=None, category=SubjectCategory.THEORY,
        quiz_applicable=True, attendance_applicable=True,
        semester_id=semester.id)
    db.add(subject)
    await db.flush()
    student = User(roll_number=f"TX-STU-{tag}", name="TX Lifecycle Student",
                   hashed_password=None, role=UserRole.STUDENT,
                   section_id=section.id)
    admin = User(roll_number=f"TX-ADM-{tag}", name="TX Lifecycle Admin",
                 hashed_password=None, role=UserRole.ADMIN, section_id=None)
    db.add_all([student, admin])
    await db.flush()
    db.add(StudentEnrollment(user_id=student.id, subject_id=subject.id,
                             enrollment_type=EnrollmentType.COMPULSORY))
    await db.flush()
    return subject, admin, student


def _sandbox(session):
    """Autoflush OFF so un-flushed in-memory state can never leak into
    intermediate reads; every service under test flushes explicitly at its
    persistence points."""
    session.autoflush = False


async def _event_rows(db, event_id) -> int:
    """ACADEMIC_EVENT projection row count for one event (all recipients)."""
    return (await db.execute(
        select(func.count()).select_from(Notification)
        .where(Notification.kind == NotificationKind.ACADEMIC_EVENT,
               Notification.occurrence_key == str(event_id))
    )).scalar_one()


async def _emit(db, event) -> int:
    """The REAL production emission path (the same post-commit trigger
    EventService uses), called directly for fixture setup."""
    await NotificationService(db).after_event_mutation(event)
    return await _event_rows(db, event.id)


async def _other_kind_rows(db, user_id) -> int:
    return (await db.execute(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user_id,
               Notification.kind != NotificationKind.ACADEMIC_EVENT)
    )).scalar_one()


async def _add_unrelated_kind_rows(db, user_id) -> int:
    """Direct projection rows of UNRELATED kinds for the recipient, created
    through the canonical emit boundary exactly as the triggers would."""
    await NotificationService(db).emit(
        user=user_id,
        kind=NotificationKind.MUST_ATTEND,
        occurrence_key="TX-EVT12",
        date=_TODAY,
        message="TX-EVT12: attend 1 lecture to reach 75%",
        subject_code="TX-EVT12",
    )
    await NotificationService(db).emit(
        user=user_id,
        kind=NotificationKind.QUIZ_APPROACHING,
        occurrence_key="2",
        date=FUT2,
        message="Quiz 2 approaching",
        quiz_cycle=2,
    )
    return await _other_kind_rows(db, user_id)


# ════════════════════════════════ T1 ════════════════════════════════════════

def test_t1_deactivate_future_event_removes_its_notification():
    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                svc = EventService(db)

                event = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                event_id = event.id
                assert await _emit(db, event) == 1, "fixture: future event emits one row"

                await svc.deactivate_event(admin, event_id)

                assert (await _event_rows(db, event_id)) == 0, \
                    "deactivation must remove the event's projection rows"
                db.expire_all()
                fresh = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == event_id)
                )).scalars().one()
                assert fresh.active is False
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T2 ════════════════════════════════════════

def test_t2_deactivate_without_notification_is_safe_and_idempotent():
    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                svc = EventService(db)

                # A PAST-dated event: the emission trigger legitimately skips
                # it, so it carries no projection rows at all.
                event = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=PAST1,
                    end_date=PAST1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                event_id = event.id
                assert await _event_rows(db, event_id) == 0

                await svc.deactivate_event(admin, event_id)   # no rows to remove
                await svc.deactivate_event(admin, event_id)   # already inactive

                assert (await _event_rows(db, event_id)) == 0
                db.expire_all()
                fresh = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == event_id)
                )).scalars().one()
                assert fresh.active is False
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T3 ════════════════════════════════════════

def test_t3_double_deactivation_is_idempotent_and_scoped():
    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                svc = EventService(db)

                e1 = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                e2 = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_TUTORIAL, start_date=FUT2,
                    end_date=FUT2, subject_id=subject.id,
                    class_type=ClassType.TUTORIAL))
                assert await _emit(db, e1) == 1
                assert await _emit(db, e2) == 1

                await svc.deactivate_event(admin, e1.id)
                await svc.deactivate_event(admin, e1.id)  # second pass: no-op

                assert (await _event_rows(db, e1.id)) == 0
                assert (await _event_rows(db, e2.id)) == 1, \
                    "the other event's projection must be untouched"
                recipient_total = (await db.execute(
                    select(func.count()).select_from(Notification)
                    .where(Notification.kind == NotificationKind.ACADEMIC_EVENT,
                           Notification.user_id == student.id)
                )).scalar_one()
                assert recipient_total == 1, "no duplicate or residue rows may appear"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T4 ════════════════════════════════════════

def test_t4_future_to_past_update_removes_notification():
    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                svc = EventService(db)

                event = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                event_id = event.id
                assert await _emit(db, event) == 1

                await svc.update_event(admin, event_id, AcademicEventUpdate(
                    start_date=PAST1, end_date=PAST1))

                assert (await _event_rows(db, event_id)) == 0, \
                    "future->past must remove the stale future-event row"
                db.expire_all()
                fresh = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == event_id)
                )).scalars().one()
                assert fresh.start_date == PAST1 and fresh.active is True
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T5 ════════════════════════════════════════

def test_t5_future_to_future_update_keeps_and_refreshes_notification():
    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                svc = EventService(db)

                event = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                event_id = event.id
                assert await _emit(db, event) == 1

                await svc.update_event(admin, event_id, AcademicEventUpdate(
                    start_date=FUT2, end_date=FUT2))

                # Row kept (exactly one) and refreshed in place by the
                # post-commit trigger with the new future date.
                assert (await _event_rows(db, event_id)) == 1
                row = (await db.execute(
                    select(Notification)
                    .where(Notification.kind == NotificationKind.ACADEMIC_EVENT,
                           Notification.occurrence_key == str(event_id))
                )).scalars().one()
                assert "Extra Lecture" in row.message
                assert FUT2.strftime("%d %b %Y") in row.message
                db.expire_all()
                fresh = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == event_id)
                )).scalars().one()
                assert fresh.start_date == FUT2 and fresh.active is True
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T6 ════════════════════════════════════════

def test_t6_past_to_past_update_creates_no_notification():
    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                svc = EventService(db)

                event = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=PAST1,
                    end_date=PAST1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                event_id = event.id
                assert await _event_rows(db, event_id) == 0, \
                    "past events never emit (trigger skip)"

                await svc.update_event(admin, event_id, AcademicEventUpdate(
                    start_date=PAST2, end_date=PAST2, note="correction"))

                assert (await _event_rows(db, event_id)) == 0, \
                    "past->past must not create a future notification"
                db.expire_all()
                fresh = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == event_id)
                )).scalars().one()
                assert fresh.start_date == PAST2 and fresh.note == "correction"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T7 ════════════════════════════════════════

def test_t7_deactivated_event_regains_no_live_notification():
    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                svc = EventService(db)

                event = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                event_id = event.id
                assert await _emit(db, event) == 1

                await svc.deactivate_event(admin, event_id)
                assert (await _event_rows(db, event_id)) == 0

                # Normal updates on the INACTIVE event (note edit, date edit)
                # must not resurrect a live projection.
                await svc.update_event(admin, event_id, AcademicEventUpdate(
                    note="still withdrawn", start_date=FUT2, end_date=FUT2))

                assert (await _event_rows(db, event_id)) == 0, \
                    "an inactive event must not regain a live notification"
                db.expire_all()
                fresh = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == event_id)
                )).scalars().one()
                assert fresh.active is False and fresh.note == "still withdrawn"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T8 ════════════════════════════════════════

def test_t8_unrelated_notification_kinds_untouched():
    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                svc = EventService(db)

                event = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                event_id = event.id
                assert await _emit(db, event) == 1
                unrelated_before = await _add_unrelated_kind_rows(db, student.id)
                assert unrelated_before == 2

                await svc.deactivate_event(admin, event_id)

                assert (await _event_rows(db, event_id)) == 0
                assert await _other_kind_rows(db, student.id) == unrelated_before, \
                    "MUST_ATTEND / QUIZ_APPROACHING rows must be untouched"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T9 ════════════════════════════════════════

def test_t9_other_events_notification_untouched():
    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                svc = EventService(db)

                e1 = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                e2 = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.SURPRISE_QUIZ, start_date=FUT2,
                    end_date=FUT2, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                assert await _emit(db, e1) == 1
                assert await _emit(db, e2) == 1

                await svc.deactivate_event(admin, e1.id)

                assert (await _event_rows(db, e1.id)) == 0
                assert (await _event_rows(db, e2.id)) == 1, \
                    "another event's projection must survive"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ═══════════════════════════════ T10 ════════════════════════════════════════

def test_t10_event_and_notification_reconcile_in_same_transaction():
    """The reconciliation is visible to the mutation's own transaction before
    any commit boundary. The sandbox wrapper structurally guarantees the
    single-commit property: EventService's `commit()` is redirected to a
    flush inside the outer transaction, so a separately-committed delete
    would survive the scenario's rollback — the post-rollback check below
    proves nothing leaked past the transaction."""

    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                svc = EventService(db)

                event = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                event_id = event.id
                assert await _emit(db, event) == 1

                await svc.deactivate_event(admin, event_id)

                # Both halves of the mutation are visible inside the SAME
                # open transaction, before any commit boundary:
                db.expire_all()
                fresh_event = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == event_id)
                )).scalars().one()
                assert fresh_event.active is False
                assert (await _event_rows(db, event_id)) == 0
                return True
            finally:
                await session.rollback()

        # Post-rollback truth on a FRESH connection: the synthetic event (and
        # therefore any projection row keyed by its id) did not persist — the
        # notification reconciliation rolled back WITH the event mutation.
        async def verify_rolled_back():
            async with AsyncSessionLocal() as db2:
                leftover = (await db2.execute(
                    select(func.count()).select_from(AcademicEvent)
                    .where(AcademicEvent.note == "still withdrawn")
                )).scalar_one()
                return leftover == 0
        assert _run(verify_rolled_back())
        return True


# ═══════════════════════════════ T11 ════════════════════════════════════════

def test_t11_evt003_guard_intact_and_rejections_mutate_no_notifications():
    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                subject_id = subject.id  # captured before any expire_all
                cycle = QuizCycle(
                    cycle_number=100000 + (uuid.uuid4().int % 900000),
                    label=f"TX-CYCLE-{tag}")
                db.add(cycle)
                await db.flush()
                schedule = QuizSchedule(
                    subject_id=subject_id, quiz_cycle_id=cycle.id,
                    elective_slot=None, date=FUT1,
                    schedule_status=ScheduleStatus.SCHEDULED)
                db.add(schedule)
                await db.flush()
                svc = EventService(db)

                notifs_before = (await db.execute(
                    select(func.count()).select_from(Notification)
                    .where(Notification.user_id == student.id)
                )).scalar_one()
                events_before = (await db.execute(
                    select(func.count()).select_from(AcademicEvent)
                    .where(AcademicEvent.subject_id == subject_id)
                )).scalar_one()
                sessions_before = (await db.execute(
                    select(func.count()).select_from(ClassSession)
                    .where(ClassSession.subject_id == subject_id)
                )).scalar_one()

                # (a) The Phase 1 create guard holds with the Phase 2 hook
                # present, and the rejected mutation changes nothing.
                with pytest.raises(EventConflict):
                    await svc.create_event(admin, AcademicEventCreate(
                        event_type=EventType.QUIZ_DAY, start_date=FUT1,
                        end_date=FUT1, subject_id=subject_id))

                # (b) Deactivation of a managed configuration is equally
                # blocked — and the fixture event + its emission survive
                # untouched (zero side effects).
                quiz_event = AcademicEvent(
                    event_type=EventType.QUIZ_DAY, start_date=FUT1,
                    end_date=FUT1, subject_id=subject_id, active=True)
                db.add(quiz_event)
                await db.flush()
                quiz_event_id = quiz_event.id
                assert await _emit(db, quiz_event) == 1
                with pytest.raises(EventConflict):
                    await svc.deactivate_event(admin, quiz_event_id)

                assert (await db.execute(
                    select(func.count()).select_from(AcademicEvent)
                    .where(AcademicEvent.subject_id == subject_id)
                )).scalar_one() == events_before + 1  # only the fixture event itself
                assert (await db.execute(
                    select(func.count()).select_from(Notification)
                    .where(Notification.user_id == student.id)
                )).scalar_one() == notifs_before + 1  # only the fixture emission
                assert (await db.execute(
                    select(func.count()).select_from(ClassSession)
                    .where(ClassSession.subject_id == subject_id)
                )).scalar_one() == sessions_before  # zero session reconciliation
                db.expire_all()
                fresh = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == quiz_event_id)
                )).scalars().one()
                assert fresh.active is True, "rejected deactivation changed nothing"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ═══════════════════════════════ T12 ════════════════════════════════════════

def test_t12_quiz_manager_lifecycle_works_and_retire_reconciles():
    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin, student = await _chain(db, tag)
                subject_id = subject.id
                cycle = QuizCycle(
                    cycle_number=100000 + (uuid.uuid4().int % 900000),
                    label=f"TX-CYCLE-{tag}")
                db.add(cycle)
                await db.flush()
                schedule = QuizSchedule(
                    subject_id=subject_id, quiz_cycle_id=cycle.id,
                    elective_slot=None, date=FUT1,
                    schedule_status=ScheduleStatus.SCHEDULED)
                db.add(schedule)
                await db.flush()
                qsvc = AdminQuizService(db)

                # (a) Quiz-manager creation still works; its own events carry
                # no ACADEMIC_EVENT projection (unchanged Phase 11C behavior)
                # and re-ensuring stays idempotent.
                assert await qsvc._ensure_quiz_event(schedule, FUT1) is True
                managed = (await db.execute(
                    select(AcademicEvent).where(
                        AcademicEvent.event_type == EventType.QUIZ_DAY,
                        AcademicEvent.subject_id == subject_id,
                        AcademicEvent.start_date == FUT1,
                    ))).scalars().one()
                assert managed.active is True
                assert await _event_rows(db, managed.id) == 0
                assert await qsvc._ensure_quiz_event(schedule, FUT1) is False

                # (b) ADOPTED-STANDALONE edge: a standalone QUIZ_DAY created
                # generically (with a live projection) whose identity a
                # schedule then backs. Retirement through the manager's
                # dedicated path must deactivate it AND reconcile its
                # projection (the EVT-001 invariant) — without routing
                # through EventService.
                standalone = await EventService(db).create_event(
                    admin, AcademicEventCreate(
                        event_type=EventType.QUIZ_DAY, start_date=FUT2,
                        end_date=FUT2, subject_id=subject_id))
                standalone_id = standalone.id  # captured before any expire_all
                assert await _emit(db, standalone) == 1
                adopt = QuizSchedule(
                    subject_id=subject_id, quiz_cycle_id=cycle.id,
                    elective_slot=None, date=FUT2,
                    schedule_status=ScheduleStatus.SCHEDULED)
                db.add(adopt)
                await db.flush()

                assert await qsvc._retire_quiz_event(subject_id, FUT2, None) is True
                await db.flush()  # the flush update_quiz_schedule's commit performs

                # (c) The schedule-backed event from (a) can still be retired
                # (no projection to reconcile — a no-op) and re-ensured. The
                # explicit flushes model the production commit that follows
                # the retirement inside update_quiz_schedule (the sandbox
                # runs with autoflush off). Runs before any expire_all so the
                # schedule instance is never touched while expired.
                assert await qsvc._retire_quiz_event(subject_id, FUT1, None) is True
                await db.flush()
                assert await qsvc._ensure_quiz_event(schedule, FUT1) is True

                db.expire_all()
                retired = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == standalone_id)
                )).scalars().one()
                assert retired.active is False
                assert (await _event_rows(db, standalone_id)) == 0, \
                    "retirement must reconcile the adopted event's projection"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True
