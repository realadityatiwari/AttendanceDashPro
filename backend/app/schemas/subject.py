from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from app.models.enums import SubjectCategory, ElectiveSlot

class SubjectResponse(BaseModel):
    id: UUID
    code: str
    name: str
    tag: Optional[str] = None
    # Phase 23.5: authoritative DB-backed catalog slot marker (NULL = common/
    # practical subject). Additive, backward compatible.
    elective_slot: Optional[ElectiveSlot] = None
    category: SubjectCategory
    quiz_applicable: bool
    attendance_applicable: bool

    class Config:
        from_attributes = True
