"""Stage 2 — authenticated password change (`PATCH /api/v1/auth/change-password`).

DB-free, in the style of test_auth_deactivation.py: the endpoint function is
called directly with a stub session and a stub authenticated user. Hashing and
verification run for real (pure functions), so the "new password verifies via
the canonical login verifier" assertions exercise production code.
"""
import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints import auth as auth_endpoint
from app.api.v1.endpoints.auth import ChangePasswordRequest, change_password, login, LoginRequest
from app.core.security import hash_password, verify_password
from app.services.refresh_token_service import RefreshTokenService

OLD = "OldPassw0rd!"
NEW = "NewPassw0rd!"


def _run(coro):
    return asyncio.run(coro)


class _StubSession:
    """Records commits and the statements executed (revocation UPDATE)."""

    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.statements = []

    async def execute(self, stmt, *a, **k):
        self.statements.append(stmt)
        return SimpleNamespace(rowcount=2)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def flush(self):
        pass

    def add(self, row):
        pass


def _user(password=OLD, *, is_active=True):
    return SimpleNamespace(
        id=uuid.uuid4(),
        roll_number="2401220100027",
        name="Student",
        hashed_password=hash_password(password),
        is_active=is_active,
    )


def _change(user, db, current=OLD, new=NEW):
    return _run(
        change_password(
            request=ChangePasswordRequest(current_password=current, new_password=new),
            current_user=user,
            db=db,
            _=None,
        )
    )


# ── Schema / policy ─────────────────────────────────────────────────────────

def test_new_password_rejects_too_short():
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password=OLD, new_password="abc1")


def test_new_password_rejects_missing_digit_and_letter():
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password=OLD, new_password="NoDigitsHere")
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password=OLD, new_password="12345678")


def test_new_password_rejects_over_128():
    with pytest.raises(ValidationError):
        ChangePasswordRequest(current_password=OLD, new_password="a1" * 65)


def test_policy_is_shared_with_registration():
    # The registration validator and the change-password validator must use
    # the SAME function, so the rule cannot drift.
    from app.api.v1.endpoints.auth import RegisterRequest, validate_password_policy

    assert RegisterRequest.model_fields["password"] is not None
    with pytest.raises(ValueError):
        validate_password_policy("short1")
    with pytest.raises(ValidationError):
        RegisterRequest(name="x", roll_number="1" * 13, password="short1",
                        elective_i="A", elective_ii="B")


# ── Success path ────────────────────────────────────────────────────────────

def test_successful_change_updates_hash_and_verifies_with_login_verifier():
    user = _user()
    db = _StubSession()
    result = _change(user, db)

    assert result == {"message": "Password updated"}
    # The NEW password verifies through the canonical login verifier...
    assert verify_password(NEW, user.hashed_password) is True
    # ...and the OLD password no longer does.
    assert verify_password(OLD, user.hashed_password) is False
    assert db.commits == 1


def test_success_response_contains_no_password_or_hash():
    user = _user()
    result = _change(user, _StubSession())
    serialized = repr(result)
    assert NEW not in serialized and OLD not in serialized
    assert "pbkdf2" not in serialized and user.hashed_password not in serialized


def test_success_revokes_this_users_refresh_sessions_in_same_transaction():
    user = _user()
    db = _StubSession()
    _change(user, db)
    # One UPDATE was issued for the revocation, and the single commit covers
    # both the hash update and the revocation (atomic unit of work).
    assert len(db.statements) == 1
    assert db.commits == 1


# ── Failure paths leave the stored credential untouched ─────────────────────

def test_wrong_current_password_rejected_without_change():
    user = _user()
    before = user.hashed_password
    db = _StubSession()
    with pytest.raises(HTTPException) as exc:
        _change(user, db, current="WrongPassw0rd!")
    assert exc.value.status_code == 400  # not 401: must not look like session expiry
    assert user.hashed_password == before
    assert db.commits == 0
    assert db.statements == []  # no revocation either


def test_account_without_password_cannot_change_via_this_endpoint():
    user = _user()
    user.hashed_password = None
    db = _StubSession()
    with pytest.raises(HTTPException) as exc:
        _change(user, db)
    assert exc.value.status_code == 400
    assert db.commits == 0


def test_invalid_new_password_fails_before_any_write():
    user = _user()
    before = user.hashed_password
    db = _StubSession()
    with pytest.raises(ValidationError):
        _change(user, db, new="short")
    assert user.hashed_password == before
    assert db.commits == 0


def test_commit_failure_propagates_and_hash_is_not_persisted_by_endpoint():
    """If the commit fails the endpoint must not swallow the error; the
    transaction is the caller/session's responsibility to roll back."""
    user = _user()

    class _FailingCommit(_StubSession):
        async def commit(self):
            raise RuntimeError("db down")

    with pytest.raises(RuntimeError):
        _change(user, _FailingCommit())


# ── Authorization boundary ──────────────────────────────────────────────────

def test_change_targets_only_the_authenticated_principal():
    me = _user(OLD)
    other = _user(OLD)
    other_before = other.hashed_password
    _change(me, _StubSession())
    assert verify_password(NEW, me.hashed_password)
    assert other.hashed_password == other_before  # untouched


def test_request_schema_accepts_no_target_identifier():
    assert set(ChangePasswordRequest.model_fields) == {"current_password", "new_password"}


def test_change_password_route_requires_authentication():
    route = next(
        r for r in auth_endpoint.router.routes
        if getattr(r, "path", "") == "/change-password" and "PATCH" in getattr(r, "methods", set())
    )
    dep_names = {d.call.__name__ for d in route.dependant.dependencies}
    assert "get_current_user" in dep_names


def test_change_password_is_rate_limited():
    route = next(
        r for r in auth_endpoint.router.routes
        if getattr(r, "path", "") == "/change-password"
    )
    dep_names = {d.call.__name__ for d in route.dependant.dependencies}
    # rate_limit(...) returns the inner `_dep`; the route must depend on one.
    assert "_dep" in dep_names


# ── Revocation semantics (SQL-level) ────────────────────────────────────────

def test_revoke_all_for_user_is_scoped_and_does_not_commit():
    db = _StubSession()
    svc = RefreshTokenService(db)
    count = _run(svc.revoke_all_for_user(uuid.uuid4()))
    assert count == 2
    assert db.commits == 0  # participates in the caller's transaction
    compiled = str(db.statements[0].compile(compile_kwargs={"literal_binds": True}))
    assert "user_id" in compiled and "is_revoked" in compiled


# ── Existing login/registration behavior unchanged ──────────────────────────

class _ResultOf:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _LoginSession:
    def __init__(self, user):
        self._user = user
        self.commits = 0

    async def execute(self, stmt, *a, **k):
        return _ResultOf([self._user] if self._user else [])

    async def commit(self):
        self.commits += 1

    async def flush(self):
        pass

    def add(self, row):
        pass


def _login_as(user, password):
    async def _issue(self, u):
        return "raw", SimpleNamespace()

    original = RefreshTokenService.issue
    RefreshTokenService.issue = _issue
    try:
        return _run(
            login(
                LoginRequest(roll_number=user.roll_number, password=password),
                response=SimpleNamespace(set_cookie=lambda *a, **k: None),
                db=_LoginSession(user),
                _=None,
            )
        )
    finally:
        RefreshTokenService.issue = original


def test_login_accepts_new_password_and_rejects_old_after_change():
    user = _user(OLD)
    _change(user, _StubSession())
    assert _login_as(user, NEW)["token_type"] == "bearer"
    with pytest.raises(HTTPException) as exc:
        _login_as(user, OLD)
    assert exc.value.status_code == 401
