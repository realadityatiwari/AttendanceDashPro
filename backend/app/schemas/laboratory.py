from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from app.models.laboratory import SignatureStatus

class LaboratoryExperimentResponse(BaseModel):
    id: UUID
    subject_id: UUID
    experiment_number: int
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True

class LaboratoryExperimentCreate(BaseModel):
    """Admin ingestion of a curriculum experiment (Phase 9.2.1)."""
    experiment_number: int = Field(ge=1)
    title: Optional[str] = None
    description: Optional[str] = None

class LaboratoryExperimentUpdate(BaseModel):
    """Admin correction of an experiment's metadata (title/description)."""
    title: Optional[str] = None
    description: Optional[str] = None

class LaboratoryRecordResponse(BaseModel):
    id: UUID
    user_id: UUID
    experiment_id: UUID
    class_session_id: Optional[UUID] = None
    signature_status: SignatureStatus
    date_conducted: Optional[date] = None
    signed_on: Optional[datetime] = None
    signed_by: Optional[UUID] = None
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    marks: Optional[float] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True

class LaboratoryRecordCreate(BaseModel):
    """Student self-tracking of an experiment (Phase 9.2.1). The record is
    ALWAYS created PENDING — signature status is not part of the payload;
    only an ADMIN can sign via the record PATCH endpoint."""
    experiment_id: UUID
    date_conducted: Optional[date] = None
    class_session_id: Optional[UUID] = None
    remarks: Optional[str] = None

class LaboratoryRecordUpdate(BaseModel):
    """Student edit of an own PENDING record (date/session/remarks) or admin
    sign/edit. Signature status may only be set to SIGNED and only by an
    admin (the service enforces both constraints)."""
    date_conducted: Optional[date] = None
    class_session_id: Optional[UUID] = None
    remarks: Optional[str] = None
    signature_status: Optional[SignatureStatus] = None

class PracticalAttendanceSummary(BaseModel):
    attended: int
    missed: int
    pending: int
    total: int
    current_practical_pct: float

class MidSemStatusSummary(BaseModel):
    designated: bool
    session_id: Optional[UUID] = None
    session_date: Optional[date] = None
    attendance_status: Optional[str] = None

class ExperimentProgressSummary(BaseModel):
    catalog_available: bool
    total: int
    signed: int
    pending_self_tracked: int
    advisory: Optional[str] = None

class LaboratorySummaryResponse(BaseModel):
    subject_code: str
    practical_attendance: PracticalAttendanceSummary
    mid_sem: MidSemStatusSummary
    experiment_progress: ExperimentProgressSummary

class LaboratoryActivityItem(BaseModel):
    id: UUID
    date: date
    class_type: str
    is_cancelled: bool
    is_extra: bool
    designation: Optional[str] = None
    attendance_status: Optional[str] = None
    experiments: List[LaboratoryRecordResponse]

class LaboratoryActivityResponse(BaseModel):
    subject_code: str
    items: List[LaboratoryActivityItem]

class MidSemDesignationPayload(BaseModel):
    """Admin request body designating an actual scheduled PRACTICAL session as
    the subject's mid-semester practical (Phase 8.2). The session must belong
    to the subject and be a PRACTICAL session; the service replaces any prior
    designation. Designation never alters attendance counting."""
    class_session_id: UUID

class MidSemDesignationResponse(BaseModel):
    subject_code: str
    session_id: Optional[UUID] = None
    # NOTE: named session_date, not date — a `date` field name shadows the
    # imported datetime.date type inside Pydantic annotations.
    session_date: Optional[date] = None
    designated: bool