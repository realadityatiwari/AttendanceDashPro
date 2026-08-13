from pydantic import BaseModel
from datetime import date
from typing import Optional, List
from uuid import UUID
from app.models.enums import EventType, ClassType

class AcademicEventResponse(BaseModel):
    id: UUID
    event_type: EventType
    start_date: date
    end_date: date
    subject_id: Optional[UUID] = None
    class_type: Optional[ClassType] = None
    is_working_day: Optional[bool] = None
    substitution_schedule_override: Optional[str] = None
    active: bool

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
