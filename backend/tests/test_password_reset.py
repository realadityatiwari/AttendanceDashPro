"""Stage 3A — admin-assisted password recovery (single-use reset tokens).

Two layers, matching the repo's established split:

1. **DB-free** unit tests (stub sessions): request policy, the generic
   failure contract, one-time disclosure, no-secret-in-logs, route auth /
   rate-limit wiring, and password-hash exchange through the canonical
   verifier.
2. **DB-backed sandbox** tests (real dev database, SAVEPOINT wrapper whose
   ``commit`` is a flush and which always rolls back): hash-at-rest,
   issuance invalidation of prior tokens, expiry, reuse, concurrent
   redemption (the one genuinely-committed test, with self-cleaning temp
   rows), atomic rollback, and the full administrative scope matrix
   (HEAD / CLASS / ELECTIVE / SUBSECTION / out-of-scope / nonexistent).

No raw token, password, or hash is ever asserted to appear in logs or
responses.
"""
import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.api.v1.endpoints import admin as admin_endpoint
from app.api.v1.endpoints import auth as auth_endpoint
from app.api.v1.endpoints.admin import issue_student_password_reset
from app.api.v1.endpoints.auth import (
    ResetPasswordRequest,
    reset_password,
    validate_password_policy,
)
from app.core.security import hash_password, verify_password
from app.db.session import AsyncSessionLocal, engine
from app.models.academic import StudentElectiveChoice, Subject
from app.models.enums import AdminRole, ElectiveSlot, UserRole
from app.models.password_reset_token import PasswordResetToken
from app.models.user import Section, Subsection, User
from app.schemas.admin_students import PasswordResetIssuance
from app.services.admin_student_service import AdminStudentService
from app.services.password_reset_service import PasswordResetError, PasswordResetService

VALID_PW = "NewPassw0rd1"
VALID_PW2 = "Another1Pass"


def _run(coro):
    return asyncio.run(coro)


# ────────────────────────────────────────────────────────────────────────
# 1. Request policy / schema
# ────────────────────────────────────────────────────────────────────────

def test_reset_request_rejects_short_password():
    with pytest.raises(ValidationError):
        ResetPasswordRequest(reset_token="t", new_password="short1")


def test_reset_request_rejects_missing_letter_or_digit():
    with pytest.raises(ValidationError):
        ResetPasswordRequest(reset_token="t", new_password="NoDigitsHere")
    with pytest.raises(ValidationError):
        ResetPasswordRequest(reset_token="t", new_password="12345678")


def test_reset_request_rejects_over_128():
    with pytest.raises(ValidationError):
        ResetPasswordRequest(reset_token="t", new_password="a1" * 65)


def test_reset_request_accepts_valid_and_carries_only_token_and_password():
    req = ResetPasswordRequest(reset_token="abc", new_password=VALID_PW)
    assert set(req.model_fields_set) == {"reset_token", "new_password"}
    # The recovery policy is the SHARED backend-authoritative function.
    assert validate_password_policy(VALID_PW) == VALID_PW


# ────────────────────────────────────────────────────────────────────────
# 2. Generic redemption failure + no secrets (DB-free, stub session)
# ────────────────────────────────────────────────────────────────────────

class _StubSession:
    def __init__(self, fail: bool = False):
        self.commits = 0
        self.rollbacks = 0
        self._fail = fail

    async def execute(self, stmt, *a, **k):
        # Redemption lookup returns no row -> unknown token path.
        scalars = SimpleNamespace(first=lambda: None)
        return SimpleNamespace(scalars=lambda: scalars, rowcount=0)

    async def commit(self):
        self.commits += 1
        if self._fail:
            raise RuntimeError("db down")

    async def rollback(self):
        self.rollbacks += 1

    async def flush(self):
        pass


