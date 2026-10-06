"""
Phase 24.9 — Admin Event Manager schemas.

The existing EventService / event registry / EventSessionSynchronizer /
AcademicEvent model are reused for all mutations.  This module provides the
additive admin-specific event read model and wraps the canonical mutation
path with the Phase 24.9 QUIZ_DAY ownership guard.
"""
from datetime import date, time
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ClassType, ElectiveSlot, EventType


# ---------------------------------------------------------------------------
# Admin event read model
# ---------------------------------------------------------------------------

class AdminEventResponse(BaseModel):
    id: UUID
    event_type: EventType
    active: bool
    start_date: date
    end_date: date
    subject_id: Optional[UUID] = None
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    # OCC-1: the exact scheduled timetable occurrence a cancellation event
    # targets (CLASS_CANCELLED / LAB_CANCELLED); null for every other type.
    timetable_entry_id: Optional[UUID] = None
    # OCC-1: server-computed human-readable description of the referenced
    # occurrence (code — name (Class type) · weekday HH:MM–HH:MM), so the
    # admin UI never reconstructs it from the weekly timetable.
    occurrence_label: Optional[str] = None
    elective_slot: Optional[ElectiveSlot] = None
    class_type: Optional[ClassType] = None
    is_working_day: Optional[bool] = None
    substitution_schedule_override: Optional[str] = None
    note: Optional[str] = None
    # Phase 24.9: whether this event is managed by the Quiz Schedule Manager
    # (meaning a QuizSchedule row exists with matching date/subject/slot).
    # QUIZ_DAY events that match an active quiz schedule must not be mutated
    # through the generic Event Manager — quiz schedule changes belong to
    # /admin/quizzes.
    quiz_schedule_managed: bool = False
    # Human-readable scope/target summary.
    target_summary: str = ""
    # Phase 24.10: the concrete subject's catalog elective slot (None for
    # common subjects and slot-wide events). Distinct from the event's own
    # elective_slot marker (set only on slot-wide events).
    subject_slot: Optional[ElectiveSlot] = None
    # Phase 24.10: server-computed mutation capability for the acting admin
    # (same can_mutate_event semantics EventService enforces). UX hint only —
    # the backend remains the authorization boundary.
    can_mutate: bool = False

    model_config = {"from_attributes": True}


class AdminEventListResponse(BaseModel):
    items: List[AdminEventResponse] = Field(default_factory=list)
    total: int = 0


class AdminEventMutationResponse(BaseModel):
    event: AdminEventResponse


# ---------------------------------------------------------------------------
# OCC-1 — occurrence options read model ("available timetable occurrences for
# event creation on this date"). The backend resolves the effective day
# (substitution/working state via the canonical calendar engine), applies the
# admin's section/subject scope and the event type's class-type constraints,
# and returns every selectable occurrence with the data the Events UI needs.
# ---------------------------------------------------------------------------

class AdminOccurrenceElectiveSubject(BaseModel):
    """A concrete elective subject a slot occurrence may be narrowed to."""
    id: UUID
    code: str
    name: str


class AdminOccurrenceOption(BaseModel):
    timetable_entry_id: UUID
    subject_id: UUID
    subject_code: str
    subject_name: str
    class_type: ClassType
    start_time: time
    end_time: time
    section_id: UUID
    section_name: str
    subsection_id: Optional[UUID] = None
    subsection_name: Optional[str] = None
    # The shared Departmental Elective slot this entry belongs to (null for
    # regular entries). Slot entries keep the anchor subject in subject_id.
    elective_slot: Optional[ElectiveSlot] = None
    # True when subject_id is the slot's shared anchor (BCS-054 / BCS-058).
    is_slot_anchor: bool = False
    # Concrete elective members the occurrence may be narrowed to (a
    # subject-specific cancellation resolves to that subject only). Empty for
    # regular entries.
    elective_subjects: List[AdminOccurrenceElectiveSubject] = Field(
        default_factory=list
    )
    # Ready-to-render label, e.g.
    # "BCS-502 — Web Technology (Lecture) · 10:00–11:00".
    display_label: str


class AdminOccurrenceOptionsResponse(BaseModel):
    """
    The canonical day resolution for the requested date plus the selectable
    occurrences. On a non-working day `items` is empty and
    `non_working_reason` explains why (Weekend or the dominant closure event).
    """
    date: date
    event_type: Optional[EventType] = None
    is_working_day: bool
    day_type: str
    # The weekday the date's schedule follows (substitution applied).
    schedule_day: str
    non_working_reason: Optional[str] = None
    items: List[AdminOccurrenceOption] = Field(default_factory=list)
    total: int = 0