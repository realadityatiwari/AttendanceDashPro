"""Phase 2A (H-5) — quiz-cycle date-order validation.

Runtime cycle numbers are derived POSITIONALLY from the effective quiz dates
(`QuizRepository.get_effective_quiz_dates_for_subjects` ranks active QUIZ_DAY
events chronologically), so an out-of-order date edit silently renumbers
cycles across eligibility, QUIZ_APPROACHING keys, and the dashboard. The fix
validates at mutation time: for one (subject, elective_slot),
Q1.date < Q2.date < Q3.date, with equal dates rejected.

Two layers:

1. DB-free: the validator against a stub repository — normal chronology
   accepted; Q2-before-Q1, Q3-before-Q2, Q2-after-Q3, Q1-after-Q2, and equal
   dates rejected; None dates skip; the sibling query is scoped by
   (subject, slot) and excludes the schedule being updated, so elective slots
   validate independently and unrelated subjects never interfere.
2. Real DB: the existing schedule state is valid under the new rule
   (read-only), and the full `update_quiz_schedule` mutation path still
   rejects out-of-order dates and still enforces semester bounds (the sandbox
   session rolls everything back).
"""
from datetime import date, timedelta
from types import SimpleNamespace
import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.academic import Semester
from app.models.enums import ElectiveSlot
from app.schemas.admin_quizzes import UpdateQuizScheduleRequest
from app.services.admin_quiz_service import AdminQuizService, AdminQuizValidationError


def _run(coro):
    return asyncio.run(coro)


def _service(repo):
    svc = AdminQuizService(None)  # constructors only store the session
    svc.repo = repo
    return svc


class _StubQuizRepo:
    """Returns the sibling set registered for (subject_id, elective_slot)."""

    def __init__(self, siblings=None):
        self._siblings = siblings or {}
        self.calls = []

    async def list_sibling_schedules(self, subject_id, elective_slot, exclude_id=None):
        self.calls.append((subject_id, elective_slot, exclude_id))
        return list(self._siblings.get((subject_id, elective_slot), []))


def _sib(cycle_number, d, *, elective_slot=None, subject_id="S", schedule_id=None):
    return SimpleNamespace(
        id=schedule_id or uuid.uuid4(),
        subject_id=subject_id,
        elective_slot=elective_slot,
        date=d,
        quiz_cycle=SimpleNamespace(cycle_number=cycle_number),
    )


def _validate(svc, subject_id, slot, cycle_number, new_date, exclude=None):
    _run(svc._validate_cycle_chronology(
        subject_id, slot, cycle_number, new_date, exclude_schedule_id=exclude
    ))


# ── accepted chronology ─────────────────────────────────────────────────────

def test_normal_chronological_schedule_accepted():
    repo = _StubQuizRepo({("S", None): [
        _sib(1, date(2026, 8, 27)),
        _sib(3, date(2026, 10, 12)),
    ]})
    _validate(_service(repo), "S", None, 2, date(2026, 9, 17))


def test_full_chronological_set_accepted_and_order_independent():
    siblings = [
        _sib(1, date(2026, 8, 27)),
        _sib(3, date(2026, 10, 12)),
    ]
    repo = _StubQuizRepo({("S", None): siblings})
    _validate(_service(repo), "S", None, 2, date(2026, 9, 17))
    # Re-validating each existing date against its siblings (excluding itself,
    # as the real repository does) never raises.
    for s in siblings:
        others = [o for o in siblings if o is not s]
        _validate(_service(_StubQuizRepo({("S", None): others})), "S", None,
                  s.quiz_cycle.cycle_number, s.date, exclude=s.id)


def test_unresolved_date_skips_validation():
    repo = _StubQuizRepo({("S", None): [_sib(1, date(2026, 8, 27))]})
    _validate(_service(repo), "S", None, 2, None)
    assert repo.calls == []  # no sibling query for a dateless mutation


# ── rejected orderings ──────────────────────────────────────────────────────

def test_q2_before_q1_rejected():
    repo = _StubQuizRepo({("S", None): [_sib(1, date(2026, 8, 27))]})
    with pytest.raises(AdminQuizValidationError) as exc:
        _validate(_service(repo), "S", None, 2, date(2026, 8, 20))
    assert "chronological" in exc.value.detail


def test_q3_before_q2_rejected():
    repo = _StubQuizRepo({("S", None): [_sib(2, date(2026, 9, 17))]})
    with pytest.raises(AdminQuizValidationError):
        _validate(_service(repo), "S", None, 3, date(2026, 9, 10))


def test_q2_after_q3_rejected():
    repo = _StubQuizRepo({("S", None): [_sib(3, date(2026, 10, 12))]})
    with pytest.raises(AdminQuizValidationError):
        _validate(_service(repo), "S", None, 2, date(2026, 10, 20))


def test_q1_moved_after_q2_rejected():
    repo = _StubQuizRepo({("S", None): [_sib(2, date(2026, 9, 17))]})
    with pytest.raises(AdminQuizValidationError):
        _validate(_service(repo), "S", None, 1, date(2026, 9, 20))


def test_equal_cycle_dates_rejected():
    for sibling_cycle, new_cycle in ((1, 2), (2, 3), (3, 2)):
        repo = _StubQuizRepo({("S", None): [_sib(sibling_cycle, date(2026, 9, 17))]})
        with pytest.raises(AdminQuizValidationError) as exc:
            _validate(_service(repo), "S", None, new_cycle, date(2026, 9, 17))
        assert "distinct" in exc.value.detail


