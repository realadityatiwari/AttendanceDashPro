from uuid import UUID
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.enums import FeedbackType


class FeedbackListItem(BaseModel):
    """Admin list item for GET /api/v1/feedback/admin.

    Includes the submitter's roll_number + name (read-only join). Never
    includes hashed_password or any credential.
    """
    id: UUID
    feedback_type: FeedbackType
    message: str
    context: Optional[str] = None
    created_at: datetime
    roll_number: str
    name: str

    class Config:
        from_attributes = True


class FeedbackListResponse(BaseModel):
    """Paginated admin feedback list."""
    items: list[FeedbackListItem]
    total: int
    page: int
    page_size: int
    pages: int
