from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from app.models.enums import SubjectCategory

class SubjectResponse(BaseModel):
    id: UUID
    code: str
    name: str
    tag: Optional[str] = None
    category: SubjectCategory
    credits: int
    quiz_applicable: bool
    attendance_applicable: bool

    class Config:
        from_attributes = True
