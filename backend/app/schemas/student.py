from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import date

class StudentSyncRequest(BaseModel):
    display_name: str
    roll_number: str

class StudentProfile(BaseModel):
    id: UUID
    # Firebase identity is retired (Phase 4.5.3): null for PostgreSQL-native
    # registrations, preserved for legacy accounts.
    firebase_uid: Optional[str] = None
    # Authorization role (Phase 6.5): "STUDENT" or "ADMIN". The backend is
    # authoritative for authorization; this is read-only profile information
    # used only to decide whether admin controls are shown.
    role: str = "STUDENT"
    # NOTE: email is not stored in PostgreSQL. It is owned by Firebase Auth.
    # The backend does not persist or return email from the DB.
    display_name: str
    roll_number: Optional[str] = None
    section_name: Optional[str] = None
    # Academic context (read-only, resolved on demand from the user's
    # section -> semester -> academic session chain and quiz schedules).
    # `program` (Phase 10B) is populated from the stored `sections.program`
    # value — never derived from the section name.
    program: Optional[str] = None
    semester_name: Optional[str] = None
    academic_session: Optional[str] = None
    semester_start: Optional[date] = None
    semester_end: Optional[date] = None
    first_quiz_date: Optional[date] = None

    class Config:
        from_attributes = True