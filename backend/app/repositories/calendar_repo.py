from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.event import AcademicEvent

class CalendarRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_all_events(self) -> List[AcademicEvent]:
        stmt = select(AcademicEvent).order_by(AcademicEvent.start_date)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
