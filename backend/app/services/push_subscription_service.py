from uuid import UUID
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.push_subscription import PushSubscription
from app.repositories.push_subscription_repo import PushSubscriptionRepository
from app.schemas.push_subscription import PushSubscriptionCreate


class PushSubscriptionService:
    """Phase 11C-P2: authenticated, owner-scoped Web Push subscription registry.

    Stores the browser PushSubscription (endpoint + p256dh + auth) that P3's
    PushDispatchService will need to deliver push messages. Ownership is always
    ``current_user.id`` — never accepted from query params or the request body.

    STORAGE ONLY: nothing here sends push messages (that is P3) and nothing
    triggers notifications (that is P4). The in-app notification system remains
    canonical.

    Endpoint -> Service -> Repository -> SQLAlchemy; no business logic lives in
    the endpoint.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PushSubscriptionRepository(db)

    async def register(self, user: User, payload: PushSubscriptionCreate) -> PushSubscription:
        """Idempotent create-or-refresh of the authenticated user's browser
        subscription. Re-registering the same endpoint (multi-tab, page reload,
        repeated enable) updates the existing row — never a duplicate — because
        UNIQUE(endpoint) is enforced by the database."""
        return await self.repo.upsert(
            user_id=user.id,
            endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
        )

    async def unsubscribe(self, user: User, subscription_id: UUID) -> bool:
        """Owner-scoped removal. Returns False (404) for another user's
        subscription or an unknown id — a student can never delete another
        user's subscription."""
        return await self.repo.delete(user.id, subscription_id)

    async def list_for_user(self, user: User) -> List[PushSubscription]:
        """All subscriptions registered for the authenticated user."""
        return await self.repo.get_by_user(user.id)
