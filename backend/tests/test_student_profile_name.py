"""Stage 1 — self-service profile name update (`PATCH /api/v1/student/me`).

DB-free: the endpoint's two collaborators are stubbed —
  - ``StudentContextService.get_context`` is patched to return a fixed
    academic context (so no database reads occur), and
  - the injected ``AsyncSession`` is a minimal stub whose ``commit``/``refresh``
    are counted.

The authenticated user is passed directly to the endpoint function the same
way ``test_auth_deactivation`` exercises ``get_current_user``/``login`` — no
HTTP server and no live database are required.
"""
import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.v1.endpoints import student as student_endpoint
from app.api.v1.endpoints.student import (
    get_student_profile,
    update_student_profile_name,
)
from app.schemas.student import (
    MAX_DISPLAY_NAME_LENGTH,
    StudentNameUpdateRequest,
)
from app.schemas.student_context import StudentContext


def _run(coro):
    return asyncio.run(coro)


class _StubSession:
    """Minimal AsyncSession stand-in: only commit/refresh are exercised by the
    endpoint (the context read is patched out)."""

    def __init__(self):
        self.commits = 0
        self.refreshed = []

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        self.refreshed.append(obj)


def _make_user(*, name="Original Name"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        roll_number="2401220100027",
        role=SimpleNamespace(value="STUDENT"),
    )


@pytest.fixture(autouse=True)
def _stub_context(monkeypatch):
    """Replace the authoritative context read with a fixed, DB-free context."""
    async def _fake_get_context(self, user):
        return StudentContext(
            user_id=user.id,
            role="STUDENT",
            section_name="CSE-51",
            program="CSE",
            is_placed=True,
        )

    monkeypatch.setattr(
        student_endpoint.StudentContextService,
        "get_context",
        _fake_get_context,
    )


# ── Schema validation (no DB, no endpoint) ──────────────────────────────────

def test_schema_trims_surrounding_whitespace():
    req = StudentNameUpdateRequest(display_name="  Aditya Tiwari  ")
    assert req.display_name == "Aditya Tiwari"


def test_schema_rejects_empty_name():
    with pytest.raises(ValidationError):
        StudentNameUpdateRequest(display_name="")


def test_schema_rejects_whitespace_only_name():
    with pytest.raises(ValidationError):
        StudentNameUpdateRequest(display_name="   \t  ")


def test_schema_rejects_over_length_name():
    with pytest.raises(ValidationError):
        StudentNameUpdateRequest(display_name="a" * (MAX_DISPLAY_NAME_LENGTH + 1))


def test_schema_accepts_exactly_max_length():
    req = StudentNameUpdateRequest(display_name="a" * MAX_DISPLAY_NAME_LENGTH)
    assert len(req.display_name) == MAX_DISPLAY_NAME_LENGTH


# ── Endpoint behavior ───────────────────────────────────────────────────────

def test_authenticated_update_persists_and_returns_profile():
    user = _make_user(name="Original Name")
    db = _StubSession()

    result = _run(
        update_student_profile_name(
            request=StudentNameUpdateRequest(display_name="  New Name  "),
            current_user=user,
            db=db,
        )
    )

    # Only the canonical field changed; unit of work committed once.
    assert user.name == "New Name"
    assert db.commits == 1
    assert db.refreshed == [user]

    # Returned profile uses the existing StudentProfile contract.
    assert result.display_name == "New Name"
    assert result.roll_number == "2401220100027"
    assert result.section_name == "CSE-51"


def test_update_only_touches_authenticated_user():
    # A second user row is never referenced — the endpoint has no target id.
    user = _make_user(name="Only Me")
    other = _make_user(name="Someone Else")
    db = _StubSession()

    _run(
        update_student_profile_name(
            request=StudentNameUpdateRequest(display_name="Renamed"),
            current_user=user,
            db=db,
        )
    )

    assert user.name == "Renamed"
    assert other.name == "Someone Else"


def test_empty_name_is_rejected_before_any_write():
    user = _make_user(name="Original Name")
    db = _StubSession()

    with pytest.raises(ValidationError):
        _run(
            update_student_profile_name(
                request=StudentNameUpdateRequest(display_name="   "),
                current_user=user,
                db=db,
            )
        )

    # No write happened; the name is preserved.
    assert user.name == "Original Name"
    assert db.commits == 0


def test_over_length_name_is_rejected_before_any_write():
    user = _make_user(name="Original Name")
    db = _StubSession()

    with pytest.raises(ValidationError):
        _run(
            update_student_profile_name(
                request=StudentNameUpdateRequest(
                    display_name="a" * (MAX_DISPLAY_NAME_LENGTH + 1)
                ),
                current_user=user,
                db=db,
            )
        )

    assert user.name == "Original Name"
    assert db.commits == 0


# ── Unauthenticated boundary ────────────────────────────────────────────────

def test_get_current_user_rejects_missing_bearer(monkeypatch):
    """Unauthenticated requests fail at the dependency boundary before the
    endpoint body runs. ``HTTPBearer`` raises 403 when no credentials are
    supplied."""
    from fastapi.security import HTTPBearer

    from app.api.dependencies.deps import security

    # HTTPBearer.__call__ is async; no credentials -> 403.
    async def _call():
        return await security(SimpleNamespace(headers={}))

    with pytest.raises(HTTPException) as exc:
        _run(_call())
    assert exc.value.status_code in (401, 403)

    # Sanity: the dependency used by both /me endpoints is the shared bearer.
    assert isinstance(security, HTTPBearer)


# ── Existing sync behavior is unchanged ─────────────────────────────────────

def test_sync_only_fills_empty_name_and_preserves_existing():
    from app.api.v1.endpoints.student import sync_student_profile
    from app.schemas.student import StudentSyncRequest

    # An account that already has a name must NOT be overwritten by sync.
    user = _make_user(name="Existing Name")
    db = _StubSession()
    section = SimpleNamespace(name="CSE-51")
    user.section = section

    result = _run(
        sync_student_profile(
            request=StudentSyncRequest(display_name="Different", roll_number="X"),
            current_user=user,
            db=db,
        )
    )
    assert user.name == "Existing Name"
    assert result.display_name == "Existing Name"