"""OCC-1 — strict occurrence/timetable enforcement for the Events system.

Regression coverage for the occurrence-driven architecture:

  A/B. Extra lecture / extra tutorial accept THEORY subjects only (practical
       subjects are rejected at the backend, even for crafted requests) and
       the class type is automatic.
  C.   Class cancellations target an exact scheduled timetable occurrence:
       the option read model lists only what is scheduled that day, the
       persisted event carries the exact timetable_entry_id, duplicate
       same-subject occurrences stay separately cancellable, and wrong
       entry/date/subject/class-type combinations are rejected.
  D.   Lab cancellations: only scheduled practical occurrences, class type
       automatically PRACTICAL, exactly one lab occurrence cancelled.
  E.   Working-day contradiction rules (weekend + working rejected outside
       the canonical WORKING_SATURDAY type; closure + working rejected) and
       the backend day-resolution defaults surfaced by the options read model.
  F.   Electives: slot occurrences stay slot-wide by default, concrete
       narrowing resolves to the member subject only (no anchor leakage,
       other members isolated).
  G.   Lifecycle: cancel -> session cancelled -> deactivate -> restored,
       idempotent re-syncs, attendance records never corrupted.

All DB scenarios run the REAL production paths (EventService create/update/
deactivate, EventSessionSynchronizer, AdminEventService read models) inside
a SAVEPOINT sandbox — same pattern as test_extra_lifecycle_foundation.py.
Only synthetic TXO-* rows are created; canonical row counts are asserted
identical before/after every test. Head-admin option reads are filtered to
the sandbox section so the dev baseline's own timetable never leaks into an
assertion.
"""
import asyncio
import uuid
from datetime import date, time

import pytest
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal, engine
from app.models.academic import AcademicSession, Semester, StudentEnrollment, Subject
from app.models.admin_scope import AdminScope
from app.models.attendance import AttendanceRecord
from app.models.enums import (
    AdminRole,
    AttendanceStatus,
    ClassType,
    ElectiveSlot,
    EnrollmentType,
    EventType,
    SubjectCategory,
    UserRole,
)
from app.models.event import AcademicEvent
from app.models.occurrence import OccurrenceOutcome, OccurrenceOutcomeType
from app.models.timetable import ClassSession, TimetableEntry
from app.models.user import Section, User
from app.schemas.calendar import AcademicEventCreate
from app.services.admin_event_service import AdminEventService
from app.services.attendance_service import AttendanceService
from app.services.elective_resolver import ElectiveResolver
from app.services.event_registry import validate_event, EventValidationError
from app.services.event_service import EventService, EventForbidden
from app.services.event_session_service import EventSessionSynchronizer
from app.repositories.session_repo import SessionRepository

# A Monday / Tuesday / Friday / Saturday / Sunday inside the dev baseline
# span (2026-07-30 is a Thursday, per the pinned lifecycle test date).
MONDAY = date(2026, 7, 27)
TUESDAY = date(2026, 7, 28)
FRIDAY = date(2026, 7, 31)
SATURDAY = date(2026, 8, 1)
SUNDAY = date(2026, 8, 2)

CODE_MAIN = "TXO-501"      # theory (common)
CODE_ABSENT = "TXO-502"    # theory, scheduled TUESDAY only (for MONDAY "not scheduled")
CODE_LAB = "TXO-551"       # practical/lab
CODE_MEMBER_A = "TXO-052"  # ELECTIVE_I member
CODE_MEMBER_B = "TXO-053"  # ELECTIVE_I member


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


