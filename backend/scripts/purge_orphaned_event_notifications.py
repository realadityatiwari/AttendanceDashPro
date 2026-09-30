"""Phase 2A (H-4a) — one-time purge of orphaned notification projections.

WHAT THIS REMOVES
    ``notifications`` rows whose ``event_id`` references an academic event that
    no longer exists. ``notifications.event_id`` has NO foreign key, so the
    ACADEMIC_EVENT projections emitted by verifier/test fixtures outlive the
    deleted fixture events (452 rows at the Phase-2A baseline, all unread).
    These are dead projections — the source facts (events) are already gone;
    no attendance/academic data is touched.

EXACT DELETE PREDICATE (the only criterion; defined once in
``app.repositories.notification_repo.orphaned_event_ref_clause``):

    DELETE FROM notifications
    WHERE event_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM academic_events ev WHERE ev.id = notifications.event_id)

    It cannot match live notifications, QUIZ_APPROACHING,
    ATTENDANCE_THRESHOLD, MUST_ATTEND, SAFE_SKIP rows (event_id IS NULL), or
    any row whose event still exists.

SAFETY MECHANISM
    - The script is DRY-RUN BY DEFAULT: it prints the full before-baseline
      (counts by kind, orphan counts, affected users, unread totals), the
      exact predicate, and the targeted row count + sample, then exits
      without deleting anything.
    - The DELETE only executes when invoked with the explicit ``--confirm``
      flag. Without it the script refuses (exit 0, nothing deleted).
    - It refuses outright when ``APP_ENV=production`` (this remediation never
      performs production DB operations).
    - After the DELETE it re-runs the integrity probe and reports the
      remaining orphan count.

USAGE
    python scripts/purge_orphaned_event_notifications.py            # dry run
    python scripts/purge_orphaned_event_notifications.py --confirm  # execute
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.notification import Notification
from app.models.user import User
from app.repositories.notification_repo import orphaned_event_ref_clause


async def _count(session, *where) -> int:
    stmt = select(func.count()).select_from(Notification)
    if where:
        stmt = stmt.where(*where)
    return (await session.execute(stmt)).scalar_one()


async def _counts_by_kind(session, *where):
    stmt = select(Notification.kind, func.count()).group_by(Notification.kind)
    if where:
        stmt = stmt.where(*where)
    stmt = stmt.order_by(Notification.kind)
    return [(str(kind), count) for kind, count in (await session.execute(stmt)).all()]


async def _affected_users(session):
    stmt = (
        select(
            User.roll_number,
            func.count().label("orphans"),
            func.count()
            .filter(Notification.is_read.is_(False), Notification.is_dismissed.is_(False))
            .label("unread_orphans"),
        )
        .join(Notification, Notification.user_id == User.id)
        .where(orphaned_event_ref_clause())
        .group_by(User.roll_number)
        .order_by(User.roll_number)
    )
    return (await session.execute(stmt)).all()


async def _sample_rows(session, sample_size: int):
    stmt = (
        select(
            Notification.id,
            Notification.kind,
            Notification.occurrence_key,
            Notification.user_id,
            Notification.event_id,
            Notification.is_read,
            Notification.created_at,
        )
        .where(orphaned_event_ref_clause())
        .order_by(Notification.created_at, Notification.id)
        .limit(sample_size)
    )
    return (await session.execute(stmt)).all()


def _print_breakdown(title: str, rows) -> None:
    print(f"  {title}")
    if not rows:
        print("    (none)")
        return
    for label, count in rows:
        print(f"    {label}: {count}")


async def _print_before(session, sample_size: int) -> int:
    total = await _count(session)
    by_kind = await _counts_by_kind(session)
    orphan_total = await _count(session, orphaned_event_ref_clause())
    orphan_unread = await _count(
        session,
        orphaned_event_ref_clause(),
        Notification.is_read.is_(False),
        Notification.is_dismissed.is_(False),
    )
    orphan_by_kind = await _counts_by_kind(session, orphaned_event_ref_clause())
    users = await _affected_users(session)
    sample = await _sample_rows(session, sample_size)

    print("=== BEFORE (SELECT-only baseline) ===")
    print(f"  notifications total: {total}")
    _print_breakdown("by kind:", by_kind)
    print(f"  orphaned event projections: {orphan_total} (unread: {orphan_unread})")
    _print_breakdown("orphaned by kind:", orphan_by_kind)
    print("  affected users:")
    if not users:
        print("    (none)")
    for roll_number, orphans, unread_orphans in users:
        print(f"    roll_number={roll_number} orphans={orphans} unread={unread_orphans}")
    print(f"  targeted sample (up to {sample_size} rows, oldest first):")
    if not sample:
        print("    (none)")
    for row in sample:
        print(
            f"    id={row.id} kind={row.kind} occurrence_key={row.occurrence_key} "
            f"user_id={row.user_id} event_id={row.event_id} "
            f"is_read={row.is_read} created_at={row.created_at}"
        )
    print()
    return orphan_total


async def _run(confirm: bool, sample_size: int) -> int:
    if confirm and settings.APP_ENV == "production":
        print(
            "REFUSED: APP_ENV=production. This remediation script never performs "
            "production DB operations; run the approved maintenance procedure instead."
        )
        return 2

    async with AsyncSessionLocal() as session:
        orphan_total = await _print_before(session, sample_size)

        print("=== TARGET (exact deletion criteria) ===")
        print(
            "  DELETE FROM notifications\n"
            "  WHERE event_id IS NOT NULL\n"
            "    AND NOT EXISTS (SELECT 1 FROM academic_events ev WHERE ev.id = notifications.event_id);"
        )
        print(f"  targeted rows: {orphan_total}")
        print()

        if not confirm:
            print("DRY RUN - no rows were deleted. Re-run with --confirm to execute the purge.")
            return 0

        if orphan_total == 0:
            print("Nothing to delete (0 targeted rows); exiting without executing the DELETE.")
            return 0

        result = await session.execute(
            delete(Notification).where(orphaned_event_ref_clause())
        )
        deleted = result.rowcount
        await session.commit()

        remaining_total = await _count(session)
        remaining_orphans = await _count(session, orphaned_event_ref_clause())
        remaining_by_kind = await _counts_by_kind(session)

        print("=== AFTER ===")
        print(f"  rows deleted: {deleted}")
        print(f"  notifications total: {remaining_total}")
        print(f"  remaining orphaned event projections: {remaining_orphans}")
        _print_breakdown("by kind:", remaining_by_kind)
        if remaining_orphans != 0:
            print("  WARNING: orphans remain - investigate before re-running.")
            return 1
        print("  Self-check OK: zero orphaned event projections remain.")
        return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Purge orphaned notification projections (H-4a). Dry-run by default; "
            "the DELETE requires --confirm."
        )
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="EXECUTE the DELETE. Without this flag the script only reports (dry run).",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=10,
        help="How many targeted rows to print in the dry-run sample (default 10).",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_run(args.confirm, args.sample_size))


if __name__ == "__main__":
    raise SystemExit(main())
