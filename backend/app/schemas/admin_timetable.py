"""
Phase 24.7-A/B — Admin Timetable schemas.

The timetable is the EXPECTED academic schedule (per Section, optionally per
Subsection) — distinct from actual ``class_sessions`` occurrences.  These
schemas let the admin API layer represent the full timetable domain contract
so later slices can serialize without inventing a second style.

24.7-A: READ REPRESENTATION (TimetableEntryAdminResponse).
24.7-B: Create/update request schemas + mutation response.
"""

from datetime import time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ClassType, ElectiveSlot


# ---------------------------------------------------------------------------
# Read response (24.7-A)
# ---------------------------------------------------------------------------

class TimetableEntryAdminResponse(BaseModel):
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


# ---------------------------------------------------------------------------
# Create / Update (24.7-B)
# ---------------------------------------------------------------------------

class CreateTimetableEntryRequest(BaseModel):
    section_id: UUID
    subject_id: UUID
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    class_type: ClassType
    room: Optional[str] = Field(None, max_length=100)
    subsection_id: Optional[UUID] = None
    elective_slot: Optional[ElectiveSlot] = None
    is_active: bool = True
    sort_order: Optional[int] = None


class UpdateTimetableEntryRequest(BaseModel):
    """Patch a timetable entry (explicit-PATCH semantics).

    ``section_id``, ``subject_id``, ``elective_slot``, ``day_of_week``,
    ``start_time``, ``end_time``, ``class_type``, and ``subsection_id`` are
    scheduling-critical fields.  Changing them on an INACTIVE entry is
    refused (INACTIVE_PARENT) — the entry must be reactivated first so
    conflict detection runs against the live context.

    Use ``model_fields_set`` to distinguish absent from explicit-null.
    """
    section_id: Optional[UUID] = None
    subject_id: Optional[UUID] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    class_type: Optional[ClassType] = None
    room: Optional[str] = Field(None, max_length=100)
    subsection_id: Optional[UUID] = None
    elective_slot: Optional[ElectiveSlot] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class TimetableEntryMutationResponse(BaseModel):
    entry: TimetableEntryAdminResponse


# ---------------------------------------------------------------------------
# Duplicate (24.7-C)
# ---------------------------------------------------------------------------

class DuplicateTimetableEntryRequest(BaseModel):
    """Duplicate an existing timetable entry server-side.

    Every field is optional: absent fields are copied from the source entry.
    Provide overrides to change the target day/time/scope as required.  The
    full resulting entry is validated (academic context, elective slot, time
    range) and conflict detection runs against the prospective entry — a
    duplicate never silently overwrites another entry.
    """
    section_id: Optional[UUID] = None
    subject_id: Optional[UUID] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    class_type: Optional[ClassType] = None
    room: Optional[str] = Field(None, max_length=100)
    subsection_id: Optional[UUID] = None
    elective_slot: Optional[ElectiveSlot] = None
    is_active: bool = True
    sort_order: Optional[int] = None