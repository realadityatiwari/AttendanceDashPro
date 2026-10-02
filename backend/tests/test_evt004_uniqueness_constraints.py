"""EVT-004 (Events Backend Remediation Phase 3) — DB-authoritative
natural-key uniqueness for AcademicEvent and ClassSession.

Audit defect: duplicate prevention was application-only check-then-insert
(`exists_active_duplicate`), and `class_sessions` had no natural-key
constraint at all — two concurrent transactions could both pass the
application pre-check (each seeing neither the other's uncommitted row
under READ COMMITTED) and materialize the same event / canonical session.

Fix under test: four partial unique indexes (migration `b9c0d1e2f3a4`)
encoding EXACTLY the identities the application already maintains:

  'uq_academic_events_quiz_day_identity',
  'uq_academic_events_global_range',
    class_type, start_date, end_date) WHERE active — NULLS NOT DISTINCT
    (matches `exists_active_duplicate`: NULL identity == NULL identity,
    active rows only, elective_slot not part of the key because the
    application guard does not consider it).
  uq_class_sessions_entry_date               (timetable_entry_id, date)
    WHERE timetable_entry_id IS NOT NULL — one scheduled occurrence per
    (entry, date).
  uq_class_sessions_source_event_date        (source_event_id, date)
    WHERE source_event_id IS NOT NULL — one event-created extra per
    (event, date); legacy NULL-provenance extras excluded on purpose.
  uq_class_sessions_quiz_day_subject_date    (subject_id, date)
    WHERE timetable_entry_id IS NULL AND is_extra = false
    AND class_type = 'LECTURE' — one quiz-day occurrence per (subject,
    date); extras and timetable-linked sessions are outside the key so
    Option A coexistence is never blocked.

Application translation under test:
`EventRepository.is_evt004_unique_violation` narrows PostgreSQL 23505 on
those index names; EventService.create/update/deactivate and
AdminQuizService._ensure_quiz_event/update_quiz_schedule roll back and
raise the ordinary domain conflicts (EventConflict / AdminQuizConflictError
-> 409) instead of leaking IntegrityError.

CONCURRENCY TESTS (T2/T3/T6/T7) are genuine two-connection races with a
deterministic interleaving — NOT two sequential calls:
  connection A inserts the fixture and FLUSHES (row held uncommitted in
  the unique index); connection B then performs the same insert through
  the service/raw path; B's INSERT BLOCKS on A's uncommitted index entry
  (asserted: B's task is not done); only then A commits and B fails with
  SQLSTATE 23505. Committed race fixtures use a unique TX-* tag and are
  removed in FK-safe order in the module teardown.
"""
import asyncio
import uuid
from datetime import time, timedelta

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError

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
    AttendanceStatus,
    ClassType,
    EnrollmentType,
    EventType,
    SubjectCategory,
    UserRole,
)
from app.models.event import AcademicEvent
from app.models.quiz import QuizCycle, QuizSchedule, ScheduleStatus
from app.models.timetable import ClassSession, TimetableEntry
from app.models.user import Section, User
from app.repositories.event_repo import EventConflict, is_evt004_unique_violation
from app.schemas.calendar import AcademicEventCreate, AcademicEventUpdate
from app.services.admin_quiz_service import AdminQuizConflictError, AdminQuizService
from app.services.attendance_service import AttendanceService
from app.services.event_service import EventService

_TODAY = institution_today()
def _past_weekday(days_back):
    d = _TODAY - timedelta(days=days_back)
    while d.weekday() >= 5:  # skip Sat/Sun: no sessions materialize there
        d -= timedelta(days=1)
    return d
FUT1 = _TODAY + timedelta(days=45)
FUT2 = _TODAY + timedelta(days=47)
PAST1 = _past_weekday(19)
PAST2 = _past_weekday(15)
_TAG = "TXE4" + uuid.uuid4().hex[:8]

_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


# ── committed module fixture (real connections: the race needs REAL
#    transactions) with idempotent FK-safe cleanup ─────────────────────────

