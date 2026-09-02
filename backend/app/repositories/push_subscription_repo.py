from uuid import UUID
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.push_subscription import PushSubscription
from app.db.base_class import IST


class PushSubscriptionRepository:
    """Persistence for the Phase 11C-P2 push-subscription registry.

    Owner is always the authenticated user resolved from the JWT
    (get_current_user) — no client-controlled identity exists anywhere in this
    repository; every read and mutation is scoped by user_id.

    Idempotency is DB-enforced: ``endpoint`` is UNIQUE, so registering the same
    browser endpoint again (multi-tab, repeated enable, page reload) can never
    create a duplicate row — the upsert refreshes the existing row in place.
    Multiple subscriptions per user are fully supported (desktop + mobile +
    PWA + another browser are independent rows, each independently removable).

    Commits follow the notification-repo convention (repo-owned transaction).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(
        self,
        user_id: UUID,
        endpoint: str,
        p256dh: str,
        auth: str,
    ) -> PushSubscription:
        """Insert a subscription row, or refresh the existing row with the
        same endpoint. Returns the row (existing or new).

        On conflict the row is reassigned to the current authenticated user:
        a browser subscription follows whoever is signed in on that browser.
        """
        now = datetime.now(IST)
        stmt = pg_insert(PushSubscription).values(
            user_id=user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_push_subscriptions_endpoint",
            set_={
                "user_id": stmt.excluded.user_id,
                "p256dh": stmt.excluded.p256dh,
                "auth": stmt.excluded.auth,
                "updated_at": now,
            },
        ).returning(PushSubscription.id)
        result = await self.db.execute(stmt)
        row_id = result.scalar_one()
        await self.db.commit()
        row = await self.get_by_id(user_id, row_id)
        return row

    async def get_by_id(self, user_id: UUID, subscription_id: UUID) -> Optional[PushSubscription]:
        """Owner-scoped row fetch — returns None for another user's row."""
        stmt = select(PushSubscription).where(
            PushSubscription.id == subscription_id,
            PushSubscription.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_by_user(self, user_id: UUID) -> List[PushSubscription]:
        """All subscriptions registered for one user (multi-device support)."""
        stmt = select(PushSubscription).where(PushSubscription.user_id == user_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, user_id: UUID, subscription_id: UUID) -> bool:
        """Owner-scoped removal (unsubscribe). Returns False when the row does
        not exist or is not owned by the user — another user's subscription is
        indistinguishable from a missing one."""
        result = await self.db.execute(
            delete(PushSubscription).where(
                PushSubscription.id == subscription_id,
                PushSubscription.user_id == user_id,
            )
        )
        await self.db.commit()
        return result.rowcount > 0
