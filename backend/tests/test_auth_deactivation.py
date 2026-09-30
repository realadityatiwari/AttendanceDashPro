"""Phase 2A (H-2) — deactivated-user access boundaries.

The deactivation kill switch, covered at the dependency/service boundaries:

- active user + valid access token -> get_current_user returns the user;
- deactivated user + valid access token (issued BEFORE deactivation) -> 401
  from get_current_user (the H-2 fix: no 8h live-token tail);
- deactivated user cannot login -> 403 (pre-existing behavior, unchanged);
- deactivated user cannot refresh -> RefreshTokenError + family revocation
  (pre-existing behavior, unchanged);
- reactivated user regains access with the same token.

DB-free: every boundary accepts its session as a parameter, so the tests
inject a stub session returning constructed rows (same style as
test_registration_enrollment_e2e's sandbox, minus the live database).
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import asyncio
import uuid

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies.deps import get_current_user
from app.api.v1.endpoints.auth import LoginRequest, login
from app.core.security import create_access_token, hash_password
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.refresh_token_service import RefreshTokenError, RefreshTokenService

_PASSWORD = "Str0ngPass!x"


def _run(coro):
    return asyncio.run(coro)


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class _Result:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalars(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _StubSession:
    """Minimal AsyncSession stand-in.

    SELECTs return the constructed rows registered for their target entity;
    UPDATE/DELETE statements (family revocation) yield an empty result.
    `commit()` is counted so the revocation commit can be asserted.
    """

    def __init__(self, by_entity=None):
        self._by_entity = by_entity or {}
        self.commits = 0
        self.added = []

    async def execute(self, stmt, *a, **k):
        try:
            entity = stmt.column_descriptions[0]["entity"]
        except Exception:
            entity = None
        return _Result(self._by_entity.get(entity, []))

    async def commit(self):
        self.commits += 1

    async def flush(self):
        pass

    def add(self, row):
        self.added.append(row)


def _make_user(*, is_active=True, roll_number="2222222222222"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        roll_number=roll_number,
        hashed_password=hash_password(_PASSWORD),
        is_active=is_active,
    )


def _access_token(user) -> str:
    return create_access_token(subject=str(user.id), roll_number=user.roll_number)


def _refresh_row(user):
    return SimpleNamespace(
        id=uuid.uuid4(),
        family_id=uuid.uuid4(),
        user_id=user.id,
        token_hash="hashed-secret",
        is_used=False,
        is_revoked=False,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )


# ── get_current_user (the H-2 fix) ──────────────────────────────────────────

def test_active_user_with_valid_token_passes():
    user = _make_user(is_active=True)
    db = _StubSession({User: [user]})
    result = _run(get_current_user(credentials=_credentials(_access_token(user)), db=db))
    assert result is user


def test_deactivated_user_with_valid_token_rejected_401():
    user = _make_user(is_active=False)
    token = _access_token(user)  # issued while the account was still active
    db = _StubSession({User: [user]})
    with pytest.raises(HTTPException) as exc:
        _run(get_current_user(credentials=_credentials(token), db=db))
    assert exc.value.status_code == 401


def test_reactivated_user_gains_access_again_with_same_token():
    user = _make_user(is_active=False)
    token = _access_token(user)
    db = _StubSession({User: [user]})
    with pytest.raises(HTTPException) as exc:
        _run(get_current_user(credentials=_credentials(token), db=db))
    assert exc.value.status_code == 401

    user.is_active = True  # reactivated by an admin
    assert _run(get_current_user(credentials=_credentials(token), db=db)) is user


def test_missing_user_still_401():
    token = _access_token(_make_user())
    db = _StubSession({})
    with pytest.raises(HTTPException) as exc:
        _run(get_current_user(credentials=_credentials(token), db=db))
    assert exc.value.status_code == 401


# ── login / refresh boundaries (unchanged behavior) ─────────────────────────

def test_deactivated_user_cannot_login_403():
    user = _make_user(is_active=False)
    db = _StubSession({User: [user]})
    with pytest.raises(HTTPException) as exc:
        _run(
            login(
                LoginRequest(roll_number=user.roll_number, password=_PASSWORD),
                response=SimpleNamespace(set_cookie=lambda *a, **k: None),
                db=db,
                _=None,
            )
        )
    assert exc.value.status_code == 403


def test_deactivated_user_cannot_refresh_and_family_is_revoked():
    user = _make_user(is_active=False)
    row = _refresh_row(user)
    db = _StubSession({RefreshToken: [row], User: [user]})
    with pytest.raises(RefreshTokenError) as exc:
        _run(RefreshTokenService(db).rotate("raw-refresh-secret"))
    assert exc.value.reuse_detected is False
    # `_revoke_family` executed and committed before raising.
    assert db.commits >= 1


def test_active_user_refresh_still_rotates_normally():
    user = _make_user(is_active=True)
    row = _refresh_row(user)
    db = _StubSession({RefreshToken: [row], User: [user]})
    rotated_user, raw_new, new_row = _run(RefreshTokenService(db).rotate("raw-refresh-secret"))
    assert rotated_user is user
    assert isinstance(raw_new, str) and raw_new
    assert new_row.family_id == row.family_id
    assert len(db.added) == 1
    assert db.commits >= 1
