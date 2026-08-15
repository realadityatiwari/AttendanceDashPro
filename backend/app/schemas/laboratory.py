from uuid import UUID
from pydantic import BaseModel
from typing import Optional
from datetime import date
from app.models.laboratory import SignatureStatus

class LaboratoryExperimentResponse(BaseModel):
    id: UUID
    subject_id: UUID
    experiment_number: int
    title: Optional[str] = None

    class Config:
        from_attributes = True

class LaboratoryRecordResponse(BaseModel):
    id: UUID
    user_id: UUID
    experiment_id: UUID
    signature_status: SignatureStatus
    date_conducted: Optional[date] = None
    marks: Optional[float] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True

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
