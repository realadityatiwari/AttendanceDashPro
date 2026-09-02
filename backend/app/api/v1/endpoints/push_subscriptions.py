from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.push_subscription import PushSubscriptionCreate, PushSubscriptionResponse
from app.services.push_subscription_service import PushSubscriptionService

router = APIRouter()


@router.post("", response_model=PushSubscriptionResponse)
async def register_push_subscription(
    payload: PushSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 11C-P2: register (create or refresh) the authenticated user's Web
    Push subscription.

    POST /api/v1/push-subscriptions — the owner is derived from the JWT
    (get_current_user); the client can never supply a user_id or target another
    user. Idempotent: registering the same endpoint again updates the existing
    row in place (DB-enforced UNIQUE(endpoint)), so repeated subscribe/register
    calls can never create duplicates. The response returns only the persisted
    row identity (id/endpoint/timestamps) — never the p256dh/auth keys.
    """
    return await PushSubscriptionService(db).register(current_user, payload)


@router.delete("/{subscription_id}", status_code=204)
async def delete_push_subscription(
    subscription_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 11C-P2: remove the authenticated user's push subscription
    (unsubscribe).

    DELETE /api/v1/push-subscriptions/{subscription_id} — owner-scoped by the
    authenticated JWT: another user's subscription is indistinguishable from a
    missing one (404), so a student can never delete another user's
    subscription.
    """
    removed = await PushSubscriptionService(db).unsubscribe(current_user, subscription_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Push subscription not found")
    return None