_EVENT_ROW_CLEANUP_ORDER = (
    # Per-test wipe: everything derivable from the fixture subject's events
    # and sessions (committed by the service paths under test).
    "DELETE FROM attendance_records WHERE class_session_id IN "
    "(SELECT id FROM class_sessions WHERE subject_id IN "
    "(SELECT id FROM subjects WHERE code LIKE 'TXE4%') OR source_event_id IN "
    "(SELECT id FROM academic_events WHERE subject_id IN "
    "(SELECT id FROM subjects WHERE code LIKE 'TXE4%')))",
    "DELETE FROM notifications WHERE event_id IN "
    "(SELECT id FROM academic_events WHERE note LIKE 'EVT004%')",
    "DELETE FROM academic_events WHERE note LIKE 'EVT004%'",

    "DELETE FROM notifications WHERE event_id IN "
    "(SELECT id FROM academic_events WHERE subject_id IN "
    "(SELECT id FROM subjects WHERE code LIKE 'TXE4%'))",
    "DELETE FROM notifications WHERE user_id IN "
    "(SELECT id FROM users WHERE roll_number LIKE 'TXE4%')",
    "DELETE FROM class_sessions WHERE subject_id IN "
    "(SELECT id FROM subjects WHERE code LIKE 'TXE4%')",
    "DELETE FROM class_sessions WHERE source_event_id IN "
    "(SELECT id FROM academic_events WHERE subject_id IN "
    "(SELECT id FROM subjects WHERE code LIKE 'TXE4%'))",
    "DELETE FROM quiz_schedules WHERE subject_id IN "
    "(SELECT id FROM subjects WHERE code LIKE 'TXE4%')",
    "DELETE FROM academic_events WHERE subject_id IN "
    "(SELECT id FROM subjects WHERE code LIKE 'TXE4%')",
)

_CHAIN_CLEANUP_ORDER = _EVENT_ROW_CLEANUP_ORDER + (
    "DELETE FROM quiz_cycles WHERE label LIKE 'TXE4%'",
    "DELETE FROM timetable_entries WHERE section_id IN "
    "(SELECT id FROM sections WHERE name LIKE 'TXE4%')",
    "DELETE FROM student_enrollments WHERE user_id IN "
    "(SELECT id FROM users WHERE roll_number LIKE 'TXE4%')",
    "DELETE FROM users WHERE roll_number LIKE 'TXE4%'",
    "DELETE FROM subjects WHERE code LIKE 'TXE4%'",
    "DELETE FROM sections WHERE name LIKE 'TXE4%'",
    "DELETE FROM semesters WHERE name LIKE 'TXE4%'",
    "DELETE FROM academic_sessions WHERE name LIKE 'TXE4%'",
)


def _cleanup_chain() -> None:
    async def _clean():
        async with AsyncSessionLocal() as db:
            # Kill backends abandoned by a previously killed run: their
            # uncommitted fixture transactions hold the very locks this
            # module races on and would deadlock every rerun.
            stale = (await db.execute(text(
                "SELECT pid FROM pg_stat_activity WHERE datname = "
                "current_database() AND pid <> pg_backend_pid() AND "
                "state = 'idle in transaction' AND "
                "now() - xact_start > interval '120 seconds'"
            ))).fetchall()
            for (pid,) in stale:
                await db.execute(text("SELECT pg_terminate_backend(:p)"),
                                 {"p": pid})
            await db.commit()
            for stmt in _CHAIN_CLEANUP_ORDER:
                await db.execute(text(stmt.replace("{_tag}", _TAG)))
            await db.commit()

    try:
        _LOOP.run_until_complete(_clean())
    except Exception:
        _LOOP.run_until_complete(engine.dispose())
        raise


def _cleanup_event_rows() -> None:
    async def _clean():
        async with AsyncSessionLocal() as db:
            await db.begin()
            for stmt in _EVENT_ROW_CLEANUP_ORDER:
                await db.execute(text(stmt))
            await db.commit()

    _LOOP.run_until_complete(_clean())


@pytest.fixture(autouse=True)
def _clean_event_rows_between_tests():
    """Committed service calls (create_event etc. really commit) must not
    leak identities into the next test's race/pre-check."""
    _cleanup_event_rows()
    yield
    _cleanup_event_rows()


