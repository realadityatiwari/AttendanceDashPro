"""Chunk — extra-session lifecycle foundation tests (schema + provenance +
synchronizer only; the read/filter layer is intentionally NOT implemented).

Pins the new ClassSession lifecycle columns and the provenance-aware extras
reconciliation:

  - is_deactivated: the source EXTRA_* event was withdrawn while the
    historical occurrence/attendance record is preserved (never deleted,
    never is_cancelled).
  - source_event_id: every NEW event-created extra records the AcademicEvent
    that caused it; legacy rows stay NULL (never backfilled, never guessed).

All scenarios run the REAL production paths (EventService create/deactivate/
update + EventSessionSynchronizer) inside a SAVEPOINT sandbox — same pattern
as test_registration_enrollment_e2e.py / test_deactivated_attended_extra.py.
Only synthetic TX-* rows are created; canonical row counts are asserted
identical before/after every test.
"""
import asyncio
import uuid
from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.timezone import institution_today
from app.db.session import AsyncSessionLocal, engine
from app.models.academic import AcademicSession, Semester, StudentEnrollment, Subject
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
from app.models.timetable import ClassSession
from app.models.user import Section, User
from app.schemas.calendar import AcademicEventCreate, AcademicEventUpdate
from app.services.attendance_service import AttendanceService
from app.services.event_service import EventService
from app.services.event_session_service import EventSessionSynchronizer

TEST_DATE = date(2026, 7, 30)  # Thursday inside the dev baseline span, in the past
SUBJECT_CODE = "TX-LIFE"


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


async def _canonical_counts():
    async with AsyncSessionLocal() as db:
        async def count(stmt):
            return (await db.execute(stmt)).scalar_one()

        return {
            "subjects": await count(select(func.count()).select_from(Subject)),
            "users": await count(select(func.count()).select_from(User)),
            "class_sessions": await count(select(func.count()).select_from(ClassSession)),
            "attendance_records": await count(select(func.count()).select_from(AttendanceRecord)),
            "academic_events": await count(select(func.count()).select_from(AcademicEvent)),
        }


async def _chain(db, tag):
    """Synthetic academic chain + subject + users + enrollment. Returns the
    ORM objects (valid inside the open sandbox transaction)."""
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
        code=SUBJECT_CODE, name="TX Lifecycle Subject", tag=None,
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
    return subject, student, admin


async def _extra(db, subject_id):
    return (await db.execute(
        select(ClassSession)
        .where(ClassSession.subject_id == subject_id,
               ClassSession.date == TEST_DATE,
               ClassSession.is_extra.is_(True))
    )).scalars().all()


async def _scenario_new_extra_gets_provenance():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, student, admin = await _chain(db, tag)
            svc = EventService(db)

            event = await svc.create_event(admin, AcademicEventCreate(
                event_type=EventType.EXTRA_LECTURE, start_date=TEST_DATE,
                end_date=TEST_DATE, subject_id=subject.id,
                class_type=ClassType.LECTURE))
            extras = await _extra(db, subject.id)

            # Idempotency: a redundant sync must not duplicate or mutate.
            await EventSessionSynchronizer(db).sync_event(event)
            await db.flush()
            extras_after_resync = await _extra(db, subject.id)

            def shape(rows):
                return sorted(
                    (str(s.id), str(s.source_event_id), s.is_deactivated,
                     s.is_cancelled) for s in rows)

            return {"before": shape(extras), "after_resync": shape(extras_after_resync),
                    "event_id": str(event.id)}
        finally:
            await session.rollback()


async def _scenario_deactivate_attended():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, student, admin = await _chain(db, tag)
            svc = EventService(db)
            att = AttendanceService(db)

            event = await svc.create_event(admin, AcademicEventCreate(
                event_type=EventType.EXTRA_LECTURE, start_date=TEST_DATE,
                end_date=TEST_DATE, subject_id=subject.id,
                class_type=ClassType.LECTURE))
            extra = (await _extra(db, subject.id))[0]
            await att.record_attendance(student.id, extra.id, AttendanceStatus.MISSED)

            await svc.deactivate_event(admin, event.id)
            kept = (await db.execute(
                select(ClassSession).where(ClassSession.id == extra.id)
            )).scalars().first()
            record = (await db.execute(
                select(AttendanceRecord)
                .where(AttendanceRecord.class_session_id == extra.id)
            )).scalars().first()

            return {
                "session_exists": kept is not None,
                "is_deactivated": kept.is_deactivated if kept else None,
                "is_cancelled": kept.is_cancelled if kept else None,
                "is_extra": kept.is_extra if kept else None,
                "source_event_id": str(kept.source_event_id) if kept else None,
                "event_id": str(event.id),
                "record_exists": record is not None,
                "record_status": str(record.status) if record else None,
            }
        finally:
            await session.rollback()


