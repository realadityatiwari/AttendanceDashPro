from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date
from app.models.enums import ClassType, EventType, SubjectCategory

class Milestone(BaseModel):
    milestone_id: str
    type: str
    date: date
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Timeline(BaseModel):
    commencement_date: date
    milestones: List[Milestone] = Field(default_factory=list)

class Subject(BaseModel):
    code: str
    name: str
    tag: Optional[str] = None
    category: SubjectCategory
    quiz_applicable: bool
    attendance_applicable: bool
    timeline: Optional[Timeline] = None

class QuizCycle(BaseModel):
    cycle: int
    label: str

class TimetableEntry(BaseModel):
    subject_code: str
    class_type: ClassType

class AcademicEvent(BaseModel):
    id: str
    version: int = 1
    event_type: EventType
    subject_code: Optional[str] = None
    class_type: Optional[ClassType] = None
    start_date: date
    end_date: date
    is_working_day: Optional[bool] = None
    substitution_schedule_override: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    active: bool = True