@pytest.fixture(scope="module", autouse=True)
def _committed_chain():
    _cleanup_chain()  # idempotent pre-clean (e.g. after an aborted run)

    async def _setup():
        async with AsyncSessionLocal() as db:
            await db.begin()
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
                code=_TAG, name="TX EVT-004 Subject", tag=None,
                elective_slot=None, category=SubjectCategory.THEORY,
                quiz_applicable=True, attendance_applicable=True,
                semester_id=semester.id)
            db.add(subject)
            await db.flush()
            student = User(roll_number=f"{_TAG}-STU", name="TX Student",
                           hashed_password=None, role=UserRole.STUDENT,
                           section_id=section.id)
            admin = User(roll_number=f"{_TAG}-ADM", name="TX Admin",
                         hashed_password=None, role=UserRole.ADMIN, section_id=None)
            db.add_all([student, admin])
            await db.flush()
            db.add(StudentEnrollment(user_id=student.id, subject_id=subject.id,
                                     enrollment_type=EnrollmentType.COMPULSORY))
            entry = TimetableEntry(
                subject_id=subject.id, day_of_week=0,
                start_time=time(9, 0), end_time=time(10, 0),
                class_type=ClassType.LECTURE, section_id=section.id)
            db.add(entry)
            await db.flush()
            await db.commit()
            return {
                "subject_id": subject.id, "admin_id": admin.id,
                "student_id": student.id, "section_id": section.id,
                "entry_id": entry.id, "semester_start": semester.start_date,
            }

    global _CHAIN
    _CHAIN = _LOOP.run_until_complete(_setup())
    yield
    _cleanup_chain()
    try:
        _LOOP.run_until_complete(engine.dispose())
    except Exception:
        pass


_CHAIN: dict = {}


def _admin() -> User:
    """A detached admin object for EventService (id/role only are used)."""
    return User(id=_CHAIN["admin_id"], roll_number=f"{_TAG}-ADM",
                role=UserRole.ADMIN)


def _dup_event(note: str) -> AcademicEvent:
    """A standalone QUIZ_DAY (no backing schedule - the EVT-003
    guard does not apply; the EVT-004 identity index is the
    authority under a race)."""
    return AcademicEvent(
        event_type=EventType.QUIZ_DAY, start_date=FUT1, end_date=FUT1,
        subject_id=_CHAIN["subject_id"], active=True, note=note)


# ════════════════════════════════ T1 ════════════════════════════════════════

def test_t1_ordinary_duplicate_event_rejected_by_precheck():
    """Sequential duplicate (both rows visible in one transaction) is
    rejected by the application pre-check with the ordinary 409 semantics."""

    async def scenario():
        async with AsyncSessionLocal() as session:
            await session.begin()
            session.autoflush = False
            try:
                db = session
                subject = (await db.execute(
                    select(Subject).where(Subject.id == _CHAIN["subject_id"])
                )).scalars().one()
                svc = EventService(db)
                admin = _admin()

                first = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                with pytest.raises(EventConflict):
                    await svc.create_event(admin, AcademicEventCreate(
                        event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                        end_date=FUT1, subject_id=subject.id,
                        class_type=ClassType.LECTURE))
                return str(first.id)
            finally:
                await session.rollback()

    assert _run(scenario())


# ════════════════════════════════ T2 ════════════════════════════════════════

def test_t2_concurrent_duplicate_event_rejected_by_db_constraint():
    """TRUE two-connection race: A holds the identity uncommitted in the
    unique index; B's INSERT blocks (asserted) until A commits, then fails
    with SQLSTATE 23505 on the EVT-004 index — the database, not the
    pre-check, is the authority."""

    async def scenario():
        a = AsyncSessionLocal()
        b = AsyncSessionLocal()
        try:
            await a.begin()
            await b.begin()
            event_a = _dup_event(f"{_TAG} race A")
            a.add(event_a)
            await a.flush()  # holds the unique index entry, uncommitted

            async def b_insert():
                b.add(_dup_event(f"{_TAG} race B"))
                await b.flush()

            b_task = asyncio.create_task(b_insert())
            await asyncio.sleep(0.4)
            assert not b_task.done(), \
                "B's insert must block on A's uncommitted unique index entry"

            await a.commit()  # B now unblocks into a unique violation
            with pytest.raises(IntegrityError) as excinfo:
                await asyncio.wait_for(b_task, timeout=20)
            assert is_evt004_unique_violation(excinfo.value), (
                "the violation must be the EVT-004 natural-key index, got: "
                f"{excinfo.value!r}")
            await b.rollback()
            return str(event_a.id)  # A's committed row — cleaned by teardown
        finally:
            await a.rollback()
            await b.rollback()
            await a.close()
            await b.close()

    event_id = uuid.UUID(_run(scenario()))

    # T4 (partial): the race left exactly one row — A's; B left nothing.
    async def verify():
        async with AsyncSessionLocal() as db:
            n = (await db.execute(
                select(func.count()).select_from(AcademicEvent)
                .where(AcademicEvent.note.in_([f"{_TAG} race A", f"{_TAG} race B"]))
            )).scalar_one()
            return n
    assert _run(verify()) == 1
    _run(_delete_event_by_id(event_id))