# ── scoping: slot independence, unrelated subjects, exclusion ──────────────

def test_elective_slots_validate_independently():
    slot_i, slot_ii = ElectiveSlot.ELECTIVE_I, ElectiveSlot.ELECTIVE_II
    repo = _StubQuizRepo({
        ("S1", slot_i): [_sib(1, date(2026, 9, 7), elective_slot=slot_i)],
        ("S1", slot_ii): [_sib(1, date(2026, 11, 1), elective_slot=slot_ii)],
    })
    # 2026-11-01 is ELECTIVE_II's cycle-1 date, but ELECTIVE_I is validated
    # against ELECTIVE_I rows only: accepted, and the query is slot-scoped.
    _validate(_service(repo), "S1", slot_i, 2, date(2026, 11, 1))
    assert repo.calls == [("S1", slot_i, None)]


def test_unrelated_subjects_do_not_interfere():
    other_date = date(2026, 9, 1)
    repo = _StubQuizRepo({
        ("A", None): [],
        ("B", None): [_sib(1, other_date)],
    })
    # The exact date that would be rejected for subject B is accepted for A:
    # B's schedule rows are never consulted.
    _validate(_service(repo), "A", None, 1, other_date)
    assert repo.calls == [("A", None, None)]


def test_exclude_schedule_id_is_passed_through():
    repo = _StubQuizRepo({("A", None): []})
    sid = uuid.uuid4()
    _validate(_service(repo), "A", None, 2, date(2026, 9, 1), exclude=sid)
    assert repo.calls == [("A", None, sid)]


def test_undated_sibling_does_not_constrain():
    repo = _StubQuizRepo({("S", None): [
        _sib(1, None),
        _sib(3, date(2026, 10, 12)),
    ]})
    _validate(_service(repo), "S", None, 2, date(2026, 9, 17))


# ════════════════════════════════════════════════════════════════════════════
# Real DB: existing state valid; mutation path rejects + semester bounds hold
# ════════════════════════════════════════════════════════════════════════════

class _RollbackSession:
    """commit() -> flush; everything rolls back when the scenario ends."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    async def commit(self):
        await self._real.flush()

    async def rollback(self):
        await self._real.rollback()


_LOOP = asyncio.new_event_loop()


def _db_run(coro):
    return _LOOP.run_until_complete(coro)


@pytest.fixture(scope="module", autouse=True)
def _loop_lifecycle():
    yield
    try:
        from app.db.session import engine
        _LOOP.run_until_complete(engine.dispose())
    except Exception:
        pass
    _LOOP.close()


def test_existing_valid_database_state_remains_valid():
    async def scenario():
        async with AsyncSessionLocal() as session:
            svc = AdminQuizService(session)
            schedules = await svc.repo.list_quiz_schedules()
            dated = [s for s in schedules if s.date is not None and s.quiz_cycle is not None]
            for s in dated:
                await svc._validate_cycle_chronology(
                    s.subject_id, s.elective_slot, s.quiz_cycle.cycle_number,
                    s.date, exclude_schedule_id=s.id,
                )
            return len(dated), len(schedules)

    dated_count, schedule_count = _db_run(scenario())
    assert schedule_count >= dated_count >= 6  # seeded scopes validate untouched


def test_update_rejects_out_of_order_date_real_db():
    async def scenario():
        async with AsyncSessionLocal() as session:
            await session.begin()
            try:
                svc = AdminQuizService(_RollbackSession(session))
                schedules = await svc.repo.list_quiz_schedules()
                groups = {}
                for s in schedules:
                    if s.date is not None and s.quiz_cycle is not None:
                        groups.setdefault((s.subject_id, s.elective_slot), []).append(s)
                rows = sorted(
                    (v for v in groups.values() if len(v) >= 2),
                    key=len, reverse=True,
                )[0]
                rows.sort(key=lambda s: s.quiz_cycle.cycle_number)
                lower, higher = rows[0], rows[1]
                bad_date = lower.date - timedelta(days=1)  # higher cycle first
                try:
                    await svc.update_quiz_schedule(
                        None, higher.id, UpdateQuizScheduleRequest(date=bad_date)
                    )
                    return "NO_ERROR"
                except AdminQuizValidationError as exc:
                    return exc.detail
            finally:
                await session.rollback()

    detail = _db_run(scenario())
    assert "chronological" in detail


def test_update_still_enforces_semester_bounds_real_db():
    async def scenario():
        async with AsyncSessionLocal() as session:
            await session.begin()
            try:
                svc = AdminQuizService(_RollbackSession(session))
                schedules = await svc.repo.list_quiz_schedules()
                target = next(
                    s for s in schedules
                    if s.date is not None and s.subject_id is not None
                )
                subject = await svc.repo.get_subject(target.subject_id)
                semester = (await session.execute(
                    select(Semester).where(Semester.id == subject.semester_id)
                )).scalars().first()
                if semester is not None and semester.end_date is not None:
                    bad_date = semester.end_date + timedelta(days=1)
                else:
                    bad_date = semester.start_date - timedelta(days=1)
                try:
                    await svc.update_quiz_schedule(
                        None, target.id, UpdateQuizScheduleRequest(date=bad_date)
                    )
                    return "NO_ERROR"
                except AdminQuizValidationError as exc:
                    return exc.detail
            finally:
                await session.rollback()

    detail = _db_run(scenario())
    assert "semester" in detail
