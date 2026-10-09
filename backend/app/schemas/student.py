from pydantic import BaseModel, field_validator
from typing import Optional
from uuid import UUID
from datetime import date

# Canonical display-name limit for the `users.name` column. Matches the
# project-wide name convention used by admin academic-entity schemas
# (e.g. `admin_structure.py` / `admin_subjects.py`). There is no DB-level
# length constraint today; validation is backend-authoritative.
MAX_DISPLAY_NAME_LENGTH = 100

class StudentSyncRequest(BaseModel):
    display_name: str
    roll_number: str

class StudentNameUpdateRequest(BaseModel):
    """Self-service profile name update (`PATCH /api/v1/student/me`).

    The target account is ALWAYS the authenticated user — no user id or roll
    number is accepted here, so a caller can never rename another account.
    The value is whitespace-normalized before validation, so a
    whitespace-only name is rejected as empty.
    """
    display_name: str

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Display name is required")
        if len(trimmed) > MAX_DISPLAY_NAME_LENGTH:
            raise ValueError(
                f"Display name must not exceed {MAX_DISPLAY_NAME_LENGTH} characters"
            )
        return trimmed

class StudentProfile(BaseModel):
    id: UUID
    # Authorization role (Phase 6.5): "STUDENT" or "ADMIN". The backend is
    # authoritative for authorization; this is read-only profile information
    # used only to decide whether admin controls are shown.
    role: str = "STUDENT"
    # NOTE: email is not stored in PostgreSQL. The backend does not persist or
    # return email from the DB.
    display_name: str
    roll_number: Optional[str] = None
    section_name: Optional[str] = None
    # Phase 23.3 (Student Academic Assignment): the student's subsection within
    # their section (part of academic placement). NULL = UNKNOWN/UNASSIGNED.
    subsection_name: Optional[str] = None
    # Phase 23.3: the student's authoritative Department Elective selection as
    # concrete subject codes (DE-I / DE-II). NULL = not assigned for that slot.
    # The authoritative resolver remains ElectiveResolver (Phase 22.4).
    elective_i: Optional[str] = None
    elective_ii: Optional[str] = None
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