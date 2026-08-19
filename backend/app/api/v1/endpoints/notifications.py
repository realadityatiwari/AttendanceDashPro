from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.notification import NotificationsResponse
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("", response_model=NotificationsResponse)
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 11A: read-only notification read model. The user_id is derived from
    the authenticated JWT (get_current_user) — never accepted from the client.
    Notifications are projections of existing engine/service outputs generated
    on-read; no persistence exists in this phase.
    """
    return await NotificationService(db).get_notifications(current_user)