"""Regression tests — deactivated attended extra is logically non-existent.

Lifecycle foundation (previous chunk): an EXTRA_* event whose extra
ClassSession already carries an AttendanceRecord is deactivated — the session
and record are preserved with is_deactivated=True (never deleted, never
is_cancelled); reactivation restores the SAME row.

This chunk implements the LOGICAL READ FILTER at the single common occurrence
layer (app.engines.practical_occurrence.group_practical_occurrences — the
funnel every counting and read-model consumer already shares), so a
deactivated extra behaves as if it does not exist for:

  A  History + history summary                 (get_history)
  B/E/F  subject attendance / forecast /
     Must Attend / Safe Skip                   (get_summary + optimizer)
  B  ERP/dashboard overall                     (dashboard _build_overall on
                                                the real repo rows)
  D  quiz eligibility windows I/II/best-case   (counts_between pipelines)
  G/H calendar session counts + notification
      thresholds (shared source query)          (get_sessions_with_status)
  I  Track daily logical view                  (get_daily_sessions)
  + the 409 mutation gate on deactivated rows
  J  normal timetable classes unaffected
  K  multiple students isolated
  L  multiple extras/events identity-separated
  M  legacy NULL-provenance rows stay logically active (never backfilled)

All scenarios run the REAL production paths inside a SAVEPOINT sandbox (same
pattern as test_registration_enrollment_e2e.py). Only synthetic TX-* rows are
created; canonical row counts are asserted identical before/after.
"""
import asyncio
import uuid
from datetime import date, time

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.timezone import institution_today
from app.db.session import AsyncSessionLocal, engine
from app.engines.attendance_engine import optimize_attendance
from app.engines.practical_occurrence import collapse_count_rows
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
from app.models.timetable import ClassSession, TimetableEntry
from app.models.user import Section, User
from app.schemas.calendar import AcademicEventCreate, AcademicEventUpdate
from app.services.attendance_service import AttendanceService
from app.services.dashboard_service import DashboardService
from app.services.event_service import EventService
from app.services.event_session_service import EventSessionSynchronizer
from app.repositories.attendance_repo import AttendanceRepository

# The reported production date: a Thursday inside the dev baseline span and
# in the past, so History (bounded to <= today) includes it while active.
TEST_DATE = date(2026, 7, 30)
SUBJECT_CODE = "TX-054"


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
            "academic_sessions": await count(select(func.count()).select_from(AcademicSession)),
            "semesters": await count(select(func.count()).select_from(Semester)),
            "sections": await count(select(func.count()).select_from(Section)),
            "subjects": await count(select(func.count()).select_from(Subject)),
            "users": await count(select(func.count()).select_from(User)),
            "enrollments": await count(select(func.count()).select_from(StudentEnrollment)),
            "timetable_entries": await count(select(func.count()).select_from(TimetableEntry)),
            "class_sessions": await count(select(func.count()).select_from(ClassSession)),
            "attendance_records": await count(select(func.count()).select_from(AttendanceRecord)),
            "academic_events": await count(select(func.count()).select_from(AcademicEvent)),
        }


async def _chain(db, tag, student_count=1):
    """Synthetic academic chain + subject + N students + enrollments."""
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
        code=SUBJECT_CODE, name="TX Extra Bug Subject", tag=None,
        elective_slot=None, category=SubjectCategory.THEORY,
        quiz_applicable=True, attendance_applicable=True,
        semester_id=semester.id)
    db.add(subject)
    await db.flush()

    students = []
    for i in range(student_count):
        student = User(
            roll_number=f"TX-STU-{tag}-{i}", name=f"TX Student {i}",
            hashed_password=None, role=UserRole.STUDENT, section_id=section.id)
        db.add(student)
        await db.flush()
        db.add(StudentEnrollment(user_id=student.id, subject_id=subject.id,
                                 enrollment_type=EnrollmentType.COMPULSORY))
        students.append(student)
    admin = User(roll_number=f"TX-ADM-{tag}", name="TX Admin",
                 hashed_password=None, role=UserRole.ADMIN, section_id=None)
    db.add(admin)
    await db.flush()
    return subject, students, admin, section


