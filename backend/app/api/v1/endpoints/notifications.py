from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.repositories.notification_repo import (
    DEFAULT_INBOX_PAGE_SIZE,
    MAX_INBOX_PAGE_SIZE,
)
from app.schemas.notification import NotificationItem, NotificationsResponse, NotificationUpdate
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("", response_model=NotificationsResponse)
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(
        DEFAULT_INBOX_PAGE_SIZE,
        ge=1,
        le=MAX_INBOX_PAGE_SIZE,
        description="Page size (1..200; default 50). Reads are always bounded.",
    ),
    offset: int = Query(
        0, ge=0, description="Newest-first offset into the live inbox."
    ),
):
    """
    Notification inbox (Phase 11A + 11B + H-4c).

    The user_id is derived from the authenticated JWT (get_current_user) —
    never accepted from the client. Notifications are projections of existing
    engine/service outputs; generation snapshots them into persisted rows
    (idempotent by UNIQUE(user_id, kind, occurrence_key)), then serves one
    bounded newest-first page plus the unread count. Dismissed notifications
    and rows whose referenced academic event no longer exists are excluded.
    """
    return await NotificationService(db).get_notifications(
        current_user, limit=limit, offset=offset
    )


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