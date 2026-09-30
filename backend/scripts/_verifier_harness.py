"""Shared verifier cleanup harness (Phase 2A, H-4b).

WHY THIS EXISTS
    Verifier fixtures create AcademicEvents through the SAME service/API paths
    as production. ``EventService.create_event`` / ``update_event`` fan out
    ACADEMIC_EVENT notification projections to every affected user — including
    pre-existing real accounts (subject enrollees, elective-slot choosers, and
    all users for global events). When a verifier then HARD-DELETES its
    fixture events (the documented cleanup pattern), those notification rows
    used to survive as orphaned projections (the H-4a pollution origin:
    ``notifications.event_id`` has no FK).

WHAT THIS PROVIDES
    - ``cleanup_fixture_event_notifications(db, event_ids)`` — deletes every
      notification row whose ``event_id`` is one of the fixture's events, for
      ALL users (never only the verifier's own test users). Fixture-scoped by
      exact event id; it can never touch live notifications or other kinds.
    - ``assert_no_orphaned_fixture_notifications(db, event_ids)`` — the
      post-cleanup self-check: asserts zero notification rows still reference
      the fixture events (run AFTER the cleanup commit).

SAFETY / SCOPE
    - Cleanup-only tooling: production notification behavior is untouched.
    - Scoped by exact fixture event ids — no date/type/shape sweeps, no global
      deletes. Deleting for all users is the point: the fixture's projections
      are fixture artifacts regardless of recipient.
    - These scripts never run against production data by design (dev DB only);
      the harness performs no other mutation.
"""
from typing import Iterable, Optional
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


def _normalize_ids(event_ids: Optional[Iterable]) -> list[UUID]:
    """Coerce ids (UUID or str) to a de-duplicated UUID list; skip None."""
    ids: list[UUID] = []
    for value in event_ids or []:
        if value is None:
            continue
        ids.append(value if isinstance(value, UUID) else UUID(str(value)))
    return list(dict.fromkeys(ids))


async def cleanup_fixture_event_notifications(
    db: AsyncSession,
    event_ids: Optional[Iterable],
    *,
    label: str = "verifier",
    verbose: bool = True,
) -> int:
    """DELETE every notification row referencing any fixture event id — for
    ALL users. Returns the number of rows deleted (0 for empty input).

    Does NOT commit: the caller keeps its existing commit structure.
    """
    ids = _normalize_ids(event_ids)
    if not ids:
        if verbose:
            print(f"[{label}] fixture notification cleanup: no fixture event ids (skipped)")
        return 0
    result = await db.execute(
        delete(Notification).where(Notification.event_id.in_(ids))
    )
    deleted = result.rowcount or 0
    if verbose:
        print(f"[{label}] fixture notification cleanup: {deleted} row(s) removed "
              f"for {len(ids)} fixture event(s), all affected users")
    return deleted


async def assert_no_orphaned_fixture_notifications(
    db: AsyncSession,
    event_ids: Optional[Iterable],
    *,
    label: str = "verifier",
    raise_on_failure: bool = True,
) -> int:
    """Self-check: count notification rows still referencing the fixture
    events. Must be 0 after cleanup + commit. Prints the result and (by
    default) raises AssertionError when rows remain."""
    ids = _normalize_ids(event_ids)
    if not ids:
        return 0
    remaining = (
        await db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.event_id.in_(ids)
            )
        )
    ).scalar_one()
    ok = remaining == 0
    print(f"[{label}] fixture notification self-check: remaining={remaining} "
          f"({'OK' if ok else 'FAIL'})")
    if not ok and raise_on_failure:
        raise AssertionError(
            f"{remaining} notification row(s) still reference fixture events; "
            "cleanup must remove notifications for ALL affected users"
        )
    return remaining