async def _extras(db, subject_id):
    return (await db.execute(
        select(ClassSession)
        .where(ClassSession.subject_id == subject_id,
               ClassSession.date == TEST_DATE,
               ClassSession.is_extra.is_(True))
    )).scalars().all()


async def _scheduled(db, subject_id):
    return (await db.execute(
        select(ClassSession)
        .where(ClassSession.subject_id == subject_id,
               ClassSession.date == TEST_DATE,
               ClassSession.is_extra.is_(False))
    )).scalars().first()


def _hist_shape(hist):
    return {
        "summary": dict(hist["summary"]),
        "extra_items": [
            {"status": str(i["status"]), "is_cancelled": i["is_cancelled"]}
            for i in hist["items"] if i["is_extra"]
        ],
        "normal_items": [
            {"status": str(i["status"]), "is_cancelled": i["is_cancelled"]}
            for i in hist["items"] if not i["is_extra"]
        ],
    }


async def _scenario_lifecycle():
    """Full A/B/C/J lifecycle through the real production paths."""
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, students, admin, section = await _chain(db, tag)
            student = students[0]
            svc = EventService(db)
            att = AttendanceService(db)
            repo = AttendanceRepository(db)
            dashboard = object.__new__(DashboardService)

            # Normal-class control: Thursday timetable lecture, materialized
            # by the same reconciliation pass as the extra.
            entry = TimetableEntry(
                subject_id=subject.id, day_of_week=3,
                start_time=time(10, 0), end_time=time(11, 0),
                class_type=ClassType.LECTURE, section_id=section.id)
            db.add(entry)
            await db.flush()

            event = await svc.create_event(admin, AcademicEventCreate(
                event_type=EventType.EXTRA_LECTURE, start_date=TEST_DATE,
                end_date=TEST_DATE, subject_id=subject.id,
                class_type=ClassType.LECTURE))
            extra = (await _extras(db, subject.id))[0]
            scheduled = await _scheduled(db, subject.id)
            extra_id, scheduled_id = extra.id, scheduled.id

            await att.record_attendance(student.id, scheduled_id, AttendanceStatus.ATTENDED)
            await att.record_attendance(student.id, extra_id, AttendanceStatus.MISSED)

            today = institution_today()

            async def reads():
                hist = _hist_shape(await att.get_history(student, subject_code=SUBJECT_CODE))
                summ = await att.get_summary(student.id, subject.id, SUBJECT_CODE, today)
                rows = await repo.get_sessions_with_status(student.id, TEST_DATE, TEST_DATE)
                daily = await att.get_daily_sessions(student.id, TEST_DATE)
                return {
                    "history": hist,
                    "lecture": summ.lecture.model_dump(),
                    "avg": summ.current_avg_pct,
                    "forecast": summ.forecast_avg_pct,
                    "optimization": summ.optimization.model_dump() if summ.optimization else None,
                    "logical_rows": [
                        (str(r["id"]), str(r["status"]))
                        for r in rows
                    ],
                    "overall": dashboard._build_overall(
                        rows=rows, today=TEST_DATE, semester_start=TEST_DATE).model_dump(),
                    "track_ids": sorted(str(s.id) for s in daily.sessions),
                    "track_extras": sum(1 for s in daily.sessions if s.is_extra),
                }

            active = await reads()

            # Deactivate via the REAL production path.
            await svc.deactivate_event(admin, event.id)

            # Write gate: a deactivated session must reject new marks (409).
            gate_exc = None
            try:
                await att.record_attendance(student.id, extra_id, AttendanceStatus.ATTENDED)
            except HTTPException as exc:
                gate_exc = exc.status_code

            # Preservation + logical reads, re-read fresh.
            extra_after = (await db.execute(
                select(ClassSession).where(ClassSession.id == extra_id))).scalars().first()
            record_after = (await db.execute(
                select(AttendanceRecord)
                .where(AttendanceRecord.class_session_id == extra_id))).scalars().first()
            scheduled_after = (await db.execute(
                select(ClassSession).where(ClassSession.id == scheduled_id))).scalars().first()

            after = await reads()

            # Capture preservation as PRIMITIVES now: these ORM instances are
            # identity-map objects that the reactivation below legitimately
            # mutates — a later read would observe the restored state.
            preserved = {
                "extra_exists": extra_after is not None,
                "extra_deactivated": extra_after.is_deactivated,
                "extra_cancelled": extra_after.is_cancelled,
                "record_exists": record_after is not None,
                "record_status": str(record_after.status) if record_after else None,
                "scheduled_exists": scheduled_after is not None,
                "scheduled_cancelled": scheduled_after.is_cancelled,
            }

            # Reactivate via the REAL production path.
            await svc.update_event(admin, event.id, AcademicEventUpdate(active=True))
            extras_reactivated = await _extras(db, subject.id)
            reactivated = await reads()

            return {
                "active": active,
                "gate_status": gate_exc,
                "preserved": preserved,
                "after": after,
                "reactivated": {
                    **reactivated,
                    "extra_count": len(extras_reactivated),
                    "same_id": any(s.id == extra_id for s in extras_reactivated),
                },
            }
        finally:
            await session.rollback()


