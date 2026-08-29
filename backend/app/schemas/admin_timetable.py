"""
Phase 24.7-A — Admin Timetable Domain schemas.

The timetable is the EXPECTED academic schedule (per Section, optionally per
Subsection) — distinct from actual ``class_sessions`` occurrences.  These
schemas let the admin API layer represent the full timetable domain contract
so later slices (24.7-B CRUD) can serialize without inventing a second style.

This slice defines the READ REPRESENTATION ONLY.  Create/update request
schemas and the CRUD endpoints belong to Phase 24.7-B.
"""

from datetime import time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ClassType, ElectiveSlot


class TimetableEntryAdminResponse(BaseModel):
    """A single expected-schedule entry (Phase 24.7 contract).

    Fields mirror the authoritative TimetableEntry model.  ``subsection_id``
    is NULL for section-wide entries; ``elective_slot`` marks the shared
    Departmental Elective slot (never resolved per student here — resolution
    stays in the student-facing layer).  ``sort_order`` is a nullable
    deterministic ordering hint.
    """
    id: UUID
    section_id: UUID
    section_name: str
    subsection_id: Optional[UUID] = None
    subsection_name: Optional[str] = None
    subject_id: UUID
    subject_code: str
    subject_name: str
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    class_type: ClassType
    room: Optional[str] = None
    elective_slot: Optional[ElectiveSlot] = None
    is_active: bool = True
    sort_order: Optional[int] = None

    model_config = {"from_attributes": True}


class TimetableEntryAdminListResponse(BaseModel):
    items: List[TimetableEntryAdminResponse] = Field(default_factory=list)
    total: int = 0
