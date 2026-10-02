"""EVT-003 (Events Backend Remediation Phase 1) — quiz-schedule-managed
QUIZ_DAY guard enforced at the domain layer.

Audit defect: the Phase 24.9 guard lived only in AdminEventService, so the
canonical /api/v1/events POST/PATCH/DELETE endpoints (which call EventService
directly) could create, edit, re-date, type-change, or deactivate a
QUIZ_DAY event backed by a SCHEDULED QuizSchedule — silently desynchronizing
quiz-date reality (active QUIZ_DAY events are the authoritative source of
quiz dates for eligibility).

The fix places the ownership resolver + rejection in EventService:

  - EventService.is_quiz_schedule_managed: the single canonical ownership
    query (AdminEventService's read model delegates to it).
  - EventService._assert_not_quiz_schedule_managed: raises EventConflict
    (-> 409) BEFORE any flush / session sync / commit / notification effect.
  - create_event: prospective identity check.
  - update_event: OLD-state check (a managed QUIZ_DAY may not be edited at
    all) + FINAL-state check (no type-change INTO a managed configuration).
  - deactivate_event: old-state check (retirement belongs exclusively to
    AdminQuizService._retire_quiz_event, which mutates the row directly and
    never routes through EventService).

Test scenarios run the REAL production services inside a SAVEPOINT sandbox
(same pattern as test_extra_lifecycle_foundation.py / test_quiz_cycle_order.py):
EventService.commit() and the notification side-channel become flushes inside
the outer transaction, and everything is rolled back. Synthetic TX-* fixtures
isolate notification recipients (no push subscriptions -> no real pushes);
scenario 8 additionally uses the REAL seeded managed identity (BCS-501 @ its
SCHEDULED quiz date) to prove guard precedence over the duplicate guard and
zero side effects where a session span actually exists.

T1 canonical create rejected            T5 admin endpoint regression (409)
T2 canonical PATCH rejected             T6 quiz-manager path preserved
T3 canonical DELETE rejected            T7 unmanaged QUIZ_DAY unchanged
T4 prospective type change rejected     T8 no side effects on rejection
"""
import asyncio
import uuid
from datetime import date

import pytest
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal, engine
from app.models.academic import AcademicSession, Semester, StudentEnrollment, Subject
from app.models.enums import (
    ClassType,
    EnrollmentType,
    EventType,
    SubjectCategory,
    UserRole,
)
from app.models.event import AcademicEvent
from app.models.notification import Notification
from app.models.quiz import QuizCycle, QuizSchedule, ScheduleStatus
from app.models.timetable import ClassSession
from app.models.user import Section, User
from app.schemas.calendar import AcademicEventCreate, AcademicEventUpdate
from app.services.admin_event_service import AdminEventDomainError, AdminEventService
from app.services.admin_quiz_service import AdminQuizService
from app.services.event_service import EventService, EventConflict

# Within the synthetic semester span; the synthetic subject has no
# class_sessions, so the baseline span is empty and the session synchronizer
# is a no-op — creation/rejection is observed purely on event rows.
D1 = date(2026, 11, 10)  # managed identity used by T1/T2/T3/T5/T6
D2 = date(2026, 11, 11)  # re-date target (unmanaged)
D3 = date(2026, 11, 12)  # ordinary EXTRA_LECTURE date for T4
D4 = date(2026, 11, 13)  # schedule-backed date the T4 type change aims at
FREE = date(2026, 11, 14)  # unmanaged QUIZ_DAY date for T7

# The REAL seeded managed identity (verified in the dev baseline): BCS-501
# Quiz II is a SCHEDULED QuizSchedule at 2026-09-17 backed by an active
# QUIZ_DAY event.
REAL_SUBJECT = "BCS-501"
REAL_MANAGED_DATE = date(2026, 9, 17)


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
    """Synthetic academic chain + quiz-bearing theory subject + admin user.
    Returns (subject, admin)."""
    academic_session = AcademicSession(
        name=f"TX-SESS-{tag}", start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 31), is_active=True)
    db.add(academic_session)
    await db.flush()
    semester = Semester(
        name=f"TX-SEM-{tag}", session_id=academic_session.id,
        start_date=date(2026, 7, 1), end_date=date(2026, 12, 31))
    db.add(semester)
    await db.flush()
    section = Section(name=f"TX-SEC-{tag}", semester_id=semester.id, program="TEST")
    db.add(section)
    await db.flush()
    subject = Subject(
        code="TX-EVT3", name="TX EVT-003 Subject", tag=None,
        elective_slot=None, category=SubjectCategory.THEORY,
        quiz_applicable=True, attendance_applicable=True,
        semester_id=semester.id)
    db.add(subject)
    await db.flush()
    admin = User(roll_number=f"TX-ADM-{tag}", name="TX EVT-003 Admin",
                 hashed_password=None, role=UserRole.ADMIN, section_id=None)
    db.add(admin)
    await db.flush()
    return subject, admin