def test_deactivated_attended_extra_lifecycle():
    before = _run(_canonical_counts())
    data = _run(_scenario_lifecycle())
    assert _run(_canonical_counts()) == before, "sandbox leaked rows"

    active, pres, after_d, react = (
        data["active"], data["preserved"], data["after"], data["reactivated"])
    only_scheduled_optimization = optimize_attendance(
        1, 1, 0, 0, 0, 0, 0, 0, 75.0).model_dump()

    # ============ A. Active extra: visible + counted normally =============
    assert len(active["history"]["extra_items"]) == 1
    assert active["history"]["extra_items"][0]["status"] == "AttendanceStatus.MISSED"
    assert active["history"]["summary"] == {
        "total": 2, "attended": 1, "missed": 1, "pending": 0,
        "cancelled": 0, "pct": 50.0}
    assert active["lecture"] == {"total": 2, "attended": 1, "missed": 1, "pending": 0}
    assert active["avg"] == pytest.approx(50.0)
    assert active["forecast"] == pytest.approx(50.0)
    assert active["overall"]["recorded"] == 2 and active["overall"]["attended"] == 1
    assert active["overall"]["overall_pct"] == pytest.approx(50.0)
    assert len(active["logical_rows"]) == 2
    assert active["track_extras"] == 1 and len(active["track_ids"]) == 2

    # ============ B. Deactivated: preserved + logically non-existent =======
    assert pres["extra_exists"] and pres["extra_deactivated"] is True
    assert pres["extra_cancelled"] is False, "never is_cancelled"
    assert pres["record_exists"]
    assert pres["record_status"] == "AttendanceStatus.MISSED"

    # History hides it; totals exclude it.
    assert after_d["history"]["extra_items"] == [], (
        "Deactivated attended extra must not appear in History")
    assert after_d["history"]["summary"]["missed"] == 0, (
        "Deactivated attended extra must not appear in logical attendance summary")
    assert after_d["history"]["summary"]["total"] == 1
    assert len(after_d["history"]["normal_items"]) == 1
    assert after_d["history"]["normal_items"][0]["status"] == "AttendanceStatus.ATTENDED"

    # Subject attendance denominator excludes it (total=2,missed=1,50% -> 1,0,100%).
    assert after_d["lecture"] == {"total": 1, "attended": 1, "missed": 0, "pending": 0}
    assert after_d["avg"] == pytest.approx(100.0)

    # Forecast excludes it.
    assert after_d["forecast"] == pytest.approx(100.0)

    # Must Attend / Safe Skip: the optimizer receives only filtered rows.
    assert after_d["optimization"] == only_scheduled_optimization

    # ERP/dashboard overall excludes it (real rows -> real builder).
    assert after_d["overall"]["recorded"] == 1 and after_d["overall"]["attended"] == 1
    assert after_d["overall"]["overall_pct"] == pytest.approx(100.0)

    # Calendar session-count + notification-threshold source query excludes it.
    assert len(after_d["logical_rows"]) == 1

    # Track daily logical view hides it.
    assert after_d["track_extras"] == 0 and len(after_d["track_ids"]) == 1

    # Write gate: 409 on a deactivated session.
    assert data["gate_status"] == 409

    # Normal timetable class is completely unaffected.
    assert pres["scheduled_exists"] and not pres["scheduled_cancelled"]

    # ============ C. Reactivation: same row, fully logical again ==========
    assert react["extra_count"] == 1 and react["same_id"]
    assert len(react["history"]["extra_items"]) == 1
    assert react["history"]["extra_items"][0]["status"] == "AttendanceStatus.MISSED"
    assert react["history"]["summary"]["missed"] == 1
    assert react["history"]["summary"]["total"] == 2
    assert react["lecture"] == {"total": 2, "attended": 1, "missed": 1, "pending": 0}
    assert react["avg"] == pytest.approx(50.0)
    assert react["forecast"] == pytest.approx(50.0)
    assert react["overall"]["recorded"] == 2
    assert react["track_extras"] == 1
    assert len(react["logical_rows"]) == 2


