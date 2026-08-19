from typing import Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.feedback import Feedback
from app.repositories.feedback_repo import FeedbackRepository
from app.schemas.feedback import FeedbackCreate


class FeedbackService:
    """Feedback submission (Phase 10C).

    The backend independently validates the message (never relying on
    frontend validation): surrounding whitespace is trimmed before
    persistence and a trimmed message shorter than 10 characters is
    rejected. Pydantic already enforces the raw 10..1000 length bounds.
    """

    MIN_MESSAGE_LENGTH = 10

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = FeedbackRepository(db)

    async def submit(self, user: User, payload: FeedbackCreate) -> Feedback:
        message = payload.message.strip()
        if len(message) < self.MIN_MESSAGE_LENGTH:
            raise HTTPException(
                status_code=422,
                detail=f"Message must be at least {self.MIN_MESSAGE_LENGTH} characters",
            )

        context: Optional[str] = payload.context
        if context is not None:
            context = context.strip()
            if context == "":
                context = None

        return await self.repo.create(
            user_id=user.id,
            feedback_type=payload.feedback_type,
            message=message,
            context=context,
        )