async def _cycle(db, tag):
    """Synthetic quiz cycle with a collision-free cycle_number (the column is
    globally UNIQUE; the seeded baseline uses 1..3)."""
    cycle = QuizCycle(
        cycle_number=100000 + (uuid.uuid4().int % 900000),
        label=f"TX-CYCLE-{tag}")
    db.add(cycle)
    await db.flush()
    return cycle


async def _schedule(db, subject_id, cycle_id, d, slot=None):
    """A SCHEDULED QuizSchedule backing the (subject, slot, date) identity —
    exactly what makes a QUIZ_DAY 'quiz-schedule managed'."""
    schedule = QuizSchedule(
        subject_id=subject_id, quiz_cycle_id=cycle_id,
        elective_slot=slot, date=d, schedule_status=ScheduleStatus.SCHEDULED)
    db.add(schedule)
    await db.flush()
    return schedule


async def _quiz_managed_event(db, subject, admin):
    """Create a managed QUIZ_DAY through the QUIZ MANAGER's own path
    (AdminQuizService._ensure_quiz_event — direct row mutation, no
    EventService). Returns (schedule, event)."""
    cycle = await _cycle(db, f"{uuid.uuid4().hex[:6]}m")
    schedule = await _schedule(db, subject.id, cycle.id, D1)
    svc = AdminQuizService(db)
    created = await svc._ensure_quiz_event(schedule, D1)
    assert created is True, "quiz-manager path must create its own event"
    event = (await db.execute(
        select(AcademicEvent).where(
            AcademicEvent.event_type == EventType.QUIZ_DAY,
            AcademicEvent.subject_id == subject.id,
            AcademicEvent.start_date == D1,
        ))).scalars().one()
    return schedule, event


async def _fresh(db, event_id):
    """The committed-to-transaction state of the event row: discards un-
    flushed in-memory mutations (what a real request rollback would discard)
    and re-reads from the database."""
    db.expire_all()
    return (await db.execute(
        select(AcademicEvent).where(AcademicEvent.id == event_id)
    )).scalars().one()


# ════════════════════════════════ T1 ════════════════════════════════════════

def _sandbox(session):
    """Sandbox tuning: autoflush OFF so a rejected mutation's un-flushed
    in-memory state can never leak into intermediate reads (production rolls
    the request session back wholesale; here expire_all+re-read models that
    by returning the last explicitly flushed state). All services under test
    flush explicitly at their persistence points."""
    session.autoflush = False


def test_t1_canonical_create_of_managed_quiz_day_rejected():
    """POST /api/v1/events equivalent: EventService.create_event with a
    QUIZ_DAY identity backed by a SCHEDULED QuizSchedule -> EventConflict
    (-> 409), and no event / session row materializes."""

    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin = await _chain(db, tag)
                cycle = await _cycle(db, tag)
                await _schedule(db, subject.id, cycle.id, D1)
                svc = EventService(db)

                events_for_subject = (
                    await db.execute(
                        select(func.count()).select_from(AcademicEvent)
                        .where(AcademicEvent.subject_id == subject.id))
                ).scalar_one()
                sessions_for_identity = (
                    await db.execute(
                        select(func.count()).select_from(ClassSession)
                        .where(ClassSession.subject_id == subject.id,
                               ClassSession.date == D1))
                ).scalar_one()

                raised = None
                try:
                    await svc.create_event(admin, AcademicEventCreate(
                        event_type=EventType.QUIZ_DAY, start_date=D1,
                        end_date=D1, subject_id=subject.id))
                except EventConflict as exc:
                    raised = exc

                assert raised is not None, "managed QUIZ_DAY creation must be rejected"
                assert "Quiz Schedule Manager" in str(raised)
                assert (
                    await db.execute(
                        select(func.count()).select_from(AcademicEvent)
                        .where(AcademicEvent.subject_id == subject.id))
                ).scalar_one() == events_for_subject
                assert (
                    await db.execute(
                        select(func.count()).select_from(ClassSession)
                        .where(ClassSession.subject_id == subject.id,
                               ClassSession.date == D1))
                ).scalar_one() == sessions_for_identity == 0
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T2 ════════════════════════════════════════

