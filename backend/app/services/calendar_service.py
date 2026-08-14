from typing import List, Dict, Any
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.calendar_engine import get_academic_day, AcademicDay, DEFAULT_WEEKENDS
from app.repositories.calendar_repo import CalendarRepository

class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CalendarRepository(db)
        
    async def get_day_schedule(self, target_date: date) -> AcademicDay:
        events = await self.repo.get_all_events()
        # Single source of truth from the calendar engine (JS getDay() indices:
        # 0=Sunday, 6=Saturday). Previously a local [5, 6] (Python weekday
        # indices) was passed here, which the engine interpreted as JS indices
        # and caused Friday to resolve non-working and Sunday working.
        return get_academic_day(target_date, events, DEFAULT_WEEKENDS)
