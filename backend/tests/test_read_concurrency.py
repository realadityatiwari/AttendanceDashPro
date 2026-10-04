"""Batch 3C — safe DB round-trip parallelization: grouping + equivalence tests.

These tests run against the LOCAL DEV DATABASE (the repo's documented
split: pure-function tests run anywhere; DB-backed verification runs against
the dev database — same convention as the other DB-backed test modules).

Covered:
  1. run_independent_reads: input-order results, bounded concurrency
     (never more than MAX_CONCURRENT_READ_SESSIONS lanes in flight),
     exception propagation.
  2. get_placement (single-join, Batch 3C) ≡ _get_placement_sequential
     (pre-3C reference) for EVERY user in the dev database, plus an explicit
     subsection-present fixture (created and removed within the test).
  3. get_context (parallel composition) ≡ sequential composition of the
     same loaders on one session.
  4. Unplaced user (section_id NULL): placement resolves nothing without
     error, subsection-independent behavior preserved.
"""

import asyncio
from uuid import uuid4

import pytest

from sqlalchemy import select, text

from app.db.session import AsyncSessionLocal, engine
from app.models.user import User, Subsection
from app.models.academic import StudentElectiveChoice
from app.core.security import hash_password
from app.services.read_concurrency import (
    MAX_CONCURRENT_READ_SESSIONS,
    run_independent_reads,
)
from app.services.student_context_service import StudentContextService


# Single module-scoped event loop: the global engine's asyncpg pool binds
# connections to the loop that created them, so every DB test in this module
# must run on ONE loop (production runs a single long-lived loop too). Using
# asyncio.run per test would recycle the loop under live pooled connections.
_loop = asyncio.new_event_loop()


def _run(coro):
    return _loop.run_until_complete(coro)


@pytest.fixture(scope="module", autouse=True)
def _loop_lifecycle():
    yield
    try:
        _loop.run_until_complete(engine.dispose())
    except Exception:
        pass
    _loop.close()


def _db_available():
    try:
        asyncio.get_event_loop_policy()
        return True
    except Exception:
        return False


async def _all_users(db):
    return (await db.execute(select(User).order_by(User.roll_number))).scalars().all()


# ---------------------------------------------------------------------------
# 1. helper semantics
# ---------------------------------------------------------------------------

async def _probe_lane(session, delay, counter):
    counter["active"] += 1
    counter["peak"] = max(counter["peak"], counter["active"])
    try:
        await session.execute(text("SELECT 1"))
        await asyncio.sleep(delay)
        return counter["tag"]
    finally:
        counter["active"] -= 1


def test_results_preserve_input_order():
    async def main():
        async with AsyncSessionLocal() as db:
            users = (await db.execute(select(User).order_by(User.roll_number).limit(4))).scalars().all()

            async def lane(s, uid):
                return (await s.execute(select(User.roll_number).where(User.id == uid))).scalar_one()

            results = await run_independent_reads([lambda s, uid=u.id: lane(s, uid) for u in users])
            assert results == [u.roll_number for u in users]
    _run(main())


def test_concurrency_is_bounded():
    async def main():
        counter = {"active": 0, "peak": 0, "tag": "x"}
        lanes = [lambda s: _probe_lane(s, 0.05, counter) for _ in range(10)]
        await run_independent_reads(lanes)
        assert counter["peak"] <= MAX_CONCURRENT_READ_SESSIONS
    _run(main())


def test_exception_in_a_lane_propagates():
    async def main():
        async def boom(s):
            raise RuntimeError("lane failure")
        async def ok(s):
            return 1
        with pytest.raises(RuntimeError):
            await run_independent_reads([ok, boom, ok])
    _run(main())


def test_empty_group_returns_empty():
    assert asyncio.run(run_independent_reads([])) == []


# ---------------------------------------------------------------------------
# 2. placement: single-join ≡ sequential reference (all users + subsections)
# ---------------------------------------------------------------------------

async def _compare_placement_for(db, user, service):
    old = await service._get_placement_sequential(user)
    # new path on a FRESH session (as production lanes do)
    async with AsyncSessionLocal() as side:
        new = await StudentContextService(side).get_placement(user)
    assert old.model_dump() == new.model_dump(), user.roll_number
    return old


def test_placement_equivalence_all_users_and_subsection_cases():
    async def main():
        subsection_row_id = None
        try:
            async with AsyncSessionLocal() as db:
                users = await _all_users(db)
                assert users, "dev DB has no users"
                # NULL-subsection case is the baseline for every user; then
                # attach a subsection to ONE user for the present case.
                section = (await db.execute(select(User.section_id).where(User.roll_number == "MEAS0000001"))).scalar_one()
                if section is not None:
                    sub = Subsection(id=uuid4(), name="MEAS subsection", section_id=section)
                    db.add(sub)
                    await db.flush()
                    meas = (await db.execute(select(User).where(User.roll_number == "MEAS0000001"))).scalars().first()
                    meas.subsection_id = sub.id
                    subsection_row_id = sub.id
                    await db.commit()

                for user in await _all_users(db):
                    await _compare_placement_for(db, user, StudentContextService(db))
        finally:
            # restore baseline: detach the fixture user + drop the fixture row
            async with AsyncSessionLocal() as db:
                if subsection_row_id is not None:
                    meas = (await db.execute(select(User).where(User.roll_number == "MEAS0000001"))).scalars().first()
                    meas.subsection_id = None
                    sub = await db.get(Subsection, subsection_row_id)
                    if sub is not None:
                        await db.delete(sub)
                    await db.commit()
    _run(main())


def test_placement_unplaced_user_no_subsection():
    async def main():
        async with AsyncSessionLocal() as db:
            ghost = User(roll_number=f"MEASGHOST{uuid4().hex[:6]}", name="ghost",
                         section_id=None, subsection_id=None)
            db.add(ghost)
            await db.flush()
            try:
                svc = StudentContextService(db)
                old = await svc._get_placement_sequential(ghost)
                new = await svc.get_placement(ghost)
                assert old.model_dump() == new.model_dump()
                assert new.is_placed is False and new.section_id is None
            finally:
                await db.delete(ghost)
                await db.commit()
    _run(main())


# ---------------------------------------------------------------------------
# 3. get_context parallel ≡ sequential composition
# ---------------------------------------------------------------------------

def test_get_context_parallel_matches_sequential_composition():
    async def main():
        async with AsyncSessionLocal() as db:
            user = (await db.execute(select(User).where(User.roll_number == "MEAS0000001"))).scalars().first()
            if user is None:
                pytest.skip("measurement user not present")
            svc = StudentContextService(db)
            # sequential composition (pre-3C structure) on one session
            seq = StudentContextService.__new__(StudentContextService)
            seq._db = db
            ctx_seq = await svc.get_placement(user)
            await seq._load_enrollments(db, user.id, ctx_seq)
            await seq._load_elective_choices(db, user.id, ctx_seq)
            await seq._load_first_quiz_date(db, user.id, ctx_seq)
            # parallel composition (production path)
            ctx_par = await svc.get_context(user)
            assert ctx_seq.model_dump() == ctx_par.model_dump()
    _run(main())