def test_t2_canonical_patch_of_managed_quiz_day_rejected():
    """PATCH /api/v1/events/{id} equivalent: an existing quiz-manager-owned
    QUIZ_DAY may not be edited through EventService at all — neither a
    harmless note edit nor a re-date. State stays unchanged."""

    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin = await _chain(db, tag)
                _, event = await _quiz_managed_event(db, subject, admin)
                svc = EventService(db)

                # Both rejections happen before any expire_all: the sandbox
                # never reuses expired ORM instances for service calls.
                with pytest.raises(EventConflict) as excinfo:
                    await svc.update_event(admin, event.id, AcademicEventUpdate(
                        note="tampered via generic path"))
                assert "Quiz Schedule Manager" in str(excinfo.value)

                with pytest.raises(EventConflict):
                    await svc.update_event(admin, event.id, AcademicEventUpdate(
                        start_date=D2, end_date=D2))

                fresh = await _fresh(db, event.id)
                assert fresh.note is None, "note edit must not persist"
                assert fresh.active is True
                assert fresh.start_date == D1, "re-date must not persist"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T3 ════════════════════════════════════════

def test_t3_canonical_delete_of_managed_quiz_day_rejected():
    """DELETE /api/v1/events/{id} equivalent: deactivating a quiz-manager-
    owned QUIZ_DAY through EventService is rejected; the event stays active."""

    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin = await _chain(db, tag)
                _, event = await _quiz_managed_event(db, subject, admin)
                svc = EventService(db)

                with pytest.raises(EventConflict) as excinfo:
                    await svc.deactivate_event(admin, event.id)
                assert "Quiz Schedule Manager" in str(excinfo.value)

                fresh = await _fresh(db, event.id)
                assert fresh.active is True, "deactivation must not persist"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T4 ════════════════════════════════════════

def test_t4_type_change_into_managed_quiz_day_rejected():
    """The prospective bypass: an ordinary event PATCHed (event_type ->
    QUIZ_DAY, re-dated) onto a schedule-backed identity is rejected on the
    FINAL state — the gap the former endpoint-layer guard never covered."""

    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin = await _chain(db, tag)
                cycle = await _cycle(db, tag)
                # D4 is schedule-backed; D3 is an ordinary unmanaged date.
                await _schedule(db, subject.id, cycle.id, D4)
                svc = EventService(db)

                event = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=D3,
                    end_date=D3, subject_id=subject.id,
                    class_type=ClassType.LECTURE))

                with pytest.raises(EventConflict) as excinfo:
                    await svc.update_event(admin, event.id, AcademicEventUpdate(
                        event_type=EventType.QUIZ_DAY, class_type=None,
                        start_date=D4, end_date=D4))
                assert "Quiz Schedule Manager" in str(excinfo.value)

                fresh = await _fresh(db, event.id)
                assert fresh.event_type == EventType.EXTRA_LECTURE
                assert fresh.start_date == D3
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T5 ════════════════════════════════════════

def test_t5_admin_service_still_rejects_prohibited_mutations():
    """Admin portal regression (service level — the route is a thin wrapper):
    AdminEventService create/update/deactivate surface the domain guard as
    AdminEventDomainError with the documented 409 status. (Full HTTP-level
    coverage lives in the out-of-band verifiers, e.g. verify_phase_24_10.py
    check 14 and verify_phase_6_5.py's security matrix.)"""

    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin = await _chain(db, tag)
                _, event = await _quiz_managed_event(db, subject, admin)
                svc = AdminEventService(db)

                # create: managed identity
                with pytest.raises(AdminEventDomainError) as exc_create:
                    await svc.create_event(admin, AcademicEventCreate(
                        event_type=EventType.QUIZ_DAY, start_date=D1,
                        end_date=D1, subject_id=subject.id))
                assert exc_create.value.http_status == 409
                assert "Quiz Schedule Manager" in exc_create.value.detail

                # update: managed event
                with pytest.raises(AdminEventDomainError) as exc_update:
                    await svc.update_event(admin, event.id, AcademicEventUpdate(
                        note="tampered via admin portal"))
                assert exc_update.value.http_status == 409

                # deactivate: managed event
                with pytest.raises(AdminEventDomainError) as exc_delete:
                    await svc.deactivate_event(admin, event.id)
                assert exc_delete.value.http_status == 409
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T6 ════════════════════════════════════════

