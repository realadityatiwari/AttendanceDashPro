from uuid import UUID
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.quiz import QuizCycle, EligibilityPolicy, QuizSchedule

class QuizRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_quiz_cycle_with_policy(self, cycle_number: int) -> Optional[QuizCycle]:
        stmt = select(QuizCycle).options(
            selectinload(QuizCycle.eligibility_policy)
        ).filter(QuizCycle.cycle_number == cycle_number)
        result = await self.db.execute(stmt)
        return result.scalars().first()
        
    async def get_quiz_schedules_for_subject(self, subject_id: UUID) -> List[QuizSchedule]:
        stmt = select(QuizSchedule).options(
            selectinload(QuizSchedule.quiz_cycle)
        ).filter(QuizSchedule.subject_id == subject_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
