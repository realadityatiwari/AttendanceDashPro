"""
Phase 24.8 — Admin Quiz Management schemas.

Cycle/policy read models, QuizSchedule management (set dates, CANCELLED status),
and QUIZ_DAY derivation overview (materialization parity).
"""
from datetime import date as DateType
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ElectiveSlot
from app.models.quiz import ScheduleStatus


# ---------------------------------------------------------------------------
# Quiz cycle + policy (read)
# ---------------------------------------------------------------------------

class AdminQuizCycleResponse(BaseModel):
    id: UUID
    cycle_number: int
    label: str
    lecture_threshold: float
    combined_threshold: Optional[float] = None

    model_config = {"from_attributes": True}


class AdminQuizCycleListResponse(BaseModel):
    items: List[AdminQuizCycleResponse] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Quiz schedule (read)
# ---------------------------------------------------------------------------

class AdminQuizScheduleResponse(BaseModel):
    id: UUID
    subject_id: UUID
    subject_code: str
    subject_name: str
    cycle_number: int
    cycle_label: str
    elective_slot: Optional[ElectiveSlot] = None
    date: Optional[DateType] = None
    schedule_status: ScheduleStatus = ScheduleStatus.SCHEDULED
    # Whether an active QUIZ_DAY AcademicEvent exists for this schedule
    # (derivation parity indicator).
    has_active_event: bool = False
    # Whether the schedule is a shared elective slot (vs common subject).
    is_elective: bool = False

    model_config = {"from_attributes": True}


class AdminQuizScheduleListResponse(BaseModel):
    items: List[AdminQuizScheduleResponse] = Field(default_factory=list)
    total: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Quiz schedule create / update
# ---------------------------------------------------------------------------

class CreateQuizScheduleRequest(BaseModel):
    subject_id: UUID
    quiz_cycle_id: UUID
    date: Optional[DateType] = None
    schedule_status: ScheduleStatus = ScheduleStatus.SCHEDULED
    elective_slot: Optional[ElectiveSlot] = None


class UpdateQuizScheduleRequest(BaseModel):
    """PATCH quiz schedule.  Omitted fields unchanged; explicit null clears
    date (→ UNRESOLVED state).  The resulting complete state is validated
    server-side, and the QUIZ_DAY event is synchronized atomically."""
    date: Optional[DateType] = None
    schedule_status: Optional[ScheduleStatus] = None

    @field_validator("schedule_status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in (ScheduleStatus.SCHEDULED, ScheduleStatus.CANCELLED,
                                         ScheduleStatus.UNRESOLVED):
            raise ValueError(f"Invalid schedule status: {v}")
        return v


class AdminQuizScheduleMutationResponse(BaseModel):
    schedule: AdminQuizScheduleResponse
    event_created: bool = False
    event_deactivated: bool = False