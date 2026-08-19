from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services.feedback_service import FeedbackService

router = APIRouter()


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 10C: persists user feedback. The user_id is derived from the
    authenticated JWT (get_current_user) — never accepted from the client.
    Any authenticated user (STUDENT or ADMIN) may submit; there is no admin
    dimension and no feedback management surface in this phase.
    """
    return await FeedbackService(db).submit(current_user, payload)