async def _scenario_reactivate_attended():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, student, admin = await _chain(db, tag)
            svc = EventService(db)
            att = AttendanceService(db)

            event = await svc.create_event(admin, AcademicEventCreate(
                event_type=EventType.EXTRA_LECTURE, start_date=TEST_DATE,
                end_date=TEST_DATE, subject_id=subject.id,
                class_type=ClassType.LECTURE))
            original_id = (await _extra(db, subject.id))[0].id
            await att.record_attendance(student.id, original_id, AttendanceStatus.MISSED)

            await svc.deactivate_event(admin, event.id)
            await svc.update_event(admin, event.id, AcademicEventUpdate(active=True))

            extras = await _extra(db, subject.id)
            restored = next(s for s in extras if s.id == original_id)
            record = (await db.execute(
                select(AttendanceRecord)
                .where(AttendanceRecord.class_session_id == original_id)
            )).scalars().first()
            return {
                "extra_count": len(extras),
                "same_id": True,
                "is_deactivated": restored.is_deactivated,
                "source_event_id": str(restored.source_event_id),
                "event_id": str(event.id),
                "record_exists": record is not None,
                "record_status": str(record.status) if record else None,
            }
        finally:
            await session.rollback()


async def _scenario_two_same_key_events():
    """Alternating lifecycle through the real service paths: each extra
    session follows ONLY its own event's state."""
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, student, admin = await _chain(db, tag)
            svc = EventService(db)
            att = AttendanceService(db)

            payload = dict(event_type=EventType.EXTRA_LECTURE,
                           start_date=TEST_DATE, end_date=TEST_DATE,
                           subject_id=subject.id, class_type=ClassType.LECTURE)
            event_a = await svc.create_event(admin, AcademicEventCreate(**payload))
            s_a = (await _extra(db, subject.id))[0]
            await att.record_attendance(student.id, s_a.id, AttendanceStatus.MISSED)

            # Deactivate A: A's session is marked; nothing else exists yet.
            await svc.deactivate_event(admin, event_a.id)
            state1 = {str(s.source_event_id): s.is_deactivated
                      for s in await _extra(db, subject.id)}

            # Create B while A is inactive (duplicate guard checks ACTIVE
            # events only): the deficit must be filled with a B-linked row.
            event_b = await svc.create_event(admin, AcademicEventCreate(**payload))
            extras = await _extra(db, subject.id)
            s_b = next(s for s in extras if s.source_event_id == event_b.id)
            await att.record_attendance(student.id, s_b.id, AttendanceStatus.MISSED)
            state2 = sorted((str(s.source_event_id), s.is_deactivated)
                            for s in extras)

            # Deactivate B: only B's session flips; A's stays deactivated.
            await svc.deactivate_event(admin, event_b.id)
            state3 = {str(s.source_event_id): s.is_deactivated
                      for s in await _extra(db, subject.id)}

            # Reactivate A (B inactive -> guard passes): A's SAME session
            # returns; B's stays deactivated.
            await svc.update_event(admin, event_a.id, AcademicEventUpdate(active=True))
            state4 = {str(s.source_event_id): (s.is_deactivated, str(s.id))
                      for s in await _extra(db, subject.id)}
            a_id = str(s_a.id)

            # Deactivate A again, reactivate B: symmetric behavior.
            await svc.deactivate_event(admin, event_a.id)
            await svc.update_event(admin, event_b.id, AcademicEventUpdate(active=True))
            state5 = {str(s.source_event_id): (s.is_deactivated, str(s.id))
                      for s in await _extra(db, subject.id)}

            return {
                "after_deactivate_a": state1,
                "after_create_b": state2,
                "after_deactivate_b": state3,
                "after_reactivate_a": state4,
                "after_reactivate_b": state5,
                "a_session_id": a_id,
                "b_session_id": str(s_b.id),
                "event_a": str(event_a.id),
                "event_b": str(event_b.id),
            }
        finally:
            await session.rollback()