async def _scenario_quiz_windows():
    """D: the quiz-window count pipelines exclude deactivated extras."""
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, students, admin, section = await _chain(db, tag)
            student = students[0]
            svc = EventService(db)
            att = AttendanceService(db)
            repo = AttendanceRepository(db)

            event = await svc.create_event(admin, AcademicEventCreate(
                event_type=EventType.EXTRA_LECTURE, start_date=TEST_DATE,
                end_date=TEST_DATE, subject_id=subject.id,
                class_type=ClassType.LECTURE))
            extra = (await _extras(db, subject.id))[0]
            await att.record_attendance(student.id, extra.id, AttendanceStatus.MISSED)

            async def window_reads():
                collapsed = await repo.get_subject_counts_between(
                    student.id, subject.id, TEST_DATE, TEST_DATE)
                raw = await repo.get_subject_counts_between_for_subjects(
                    student.id, [subject.id], TEST_DATE, TEST_DATE)
                raw_collapsed = collapse_count_rows(raw)
                return {
                    "collapsed": sorted((str(ct), str(st)) for ct, st in collapsed),
                    "raw_count": len(raw),
                    "raw_deactivated_rows": sum(1 for r in raw if r.get("is_deactivated")),
                    "raw_collapsed": sorted((str(ct), str(st)) for ct, st in raw_collapsed),
                }

            active = await window_reads()
            await svc.deactivate_event(admin, event.id)
            after = await window_reads()
            await svc.update_event(admin, event.id, AcademicEventUpdate(active=True))
            reactivated = await window_reads()
            return {"active": active, "after": after, "reactivated": reactivated}
        finally:
            await session.rollback()


def test_deactivated_extra_excluded_from_quiz_window_pipeline():
    before = _run(_canonical_counts())
    data = _run(_scenario_quiz_windows())
    assert _run(_canonical_counts()) == before

    # Active: the extra's MISSED mark is inside the eligibility window input.
    assert (str(ClassType.LECTURE), str(AttendanceStatus.MISSED)) in data["active"]["collapsed"]
    assert data["active"]["raw_count"] == 1
    assert (str(ClassType.LECTURE), str(AttendanceStatus.MISSED)) in data["active"]["raw_collapsed"]

    # After deactivation: excluded from the collapsed window input (the exact
    # pipeline Criterion I/II/best-case consume), while the RAW rows still
    # carry the preserved session (data is never deleted).
    assert (str(ClassType.LECTURE), str(AttendanceStatus.MISSED)) not in data["after"]["collapsed"]
    assert data["after"]["raw_count"] == 1, "raw rows must preserve the deactivated session"
    assert data["after"]["raw_deactivated_rows"] == 1
    assert data["after"]["collapsed"] == [], (
        "the deactivated extra must be absent from the collapsed window input")
    assert (str(ClassType.LECTURE), str(AttendanceStatus.MISSED)) not in data["after"]["raw_collapsed"]

    # Reactivation participates again.
    assert (str(ClassType.LECTURE), str(AttendanceStatus.MISSED)) in data["reactivated"]["collapsed"]


