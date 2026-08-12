from uuid import UUID
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.timetable import TimetableEntry, ClassSession

class TimetableRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_weekly_entries_for_section(self, section_id: UUID) -> List[TimetableEntry]:
        stmt = select(TimetableEntry).options(
            selectinload(TimetableEntry.subject)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_class_sessions_for_subject(self, subject_id: UUID) -> List[ClassSession]:
        stmt = select(ClassSession).filter(ClassSession.subject_id == subject_id).order_by(ClassSession.date)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
