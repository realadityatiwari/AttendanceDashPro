"""
Phase 24.6 — Admin Subject / Curriculum Management schemas.

Admin contracts for the scoped subject list, detail, create, and update.
Read authorization is require_any_admin (scoped per approval matrix).
Write authorization is require_head_admin only.

No delete schema — destructive action policy (Gate 7) is unresolved.
"""

from datetime import date
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ElectiveSlot, SubjectCategory
from app.schemas.admin_structure import RegistrationWarning


# ---------------------------------------------------------------------------
# Subject list item (scoped — every admin type sees a subset)
# ---------------------------------------------------------------------------

class AdminSubjectSummary(BaseModel):
    """A single subject row in the scoped admin curriculum list.

    Semester/session context attached so CLASS_ADMIN can verify scope.
    Dependent counts are bounded aggregate queries, never materialized lists.
    """
    id: UUID
    code: str
    name: str
    tag: Optional[str] = None
    elective_slot: Optional[ElectiveSlot] = None
    category: SubjectCategory
    quiz_applicable: bool
    attendance_applicable: bool
    semester_id: UUID
    semester_name: str
    session_name: str
    # Whether this subject is a shared elective anchor (BCS-054 / BCS-058).
    is_anchor: bool = False
    # Bounded counts — one subquery per list, not per-row.
    enrollment_count: int = 0
    elective_choice_count: int = 0

    model_config = {"from_attributes": True}


class AdminSubjectListResponse(BaseModel):
    items: List[AdminSubjectSummary] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Subject detail (richer — includes all bounded dependent counts)
# ---------------------------------------------------------------------------

class AdminSubjectDetail(AdminSubjectSummary):
    """Full subject detail for the admin curriculum area.

    Dependent counts are bounded aggregate queries, never row materialization.
    """
    # Additional dependent counts not shown in the list.
    timetable_entry_count: int = 0
    class_session_count: int = 0
    quiz_schedule_count: int = 0
    lab_experiment_count: int = 0
    attendance_record_count: int = 0


# ---------------------------------------------------------------------------
# Create / Update
# ---------------------------------------------------------------------------

class CreateSubjectRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=200)
    tag: Optional[str] = Field(None, max_length=50)
    elective_slot: Optional[ElectiveSlot] = None
    category: SubjectCategory
    quiz_applicable: bool = True
    attendance_applicable: bool = True
    semester_id: UUID


class UpdateSubjectRequest(BaseModel):
    """Patch a subject.

    ``code`` and ``semester_id`` are explicitly included in this schema but
    the service rejects any attempt to change them with 409 — they are
    immutable after creation.  The fields are present so the 409 response is
    explicit (not a silent 422 from Pydantic extra-field rejection).

    ``elective_slot`` follows the project's explicit-PATCH convention:
    - absent (not in the JSON body) → unchanged
    - present with a value (e.g. ``ELECTIVE_I``) → set
    - present with ``null`` → clear (remove from catalog)
    Use ``request.model_fields_set`` to distinguish absent from explicit null.
    """
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    tag: Optional[str] = Field(None, max_length=50)
    elective_slot: Optional[ElectiveSlot] = None
    category: Optional[SubjectCategory] = None
    quiz_applicable: Optional[bool] = None
    attendance_applicable: Optional[bool] = None
    semester_id: Optional[UUID] = None


# ---------------------------------------------------------------------------
# Mutation response
# ---------------------------------------------------------------------------

class SubjectMutationResponse(BaseModel):
    subject: AdminSubjectDetail
    warnings: List[RegistrationWarning] = Field(default_factory=list)