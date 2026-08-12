from pydantic import BaseModel
from typing import Union
from uuid import UUID
from app.models.enums import ClassType
from app.schemas.subject import SubjectResponse

class TimetableEntryResponse(BaseModel):
    id: UUID
    day_of_week: int
    class_type: ClassType
    subject: SubjectResponse

    class Config:
        from_attributes = True