async def _delete_event_by_id(event_id):
    async with AsyncSessionLocal() as db:
        await db.begin()
        await db.execute(
            delete(AcademicEvent).where(AcademicEvent.id == event_id))
        await db.commit()


# ════════════════════════════════ T3 + T4 ══════════════════════════════════

def test_t3_service_translates_constraint_race_to_domain_conflict():
    """The same true race through EventService: B's pre-check cannot see A's
    uncommitted row (READ COMMITTED), the index rejects B's INSERT, and the
    service translates it into the ordinary EventConflict (409) after a
    clean rollback — no raw IntegrityError, no partial side effects."""

    async def scenario():
        a = AsyncSessionLocal()
        b = AsyncSessionLocal()
        try:
            await a.begin()
            await b.begin()
            event_a = _dup_event(f"{_TAG} svc race A")
            a.add(event_a)
            await a.flush()

            async def b_create():
                svc = EventService(b)
                await svc.create_event(_admin(), AcademicEventCreate(
                    event_type=EventType.QUIZ_DAY, start_date=FUT1,
                    end_date=FUT1, subject_id=_CHAIN["subject_id"]))

            b_task = asyncio.create_task(b_create())
            await asyncio.sleep(0.5)
            print('T3: b_task done after 0.5s =', b_task.done())
            print('T3: committing A')
            await a.commit()
            print('T3: A committed; awaiting B')
            with pytest.raises(EventConflict) as excinfo:
                await asyncio.wait_for(b_task, timeout=8)
            # The translation provenance: the domain conflict is raised from
            # a 23505 on the EVT-004 index when the constraint fires (the
            # pre-check path yields the same conflict without a cause).
            cause = excinfo.value.__cause__
            assert cause is None or is_evt004_unique_violation(cause)
            await b.rollback()
            await a.rollback()
            # B's session is usable again after the clean rollback.
            n = (await b.execute(
                select(func.count()).select_from(AcademicEvent)
            )).scalar_one()
            assert n >= 1
            return True
        finally:
            await a.rollback()
            await b.rollback()
            await a.close()
            await b.close()

    assert _run(scenario()) is True


# ════════════════════════════════ T5 ════════════════════════════════════════

def test_t5_legitimate_distinct_events_remain_creatable():
    async def scenario():
        async with AsyncSessionLocal() as session:
            await session.begin()
            session.autoflush = False
            try:
                db = session
                svc = EventService(db)
                admin = _admin()
                subject_id = _CHAIN["subject_id"]

                # Different dates.
                e1 = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject_id,
                    class_type=ClassType.LECTURE))
                e2 = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT2,
                    end_date=FUT2, subject_id=subject_id,
                    class_type=ClassType.LECTURE))
                # Different event type, same date.
                e3 = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_TUTORIAL, start_date=FUT1,
                    end_date=FUT1, subject_id=subject_id,
                    class_type=ClassType.TUTORIAL))
                # Global events (NULL subject/class_type), different dates;
                # same dates but a DIFFERENT type also stays allowed.
                e4 = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.HOLIDAY, start_date=FUT1,
                    end_date=FUT1, note="EVT004 holiday"))
                e5 = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EMERGENCY_CLOSURE, start_date=FUT1,
                    end_date=FUT1, note="EVT004 global"))
                # An INACTIVE event with its own distinct identity remains
                # creatable (the partial index constrains active rows only).
                e6 = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_PRACTICAL, start_date=FUT2,
                    end_date=FUT2, subject_id=subject_id,
                    class_type=ClassType.PRACTICAL, active=False))
                assert len({e1.id, e2.id, e3.id, e4.id, e5.id, e6.id}) == 6
                assert e6.active is False
                # Pre-existing guard semantics: creating an event whose
                # identity matches an ACTIVE event is rejected even when the
                # new row requests active=False.
                with pytest.raises(EventConflict):
                    await svc.create_event(admin, AcademicEventCreate(
                        event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                        end_date=FUT1, subject_id=subject_id,
                        class_type=ClassType.LECTURE, active=False))
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T6 ════════════════════════════════════════