async def _scenario_two_active_same_key_events():
    """The DB allows two ACTIVE same-key extra events (the service duplicate
    guard only fires through the API). The reconciler must give each event
    its own provenance-linked session."""
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, student, admin = await _chain(db, tag)

            event_a = AcademicEvent(
                event_type=EventType.EXTRA_LECTURE, start_date=TEST_DATE,
                end_date=TEST_DATE, subject_id=subject.id,
                class_type=ClassType.LECTURE, active=True)
            event_b = AcademicEvent(
                event_type=EventType.EXTRA_LECTURE, start_date=TEST_DATE,
                end_date=TEST_DATE, subject_id=subject.id,
                class_type=ClassType.LECTURE, active=True)
            db.add_all([event_a, event_b])
            await db.flush()
            await EventSessionSynchronizer(db).sync_event(event_a)
            await db.flush()

            by_source = {str(s.source_event_id): s for s in await _extra(db, subject.id)}
            return {
                "count": len(by_source),
                "a_linked": str(event_a.id) in by_source,
                "b_linked": str(event_b.id) in by_source,
                "all_active": all(not s.is_deactivated for s in by_source.values()),
            }
        finally:
            await session.rollback()


async def _scenario_legacy_null_provenance():
    """A pre-migration style row (NULL provenance, attended) must be marked
    on withdrawal and count-restored on demand — with its provenance NEVER
    invented."""
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, student, admin = await _chain(db, tag)

            # Legacy row: created before provenance existed (source NULL).
            legacy = ClassSession(
                subject_id=subject.id, date=TEST_DATE,
                class_type=ClassType.LECTURE, is_extra=True,
                is_cancelled=False, is_deactivated=False,
                timetable_entry_id=None, source_event_id=None)
            db.add(legacy)
            await db.flush()
            db.add(AttendanceRecord(user_id=student.id,
                                    class_session_id=legacy.id,
                                    status=AttendanceStatus.MISSED))
            await db.flush()

            # Withdrawal: no active extra event -> legacy attended extra is
            # marked deactivated (never deleted, never cancelled), and its
            # provenance is NOT invented.
            dummy = AcademicEvent(
                event_type=EventType.EXTRA_LECTURE, start_date=TEST_DATE,
                end_date=TEST_DATE, subject_id=subject.id,
                class_type=ClassType.LECTURE, active=False)
            db.add(dummy)
            await db.flush()
            await EventSessionSynchronizer(db).sync_event(dummy)
            await db.flush()
            after_withdraw = (await db.execute(
                select(ClassSession).where(ClassSession.id == legacy.id)
            )).scalars().first()
            # Capture primitives NOW: the ORM instance is the identity-map
            # object also returned by the restore-phase queries below, so a
            # later re-read would observe the RESTORED state, not the
            # withdrawn one.
            withdraw = {
                "deactivated": after_withdraw.is_deactivated,
                "cancelled": after_withdraw.is_cancelled,
                "source_null": after_withdraw.source_event_id is None,
            }

            # Demand returns (event active again): the count-based path may
            # restore the legacy row — still WITHOUT assigning provenance.
            dummy.active = True
            await db.flush()
            await EventSessionSynchronizer(db).sync_event(dummy)
            await db.flush()
            extras = await _extra(db, subject.id)
            records_intact = True
            for s in extras:
                rec = (await db.execute(
                    select(AttendanceRecord)
                    .where(AttendanceRecord.class_session_id == s.id)
                )).scalars().first()
                if rec is None:
                    records_intact = False

            return {
                "withdraw_deactivated": withdraw["deactivated"],
                "withdraw_cancelled": withdraw["cancelled"],
                "withdraw_source_null": withdraw["source_null"],
                "restore_count": len(extras),
                "restore_deactivated": [s.is_deactivated for s in extras],
                "restore_source_all_null": all(s.source_event_id is None for s in extras),
                "record_intact": records_intact,
            }
        finally:
            await session.rollback()


