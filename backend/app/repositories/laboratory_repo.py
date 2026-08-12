from uuid import UUID
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.laboratory import LaboratoryExperiment, LaboratoryRecord

class LaboratoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_experiments_for_subject(self, subject_id: UUID) -> List[LaboratoryExperiment]:
        stmt = select(LaboratoryExperiment).filter(LaboratoryExperiment.subject_id == subject_id).order_by(LaboratoryExperiment.experiment_number)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_student_records(self, user_id: UUID, subject_id: UUID) -> List[LaboratoryRecord]:
        stmt = select(LaboratoryRecord).join(LaboratoryExperiment).filter(
            LaboratoryRecord.student_id == user_id,
            LaboratoryExperiment.subject_id == subject_id
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
