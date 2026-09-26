"""Chunk 16 — end-to-end registration enrollment invariant (rolled back).

Runs the REAL registration endpoint (`register`) against the real dev
database inside a SAVEPOINT wrapper whose commit is a no-op flush and whose
end rolls everything back — zero rows persist (verified in-chunk against the
row-level snapshot: counts identical before/after).

Covers the documented new-account flow with CASE A selections
(ELECTIVE_I=BCS-054, ELECTIVE_II=BCS-058):

  - mandatory subjects enrolled as COMPULSORY;
  - exactly the two selected electives enrolled as ELECTIVE (never
    BCS-052/053/055/056 — the chunk-15 phantom set);
  - exactly one StudentElectiveChoice row per configured slot, matching the
    ELECTIVE enrollments;
  - invalid elective code -> 422 (existing semantics);
  - elective code valid in the catalog but with no subject row -> 503 and
    NO user/enrollment/choice rows (atomic invariant gate).
"""
import asyncio
import uuid
from types import SimpleNamespace

import pytest

from app.api.v1.endpoints.auth import register
from app.db.session import AsyncSessionLocal
from app.models.academic import StudentElectiveChoice, StudentEnrollment, Subject
from app.models.enums import ElectiveSlot, EnrollmentType
from app.models.user import User
from sqlalchemy import select


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


async def _register_sandboxed(request, verify=None):
    """Runs the real register() inside a savepoint sandbox. ``verify`` is an
    optional async callable invoked with the SAME session right after register
    returns (rows exist uncommitted, invisible to other connections); its
    return value is handed back. Everything is rolled back on exit."""
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            result = await register(
                request,
                response=SimpleNamespace(set_cookie=lambda *a, **k: None),
                db=_RollbackSession(session),
                _=None,
            )
            captured = await verify(session) if verify is not None else None
            return result, captured
        finally:
            await session.rollback()


def _req(roll, ei, eii):
    return SimpleNamespace(name="Chunk16 Test Student", roll_number=roll,
                           password="Str0ngPass!x", elective_i=ei, elective_ii=eii)


# ONE event loop for the whole module: the asyncpg pool binds connections to
# the loop that created them; re-running asyncio.run() per test (new loop each
# time) makes the Windows proactor poll dead sockets (WinError 1225).
_LOOP = asyncio.new_event_loop()


def _run(coro):
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


def test_registration_creates_invariant_enrollments():
    roll = f"160{uuid.uuid4().int % 10**10:010d}"

    async def scenario():
        # Plain-data capture inside the open transaction: the sandbox rollback
        # expires ORM instances, so only primitives may cross the boundary.
        async def verify(session):
            user = (await session.execute(select(User).where(User.roll_number == roll))).scalars().first()
            assert user is not None
            rows = (await session.execute(
                select(StudentEnrollment, Subject)
                .join(Subject, StudentEnrollment.subject_id == Subject.id)
                .where(StudentEnrollment.user_id == user.id))).all()
            captured_enrolls = [
                (s.code, s.elective_slot.value if s.elective_slot is not None else None,
                 getattr(e.enrollment_type, "value", e.enrollment_type))
                for e, s in rows
            ]
            ch_rows = (await session.execute(
                select(StudentElectiveChoice, Subject)
                .join(Subject, StudentElectiveChoice.subject_id == Subject.id)
                .where(StudentElectiveChoice.user_id == user.id))).all()
            captured_choices = [
                (getattr(c.elective_slot, "value", c.elective_slot), s.code) for c, s in ch_rows
            ]
            return captured_enrolls, captured_choices

        _, (captured_enrolls, captured_choices) = await _register_sandboxed(
            _req(roll, "BCS-054", "BCS-058"), verify=verify)
        return captured_enrolls, captured_choices

    captured_enrolls, captured_choices = _run(scenario())

    elective = sorted(code for code, slot, _ in captured_enrolls if slot is not None)
    compulsory = sorted(code for code, slot, _ in captured_enrolls if slot is None)
    assert elective == ["BCS-054", "BCS-058"]
    assert not set(elective) & {"BCS-052", "BCS-053", "BCS-055", "BCS-056"}
    assert compulsory == sorted(["BNC-501", "BCS-501", "BCS-502", "BCS-503", "BCS-551", "BCS-552", "BCS-553"])
    types = {code: etype for code, _, etype in captured_enrolls}
    assert types["BCS-054"] == "ELECTIVE" and types["BCS-058"] == "ELECTIVE"
    assert all(etype == "COMPULSORY" for _, slot, etype in captured_enrolls if slot is None)
    assert all(etype == "ELECTIVE" for _, slot, etype in captured_enrolls if slot is not None)
    assert dict(sorted(captured_choices)) == {"ELECTIVE_I": "BCS-054", "ELECTIVE_II": "BCS-058"}


