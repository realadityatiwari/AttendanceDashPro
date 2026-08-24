from uuid import UUID
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.feedback import Feedback
from app.models.enums import FeedbackType


class FeedbackRepository:
    """Persistence for user feedback (Phase 10C). The owner is always
    derived from the authenticated user â€” no client-controlled identity."""

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

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 20,
        feedback_type: Optional[str] = None,
    ) -> tuple[list[Feedback], int]:
        """Admin-only: newest-first paginated list with the submitter joined.
        Returns (items, total_count)."""
        stmt = (
            select(Feedback)
            .options(selectinload(Feedback.user))
            .order_by(Feedback.created_at.desc())
        )
        count_stmt = select(func.count()).select_from(Feedback)
        if feedback_type:
            try:
                ft = FeedbackType(feedback_type)
            except ValueError:
                ft = None
            if ft is not None:
                stmt = stmt.where(Feedback.feedback_type == ft)
                count_stmt = count_stmt.where(Feedback.feedback_type == ft)

        total = (await self.db.execute(count_stmt)).scalar() or 0
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total

    async def get_by_id(self, feedback_id: UUID) -> Optional[Feedback]:
        stmt = (
            select(Feedback)
            .options(selectinload(Feedback.user))
            .where(Feedback.id == feedback_id)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()