from uuid import UUID
from typing import List, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_, delete, exists, func, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.notification import Notification
from app.models.event import AcademicEvent
from app.models.enums import NotificationKind
from app.db.base_class import IST


# H-4c (Phase 2A): bounded inbox reads.  The inbox is a newest-first page;
# the server caps the page size so no unbounded SELECT can be issued and an
# oversized/poisoned inbox can never flood a single response.  Age-based
# retention is deliberately NOT implemented here: no retention period is
# documented anywhere in the project, so it remains a product decision
# (see docs/REMEDIATION_READINESS_REPORT.md D-5 / the Phase 2A report).
DEFAULT_INBOX_PAGE_SIZE = 50
MAX_INBOX_PAGE_SIZE = 200


def clamp_inbox_page_size(limit: Optional[int]) -> int:
    """Clamp a requested inbox page size into [1, MAX_INBOX_PAGE_SIZE]."""
    try:
        value = int(limit) if limit is not None else DEFAULT_INBOX_PAGE_SIZE
    except (TypeError, ValueError):
        value = DEFAULT_INBOX_PAGE_SIZE
    return max(1, min(value, MAX_INBOX_PAGE_SIZE))


def orphaned_event_ref_clause():
    """The exact H-4a orphan predicate: notification rows whose ``event_id``
    points at an academic event that no longer exists (``notifications.event_id``
    carries no FK, so these projections outlive their event). This is the
    complement of the live guard below and the ONLY criterion the one-time
    purge script (``scripts/purge_orphaned_event_notifications.py``) deletes
    on — no other kind or row can match it."""
    return and_(
        Notification.event_id.isnot(None),
        ~exists(
            select(AcademicEvent.id).where(AcademicEvent.id == Notification.event_id)
        ),
    )


def _live_event_ref_clause():
    """A notification with an ``event_id`` is only live while its academic
    event still exists (``notifications.event_id`` carries no FK).  Rows whose
    event was deleted — the orphaned ACADEMIC_EVENT projections of H-4a — can
    never surface through the inbox or the unread badge, even before the
    one-time purge runs.  Non-event kinds (``event_id IS NULL``) and rows
    whose event still exists are unaffected."""
    return or_(
        Notification.event_id.is_(None),
        exists(
            select(AcademicEvent.id).where(AcademicEvent.id == Notification.event_id)
        ),
    )