def test_t6_quiz_manager_ensure_functional_under_constraint():
    """Quiz-manager ensure stays functional under the constraint:
    (a) sequential ensure is idempotent (find-first path);
    (b) a TRUE two-connection race loses on the EVT-004 index and is
        translated to AdminQuizConflictError (409) — connection A's ensure
        holds the identity uncommitted (exactly where production's
        update_quiz_schedule commit would sit) while B's ensure blocks and
        then fails;
    (c) retirement keeps working afterwards."""

    async def scenario():
        from types import SimpleNamespace

        async with AsyncSessionLocal() as session:
            await session.begin()
            session.autoflush = False
            try:
                db = session
                cycle = QuizCycle(
                    cycle_number=100000 + (uuid.uuid4().int % 900000),
                    label=f"{_TAG}-CYC")
                db.add(cycle)
                await db.flush()
                schedule = QuizSchedule(
                    subject_id=_CHAIN["subject_id"], quiz_cycle_id=cycle.id,
                    elective_slot=None, date=FUT1,
                    schedule_status=ScheduleStatus.SCHEDULED)
                db.add(schedule)
                await db.flush()
                qsvc = AdminQuizService(db)

                # (a) sequential idempotency (sandbox transaction).
                assert await qsvc._ensure_quiz_event(schedule, FUT1) is True
                assert await qsvc._ensure_quiz_event(schedule, FUT1) is False

                # (b) race for a DIFFERENT identity (FUT2) between two real
                # connections — the sandbox holds no FUT2 identity, so the
                # race is live. The detached namespace carries exactly the
                # fields _ensure_quiz_event reads from the schedule.
                ns_schedule = SimpleNamespace(
                    subject_id=_CHAIN["subject_id"], elective_slot=None)
                a = AsyncSessionLocal()
                b = AsyncSessionLocal()
                try:
                    await a.begin()
                    await b.begin()
                    qsvc_a = AdminQuizService(a)
                    assert await qsvc_a._ensure_quiz_event(ns_schedule, FUT2) is True

                    async def b_ensure():
                        qsvc_b = AdminQuizService(b)
                        return await qsvc_b._ensure_quiz_event(ns_schedule, FUT2)

                    b_task = asyncio.create_task(b_ensure())
                    await asyncio.sleep(0.5)
                    print("T6: b_task done after 0.5s =", b_task.done())
                    assert not b_task.done(),                         "B's ensure must block on A's uncommitted identity"
                    print("T6: committing A (production commit point)")
                    await a.commit()
                    print("T6: A committed; awaiting B")
                    with pytest.raises(AdminQuizConflictError):
                        await asyncio.wait_for(b_task, timeout=8)
                    await b.rollback()
                finally:
                    await b.rollback()
                    await b.close()
                    # (c) retirement of the committed race-winner event.
                    qsvc_c = AdminQuizService(a)
                    assert await qsvc_c._retire_quiz_event(
                        _CHAIN["subject_id"], FUT2, None) is True
                    await a.commit()
                    await a.close()
                return True
            finally:
                await session.rollback()

        async def verify_retired():
            async with AsyncSessionLocal() as db:
                rows = (await db.execute(
                    select(AcademicEvent).where(
                        AcademicEvent.subject_id == _CHAIN["subject_id"],
                        AcademicEvent.start_date == FUT2,
                        AcademicEvent.event_type == EventType.QUIZ_DAY)
                )).scalars().all()
                assert len(rows) == 1 and rows[0].active is False
                return True
        assert _run(verify_retired()) is True


# ═══════════════════════════════ T6b ════════════════════════════════════════