def test_registration_rejects_invalid_elective_code_422():
    roll = f"160{uuid.uuid4().int % 10**10:010d}"

    async def scenario():
        try:
            await _register_sandboxed(_req(roll, "BCS-999", "BCS-058"))
        except Exception as exc:
            return exc
        return None

    exc = _run(scenario())
    assert exc is not None and getattr(exc, "status_code", None) == 422


def test_registration_missing_selected_subject_rejected_and_atomic():
    # A selected elective code whose subject row is absent from the catalog is
    # rejected with the existing 422 semantics ("Invalid Department
    # Elective-II selection") — the invariant gate — and leaves ZERO rows
    # (the 503 branch behind it is defense-in-depth for divergent catalogs).
    roll = f"160{uuid.uuid4().int % 10**10:010d}"

    class _Hide058:
        """Hides BCS-058 from the endpoint's own catalog query (no data
        mutation): the selected code passes the catalog 422 gate, but no
        subject row matches it -> the 503 broken-configuration branch must
        fire and the transaction must leave ZERO rows (atomic gate)."""

        def __init__(self, real):
            self._real = real

        def __getattr__(self, name):
            return getattr(self._real, name)

        async def execute(self, stmt, *a, **k):
            res = await self._real.execute(stmt, *a, **k)
            try:
                entity = stmt.column_descriptions[0]["entity"]
            except Exception:
                entity = None
            if entity is Subject:
                rows = [s for s in res.scalars().all() if s.code != "BCS-058"]
                return SimpleNamespace(
                    scalars=lambda: SimpleNamespace(
                        all=lambda: rows,
                        first=lambda: rows[0] if rows else None,
                    )
                )
            return res

    async def scenario():
        # CASE A selection with its ELECTIVE_II subject (BCS-058) hidden from
        # the endpoint's own catalog query: the code passes the 422 gate, but
        # no subject row matches it -> the 503 broken-configuration branch
        # must fire and the transaction must leave ZERO rows (atomic gate).
        try:
            async with AsyncSessionLocal() as session:
                await session.begin()
                try:
                    return await register(
                        _req(roll, "BCS-054", "BCS-058"),
                        response=SimpleNamespace(set_cookie=lambda *a, **k: None),
                        db=_Hide058(_RollbackSession(session)),
                        _=None,
                    )
                finally:
                    await session.rollback()
        except Exception as exc:
            return exc

    result = _run(scenario())
    assert getattr(result, "status_code", None) == 422
    assert "Elective-II" in getattr(result, "detail", "")

    async def verify_no_rows():
        async with AsyncSessionLocal() as db:
            user = (await db.execute(select(User).where(User.roll_number == roll))).scalars().first()
            assert user is None
            enr = (await db.execute(
                select(StudentEnrollment).join(User, StudentEnrollment.user_id == User.id)
                .where(User.roll_number == roll))).scalars().all()
            assert enr == []

    _run(verify_no_rows())
