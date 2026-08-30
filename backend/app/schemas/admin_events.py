"""
Phase 24.9 — Admin Event Manager schemas.

The existing EventService / event registry / EventSessionSynchronizer /
AcademicEvent model are reused for all mutations.  This module provides the
additive admin-specific event read model and wraps the canonical mutation
path with the Phase 24.9 QUIZ_DAY ownership guard.
"""
from datetime import date
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