def test_reset_endpoint_unknown_token_returns_generic_400():
    db = _StubSession()
    with pytest.raises(HTTPException) as exc:
        _run(reset_password(
            request=ResetPasswordRequest(reset_token="nope", new_password=VALID_PW),
            db=db, _=None,
        ))
    assert exc.value.status_code == 400
    # Consistent generic detail — never reveals whether the token/account exists.
    assert exc.value.detail == "Invalid or expired reset token"
    assert db.rollbacks == 1
    assert db.commits == 0


def test_reset_endpoint_response_and_error_contain_no_secrets():
    db = _StubSession()
    with pytest.raises(HTTPException) as exc:
        _run(reset_password(
            request=ResetPasswordRequest(reset_token="tok-xyz", new_password=VALID_PW),
            db=db, _=None,
        ))
    serialized = f"{exc.value.detail}"
    assert "tok-xyz" not in serialized and VALID_PW not in serialized


def test_reset_endpoint_returns_message_without_creating_a_session():
    # Successful path via a service stub: assert the JSON payload only.
    from app.services import password_reset_service as prs

    original = prs.PasswordResetService.redeem

    async def _ok(self, raw, new):
        return SimpleNamespace(id=uuid.uuid4())

    prs.PasswordResetService.redeem = _ok
    try:
        db = _StubSession()
        result = _run(reset_password(
            request=ResetPasswordRequest(reset_token="tok", new_password=VALID_PW),
            db=db, _=None,
        ))
    finally:
        prs.PasswordResetService.redeem = original

    assert result == {"message": "Password updated"}
    assert db.commits == 1
    # No token/password/hash leaks into the response envelope.
    assert "tok" not in repr(result) and VALID_PW not in repr(result)


def test_reset_endpoint_commit_failure_is_503_and_rolls_back():
    from app.services import password_reset_service as prs

    original = prs.PasswordResetService.redeem

    async def _ok(self, raw, new):
        return SimpleNamespace(id=uuid.uuid4())

    prs.PasswordResetService.redeem = _ok
    try:
        db = _StubSession(fail=True)
        with pytest.raises(HTTPException) as exc:
            _run(reset_password(
                request=ResetPasswordRequest(reset_token="tok", new_password=VALID_PW),
                db=db, _=None,
            ))
    finally:
        prs.PasswordResetService.redeem = original
    assert exc.value.status_code == 503
    assert db.rollbacks == 1


# ────────────────────────────────────────────────────────────────────────
# 3. Issuance endpoint wiring / response contract (DB-free)
# ────────────────────────────────────────────────────────────────────────

def test_issue_endpoint_returns_raw_token_once_and_expiry(monkeypatch):
    expiry = datetime.now(timezone.utc) + timedelta(minutes=60)
    captured = {}

    async def _fake_issue(self, user, student_id):
        captured["admin"] = user.id
        captured["student"] = student_id
        return "RAW-TOKEN-abc", expiry

    monkeypatch.setattr(AdminStudentService, "issue_password_reset", _fake_issue)

    admin = SimpleNamespace(id=uuid.uuid4())
    student_id = uuid.uuid4()
    result = _run(issue_student_password_reset(
        student_id=student_id, current_user=admin, db=_StubSession(), _=None,
    ))

    assert isinstance(result, PasswordResetIssuance)
    assert result.reset_token == "RAW-TOKEN-abc"
    assert result.expires_at == expiry
    assert captured == {"admin": admin.id, "student": student_id}


def test_admin_issue_route_requires_admin_auth_and_is_rate_limited():
    route = next(
        r for r in admin_endpoint.router.routes
        if getattr(r, "path", "") == "/students/{student_id}/password-reset"
        and "POST" in getattr(r, "methods", set())
    )
    dep_names = {d.call.__name__ for d in route.dependant.dependencies}
    assert "require_any_admin" in dep_names
    assert "_dep" in dep_names  # rate_limit(...) inner dependency


