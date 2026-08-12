from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class StudentProfile(BaseModel):
    id: UUID
    firebase_uid: str
    email: str
    display_name: str
    roll_number: Optional[str] = None
    section_name: Optional[str] = None

    class Config:
        from_attributes = True