async def _scenario_multi_student():
    """K: deactivation must not leak across students; records preserved."""
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, students, admin, section = await _chain(db, tag, student_count=2)
            svc = EventService(db)
            att = AttendanceService(db)
            repo = AttendanceRepository(db)

            event = await svc.create_event(admin, AcademicEventCreate(
                event_type=EventType.EXTRA_LECTURE, start_date=TEST_DATE,
                end_date=TEST_DATE, subject_id=subject.id,
                class_type=ClassType.LECTURE))
            extra = (await _extras(db, subject.id))[0]
            await att.record_attendance(students[0].id, extra.id, AttendanceStatus.MISSED)
            await att.record_attendance(students[1].id, extra.id, AttendanceStatus.ATTENDED)

            await svc.deactivate_event(admin, event.id)

            per_student = []
            records = []
            for s in students:
                hist = _hist_shape(await att.get_history(s, subject_code=SUBJECT_CODE))
                summ = await att.get_summary(s.id, subject.id, SUBJECT_CODE,
                                             institution_today())
                per_student.append({
                    "extra_items": hist["extra_items"],
                    "summary_missed": hist["summary"]["missed"],
                    "lecture": summ.lecture.model_dump(),
                })
                rec = (await db.execute(
                    select(AttendanceRecord)
                    .where(AttendanceRecord.class_session_id == extra.id,
                           AttendanceRecord.user_id == s.id))).scalars().first()
                records.append(str(rec.status) if rec else None)

            return {"per_student": per_student, "records": records}
        finally:
            await session.rollback()


def test_deactivated_extra_isolated_per_student_and_records_preserved():
    before = _run(_canonical_counts())
    data = _run(_scenario_multi_student())
    assert _run(_canonical_counts()) == before

    for i, ps in enumerate(data["per_student"]):
        assert ps["extra_items"] == [], f"student {i} must not see the deactivated extra"
        assert ps["summary_missed"] == 0
        assert ps["lecture"] == {"total": 0, "attended": 0, "missed": 0, "pending": 0}
    # Both records remain preserved exactly as marked.
    assert data["records"] == [
        "AttendanceStatus.MISSED", "AttendanceStatus.ATTENDED"]