async def _scenario_unattended_extra_still_deleted():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, student, admin = await _chain(db, tag)
            svc = EventService(db)

            event = await svc.create_event(admin, AcademicEventCreate(
                event_type=EventType.EXTRA_LECTURE, start_date=TEST_DATE,
                end_date=TEST_DATE, subject_id=subject.id,
                class_type=ClassType.LECTURE))
            before = len(await _extra(db, subject.id))
            await svc.deactivate_event(admin, event.id)
            after = await _extra(db, subject.id)
            return {"created": before, "after_deactivate": len(after)}
        finally:
            await session.rollback()


def test_new_extra_event_gets_provenance_and_stays_active():
    before = _run(_canonical_counts())
    data = _run(_scenario_new_extra_gets_provenance())
    assert _run(_canonical_counts()) == before

    assert len(data["before"]) == 1
    session_id, source, deactivated, cancelled = data["before"][0]
    assert source == data["event_id"], "new extra must record its causing event"
    assert deactivated is False and cancelled is False
    assert data["before"] == data["after_resync"], "redundant sync must be a no-op"


def test_attended_extra_survives_deactivation_marked_not_cancelled():
    before = _run(_canonical_counts())
    data = _run(_scenario_deactivate_attended())
    assert _run(_canonical_counts()) == before

    assert data["session_exists"], "attended extra must survive deactivation"
    assert data["is_deactivated"] is True, "deactivation must set is_deactivated"
    assert data["is_cancelled"] is False, "is_cancelled must never be set by withdrawal"
    assert data["is_extra"] is True
    assert data["source_event_id"] == data["event_id"]
    assert data["record_exists"] and data["record_status"] == "AttendanceStatus.MISSED"


def test_reactivation_restores_same_session_no_duplicate():
    before = _run(_canonical_counts())
    data = _run(_scenario_reactivate_attended())
    assert _run(_canonical_counts()) == before

    assert data["extra_count"] == 1, "reactivation must not duplicate the extra"
    assert data["is_deactivated"] is False, "reactivation must clear is_deactivated"
    assert data["source_event_id"] == data["event_id"]
    assert data["record_exists"] and data["record_status"] == "AttendanceStatus.MISSED"


def test_two_same_key_events_stay_identity_separated():
    before = _run(_canonical_counts())
    data = _run(_scenario_two_same_key_events())
    assert _run(_canonical_counts()) == before

    assert data["after_deactivate_a"] == {data["event_a"]: True}
    # B's creation fills the deficit with a B-linked row (identity-exact).
    assert set(data["after_create_b"]) == {
        (data["event_a"], True), (data["event_b"], False)}
    assert data["after_deactivate_b"] == {
        data["event_a"]: True, data["event_b"]: True}
    # Reactivating A restores A's SAME session only.
    a_state = data["after_reactivate_a"][data["event_a"]]
    assert a_state == (False, data["a_session_id"]), "A must restore its own row"
    assert data["after_reactivate_a"][data["event_b"]][0] is True
    # Symmetric for B.
    b_state = data["after_reactivate_b"][data["event_b"]]
    assert b_state == (False, data["b_session_id"]), "B must restore its own row"
    assert data["after_reactivate_b"][data["event_a"]][0] is True


def test_two_active_same_key_events_each_get_own_linked_session():
    before = _run(_canonical_counts())
    data = _run(_scenario_two_active_same_key_events())
    assert _run(_canonical_counts()) == before

    assert data["count"] == 2
    assert data["a_linked"] and data["b_linked"]
    assert data["all_active"]


def test_legacy_null_provenance_row_is_marked_and_count_restored():
    before = _run(_canonical_counts())
    data = _run(_scenario_legacy_null_provenance())
    assert _run(_canonical_counts()) == before

    assert data["withdraw_deactivated"] is True
    assert data["withdraw_cancelled"] is False
    assert data["withdraw_source_null"], "provenance must never be invented"
    assert data["restore_count"] == 1
    assert data["restore_deactivated"] == [False]
    assert data["restore_source_all_null"], "legacy row stays NULL-provenance"
    assert data["record_intact"]


def test_unattended_extra_still_deleted_on_deactivation():
    before = _run(_canonical_counts())
    data = _run(_scenario_unattended_extra_still_deleted())
    assert _run(_canonical_counts()) == before

    assert data["created"] == 1
    assert data["after_deactivate"] == 0, "unattended extras are still deleted"
