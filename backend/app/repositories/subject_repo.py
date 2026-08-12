from uuid import UUID
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.academic import Subject

class SubjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_all_subjects(self) -> List[Subject]:
        stmt = select(Subject)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_code(self, subject_code: str) -> Optional[Subject]:
        stmt = select(Subject).filter(Subject.code == subject_code)
        result = await self.db.execute(stmt)
        return result.scalars().first()
        
    async def get_by_id(self, subject_id: UUID) -> Optional[Subject]:
        stmt = select(Subject).filter(Subject.id == subject_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()
