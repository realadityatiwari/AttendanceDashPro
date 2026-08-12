from uuid import UUID
from pydantic import BaseModel
from typing import Optional
from datetime import date
from app.models.laboratory import SignatureStatus

class LaboratoryExperimentResponse(BaseModel):
    id: UUID
    subject_id: UUID
    experiment_number: int
    title: str

    class Config:
        from_attributes = True

class LaboratoryRecordResponse(BaseModel):
    id: UUID
    student_id: UUID
    experiment_id: UUID
    signature_status: SignatureStatus
    date_conducted: Optional[date] = None
    marks: Optional[float] = None
    remarks: Optional[str] = None

    class Config:
        from_attributes = True