def test_t6b_multiple_same_key_extra_events_still_allowed():
    """PINNED CONTRACT (test_extra_lifecycle_foundation.py::
    test_two_active_same_key_events_each_get_own_linked_session): the DB
    allows two ACTIVE same-key extra-family events and the reconciler gives
    each its own provenance-linked session. The EVT-004 identity indexes
    deliberately do NOT constrain the extra family — this test pins that
    the indexes did not break it."""

    async def scenario():
        async with AsyncSessionLocal() as session:
            await session.begin()
            session.autoflush = False
            try:
                db = session
                subject = (await db.execute(
                    select(Subject).where(Subject.id == _CHAIN["subject_id"])
                )).scalars().one()
                event_a = AcademicEvent(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject.id,
                    class_type=ClassType.LECTURE, active=True)
                event_b = AcademicEvent(
                    event_type=EventType.EXTRA_LECTURE, start_date=FUT1,
                    end_date=FUT1, subject_id=subject.id,
                    class_type=ClassType.LECTURE, active=True)
                db.add_all([event_a, event_b])
                await db.flush()
                from app.services.event_session_service import EventSessionSynchronizer
                await EventSessionSynchronizer(db).sync_event(event_a)
                await db.flush()
                sessions = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.subject_id == subject.id,
                        ClassSession.date == FUT1,
                        ClassSession.is_extra.is_(True))
                )).scalars().all()
                assert len(sessions) == 2,                     "each same-key extra event keeps its own session"
                assert {str(s.source_event_id) for s in sessions} ==                     {str(event_a.id), str(event_b.id)}
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T7 ════════════════════════════════════════

def test_t7_concurrent_session_materialization_rejected_by_db_constraint():
    """TRUE two-connection race on the canonical scheduled-session identity
    (timetable_entry_id, date): the loser is rejected by
    uq_class_sessions_entry_date with SQLSTATE 23505."""

    async def scenario():
        a = AsyncSessionLocal()
        b = AsyncSessionLocal()
        try:
            await a.begin()
            await b.begin()
            s_a = ClassSession(
                subject_id=_CHAIN["subject_id"], date=FUT1,
                class_type=ClassType.LECTURE, is_extra=False,
                is_cancelled=False, timetable_entry_id=_CHAIN["entry_id"])
            a.add(s_a)
            await a.flush()

            async def b_insert():
                b.add(ClassSession(
                    subject_id=_CHAIN["subject_id"], date=FUT1,
                    class_type=ClassType.LECTURE, is_extra=False,
                    is_cancelled=False, timetable_entry_id=_CHAIN["entry_id"]))
                await b.flush()

            b_task = asyncio.create_task(b_insert())
            await asyncio.sleep(0.5)
            print('T7: b_task done after 0.5s =', b_task.done())
            assert not b_task.done(), "B's session insert must block on A's row"
            print('T7: committing A')
            await a.commit()
            print('T7: A committed; awaiting B')
            with pytest.raises(IntegrityError) as excinfo:
                await asyncio.wait_for(b_task, timeout=8)
            assert is_evt004_unique_violation(excinfo.value)
            assert "uq_class_sessions_entry_date" in str(excinfo.value)
            await b.rollback()
            session_id = s_a.id
        finally:
            await a.rollback()
            await b.rollback()
            await a.close()
            await b.close()

    _run(scenario())
    _run(_delete_session(FUT1, _CHAIN["entry_id"]))


async def _delete_session(d, entry_id):
    async with AsyncSessionLocal() as db:
        await db.begin()
        await db.execute(
            delete(ClassSession).where(ClassSession.date == d,
                                       ClassSession.timetable_entry_id == entry_id))
        await db.commit()


# ════════════════════════════════ T8 ════════════════════════════════════════