async def _scalar_query(stmt):
    """One-off scalar query on a fresh connection (outside any sandbox) —
    used to ground data-dependent test premises in the authoritative DB."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(stmt)
        return result.scalar_one()


@pytest.fixture(scope="module", autouse=True)
def _loop_occurrence():
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
            "occurrence_outcomes": await count(select(func.count()).select_from(OccurrenceOutcome)),
            "timetable_entries": await count(select(func.count()).select_from(TimetableEntry)),
        }


async def _chain(db, tag):
    """Synthetic academic chain + subjects + timetable entries + users.

    Returns a dict with the subjects, the timetable entries (keyed by role),
    the HEAD admin (legacy ADMIN), a scoped CLASS admin (own section), a
    CLASS admin scoped to an EMPTY section, and a student enrolled in the
    main theory subject.
    """
    academic_session = AcademicSession(
        name=f"TXO-SESS-{tag}", start_date=date(2026, 7, 1),
        end_date=date(2026, 12, 31), is_active=True)
    db.add(academic_session)
    await db.flush()
    semester = Semester(
        name=f"TXO-SEM-{tag}", session_id=academic_session.id,
        start_date=date(2026, 7, 1), end_date=date(2026, 12, 31))
    db.add(semester)
    await db.flush()
    section = Section(name=f"TXO-SEC-{tag}", semester_id=semester.id, program="TEST")
    other_section = Section(name=f"TXO-SEC2-{tag}", semester_id=semester.id, program="TEST")
    db.add_all([section, other_section])
    await db.flush()

    def _subject(code, category, slot=None):
        return Subject(
            code=code, name=f"TXO Subject {code}", tag=None,
            elective_slot=slot, category=category,
            quiz_applicable=True, attendance_applicable=True,
            semester_id=semester.id)

    main = _subject(CODE_MAIN, SubjectCategory.THEORY)
    absent = _subject(CODE_ABSENT, SubjectCategory.THEORY)
    lab = _subject(CODE_LAB, SubjectCategory.LAB)
    member_a = _subject(CODE_MEMBER_A, SubjectCategory.THEORY, ElectiveSlot.ELECTIVE_I)
    member_b = _subject(CODE_MEMBER_B, SubjectCategory.THEORY, ElectiveSlot.ELECTIVE_I)
    db.add_all([main, absent, lab, member_a, member_b])
    await db.flush()

    # The shared anchor subject for ELECTIVE_I is resolved through the
    # canonical ElectiveResolver (BCS-054 by code — the real active-session
    # anchor; never a synthetic guess).
    anchor = await ElectiveResolver(db).anchor_subject_for_slot(ElectiveSlot.ELECTIVE_I)
    assert anchor is not None, "dev baseline must configure the ELECTIVE_I anchor"

    def _entry(subject_id, dow, start, end, class_type, slot=None, section_id=None):
        return TimetableEntry(
            subject_id=subject_id, day_of_week=dow, start_time=start,
            end_time=end, class_type=class_type, section_id=section_id or section.id,
            is_active=True, elective_slot=slot)

    entries = {
        "lect_mon_a": _entry(main.id, 0, time(10, 0), time(11, 0), ClassType.LECTURE),
        "lect_mon_b": _entry(main.id, 0, time(11, 0), time(12, 0), ClassType.LECTURE),
        "tut_mon": _entry(main.id, 0, time(13, 0), time(14, 0), ClassType.TUTORIAL),
        "slot_mon": _entry(anchor.id, 0, time(14, 0), time(15, 0), ClassType.LECTURE, ElectiveSlot.ELECTIVE_I),
        "lab_tue_a": _entry(lab.id, 1, time(9, 0), time(10, 0), ClassType.PRACTICAL),
        "lab_tue_b": _entry(lab.id, 1, time(10, 0), time(11, 0), ClassType.PRACTICAL),
        "absent_tue": _entry(absent.id, 1, time(11, 0), time(12, 0), ClassType.LECTURE),
    }
    db.add_all(entries.values())
    await db.flush()

    head = User(roll_number=f"TXO-HEAD-{tag}", name="TXO Head Admin",
                hashed_password=None, role=UserRole.ADMIN, section_id=None)
    class_admin = User(roll_number=f"TXO-CLSA-{tag}", name="TXO Class Admin",
                       hashed_password=None, role=UserRole.STUDENT, section_id=None)
    other_admin = User(roll_number=f"TXO-OTHA-{tag}", name="TXO Other Admin",
                       hashed_password=None, role=UserRole.STUDENT, section_id=None)
    student = User(roll_number=f"TXO-STU-{tag}", name="TXO Student",
                   hashed_password=None, role=UserRole.STUDENT, section_id=section.id)
    db.add_all([head, class_admin, other_admin, student])
    await db.flush()
    db.add(AdminScope(user_id=class_admin.id, role=AdminRole.CLASS_ADMIN,
                      section_id=section.id, active=True))
    # Scoped to the OTHER (empty) section: nothing visible.
    db.add(AdminScope(user_id=other_admin.id, role=AdminRole.CLASS_ADMIN,
                      section_id=other_section.id, active=True))
    db.add(StudentEnrollment(user_id=student.id, subject_id=main.id,
                             enrollment_type=EnrollmentType.COMPULSORY))
    await db.flush()

    return {
        "session": academic_session, "semester": semester, "section": section,
        "section_id": str(section.id),
        "main": main, "absent": absent, "lab": lab,
        "member_a": member_a, "member_b": member_b, "anchor": anchor,
        "entries": entries, "head": head, "class_admin": class_admin,
        "other_admin": other_admin, "student": student,
    }


async def _materialize_scheduled(db, entries, day):
    """Mimic the baseline expansion: one scheduled session per entry/date."""
    repo = SessionRepository(db)
    for entry in entries.values():
        if entry.day_of_week == day.weekday():
            repo.add_session(
                subject_id=entry.subject_id, date=day,
                class_type=entry.class_type, is_extra=False,
                timetable_entry_id=entry.id)
    await db.flush()


async def _sessions_for_entry(db, entry_id, day):
    return (await db.execute(
        select(ClassSession).where(
            ClassSession.timetable_entry_id == entry_id,
            ClassSession.date == day)
    )).scalars().all()


async def _extras(db, subject_id, day, class_type=None):
    stmt = select(ClassSession).where(
        ClassSession.subject_id == subject_id,
        ClassSession.date == day,
        ClassSession.is_extra.is_(True))
    if class_type is not None:
        stmt = stmt.where(ClassSession.class_type == class_type)
    return (await db.execute(stmt)).scalars().all()


def _sandbox_only(options, section_id):
    """Filter an options response to the sandbox section — the dev baseline's
    own timetable must never leak into an assertion."""
    return [o for o in options.items if str(o.section_id) == section_id]


# ---------------------------------------------------------------------------
# A/B — extra lecture / tutorial: theory subjects only
# ---------------------------------------------------------------------------

async def _scenario_extras_theory_accepted():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            svc = EventService(db)
            lecture = await svc.create_event(chain["head"], AcademicEventCreate(
                event_type=EventType.EXTRA_LECTURE, start_date=MONDAY,
                end_date=MONDAY, subject_id=chain["main"].id,
                class_type=ClassType.LECTURE))
            tutorial = await svc.create_event(chain["head"], AcademicEventCreate(
                event_type=EventType.EXTRA_TUTORIAL, start_date=MONDAY,
                end_date=MONDAY, subject_id=chain["main"].id,
                class_type=ClassType.TUTORIAL))
            lecture_extras = await _extras(db, chain["main"].id, MONDAY, ClassType.LECTURE)
            tutorial_extras = await _extras(db, chain["main"].id, MONDAY, ClassType.TUTORIAL)
            return {
                "lecture_ok": lecture is not None,
                "tutorial_ok": tutorial is not None,
                "lecture_class_type": lecture.class_type,
                "tutorial_class_type": tutorial.class_type,
                "lecture_subject": str(lecture.subject_id),
                "tutorial_subject": str(tutorial.subject_id),
                "main_id": str(chain["main"].id),
                "lecture_entry_reference": lecture.timetable_entry_id,
                "tutorial_entry_reference": tutorial.timetable_entry_id,
                "lecture_extra_count": len(lecture_extras),
                "tutorial_extra_count": len(tutorial_extras),
            }
        finally:
            await session.rollback()


async def _scenario_extra_rejects_lab(event_type, class_type):
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            svc = EventService(db)
            try:
                await svc.create_event(chain["head"], AcademicEventCreate(
                    event_type=event_type, start_date=MONDAY, end_date=MONDAY,
                    subject_id=chain["lab"].id, class_type=class_type))
                return {"rejected": False, "error": None}
            except EventValidationError as exc:
                return {"rejected": True, "error": str(exc)}
        finally:
            await session.rollback()


# ---------------------------------------------------------------------------
# C — class cancellation: occurrence-driven
# ---------------------------------------------------------------------------

async def _scenario_options_for_date(user_key, day, event_type=None):
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            svc = AdminEventService(db)
            options = await svc.list_occurrence_options(
                chain[user_key], for_date=day,
                event_type=event_type)
            return {
                "is_working_day": options.is_working_day,
                "day_type": options.day_type,
                "schedule_day": options.schedule_day,
                "non_working_reason": options.non_working_reason,
                "items": _sandbox_only(options, chain["section_id"]),
                "slot_entry": next(
                    (o for o in _sandbox_only(options, chain["section_id"])
                     if o.elective_slot is not None), None),
            }
        finally:
            await session.rollback()


async def _scenario_create_occurrence_cancellation():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            await _materialize_scheduled(db, chain["entries"], MONDAY)
            svc = EventService(db)
            entry = chain["entries"]["lect_mon_a"]
            event = await svc.create_event(chain["head"], AcademicEventCreate(
                event_type=EventType.CLASS_CANCELLED, start_date=MONDAY,
                end_date=MONDAY, subject_id=chain["main"].id,
                class_type=ClassType.LECTURE,
                timetable_entry_id=entry.id))
            target_sessions = await _sessions_for_entry(db, entry.id, MONDAY)
            twin_sessions = await _sessions_for_entry(
                db, chain["entries"]["lect_mon_b"].id, MONDAY)
            tut_sessions = await _sessions_for_entry(
                db, chain["entries"]["tut_mon"].id, MONDAY)
            return {
                "event_id": str(event.id),
                "stored_entry": str(event.timetable_entry_id),
                "entry_id": str(entry.id),
                "stored_subject": str(event.subject_id),
                "main_id": str(chain["main"].id),
                "stored_class_type": event.class_type,
                "stored_slot": event.elective_slot,
                "target_cancelled": [s.is_cancelled for s in target_sessions],
                "twin_cancelled": [s.is_cancelled for s in twin_sessions],
                "tut_cancelled": [s.is_cancelled for s in tut_sessions],
            }
        finally:
            await session.rollback()


async def _scenario_cancellation_rejections():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            await _materialize_scheduled(db, chain["entries"], MONDAY)
            svc = EventService(db)
            errors = {}

            async def attempt(key, **payload):
                try:
                    await svc.create_event(chain["head"], AcademicEventCreate(**payload))
                    errors[key] = None
                except EventValidationError as exc:
                    errors[key] = str(exc)

            # Wrong weekday: the lab entry is scheduled on TUESDAY, the event
            # targets MONDAY.
            await attempt("weekday", event_type=EventType.CLASS_CANCELLED,
                          start_date=MONDAY, end_date=MONDAY,
                          subject_id=chain["lab"].id,
                          class_type=ClassType.PRACTICAL,
                          timetable_entry_id=chain["entries"]["lab_tue_a"].id)
            # Non-scheduled subject: TXO-502 has no Monday occurrence.
            await attempt("weekday_absent", event_type=EventType.CLASS_CANCELLED,
                          start_date=MONDAY, end_date=MONDAY,
                          subject_id=chain["absent"].id,
                          class_type=ClassType.LECTURE,
                          timetable_entry_id=chain["entries"]["absent_tue"].id)
            # Subject/occurrence mismatch: the Monday lecture entry with a
            # different subject.
            await attempt("subject", event_type=EventType.CLASS_CANCELLED,
                          start_date=MONDAY, end_date=MONDAY,
                          subject_id=chain["absent"].id,
                          class_type=ClassType.LECTURE,
                          timetable_entry_id=chain["entries"]["lect_mon_a"].id)
            # Class-type contradiction: the entry is a lecture.
            await attempt("class_type", event_type=EventType.CLASS_CANCELLED,
                          start_date=MONDAY, end_date=MONDAY,
                          subject_id=chain["main"].id,
                          class_type=ClassType.TUTORIAL,
                          timetable_entry_id=chain["entries"]["lect_mon_a"].id)
            # Missing reference entirely (crafted request bypassing the UI).
            await attempt("missing_reference", event_type=EventType.CLASS_CANCELLED,
                          start_date=MONDAY, end_date=MONDAY,
                          subject_id=chain["main"].id,
                          class_type=ClassType.LECTURE)
            # LAB_CANCELLED pointing at a lecture occurrence: the derived
            # class type (LECTURE) contradicts the PRACTICAL-only registry.
            await attempt("lab_on_lecture", event_type=EventType.LAB_CANCELLED,
                          start_date=MONDAY, end_date=MONDAY,
                          subject_id=chain["main"].id,
                          class_type=ClassType.LECTURE,
                          timetable_entry_id=chain["entries"]["lect_mon_a"].id)
            # LAB_CANCELLED with a lab subject but a non-practical occurrence.
            await attempt("lab_subject_mismatch", event_type=EventType.LAB_CANCELLED,
                          start_date=MONDAY, end_date=MONDAY,
                          subject_id=chain["lab"].id,
                          class_type=ClassType.PRACTICAL,
                          timetable_entry_id=chain["entries"]["tut_mon"].id)
            # An occurrence reference is forbidden on non-cancellation types.
            await attempt("entry_on_extra", event_type=EventType.EXTRA_LECTURE,
                          start_date=MONDAY, end_date=MONDAY,
                          subject_id=chain["main"].id,
                          class_type=ClassType.LECTURE,
                          timetable_entry_id=chain["entries"]["lect_mon_a"].id)
            # Deactivated timetable entries are no longer cancellable.
            entry = chain["entries"]["lect_mon_b"]
            entry.is_active = False
            await db.flush()
            await attempt("inactive_entry", event_type=EventType.CLASS_CANCELLED,
                          start_date=MONDAY, end_date=MONDAY,
                          subject_id=chain["main"].id,
                          class_type=ClassType.LECTURE,
                          timetable_entry_id=entry.id)
            return errors
        finally:
            await session.rollback()


async def _scenario_duplicate_occurrences_separately_cancellable():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            await _materialize_scheduled(db, chain["entries"], MONDAY)
            svc = EventService(db)
            entry_a = chain["entries"]["lect_mon_a"]
            entry_b = chain["entries"]["lect_mon_b"]

            event_a = await svc.create_event(chain["head"], AcademicEventCreate(
                event_type=EventType.CLASS_CANCELLED, start_date=MONDAY,
                end_date=MONDAY, subject_id=chain["main"].id,
                class_type=ClassType.LECTURE, timetable_entry_id=entry_a.id))
            # Same subject + class type + date, DIFFERENT occurrence: not a
            # duplicate — each occurrence stays separately cancellable.
            event_b = await svc.create_event(chain["head"], AcademicEventCreate(
                event_type=EventType.CLASS_CANCELLED, start_date=MONDAY,
                end_date=MONDAY, subject_id=chain["main"].id,
                class_type=ClassType.LECTURE, timetable_entry_id=entry_b.id))

            sessions_a = await _sessions_for_entry(db, entry_a.id, MONDAY)
            sessions_b = await _sessions_for_entry(db, entry_b.id, MONDAY)
            # Capture primitives NOW: the ORM instances are the identity-map
            # objects the later deactivate/resync below mutates.
            a_cancelled = [s.is_cancelled for s in sessions_a]
            b_cancelled = [s.is_cancelled for s in sessions_b]

            # Re-running the synchronizer is idempotent (no duplicate events,
            # no state drift).
            await svc.deactivate_event(chain["head"], event_b.id)
            await EventSessionSynchronizer(db).sync_event(event_a)
            await db.flush()
            sessions_b_after = await _sessions_for_entry(db, entry_b.id, MONDAY)
            sessions_a_after = await _sessions_for_entry(db, entry_a.id, MONDAY)

            return {
                "a_stored": str(event_a.timetable_entry_id),
                "b_stored": str(event_b.timetable_entry_id),
                "a_cancelled": a_cancelled,
                "b_cancelled": b_cancelled,
                "a_after_resync": [s.is_cancelled for s in sessions_a_after],
                "b_after_deactivate": [s.is_cancelled for s in sessions_b_after],
            }
        finally:
            await session.rollback()


# ---------------------------------------------------------------------------
# D — lab cancellation: exact practical occurrence only
# ---------------------------------------------------------------------------

async def _scenario_lab_cancellation_exact():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            await _materialize_scheduled(db, chain["entries"], TUESDAY)
            svc = EventService(db)
            entry_a = chain["entries"]["lab_tue_a"]
            entry_b = chain["entries"]["lab_tue_b"]
            event = await svc.create_event(chain["head"], AcademicEventCreate(
                event_type=EventType.LAB_CANCELLED, start_date=TUESDAY,
                end_date=TUESDAY, subject_id=chain["lab"].id,
                class_type=ClassType.PRACTICAL,
                timetable_entry_id=entry_a.id))
            sessions_a = await _sessions_for_entry(db, entry_a.id, TUESDAY)
            sessions_b = await _sessions_for_entry(db, entry_b.id, TUESDAY)
            return {
                "stored_class_type": event.class_type,
                "stored_entry": str(event.timetable_entry_id),
                "entry_a_id": str(entry_a.id),
                "a_cancelled": [s.is_cancelled for s in sessions_a],
                "b_cancelled": [s.is_cancelled for s in sessions_b],
            }
        finally:
            await session.rollback()


# ---------------------------------------------------------------------------
# F — electives: slot occurrences, concrete narrowing, no anchor leakage
# ---------------------------------------------------------------------------

async def _scenario_slot_occurrence_slotwide():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            await _materialize_scheduled(db, chain["entries"], MONDAY)
            svc = EventService(db)
            entry = chain["entries"]["slot_mon"]
            # Slot occurrence, no narrowing -> slot-wide event (anchor + slot
            # marker), derived entirely by the backend.
            event = await svc.create_event(chain["head"], AcademicEventCreate(
                event_type=EventType.CLASS_CANCELLED, start_date=MONDAY,
                end_date=MONDAY, subject_id=None,
                timetable_entry_id=entry.id))
            sessions = await _sessions_for_entry(db, entry.id, MONDAY)
            return {
                "stored_subject": str(event.subject_id),
                "anchor_id": str(chain["anchor"].id),
                "stored_slot": event.elective_slot.value if event.elective_slot else None,
                "stored_class_type": event.class_type,
                "slot_cancelled": [s.is_cancelled for s in sessions],
            }
        finally:
            await session.rollback()


async def _scenario_slot_occurrence_concrete_narrowing():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            await _materialize_scheduled(db, chain["entries"], MONDAY)
            svc = EventService(db)
            entry = chain["entries"]["slot_mon"]
            # Narrowed to member A: subject-specific cancellation — the
            # shared slot session stays, member A resolves a CANCELLED
            # outcome, member B (and the anchor) are untouched.
            event = await svc.create_event(chain["head"], AcademicEventCreate(
                event_type=EventType.CLASS_CANCELLED, start_date=MONDAY,
                end_date=MONDAY, subject_id=chain["member_a"].id,
                timetable_entry_id=entry.id))
            sessions = await _sessions_for_entry(db, entry.id, MONDAY)
            session_ids = [s.id for s in sessions]
            outcomes = (await db.execute(
                select(OccurrenceOutcome).where(
                    OccurrenceOutcome.class_session_id.in_(session_ids))
            )).scalars().all()
            return {
                "stored_subject": str(event.subject_id),
                "member_a_id": str(chain["member_a"].id),
                "anchor_id": str(chain["anchor"].id),
                "stored_slot": event.elective_slot,
                "slot_cancelled": [s.is_cancelled for s in sessions],
                "outcomes": [
                    (str(o.subject_id), o.outcome_type.value) for o in outcomes
                ],
            }
        finally:
            await session.rollback()


async def _scenario_narrowing_rejections():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            await _materialize_scheduled(db, chain["entries"], MONDAY)
            svc = EventService(db)
            errors = {}
            # A subject outside the slot can never narrow the slot occurrence.
            try:
                await svc.create_event(chain["head"], AcademicEventCreate(
                    event_type=EventType.CLASS_CANCELLED, start_date=MONDAY,
                    end_date=MONDAY, subject_id=chain["main"].id,
                    timetable_entry_id=chain["entries"]["slot_mon"].id))
                errors["non_member"] = None
            except EventValidationError as exc:
                errors["non_member"] = str(exc)
            # Slot-wide cancellation of a slot occurrence is HEAD-only.
            try:
                await svc.create_event(chain["class_admin"], AcademicEventCreate(
                    event_type=EventType.CLASS_CANCELLED, start_date=MONDAY,
                    end_date=MONDAY, subject_id=None,
                    timetable_entry_id=chain["entries"]["slot_mon"].id))
                errors["slotwide_scope"] = None
            except EventForbidden as exc:
                errors["slotwide_scope"] = str(exc)
            return errors
        finally:
            await session.rollback()


# ---------------------------------------------------------------------------
# G — lifecycle: cancel -> deactivate -> restore; attendance intact
# ---------------------------------------------------------------------------

async def _scenario_cancellation_lifecycle():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            await _materialize_scheduled(db, chain["entries"], MONDAY)
            svc = EventService(db)
            att = AttendanceService(db)
            entry = chain["entries"]["lect_mon_a"]

            # A stale mark exists BEFORE the cancellation is known.
            sessions = await _sessions_for_entry(db, entry.id, MONDAY)
            target = sessions[0]
            await att.record_attendance(
                chain["student"].id, target.id, AttendanceStatus.MISSED)

            event = await svc.create_event(chain["head"], AcademicEventCreate(
                event_type=EventType.CLASS_CANCELLED, start_date=MONDAY,
                end_date=MONDAY, subject_id=chain["main"].id,
                class_type=ClassType.LECTURE, timetable_entry_id=entry.id))
            await db.flush()
            cancelled_state = (await db.execute(
                select(ClassSession).where(ClassSession.id == target.id)
            )).scalars().first()
            # Capture primitives NOW (identity-map aliasing — the same row is
            # re-read after the resync and the deactivation below).
            cancelled_after_create = cancelled_state.is_cancelled

            # Idempotency: a redundant sync must not change anything.
            await EventSessionSynchronizer(db).sync_event(event)
            await db.flush()
            again = (await db.execute(
                select(ClassSession).where(ClassSession.id == target.id)
            )).scalars().first()
            cancelled_after_resync = again.is_cancelled

            # Deactivation restores the occurrence exactly.
            await svc.deactivate_event(chain["head"], event.id)
            await db.flush()
            restored = (await db.execute(
                select(ClassSession).where(ClassSession.id == target.id)
            )).scalars().first()
            record = (await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.class_session_id == target.id)
            )).scalars().first()
            return {
                "cancelled_after_create": cancelled_after_create,
                "cancelled_after_resync": cancelled_after_resync,
                "restored_cancelled": restored.is_cancelled,
                "restored_extra": restored.is_extra,
                "record_exists": record is not None,
                "record_status": str(record.status) if record else None,
            }
        finally:
            await session.rollback()


async def _scenario_options_with_holiday():
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            chain = await _chain(db, tag)
            db.add(AcademicEvent(
                event_type=EventType.HOLIDAY, start_date=MONDAY,
                end_date=MONDAY, note="TXO holiday", active=True))
            await db.flush()
            svc = AdminEventService(db)
            holiday_monday = await svc.list_occurrence_options(
                chain["head"], for_date=MONDAY,
                event_type=EventType.CLASS_CANCELLED)
            plain_saturday = await svc.list_occurrence_options(
                chain["head"], for_date=SATURDAY,
                event_type=EventType.CLASS_CANCELLED)
            plain_sunday = await svc.list_occurrence_options(
                chain["head"], for_date=SUNDAY,
                event_type=EventType.CLASS_CANCELLED)
            return {
                "holiday_monday_working": holiday_monday.is_working_day,
                "holiday_reason": holiday_monday.non_working_reason,
                "holiday_items": len(holiday_monday.items),
                "saturday_working": plain_saturday.is_working_day,
                "saturday_reason": plain_saturday.non_working_reason,
                "saturday_schedule_day": plain_saturday.schedule_day,
                "sunday_working": plain_sunday.is_working_day,
            }
        finally:
            await session.rollback()


# ---------------------------------------------------------------------------
# Test bodies (each asserts canonical counts are untouched)
# ---------------------------------------------------------------------------

def test_extra_lecture_and_tutorial_theory_subjects_accepted_automatic_class_type():
    before = _run(_canonical_counts())
    data = _run(_scenario_extras_theory_accepted())
    assert _run(_canonical_counts()) == before

    assert data["lecture_ok"] is True
    assert data["tutorial_ok"] is True
    # Class type is automatic and matches the event type (never arbitrary).
    assert data["lecture_class_type"] == ClassType.LECTURE
    assert data["tutorial_class_type"] == ClassType.TUTORIAL
    assert data["lecture_subject"] == data["main_id"]
    assert data["tutorial_subject"] == data["main_id"]
    assert data["lecture_entry_reference"] is None, "extras are not occurrence-referenced"
    assert data["tutorial_entry_reference"] is None
    assert data["lecture_extra_count"] == 1
    assert data["tutorial_extra_count"] == 1


def test_extra_lecture_rejects_practical_subject():
    data = _run(_scenario_extra_rejects_lab(EventType.EXTRA_LECTURE, ClassType.LECTURE))
    assert data["rejected"] is True
    assert "theory" in data["error"].lower()


def test_extra_tutorial_rejects_practical_subject():
    data = _run(_scenario_extra_rejects_lab(EventType.EXTRA_TUTORIAL, ClassType.TUTORIAL))
    assert data["rejected"] is True
    assert "theory" in data["error"].lower()


def test_options_only_list_scheduled_occurrences_for_the_date():
    before = _run(_canonical_counts())
    monday = _run(_scenario_options_for_date("head", MONDAY, EventType.CLASS_CANCELLED))
    assert _run(_canonical_counts()) == before

    assert monday["is_working_day"] is True
    assert monday["schedule_day"] == "MONDAY"
    items = monday["items"]
    # Monday sandbox schedule: two lectures + one tutorial of TXO-501 + the
    # shared ELECTIVE_I slot lecture. TXO-502 (Tuesday-only) and the lab must
    # NOT appear; practicals are filtered out by the CLASS_CANCELLED rule.
    assert len(items) == 4
    assert all("TXO-551" not in o.display_label for o in items)
    assert all("TXO-502" not in o.display_label for o in items)
    assert sorted(o.class_type.value for o in items) == ["L", "L", "L", "T"]
    # Two same-subject lecture occurrences are separately selectable and
    # distinguishable (different times).
    lectures = sorted(
        o.display_label for o in items
        if o.subject_code == CODE_MAIN and o.class_type == ClassType.LECTURE)
    assert len(lectures) == 2 and len(set(lectures)) == 2
    # The slot entry keeps its anchor and offers concrete members.
    slot_entry = monday["slot_entry"]
    assert slot_entry is not None and slot_entry.is_slot_anchor is True
    member_codes = [m.code for m in slot_entry.elective_subjects]
    assert CODE_MEMBER_A in member_codes and CODE_MEMBER_B in member_codes
    assert "BCS-054" not in member_codes, "the anchor is never offered as a member"


def test_options_scoped_by_admin_scope():
    before = _run(_canonical_counts())
    class_scoped = _run(_scenario_options_for_date("class_admin", MONDAY, EventType.CLASS_CANCELLED))
    empty_scoped = _run(_scenario_options_for_date("other_admin", MONDAY, EventType.CLASS_CANCELLED))
    lab_tuesday = _run(_scenario_options_for_date("head", TUESDAY, EventType.LAB_CANCELLED))
    assert _run(_canonical_counts()) == before

    # The CLASS admin sees exactly their section's Monday L/T occurrences.
    assert len(class_scoped["items"]) == 4
    # The other section has no entries: nothing visible.
    assert empty_scoped["items"] == []
    # LAB_CANCELLED on Tuesday: only the two practical occurrences.
    assert lab_tuesday["items"], "scheduled labs must be listed"
    assert sorted(o.class_type.value for o in lab_tuesday["items"]) == ["P", "P"]
    assert all("TXO-551" in o.display_label for o in lab_tuesday["items"])


def test_options_day_resolution_weekend_and_holiday():
    before = _run(_canonical_counts())
    data = _run(_scenario_options_with_holiday())
    assert _run(_canonical_counts()) == before

    # Working-day defaults: ordinary weekday working; Saturday/Sunday
    # non-working; an active closure makes the weekday non-working.
    assert data["holiday_monday_working"] is False
    assert data["holiday_reason"] == "Holiday"
    assert data["holiday_items"] == 0
    assert data["saturday_working"] is False
    assert data["saturday_reason"] == "Weekend"
    assert data["saturday_schedule_day"] == "SATURDAY"
    assert data["sunday_working"] is False


def test_occurrence_cancellation_persists_exact_entry_and_cancels_only_it():
    before = _run(_canonical_counts())
    data = _run(_scenario_create_occurrence_cancellation())
    assert _run(_canonical_counts()) == before

    assert data["stored_entry"] == data["entry_id"]
    assert data["stored_subject"] == data["main_id"]
    assert data["stored_class_type"] == ClassType.LECTURE
    assert data["stored_slot"] is None
    assert data["target_cancelled"] == [True], "the exact occurrence is cancelled"
    assert data["twin_cancelled"] == [False], "the twin occurrence stays active"
    assert data["tut_cancelled"] == [False], "other class types stay active"


def test_cancellation_rejections():
    before = _run(_canonical_counts())
    errors = _run(_scenario_cancellation_rejections())
    assert _run(_canonical_counts()) == before

    assert errors["weekday"] is not None and "not scheduled" in errors["weekday"]
    assert errors["weekday_absent"] is not None
    assert errors["subject"] is not None and "match" in errors["subject"].lower()
    assert errors["class_type"] is not None and "match" in errors["class_type"].lower()
    assert errors["missing_reference"] is not None and "timetable occurrence" in errors["missing_reference"]
    assert errors["lab_on_lecture"] is not None
    assert errors["lab_subject_mismatch"] is not None
    assert errors["entry_on_extra"] is not None and "must not reference" in errors["entry_on_extra"]
    assert errors["inactive_entry"] is not None and "deactivated" in errors["inactive_entry"]


def test_duplicate_same_subject_occurrences_separately_cancellable():
    before = _run(_canonical_counts())
    data = _run(_scenario_duplicate_occurrences_separately_cancellable())
    assert _run(_canonical_counts()) == before

    assert data["a_stored"] != data["b_stored"], "each event pins its own occurrence"
    assert data["a_cancelled"] == [True]
    assert data["b_cancelled"] == [True]
    # After deactivating B and a redundant resync of A: A stays cancelled,
    # B's occurrence is restored exactly (no duplicate sessions, no drift).
    assert data["a_after_resync"] == [True]
    assert data["b_after_deactivate"] == [False]


def test_lab_cancellation_cancels_only_that_practical_occurrence():
    before = _run(_canonical_counts())
    data = _run(_scenario_lab_cancellation_exact())
    assert _run(_canonical_counts()) == before

    assert data["stored_class_type"] == ClassType.PRACTICAL
    assert data["stored_entry"] == data["entry_a_id"]
    assert data["a_cancelled"] == [True], "the selected lab occurrence is cancelled"
    assert data["b_cancelled"] == [False], "the other lab occurrence is untouched"


def test_working_day_contradictions_rejected():
    # weekend + working=true is only representable as WORKING_SATURDAY.
    with pytest.raises(EventValidationError, match="weekend"):
        validate_event(
            event_type=EventType.WORKING_DAY_OVERRIDE,
            start_date=SATURDAY, end_date=SATURDAY, is_working_day=True)
    with pytest.raises(EventValidationError, match="weekend"):
        validate_event(
            event_type=EventType.WORKING_DAY_OVERRIDE,
            start_date=SUNDAY, end_date=SUNDAY, is_working_day=True)
    # A range covering a weekend date is rejected as well.
    with pytest.raises(EventValidationError, match="weekend"):
        validate_event(
            event_type=EventType.WORKING_DAY_OVERRIDE,
            start_date=FRIDAY, end_date=SATURDAY, is_working_day=True)
    # An ordinary weekday override stays representable in both directions.
    validate_event(
        event_type=EventType.WORKING_DAY_OVERRIDE,
        start_date=MONDAY, end_date=MONDAY, is_working_day=True)
    validate_event(
        event_type=EventType.WORKING_DAY_OVERRIDE,
        start_date=MONDAY, end_date=MONDAY, is_working_day=False)
    # WORKING_SATURDAY keeps its pinned semantics: always working, and only
    # Saturdays flip (a range containing a Sunday never forces the Sunday).
    with pytest.raises(EventValidationError, match="Working Saturday"):
        validate_event(
            event_type=EventType.WORKING_SATURDAY,
            start_date=SATURDAY, end_date=SATURDAY, is_working_day=False)
    validate_event(
        event_type=EventType.WORKING_SATURDAY,
        start_date=SATURDAY, end_date=SUNDAY, is_working_day=True)
    # Closures can never claim a working state.
    with pytest.raises(EventValidationError, match="closure"):
        validate_event(
            event_type=EventType.HOLIDAY,
            start_date=MONDAY, end_date=MONDAY, is_working_day=True)


def test_slot_occurrence_defaults_to_slot_wide():
    before = _run(_canonical_counts())
    data = _run(_scenario_slot_occurrence_slotwide())
    assert _run(_canonical_counts()) == before

    assert data["stored_subject"] == data["anchor_id"]
    assert data["stored_slot"] == "ELECTIVE_I"
    assert data["stored_class_type"] == ClassType.LECTURE
    assert data["slot_cancelled"] == [True], "slot-wide cancels the shared session"


def test_slot_occurrence_concrete_narrowing_isolates_members():
    before = _run(_canonical_counts())
    data = _run(_scenario_slot_occurrence_concrete_narrowing())
    assert _run(_canonical_counts()) == before

    assert data["stored_subject"] == data["member_a_id"]
    assert data["stored_slot"] is None, "a narrowed event is subject-specific"
    assert data["slot_cancelled"] == [False], "the shared session stays for the slot"
    assert (data["member_a_id"], OccurrenceOutcomeType.CANCELLED.value) in data["outcomes"]
    assert all(
        subject_id != data["anchor_id"] for subject_id, _ in data["outcomes"]
    ), "no anchor-subject outcome may exist (no anchor leakage)"


def test_narrowing_and_scope_rejections():
    before = _run(_canonical_counts())
    errors = _run(_scenario_narrowing_rejections())
    assert _run(_canonical_counts()) == before

    assert errors["non_member"] is not None and "slot" in errors["non_member"].lower()
    assert errors["slotwide_scope"] is not None


def test_cancellation_lifecycle_restores_session_and_attendance():
    before = _run(_canonical_counts())
    data = _run(_scenario_cancellation_lifecycle())
    assert _run(_canonical_counts()) == before

    assert data["cancelled_after_create"] is True
    assert data["cancelled_after_resync"] is True, "redundant sync is idempotent"
    assert data["restored_cancelled"] is False, "deactivation restores the occurrence"
    assert data["restored_extra"] is False
    assert data["record_exists"] is True
    assert data["record_status"] == "AttendanceStatus.MISSED", \
        "attendance records are never corrupted by the cancellation lifecycle"


# ---------------------------------------------------------------------------
# OCC-1b — route registration/ordering + the authoritative CSE Wednesday
# occurrence (2026-10-07 → BNC-501), read against the real dev-DB source of
# truth, plus scope enforcement on the same read.
# ---------------------------------------------------------------------------

def test_occurrence_options_route_registered_before_event_id_route():
    """REGRESSION for the reported empty-picker failure mode: if the static
    /events/occurrence-options route is missing or registered AFTER the
    dynamic /events/{event_id} route, FastAPI matches the dynamic route and
    the request fails UUID parsing (422) — which the UI previously rendered
    as "No classes scheduled on this date" for a fully scheduled day."""
    from app.main import app

    spec = app.openapi()
    paths = list(spec["paths"].keys())
    occurrence_path = "/api/v1/admin/events/occurrence-options"
    detail_path = "/api/v1/admin/events/{event_id}"
    assert occurrence_path in paths, (
        "occurrence-options route missing from the app — the running process "
        "would serve the picker from a stale route table"
    )
    assert detail_path in paths
    assert paths.index(occurrence_path) < paths.index(detail_path), (
        "occurrence-options must be registered BEFORE /events/{event_id} so "
        "the static path wins route matching"
    )


async def _scenario_real_cse_wednesday_occurrence():
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            head = (await db.execute(
                select(User).where(User.role == UserRole.ADMIN)
            )).scalars().first()
            assert head is not None, "dev DB must hold the HEAD admin"

            svc = AdminEventService(db)
            options = await svc.list_occurrence_options(
                head, for_date=date(2026, 10, 7),
                event_type=EventType.CLASS_CANCELLED)

            # Scoped-admin variants on the SAME authoritative read: one CLASS
            # admin covering the section that owns the BNC-501 entry, one
            # scoped to an empty synthetic section.
            bnc = (await db.execute(
                select(Subject).where(Subject.code == "BNC-501")
            )).scalars().first()
            assert bnc is not None, "authoritative BNC-501 subject missing"
            bnc_entry = (await db.execute(
                select(TimetableEntry).where(
                    TimetableEntry.subject_id == bnc.id,
                    TimetableEntry.day_of_week == 2,
                    TimetableEntry.is_active.is_(True))
            )).scalars().first()
            assert bnc_entry is not None, (
                "authoritative timetable data missing: no active BNC-501 "
                "Wednesday (day_of_week=2) entry in the dev DB"
            )
            real_section_id = bnc_entry.section_id
            real_section = (await db.execute(
                select(Section).where(Section.id == real_section_id)
            )).scalars().first()
            empty_section = Section(
                name=f"TXO-EMPTY-{uuid.uuid4().hex[:6]}",
                semester_id=real_section.semester_id, program="TEST")
            db.add(empty_section)
            await db.flush()
            scoped_ok = User(roll_number=f"TXO-WED-A-{uuid.uuid4().hex[:6]}",
                             name="TXO Scoped Admin", hashed_password=None,
                             role=UserRole.STUDENT, section_id=None)
            scoped_none = User(roll_number=f"TXO-WED-B-{uuid.uuid4().hex[:6]}",
                               name="TXO Other Admin", hashed_password=None,
                               role=UserRole.STUDENT, section_id=None)
            db.add_all([scoped_ok, scoped_none])
            await db.flush()
            db.add(AdminScope(user_id=scoped_ok.id, role=AdminRole.CLASS_ADMIN,
                              section_id=real_section_id, active=True))
            db.add(AdminScope(user_id=scoped_none.id, role=AdminRole.CLASS_ADMIN,
                              section_id=empty_section.id, active=True))
            await db.flush()

            for_user = await svc.list_occurrence_options(
                scoped_ok, for_date=date(2026, 10, 7),
                event_type=EventType.CLASS_CANCELLED)
            for_none = await svc.list_occurrence_options(
                scoped_none, for_date=date(2026, 10, 7),
                event_type=EventType.CLASS_CANCELLED)

            def summarize(resp):
                return [
                    (o.subject_code, o.class_type.value,
                     o.start_time.strftime("%H:%M"), o.display_label,
                     o.elective_slot.value if o.elective_slot else None,
                     o.is_slot_anchor)
                    for o in resp.items
                ]

            return {
                "is_working_day": options.is_working_day,
                "schedule_day": options.schedule_day,
                "head_items": summarize(options),
                "scoped_items": summarize(for_user),
                "empty_scoped_items": summarize(for_none),
                "bnc_entry_id": str(bnc_entry.id),
            }
        finally:
            await session.rollback()


def test_occurrence_options_include_real_bnc501_wednesday_occurrence():
    """AUTHORITATIVE SOURCE REGRESSION: the official B.Tech III Year V
    Semester schedule places 05–10 Oct 2026 in Week 13; Wednesday 07 Oct 2026
    carries BNC-501. The occurrence resolver must surface that exact
    scheduled occurrence for the CSE scope — with its class type and time —
    while a subject scheduled only on OTHER weekdays and a practical subject
    must not appear for CLASS_CANCELLED."""
    data = _run(_scenario_real_cse_wednesday_occurrence())

    # Day resolution: 2026-10-07 is a working Wednesday (engine-resolved).
    assert data["is_working_day"] is True
    assert data["schedule_day"] == "WEDNESDAY"

    head = data["head_items"]
    codes = [item[0] for item in head]

    # The scheduled BNC-501 Wednesday lecture is offered exactly once, with
    # its server-derived class type and time in the label.
    bnc = [item for item in head if item[0] == "BNC-501"]
    assert len(bnc) == 1, f"expected exactly one BNC-501 Wednesday occurrence, got {bnc}"
    code, class_type, start, label, slot, anchor = bnc[0]
    assert class_type == "L", "class type comes from the authoritative occurrence"
    assert start == "11:00"
    assert "(Lecture)" in label and "11:00" in label

    # An unscheduled subject for this date does not appear (BCS-551 is a
    # practical subject scheduled Mon/Thu — doubly excluded: weekday + the
    # CLASS_CANCELLED L/T class-type constraint).
    assert "BCS-551" not in codes
    # Another weekday's class does not appear (BCS-501 is scheduled Tue/Thu,
    # never Wednesday — the negative is grounded in the authoritative data).
    wednesday_bcs501 = _run(_scalar_query(
        select(func.count()).select_from(TimetableEntry).where(
            TimetableEntry.day_of_week == 2,
            TimetableEntry.is_active.is_(True),
            TimetableEntry.subject_id.in_(select(Subject.id).where(
                Subject.code == "BCS-501")))
    ))
    assert wednesday_bcs501 == 0, "test premise broken: BCS-501 now has a Wednesday entry"
    assert "BCS-501" not in codes
    # Web Technology IS scheduled Wednesday and appears with its class type.
    assert any(item[0] == "BCS-502" and item[1] == "L" for item in head)

    # Every option label carries the server-derived class type and time —
    # never a bare subject name.
    assert all(
        ("(Lecture)" in item[3] or "(Tutorial)" in item[3]) and "·" in item[3]
        for item in head
    )

    # Electives remain canonical: slot entries keep the shared anchor and
    # offer the concrete catalog members; the anchor itself is never a member.
    slot_items = [item for item in head if item[4] is not None]
    assert slot_items, "the CSE Wednesday timetable carries elective-slot entries"
    assert all(item[5] is True for item in slot_items)

    # Scope filtering remains enforced on the same authoritative read.
    assert any(item[0] == "BNC-501" for item in data["scoped_items"]), (
        "the section-scoped admin must still see the BNC-501 Wednesday occurrence"
    )
    assert data["empty_scoped_items"] == [], (
        "an admin scoped to a section with no timetable sees nothing"
    )
