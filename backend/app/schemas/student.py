from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class StudentSyncRequest(BaseModel):
    display_name: str
    roll_number: str

class StudentProfile(BaseModel):
    id: UUID
    firebase_uid: str
    # NOTE: email is not stored in PostgreSQL. It is owned by Firebase Auth.
    # The backend does not persist or return email from the DB.
    display_name: str
    roll_number: Optional[str] = None
    section_name: Optional[str] = None

    class Config:
        from_attributes = True