def test_reset_route_is_public_and_rate_limited():
    route = next(
        r for r in auth_endpoint.router.routes
        if getattr(r, "path", "") == "/reset-password" and "POST" in getattr(r, "methods", set())
    )
    dep_names = {d.call.__name__ for d in route.dependant.dependencies}
    # No authentication dependency: the token is the recovery proof.
    assert "get_current_user" not in dep_names
    assert "_dep" in dep_names


# ────────────────────────────────────────────────────────────────────────
# 4. DB-backed service behaviour (sandboxed; always rolled back)
# ────────────────────────────────────────────────────────────────────────

_LOOP = asyncio.new_event_loop()


def _dbrun(coro):
    return _LOOP.run_until_complete(coro)


@pytest.fixture(scope="module", autouse=True)
def _loop_lifecycle():
    yield
    try:
        _LOOP.run_until_complete(engine.dispose())
    except Exception:
        pass
    _LOOP.close()


class _RollbackSession:
    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    async def commit(self):
        await self._real.flush()

    async def rollback(self):
        await self._real.rollback()


async def _admin_and_students(session):
    admin = (await session.execute(select(User).where(User.role == UserRole.ADMIN))).scalars().first()
    students = (await session.execute(select(User).where(User.role == UserRole.STUDENT).limit(2))).scalars().all()
    assert admin is not None and len(students) >= 2
    return admin, students[0], students[1]


def _scenario(fn):
    async def runner():
        async with AsyncSessionLocal() as session:
            await session.begin()
            try:
                return await fn(session)
            finally:
                await session.rollback()
    return _dbrun(runner())


def test_service_persists_only_the_hash_and_returns_raw_once():
    async def body(session):
        admin, student, _ = await _admin_and_students(session)
        svc = PasswordResetService(_RollbackSession(session))
        raw, row = await svc.issue(student, admin)
        assert row.token_hash == hashlib.sha256(raw.encode()).hexdigest()
        assert row.token_hash != raw
        assert len(row.token_hash) == 64
        assert row.user_id == student.id and row.issued_by_id == admin.id
        assert row.redeemed_at is None and row.is_revoked is False
        # The raw secret is not stored anywhere on the row.
        assert raw not in (row.token_hash or "")
    _scenario(body)


def test_service_issuance_invalidates_prior_outstanding_token():
    async def body(session):
        admin, student, _ = await _admin_and_students(session)
        svc = PasswordResetService(_RollbackSession(session))
        raw1, row1 = await svc.issue(student, admin)
        raw2, row2 = await svc.issue(student, admin)
        first = (await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.id == row1.id)
        )).scalars().first()
        second = (await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.id == row2.id)
        )).scalars().first()
        assert first.is_revoked is True
        assert second.is_revoked is False

        # The stale raw token can no longer be redeemed...
        with pytest.raises(PasswordResetError):
            await svc.redeem(raw1, VALID_PW)
        # ...but the fresh one can.
        user = await svc.redeem(raw2, VALID_PW)
        assert verify_password(VALID_PW, user.hashed_password)
    _scenario(body)


def test_service_rejects_expired_token_without_touching_password():
    async def body(session):
        admin, student, _ = await _admin_and_students(session)
        svc = PasswordResetService(_RollbackSession(session))
        before = student.hashed_password
        raw, row = await svc.issue(student, admin)
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.flush()

        with pytest.raises(PasswordResetError):
            await svc.redeem(raw, VALID_PW)
        assert student.hashed_password == before
        assert row.redeemed_at is None
    _scenario(body)


def test_service_reuse_fails_second_time_and_does_not_reopen():
    async def body(session):
        admin, student, _ = await _admin_and_students(session)
        svc = PasswordResetService(_RollbackSession(session))
        raw, row = await svc.issue(student, admin)
        await svc.redeem(raw, VALID_PW)
        assert verify_password(VALID_PW, student.hashed_password)
        with pytest.raises(PasswordResetError):
            await svc.redeem(raw, VALID_PW2)
        # Still the first new password — the failed reuse changed nothing.
        assert verify_password(VALID_PW, student.hashed_password)
    _scenario(body)


