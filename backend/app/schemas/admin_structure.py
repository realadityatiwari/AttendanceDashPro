"""
Pydantic schemas for Phase 24.5 — Academic Structure Management.

Read/create/update schemas for:
  - AcademicSession (HEAD_ADMIN managed)
  - Semester (under a session)
  - Section (under a semester)
  - Subsection (under a section)

No delete schemas — destructive action policy (Gate 7) is unresolved.

Registration-warning metadata is included in creation/mutation responses to
surface the operational impact of adding semesters/sections that break the
single-active-session registration auto-assign invariant.
"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared warning metadata
# ---------------------------------------------------------------------------

class RegistrationWarning(BaseModel):
    """Truthful operational warning attached to responses when creating
    structure elements that affect student self-registration.

    Registration currently requires:
      - Exactly 1 active AcademicSession
      - Exactly 1 Semester under that session
      - Exactly 1 Section under that semester

    Creating a second semester or section breaks the auto-assign and causes
    new registrations to fail with 409.  Existing students are NOT affected.
    This warning is informational only — the operation is not blocked by it.
    """
    code: str  # e.g. "MULTI_SEMESTER" / "MULTI_SECTION"
    message: str


# ---------------------------------------------------------------------------
# AcademicSession schemas
# ---------------------------------------------------------------------------

class AcademicSessionResponse(BaseModel):
    """A single academic session (e.g. "2026-27")."""
    id: UUID
    name: str
    start_date: date
    end_date: date
    is_active: bool
    semester_count: int = 0

    model_config = {"from_attributes": True}


class CreateSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    start_date: date
    end_date: date
    # New sessions always start inactive; explicit activation is separate.


class UpdateSessionRequest(BaseModel):
    """Patch a session name/dates.

    is_active changes go through the explicit /activate or /deactivate
    sub-resources to enforce the single-active invariant atomically.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class SessionActivationResponse(BaseModel):
    """Result of an explicit activate/deactivate operation."""
    id: UUID
    name: str
    is_active: bool
    warnings: List[RegistrationWarning] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Semester schemas
# ---------------------------------------------------------------------------

class SemesterResponse(BaseModel):
    id: UUID
    name: str
    session_id: UUID
    session_name: str
    start_date: date
    end_date: date
    section_count: int = 0

    model_config = {"from_attributes": True}


class CreateSemesterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    start_date: date
    end_date: date


class UpdateSemesterRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class SemesterMutationResponse(BaseModel):
    semester: SemesterResponse
    warnings: List[RegistrationWarning] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Section schemas
# ---------------------------------------------------------------------------

class SectionResponse(BaseModel):
    id: UUID
    name: str
    program: Optional[str] = None
    semester_id: UUID
    semester_name: str
    subsection_count: int = 0
    student_count: int = 0

    model_config = {"from_attributes": True}


class CreateSectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    # program: free-text (no Branch entity — Phase 23.1 Gate 3 open)
    program: Optional[str] = Field(None, max_length=100)


class UpdateSectionRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    program: Optional[str] = Field(None, max_length=100)


class SectionMutationResponse(BaseModel):
    section: SectionResponse
    warnings: List[RegistrationWarning] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Subsection schemas
# ---------------------------------------------------------------------------

class SubsectionAdminResponse(BaseModel):
    """Richer subsection view for the structure area (Phase 24.5).

    Note: this is separate from SubsectionDropdownResponse in admin_students.py
    which is a lightweight dropdown helper for the student assignment dialogs.
    """
    id: UUID
    name: str
    section_id: UUID
    section_name: str
    # Nullable per authoritative Phase 23.1 semantics — no fabricated default.
    max_strength: Optional[int] = None
    student_count: int = 0

    model_config = {"from_attributes": True}


class CreateSubsectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    max_strength: Optional[int] = Field(None, ge=1)


class UpdateSubsectionRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    max_strength: Optional[int] = Field(None, ge=1)
