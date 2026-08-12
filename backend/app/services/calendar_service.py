from typing import List, Dict, Any
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.calendar_engine import get_academic_day, AcademicDay
from app.repositories.calendar_repo import CalendarRepository

class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CalendarRepository(db)
        
    async def get_day_schedule(self, target_date: date) -> AcademicDay:
        events_models = await self.repo.get_all_events()
        # Mocking to dict for engine compatibility
        events = [{"date": e.start_date, "type": e.event_type.value} for e in events_models]
        default_weekends = [5, 6] # Saturday, Sunday
        
        return get_academic_day(target_date, events, default_weekends)