def test_service_unknown_token_is_rejected_generically():
    async def body(session):
        svc = PasswordResetService(_RollbackSession(session))
        with pytest.raises(PasswordResetError) as exc:
            await svc.redeem("not-a-real-token", VALID_PW)
        assert "not-a-real-token" not in str(exc.value)
    _scenario(body)


def test_service_redeem_updates_only_target_user_hash():
    async def body(session):
        admin, student, other = await _admin_and_students(session)
        other_before = other.hashed_password
        svc = PasswordResetService(_RollbackSession(session))
        raw, _ = await svc.issue(student, admin)
        await svc.redeem(raw, VALID_PW)
        assert verify_password(VALID_PW, student.hashed_password)
        assert other.hashed_password == other_before
    _scenario(body)


def test_service_no_secret_in_logs(caplog, monkeypatch):
    async def body(session):
        admin, student, _ = await _admin_and_students(session)
        svc = PasswordResetService(_RollbackSession(session))
        raw, row = await svc.issue(student, admin)
        await svc.redeem(raw, VALID_PW)
        return raw

    with caplog.at_level(logging.DEBUG):
        raw = _scenario(body)
    blob = "\n".join(r.getMessage() for r in caplog.records) + "\n".join(
        str(r.__dict__) for r in caplog.records
    )
    assert raw not in blob
    assert VALID_PW not in blob
    assert "pbkdf2" not in blob


# ────────────────────────────────────────────────────────────────────────
# 5. Concurrent redemption (genuinely committed; self-cleaning temp rows)
# ────────────────────────────────────────────────────────────────────────

def test_concurrent_redemption_allows_exactly_one_winner():
    async def scenario():
        token_id = None
        temp_user_id = None
        issuer_id = None
        try:
            # Arrange: a real temp student + committed token (needed so two
            # independent transactions can contend on the same row).
            async with AsyncSessionLocal() as s:
                admin = (await s.execute(
                    select(User).where(User.role == UserRole.ADMIN)
                )).scalars().first()
                issuer_id = admin.id
                temp = User(
                    roll_number=f"t3a{uuid.uuid4().int % 10**10:010d}",
                    name="Stage3A Concurrency",
                    hashed_password=hash_password("Initial1Pass"),
                    role=UserRole.STUDENT,
                )
                s.add(temp)
                await s.flush()
                temp_user_id = temp.id
                raw, row = await PasswordResetService(s).issue(temp, admin)
                token_id = row.id
                await s.commit()

            async def one_attempt(password):
                async with AsyncSessionLocal() as s:
                    try:
                        await PasswordResetService(s).redeem(raw, password)
                        await s.commit()
                        return True
                    except PasswordResetError:
                        await s.rollback()
                        return False

            results = await asyncio.gather(
                one_attempt(VALID_PW), one_attempt(VALID_PW2)
            )
            return results
        finally:
            # Cleanup: remove token + temp user across a fresh transaction.
            async with AsyncSessionLocal() as s:
                if temp_user_id is not None:
                    await s.execute(
                        delete(PasswordResetToken).where(
                            PasswordResetToken.user_id == temp_user_id
                        )
                    )
                    await s.execute(delete(User).where(User.id == temp_user_id))
                await s.commit()

    results = _dbrun(scenario())
    assert sorted(results) == [False, True], results


# ────────────────────────────────────────────────────────────────────────
# 6. Administrative scope matrix (DB-backed sandbox)
# ────────────────────────────────────────────────────────────────────────

def _temp_user(role=UserRole.STUDENT, section_id=None, name="Temp"):
    return User(
        roll_number=f"t3a{uuid.uuid4().int % 10**10:010d}",
        name=name,
        hashed_password=hash_password("Temp1Pass!"),
        role=role,
        section_id=section_id,
    )


async def _issue_expect_ok(session, caller, student):
    raw, expiry = await AdminStudentService(_RollbackSession(session)).issue_password_reset(caller, student.id)
    assert isinstance(raw, str) and len(raw) >= 20
    assert expiry > datetime.now(timezone.utc)
    return raw


