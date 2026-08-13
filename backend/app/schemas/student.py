from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import date

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
    # Academic context (read-only, resolved on demand from the user's
    # section -> semester -> academic session chain and quiz schedules).
    # `program` is always None today: the schema has no program/branch
    # column; only section names (e.g. "CSE-51") exist.
    program: Optional[str] = None
    semester_name: Optional[str] = None
    academic_session: Optional[str] = None
    semester_start: Optional[date] = None
    first_quiz_date: Optional[date] = None

    class Config:
        from_attributes = True