from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.feedback import Feedback
from app.models.enums import FeedbackType


class FeedbackRepository:
    """Persistence for user feedback (Phase 10C). The owner is always
    derived from the authenticated user — no client-controlled identity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: UUID,
        feedback_type: FeedbackType,
        message: str,
        context: Optional[str] = None,
    ) -> Feedback:
        feedback = Feedback(
            user_id=user_id,
            feedback_type=feedback_type,
            message=message,
            context=context,
        )
        self.db.add(feedback)
        await self.db.commit()
        await self.db.refresh(feedback)
        return feedback