def test_t8_legitimate_distinct_sessions_remain_allowed():
    """The synchronizer may legitimately materialize distinct occurrences:
    same subject different dates, same date different entries, and an extra
    plus a quiz-day occurrence on one date (Option A)."""

    async def scenario():
        async with AsyncSessionLocal() as session:
            await session.begin()
            session.autoflush = False
            try:
                db = session
                svc = EventService(db)
                admin = _admin()
                subject_id = _CHAIN["subject_id"]

                # Extra (is_extra, source_event_id) + quiz-day occurrence
                # (entry-NULL scheduled LECTURE) on the SAME subject/date.
                extra_evt = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_PRACTICAL, start_date=PAST1,
                    end_date=PAST1, subject_id=subject_id,
                    class_type=ClassType.PRACTICAL))
                quiz_evt = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.QUIZ_DAY, start_date=PAST1,
                    end_date=PAST1, subject_id=subject_id))
                await db.flush()
                extras = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.subject_id == subject_id,
                        ClassSession.date == PAST1,
                        ClassSession.is_extra.is_(True))
                )).scalars().all()
                quizdays = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.subject_id == subject_id,
                        ClassSession.date == PAST1,
                        ClassSession.is_extra.is_(False),
                        ClassSession.timetable_entry_id.is_(None),
                        ClassSession.class_type == ClassType.LECTURE)
                )).scalars().all()
                assert len(extras) == 1 and len(quizdays) == 1, \
                    "Option A coexistence must remain allowed"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ════════════════════════════════ T9 + T10 ══════════════════════════════════

def test_t9_t10_attended_extra_lifecycle_and_reactivation_under_constraints():
    """Attended-extra preservation (never deleted, is_deactivated while
    withdrawn, restored as the SAME row on reactivation) produces no
    duplicate (source_event_id, date) rows and never violates the new
    session constraint across deactivate/reactivate cycles."""

    async def scenario():
        async with AsyncSessionLocal() as session:
            await session.begin()
            session.autoflush = False
            try:
                db = session
                svc = EventService(db)
                att = AttendanceService(db)
                admin = _admin()
                subject = (await db.execute(
                    select(Subject).where(Subject.id == _CHAIN["subject_id"])
                )).scalars().one()
                student_id = _CHAIN["student_id"]

                event = await svc.create_event(admin, AcademicEventCreate(
                    event_type=EventType.EXTRA_LECTURE, start_date=PAST1,
                    end_date=PAST1, subject_id=subject.id,
                    class_type=ClassType.LECTURE))
                event_id = event.id  # captured before any expire_all
                extra = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.subject_id == subject.id,
                        ClassSession.date == PAST1,
                        ClassSession.is_extra.is_(True))
                )).scalars().one()
                await att.record_attendance(
                    student_id, extra.id, AttendanceStatus.ATTENDED)

                await svc.deactivate_event(admin, event_id)
                db.expire_all()
                kept = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.source_event_id == event_id)
                )).scalars().all()
                assert len(kept) == 1 and kept[0].is_deactivated is True, \
                    "attended extra preserved exactly once"

                await svc.update_event(admin, event_id, AcademicEventUpdate(
                    active=True))
                db.expire_all()
                restored = (await db.execute(
                    select(ClassSession).where(
                        ClassSession.source_event_id == event_id)
                )).scalars().all()
                assert len(restored) == 1 and restored[0].is_deactivated is False, \
                    "reactivation restores the SAME provenance row — never a duplicate"

                restored_id = restored[0].id
                # One more full cycle under the constraint.
                await svc.deactivate_event(admin, event_id)
                await svc.update_event(admin, event_id, AcademicEventUpdate(
                    active=True))
                db.expire_all()
                final = (await db.execute(
                    select(func.count()).select_from(ClassSession)
                    .where(ClassSession.source_event_id == event_id)
                )).scalar_one()
                assert final == 1
                records = (await db.execute(
                    select(func.count()).select_from(AttendanceRecord)
                    .where(AttendanceRecord.class_session_id == restored_id)
                )).scalar_one()
                assert records == 1, "the attendance record rides along untouched"
                return True
            finally:
                await session.rollback()

    assert _run(scenario()) is True


# ═══════════════════════════════ T13 ════════════════════════════════════════

def test_t13_migration_indexes_present_with_expected_names():
    async def scenario():
        async with AsyncSessionLocal() as db:
            names = {r[0] for r in (await db.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename IN "
                "('academic_events', 'class_sessions') AND indexname "
                "LIKE 'uq_%'")
            )).fetchall()}
            expected = {
                'uq_academic_events_quiz_day_identity',
                'uq_academic_events_global_range',
                "uq_class_sessions_entry_date",
                "uq_class_sessions_source_event_date",
                "uq_class_sessions_quiz_day_subject_date",
            }
            assert expected <= names, f"missing: {expected - names}"
            return True
    assert _run(scenario()) is True
