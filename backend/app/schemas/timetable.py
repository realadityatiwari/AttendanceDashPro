from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from app.models.enums import ClassType, ElectiveSlot
from app.schemas.subject import SubjectResponse

class TimetableEntryResponse(BaseModel):
    id: UUID
    day_of_week: int
    class_type: ClassType
    subject: SubjectResponse
    # Phase 22.4: the logical Departmental Elective slot this shared entry
    # belongs to (ELECTIVE_I / ELECTIVE_II), or null for regular entries.
    # `subject` is already resolved to the authenticated student's selection
    # by the timetable endpoint; this marker is presentation/admin context.
    elective_slot: Optional[ElectiveSlot] = None

    class Config:
        from_attributes = True