async def _scenario_two_events():
    """L: event A deactivated while B active -> exactly B participates;
    reactivating A restores A's own row; no duplicate."""
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, students, admin, section = await _chain(db, tag)
            student = students[0]
            svc = EventService(db)
            att = AttendanceService(db)
            sync = EventSessionSynchronizer(db)

            # Two same-key events active at once (the DB allows it; the API
            # duplicate guard is intentionally bypassed for both-active
            # coverage — the reconciler must identity-separate them).
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
            await sync.sync_event(event_a)
            await db.flush()

            by_source = {str(s.source_event_id): s for s in await _extras(db, subject.id)}
            s_a, s_b = by_source[str(event_a.id)], by_source[str(event_b.id)]
            await att.record_attendance(student.id, s_a.id, AttendanceStatus.MISSED)
            await att.record_attendance(student.id, s_b.id, AttendanceStatus.ATTENDED)

            # Deactivate A via the real service path.
            await svc.deactivate_event(admin, event_a.id)

            hist = _hist_shape(await att.get_history(student, subject_code=SUBJECT_CODE))
            summ = await att.get_summary(student.id, subject.id, SUBJECT_CODE,
                                         institution_today())
            after_a_off = {
                "extra_statuses": sorted(str(i["status"])
                                         for i in hist["extra_items"]),
                "missed": hist["summary"]["missed"],
                "attended": hist["summary"]["attended"],
                "lecture": summ.lecture.model_dump(),
            }

            # Reactivate A via the real reconciliation path (the API-level
            # duplicate guard would refuse a second ACTIVE same-key event;
            # the DB allows it and the reconciler handles it).
            event_a.active = True
            await db.flush()
            await sync.sync_event(event_a)
            await db.flush()

            extras = await _extras(db, subject.id)
            hist = _hist_shape(await att.get_history(student, subject_code=SUBJECT_CODE))
            summ = await att.get_summary(student.id, subject.id, SUBJECT_CODE,
                                         institution_today())
            after_a_back = {
                "extra_count": len(extras),
                "same_ids": {s.id for s in extras} == {s_a.id, s_b.id},
                "extra_statuses": sorted(str(i["status"])
                                         for i in hist["extra_items"]),
                "missed": hist["summary"]["missed"],
                "attended": hist["summary"]["attended"],
                "lecture": summ.lecture.model_dump(),
            }
            return {"after_a_off": after_a_off, "after_a_back": after_a_back}
        finally:
            await session.rollback()


def test_two_events_identity_separated_logical_participation():
    before = _run(_canonical_counts())
    data = _run(_scenario_two_events())
    assert _run(_canonical_counts()) == before

    off, back = data["after_a_off"], data["after_a_back"]
    # A deactivated -> exactly B (ATTENDED) participates; A's MISSED vanishes.
    assert off["extra_statuses"] == ["AttendanceStatus.ATTENDED"]
    assert off["missed"] == 0 and off["attended"] == 1
    assert off["lecture"] == {"total": 1, "attended": 1, "missed": 0, "pending": 0}
    # A reactivated -> its SAME session participates again; no duplicate.
    assert back["extra_count"] == 2 and back["same_ids"]
    assert back["extra_statuses"] == [
        "AttendanceStatus.ATTENDED", "AttendanceStatus.MISSED"]
    assert back["missed"] == 1 and back["attended"] == 1
    assert back["lecture"] == {"total": 2, "attended": 1, "missed": 1, "pending": 0}


async def _scenario_legacy_active():
    """M: a legacy NULL-provenance extra with is_deactivated=false stays
    logically active; no provenance is ever invented."""
    tag = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            db = _RollbackSession(session)
            subject, students, admin, section = await _chain(db, tag)
            student = students[0]
            att = AttendanceService(db)

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

            # Pure read-side contract: NO synchronizer pass runs here (the
            # write-side marking of unclaimed legacy rows on reconciliation is
            # covered by the foundation tests). The read layer must treat
            # is_deactivated=false as a fully logical occurrence regardless of
            # provenance — no backfill, no inference.
            hist = _hist_shape(await att.get_history(student, subject_code=SUBJECT_CODE))
            row = (await db.execute(
                select(ClassSession).where(ClassSession.id == legacy.id))).scalars().first()
            return {
                "extra_items": hist["extra_items"],
                "summary_missed": hist["summary"]["missed"],
                "deactivated": row.is_deactivated,
                "source_null": row.source_event_id is None,
                "record_exists": (await db.execute(
                    select(AttendanceRecord)
                    .where(AttendanceRecord.class_session_id == legacy.id))).scalars().first() is not None,
            }
        finally:
            await session.rollback()


def test_legacy_null_provenance_extra_remains_logically_active():
    before = _run(_canonical_counts())
    data = _run(_scenario_legacy_active())
    assert _run(_canonical_counts()) == before

    assert data["extra_items"] == [{"status": "AttendanceStatus.MISSED",
                                    "is_cancelled": False}]
    assert data["summary_missed"] == 1
    assert data["deactivated"] is False
    assert data["source_null"], "legacy provenance must never be invented"
    assert data["record_exists"]
