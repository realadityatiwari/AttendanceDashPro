from pydantic import BaseModel
from datetime import date
from typing import Optional, List
from uuid import UUID
from app.models.enums import EventType

class AcademicEventResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    event_type: EventType
    start_date: date
    end_date: date
    is_holiday: bool

    class Config:
        from_attributes = True

class AcademicDayResponse(BaseModel):
    date: date
    is_working_day: bool
    day_type: str
    is_teaching_day: bool
    original_day_of_week: str
    substitution_schedule_override: Optional[str] = None
    events: List[AcademicEventResponse] = []