def test_t6_quiz_manager_path_preserved():
    """The Quiz Schedule Manager must keep full ownership: create, idempotent
    re-ensure, and retirement all still work through AdminQuizService's
    dedicated path (which never routes through EventService)."""

    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin = await _chain(db, tag)
                cycle = await _cycle(db, tag)
                schedule = await _schedule(db, subject.id, cycle.id, D1)
                subject_id = subject.id  # captured before any expire_all
                svc = AdminQuizService(db)

                assert await svc._ensure_quiz_event(schedule, D1) is True
                event = (await db.execute(
                    select(AcademicEvent).where(
                        AcademicEvent.event_type == EventType.QUIZ_DAY,
                        AcademicEvent.subject_id == subject_id,
                        AcademicEvent.start_date == D1,
                    ))).scalars().one()
                event_id = event.id
                assert event.active is True

                # Idempotent: the manager never duplicates its own event.
                assert await svc._ensure_quiz_event(schedule, D1) is False

                # Retirement through the manager's dedicated path works...
                assert await svc._retire_quiz_event(subject_id, D1, None) is True
                # (production commits after the mutation — the flush the
                # commit would perform is explicit here because the sandbox
                # runs with autoflush off)
                await db.flush()
                # ...and re-ensuring re-creates the quiz reality (a NEW active
                # event; the retired row is preserved history).
                assert await svc._ensure_quiz_event(schedule, D1) is True

                db.expire_all()
                retired = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == event_id)
                )).scalars().one()
                assert retired.active is False
                active_now = (await db.execute(
                    select(func.count()).select_from(AcademicEvent)
                    .where(AcademicEvent.event_type == EventType.QUIZ_DAY,
                           AcademicEvent.subject_id == subject_id,
                           AcademicEvent.start_date == D1,
                           AcademicEvent.active.is_(True))
                )).scalar_one()
                assert active_now == 1
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T7 ════════════════════════════════════════

def test_t7_unmanaged_quiz_day_creation_unchanged():
    """A QUIZ_DAY at an identity with no backing SCHEDULED QuizSchedule is a
    legitimate standalone event and must keep working exactly as before."""

    async def scenario():
        tag = uuid.uuid4().hex[:8]
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                subject, admin = await _chain(db, tag)
                svc = EventService(db)

                event = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.QUIZ_DAY, start_date=FREE,
                    end_date=FREE, subject_id=subject.id))
                event_id = event.id  # captured before any expire_all
                assert event.active is True
                assert event.event_type == EventType.QUIZ_DAY
                assert event.start_date == FREE

                # And it remains editable (it is NOT quiz-manager-owned).
                await svc.update_event(admin, event_id, AcademicEventUpdate(
                    note="standalone quiz day"))
                db.expire_all()
                fresh = (await db.execute(
                    select(AcademicEvent).where(AcademicEvent.id == event_id)
                )).scalars().one()
                assert fresh.note == "standalone quiz day"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T8 ════════════════════════════════════════

def test_t8_rejection_has_no_side_effects_on_real_managed_identity():
    """Against the REAL seeded managed identity (BCS-501 @ 2026-09-17, whose
    SCHEDULED QuizSchedule and active QUIZ_DAY event both exist):

    - the DOMAIN guard fires (message says Quiz Schedule Manager) — proving
      precedence over the duplicate guard that also covers this identity;
    - zero side effects: no phantom event, no session reconciliation, no
      notification rows."""
    tag = uuid.uuid4().hex[:8]

    async def scenario():
        async with AsyncSessionLocal() as session:
            await session.begin()
            _sandbox(session)
            try:
                db = _RollbackSession(session)
                _, admin = await _chain(db, tag)
                subject_id = (await db.execute(
                    select(Subject.id).where(Subject.code == REAL_SUBJECT)
                )).scalar_one()

                svc = EventService(db)
                events_before = (
                    await db.execute(
                        select(func.count()).select_from(AcademicEvent)
                        .where(AcademicEvent.subject_id == subject_id))
                ).scalar_one()
                sessions_before = (
                    await db.execute(
                        select(func.count()).select_from(ClassSession)
                        .where(ClassSession.subject_id == subject_id,
                               ClassSession.date == REAL_MANAGED_DATE))
                ).scalar_one()
                notifications_before = (
                    await db.execute(select(func.count()).select_from(Notification))
                ).scalar_one()

                with pytest.raises(EventConflict) as excinfo:
                    await svc.create_event(admin, AcademicEventCreate(
                        event_type=EventType.QUIZ_DAY,
                        start_date=REAL_MANAGED_DATE,
                        end_date=REAL_MANAGED_DATE,
                        subject_id=subject_id))
                assert "Quiz Schedule Manager" in str(excinfo.value)

                db.expire_all()
                assert (
                    await db.execute(
                        select(func.count()).select_from(AcademicEvent)
                        .where(AcademicEvent.subject_id == subject_id))
                ).scalar_one() == events_before, "no phantom event may persist"
                assert (
                    await db.execute(
                        select(func.count()).select_from(ClassSession)
                        .where(ClassSession.subject_id == subject_id,
                               ClassSession.date == REAL_MANAGED_DATE))
                ).scalar_one() == sessions_before, "no session reconciliation"
                assert (
                    await db.execute(select(func.count()).select_from(Notification))
                ).scalar_one() == notifications_before, "no notification mutation"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True
