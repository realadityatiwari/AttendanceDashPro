from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.notification import NotificationItem, NotificationsResponse, NotificationUpdate
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("", response_model=NotificationsResponse)
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Notification inbox (Phase 11A + 11B).

    The user_id is derived from the authenticated JWT (get_current_user) —
    never accepted from the client. Notifications are projections of existing
    engine/service outputs; generation snapshots them into persisted rows
    (idempotent by UNIQUE(user_id, kind, occurrence_key)), then serves the
    inbox newest-first with the unread count. Dismissed notifications are
    excluded.
    """
    return await NotificationService(db).get_notifications(current_user)


@router.patch("/{notification_id}", response_model=NotificationItem)
async def update_notification_state(
    notification_id: UUID,
    payload: NotificationUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 11B: apply read/dismiss state to one persisted notification.

    Owner-scoped by the authenticated JWT — a notification belonging to another
    user is indistinguishable from a missing one (404). Idempotent: repeating
    the same transition is a no-op success. The notification_id is the
    persisted row id returned by the inbox; the client never supplies a user_id.
    """
    item = await NotificationService(db).update_state(
        current_user,
        notification_id=notification_id,
        is_read=payload.is_read,
        is_dismissed=payload.is_dismissed,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return item