class NotificationRepository:
    """Persistence for the Phase 11B notification inbox.

    Owner is always the authenticated user resolved from the JWT
    (get_current_user) — no client-controlled identity exists anywhere in this
    repository; every read and mutation is scoped by user_id.

    Idempotency is DB-enforced: upsert() keys on UNIQUE(user_id, kind,
    occurrence_key), so regenerating the same projection can never create a
    duplicate row (audit §8-5 and §9-11B). The upsert refreshes only the
    mutable projection fields (message / subject references / updated_at);
    `date`, `is_read`, `is_dismissed` and `created_at` are preserved, so a
    read/dismissed notification stays read/dismissed while its source
    condition still holds.

    Commits follow the feedback-repo convention (repo-owned transaction).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(
        self,
        user_id: UUID,
        kind: NotificationKind,
        occurrence_key: str,
        date: date,
        message: str,
        subject_code: Optional[str] = None,
        subject_name: Optional[str] = None,
        session_id: Optional[UUID] = None,
        quiz_cycle: Optional[int] = None,
        event_id: Optional[UUID] = None,
    ) -> UUID:
        """Insert the projection row, or refresh the existing row with the
        same (user_id, kind, occurrence_key). Returns the row id (existing or
        new)."""
        now = datetime.now(IST)
        stmt = pg_insert(Notification).values(
            user_id=user_id,
            kind=kind,
            occurrence_key=occurrence_key,
            date=date,
            message=message,
            subject_code=subject_code,
            subject_name=subject_name,
            session_id=session_id,
            quiz_cycle=quiz_cycle,
            event_id=event_id,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_notifications_user_kind_occurrence_key",
            set_={
                "message": stmt.excluded.message,
                "subject_code": stmt.excluded.subject_code,
                "subject_name": stmt.excluded.subject_name,
                "updated_at": now,
            },
        ).returning(Notification.id)
        result = await self.db.execute(stmt)
        row_id = result.scalar_one()
        await self.db.commit()
        return row_id

    async def upsert_many(
        self,
        rows: List[dict],
    ) -> None:
        """Batch-upsert a set of generated projections in ONE transaction.

        Performance optimization (2026-09-02): the generation loop previously
        called upsert() once per projection — N sequential INSERT ... ON
        CONFLICT statements with an individual COMMIT each (N database round
        trips during dashboard startup). This executes the SAME upsert
        semantics as a single multi-row INSERT ... ON CONFLICT DO UPDATE
        statement and commits ONCE, collapsing N round trips into 1 while
        keeping the whole batch atomic: a failure in any row rolls back the
        entire statement, so partial regeneration can never persist an
        inconsistent inbox (stronger than the previous per-row commits).

        Idempotency is unchanged and still DB-enforced: every row keys on
        UNIQUE(user_id, kind, occurrence_key) via the same conflict clause,
        so regenerating the same occurrence refreshes in place — never a
        duplicate. The conflict clause refreshes only the mutable projection
        fields (message / subject references / updated_at); `date`,
        `is_read`, `is_dismissed` and `created_at` are preserved, so
        read/dismissed notifications stay read/dismissed while their source
        condition still holds.

        Ordering is preserved: created_at is staggered in list order (one
        microsecond per row) so the inbox sort (created_at desc, id desc)
        renders newly created rows in the same order the previous
        sequential-commit loop produced.

        Each row is a dict with the same keys as upsert()'s positional
        arguments (user_id, kind, occurrence_key, date, message,
        subject_code, subject_name, session_id, quiz_cycle, event_id). Rows
        are deduplicated by (kind, occurrence_key), keeping the LAST
        occurrence — identical to sequential upsert semantics (the later
        write wins) and required for a multi-row statement (a conflict key
        may appear only once per VALUES list).
        """
        if not rows:
            return
        now = datetime.now(IST)
        # Deduplicate by idempotency key, keeping the last occurrence (the
        # sequential upsert semantics: the later write refreshes the row).
        by_key: dict[tuple[UUID, NotificationKind, str], dict] = {}
        for row in rows:
            by_key[(row["user_id"], row["kind"], row["occurrence_key"])] = row
        unique_rows = list(by_key.values())
        # Stagger created_at in list order so the inbox sort renders newly
        # created rows exactly as the old per-item commit loop did.
        values = [
            {
                "user_id": row["user_id"],
                "kind": row["kind"],
                "occurrence_key": row["occurrence_key"],
                "date": row["date"],
                "message": row["message"],
                "subject_code": row.get("subject_code"),
                "subject_name": row.get("subject_name"),
                "session_id": row.get("session_id"),
                "quiz_cycle": row.get("quiz_cycle"),
                "event_id": row.get("event_id"),
                "created_at": now + timedelta(microseconds=i),
                "updated_at": now,
            }
            for i, row in enumerate(unique_rows)
        ]
        stmt = pg_insert(Notification).values(values)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_notifications_user_kind_occurrence_key",
            set_={
                "message": stmt.excluded.message,
                "subject_code": stmt.excluded.subject_code,
                "subject_name": stmt.excluded.subject_name,
                "updated_at": now,
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def get_inbox(
        self,
        user_id: UUID,
        *,
        limit: Optional[int] = DEFAULT_INBOX_PAGE_SIZE,
        offset: int = 0,
    ) -> List[Notification]:
        """The user's inbox, newest first (audit 11B objective).

        H-4c (Phase 2A): the read is bounded — page size is clamped to
        [1, MAX_INBOX_PAGE_SIZE] and the offset is non-negative, so no
        unbounded SELECT can be issued. Dismissed notifications are excluded;
        so are orphaned event projections whose academic event no longer
        exists (they can never surface). Ordering is deterministic:
        created_at DESC, id DESC."""
        page_size = clamp_inbox_page_size(limit)
        page_offset = max(0, int(offset or 0))
        stmt = (
            select(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_dismissed.is_(False),
                _live_event_ref_clause(),
            )
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(page_size)
            .offset(page_offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_inbox(self, user_id: UUID) -> int:
        """Total non-dismissed LIVE rows (the pagination ``total``). Excludes
        orphaned event projections for the same reason get_inbox does."""
        stmt = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.is_dismissed.is_(False),
            _live_event_ref_clause(),
        )
        return (await self.db.execute(stmt)).scalar() or 0

    async def get_by_id(self, user_id: UUID, notification_id: UUID) -> Optional[Notification]:
        """Owner-scoped row fetch — returns None for another user's row."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_occurrence_key(
        self,
        user_id: UUID,
        kind: NotificationKind,
        occurrence_key: str,
    ) -> Optional[Notification]:
        """Owner-scoped lookup by the idempotency key (Phase 11C-P4).

        The emission boundary uses this to decide whether a canonical
        notification already exists before inserting (so a repeated trigger /
        sweep refreshes in place and never re-pushes)."""
        stmt = select(Notification).where(
            Notification.user_id == user_id,
            Notification.kind == kind,
            Notification.occurrence_key == occurrence_key,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def try_create(
        self,
        user_id: UUID,
        kind: NotificationKind,
        occurrence_key: str,
        date: date,
        message: str,
        subject_code: Optional[str] = None,
        subject_name: Optional[str] = None,
        session_id: Optional[UUID] = None,
        quiz_cycle: Optional[int] = None,
        event_id: Optional[UUID] = None,
    ) -> Optional[Notification]:
        """Insert a NEW notification row, or return None when a row with the
        same (user_id, kind, occurrence_key) already exists.

        Phase 11C-P4: the emission boundary's race-free create. Uses
        PostgreSQL ``INSERT ... ON CONFLICT DO NOTHING RETURNING id`` — one
        atomic statement — so a concurrent sweep/trigger can never produce a
        duplicate row AND never falsely reports "newly created". Returns None
        when the row pre-existed (caller refreshes in place without pushing).
        """
        now = datetime.now(IST)
        stmt = pg_insert(Notification).values(
            user_id=user_id,
            kind=kind,
            occurrence_key=occurrence_key,
            date=date,
            message=message,
            subject_code=subject_code,
            subject_name=subject_name,
            session_id=session_id,
            quiz_cycle=quiz_cycle,
            event_id=event_id,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_notifications_user_kind_occurrence_key",
        ).returning(Notification.id)
        result = await self.db.execute(stmt)
        row_id = result.scalar_one_or_none()
        if row_id is None:
            return None
        await self.db.commit()
        return await self.get_by_id(user_id, row_id)

    async def count_unread(self, user_id: UUID) -> int:
        """Unread, non-dismissed, LIVE notifications (the bell badge count).

        H-4c: orphaned event projections are excluded so the badge always
        matches the rows the inbox can actually surface."""
        stmt = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
            Notification.is_dismissed.is_(False),
            _live_event_ref_clause(),
        )
        return (await self.db.execute(stmt)).scalar() or 0

    async def count_for_user(self, user_id: UUID) -> int:
        stmt = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id
        )
        return (await self.db.execute(stmt)).scalar() or 0

    async def update_state(
        self,
        user_id: UUID,
        notification_id: UUID,
        is_read: Optional[bool] = None,
        is_dismissed: Optional[bool] = None,
    ) -> Optional[Notification]:
        """Apply read/dismiss state (audit 11B objective: PATCH
        read/dismiss). Owner-scoped; idempotent (repeating the same value is a
        no-op success)."""
        row = await self.get_by_id(user_id, notification_id)
        if row is None:
            return None
        if is_read is not None:
            row.is_read = is_read
        if is_dismissed is not None:
            row.is_dismissed = is_dismissed
        await self.db.commit()
        return row

    async def delete(self, user_id: UUID, notification_id: UUID) -> bool:
        """Physical removal (dismissal). Owner-scoped; returns False when the
        row does not exist or is not owned by the user."""
        result = await self.db.execute(
            delete(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        await self.db.commit()
        return result.rowcount > 0