from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from uuid import UUID
from datetime import date

from app.models.enums import ElectiveSlot, EnrollmentType


class AdminStudentSummary(BaseModel):
    """A single student row in the scoped admin list (Phase 24.3).

    Read-only presentation of one STUDENT-role account with its academic
    placement. ``is_placed`` is True only when the student has a section
    (section -> semester -> session resolution happens in the detail read).
    Unplaced / unassigned-subsection students are represented honestly
    (NULL), never fabricated."""
    id: UUID
    roll_number: str
    name: str
    section_name: Optional[str] = None
    program: Optional[str] = None
    semester_name: Optional[str] = None
    subsection_name: Optional[str] = None
    is_placed: bool = False
    is_active: bool = True


class AdminStudentListResponse(BaseModel):
    """Scoped, paginated student list (Phase 24.3).

    ``total`` / ``pages`` reflect the scope-filtered count, so a scoped admin
    never learns the size of the global student body beyond their scope."""
    items: List[AdminStudentSummary] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    pages: int = 0


class AdminStudentEnrollment(BaseModel):
    """One enrollment row in the detail read — reuse of the authoritative
    Phase 23.3 COMPULSORY / ELECTIVE discriminator (no re-derivation)."""
    id: UUID
    code: str
    name: str
    enrollment_type: EnrollmentType


class AdminStudentDetail(BaseModel):
    """Full academic context of one student for a scoped admin (Phase 24.3).

    Composed from ``StudentContextService.get_context`` — the single
    authoritative context authority (placement, enrollments with their
    COMPULSORY/ELECTIVE types, elective choices, inconsistencies). Read-only;
    no attendance mathematics (that is the Phase 24.13 attendance-admin
    domain). Unknown/incomplete state is honest (NULL / empty /
    ``inconsistencies``), never repaired."""
    id: UUID
    roll_number: str
    name: str
    is_active: bool = True

    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    program: Optional[str] = None
    semester_id: Optional[UUID] = None
    semester_name: Optional[str] = None
    semester_start: Optional[date] = None
    semester_end: Optional[date] = None
    academic_session_id: Optional[UUID] = None
    academic_session_name: Optional[str] = None
    subsection_id: Optional[UUID] = None
    subsection_name: Optional[str] = None
    is_placed: bool = False

    enrollments: List[AdminStudentEnrollment] = Field(default_factory=list)
    compulsory_subjects: List[AdminStudentEnrollment] = Field(default_factory=list)
    elective_subjects: List[AdminStudentEnrollment] = Field(default_factory=list)
    elective_choices: Dict[str, str] = Field(default_factory=dict)
    inconsistencies: List[str] = Field(default_factory=list)
    first_quiz_date: Optional[date] = None

class AssignSubsectionRequest(BaseModel):
    subsection_id: UUID

class CorrectElectiveRequest(BaseModel):
    slot: ElectiveSlot
    subject_id: UUID

class SetStudentStatusRequest(BaseModel):
    is_active: bool

class SubsectionDropdownResponse(BaseModel):
    id: UUID
    name: str
    max_strength: Optional[int] = None
    current_strength: Optional[int] = None

class ElectiveDropdownResponse(BaseModel):
    id: UUID
    code: str
    name: str
    elective_slot: ElectiveSlot
