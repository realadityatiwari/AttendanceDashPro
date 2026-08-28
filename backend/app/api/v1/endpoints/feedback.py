from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user, require_head_admin
from app.models.user import User
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.schemas.feedback_admin import FeedbackListItem, FeedbackListResponse
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
    authenticated JWT (get_current_user) â€” never accepted from the client.
    Any authenticated user (STUDENT or ADMIN) may submit; there is no admin
    dimension and no feedback management surface in this phase.
    """
    return await FeedbackService(db).submit(current_user, payload)


@router.get("/admin", response_model=FeedbackListResponse)
async def list_feedback_admin(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="items per page"),
    feedback_type: str | None = Query(None, description="filter by FeedbackType"),
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 21B: admin-only paginated feedback list, newest first. STUDENT â†’
    403 (require_head_admin); unauthenticated â†’ 401 (auth dependency chain).
    Only the submitter's roll_number/name are joined â€” no credentials.
    """
    items, total = await FeedbackService(db).list_admin(
        page=page,
        page_size=page_size,
        feedback_type=feedback_type,
    )
    pages = (total + page_size - 1) // page_size if total else 0
    return FeedbackListResponse(
        items=[
            FeedbackListItem(
                id=f.id,
                feedback_type=f.feedback_type,
                message=f.message,
                context=f.context,
                created_at=f.created_at,
                roll_number=f.user.roll_number if f.user else "",
                name=f.user.name if f.user else "Unknown",
            )
            for f in items
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/admin/{feedback_id}", response_model=FeedbackListItem)
async def get_feedback_admin(
    feedback_id: str,
    _admin: User = Depends(require_head_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 21B: admin-only single feedback item. 404 when absent; STUDENT â†’
    403; unauthenticated â†’ 401.
    """
    f = await FeedbackService(db).get_admin(feedback_id)
    return FeedbackListItem(
        id=f.id,
        feedback_type=f.feedback_type,
        message=f.message,
        context=f.context,
        created_at=f.created_at,
        roll_number=f.user.roll_number if f.user else "",
        name=f.user.name if f.user else "Unknown",
    )