def _issue_expect_404(session, caller, student_id):
    async def call():
        with pytest.raises(HTTPException) as exc:
            await AdminStudentService(_RollbackSession(session)).issue_password_reset(caller, student_id)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Student not found"
    return call()


def test_head_admin_can_issue_for_any_student():
    async def body(session):
        section = (await session.execute(select(Section).limit(1))).scalars().first()
        head = _temp_user(role=UserRole.ADMIN, name="Head")
        placed = _temp_user(section_id=section.id, name="Placed")
        unplaced = _temp_user(name="Unplaced")
        session.add_all([head, placed, unplaced])
        await session.flush()
        await _issue_expect_ok(session, head, placed)
        await _issue_expect_ok(session, head, unplaced)
    _scenario(body)


def test_class_admin_in_scope_allowed_out_of_scope_404():
    async def body(session):
        section = (await session.execute(select(Section).limit(1))).scalars().first()
        other_section = Section(name=f"TMP-{uuid.uuid4().hex[:6]}", semester_id=section.semester_id)
        session.add(other_section)
        await session.flush()

        caller = _temp_user(name="ClassAdmin")
        session.add(caller)
        await session.flush()
        from app.models.admin_scope import AdminScope
        session.add(AdminScope(user_id=caller.id, role=AdminRole.CLASS_ADMIN, section_id=section.id))

        in_scope = _temp_user(section_id=section.id, name="InScope")
        out_scope = _temp_user(section_id=other_section.id, name="OutScope")
        session.add_all([in_scope, out_scope])
        await session.flush()

        await _issue_expect_ok(session, caller, in_scope)
        await _issue_expect_404(session, caller, out_scope.id)
    _scenario(body)


def test_elective_admin_roster_scope_allowed_outsider_404():
    async def body(session):
        elective = (await session.execute(
            select(Subject).where(Subject.elective_slot == ElectiveSlot.ELECTIVE_I).limit(1)
        )).scalars().first()
        caller = _temp_user(name="ElectiveAdmin")
        in_roster = _temp_user(name="InRoster")
        outsider = _temp_user(name="Outsider")
        session.add_all([caller, in_roster, outsider])
        await session.flush()
        from app.models.admin_scope import AdminScope
        session.add(AdminScope(user_id=caller.id, role=AdminRole.ELECTIVE_ADMIN, subject_id=elective.id))
        session.add(StudentElectiveChoice(
            user_id=in_roster.id, elective_slot=ElectiveSlot.ELECTIVE_I, subject_id=elective.id
        ))
        await session.flush()

        await _issue_expect_ok(session, caller, in_roster)
        await _issue_expect_404(session, caller, outsider.id)
    _scenario(body)


def test_subsection_admin_is_inert_deny():
    async def body(session):
        section = (await session.execute(select(Section).limit(1))).scalars().first()
        subsection = Subsection(name=f"TMP-{uuid.uuid4().hex[:6]}", section_id=section.id)
        session.add(subsection)
        await session.flush()

        caller = _temp_user(name="SubAdmin")
        student = _temp_user(section_id=section.id, name="Student")
        session.add_all([caller, student])
        await session.flush()
        from app.models.admin_scope import AdminScope
        session.add(AdminScope(user_id=caller.id, role=AdminRole.SUBSECTION_ADMIN, subsection_id=subsection.id))
        await session.flush()

        await _issue_expect_404(session, caller, student.id)
    _scenario(body)


def test_student_caller_without_scope_is_404_and_nonexistent_is_404():
    async def body(session):
        section = (await session.execute(select(Section).limit(1))).scalars().first()
        caller = _temp_user(name="PlainStudent")
        student = _temp_user(section_id=section.id, name="Student")
        session.add_all([caller, student])
        await session.flush()
        await _issue_expect_404(session, caller, student.id)
        await _issue_expect_404(session, caller, uuid.uuid4())
    _scenario(body)