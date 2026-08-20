from uuid import UUID
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.notification import Notification
from app.models.enums import NotificationKind
from app.db.base_class import IST


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

    async def get_inbox(self, user_id: UUID) -> List[Notification]:
        """The user's inbox, newest first (audit 11B objective). Dismissed
        notifications are excluded from the inbox."""
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id, Notification.is_dismissed.is_(False))
            .order_by(Notification.created_at.desc(), Notification.id.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, user_id: UUID, notification_id: UUID) -> Optional[Notification]:
        """Owner-scoped row fetch — returns None for another user's row."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def count_unread(self, user_id: UUID) -> int:
        """Unread, non-dismissed notifications (the bell badge count)."""
        stmt = select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
            Notification.is_dismissed.is_(False),
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