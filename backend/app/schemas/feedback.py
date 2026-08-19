from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.enums import FeedbackType


class FeedbackCreate(BaseModel):
    """Create payload for POST /api/v1/feedback (Phase 10C).

    user_id and created_at are intentionally absent — both are
    server-controlled (JWT identity + server timestamp).
    """
    feedback_type: FeedbackType
    message: str = Field(min_length=10, max_length=1000)
    context: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: UUID
    user_id: UUID
    feedback_type: FeedbackType
    message: str
    context: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True