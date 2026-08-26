from pydantic import BaseModel
from datetime import date
from typing import Optional, List
from uuid import UUID
from app.models.enums import EventType, ClassType, ElectiveSlot

class AcademicEventResponse(BaseModel):
    id: UUID
    event_type: EventType
    start_date: date
    end_date: date
    subject_id: Optional[UUID] = None
    # Phase 22.4: the logical Departmental Elective slot the event belongs to
    # (null for regular events). A slot event is ONE shared row for all
    # students; `resolved_subject_*` carries the effective subject resolved
    # for the authenticated student (their selected elective, or the shared
    # anchor for a user with no selection — e.g. ADMIN).
    elective_slot: Optional[ElectiveSlot] = None
    resolved_subject_id: Optional[UUID] = None
    resolved_subject_code: Optional[str] = None
    resolved_subject_name: Optional[str] = None
    class_type: Optional[ClassType] = None
    is_working_day: Optional[bool] = None
    substitution_schedule_override: Optional[str] = None
    note: Optional[str] = None
    active: bool

    class Config:
        from_attributes = True

class AcademicEventCreate(BaseModel):
    """
    Create payload (Phase 6.5 + Phase 9.1 + Phase 22.4). Structural shape only;
    business rules live in the event validation registry (EventService).
    `elective_slot` scopes the event to a Departmental Elective logical slot
    (ADMIN-only; the server resolves and stores the shared anchor subject).
    `subject_id` and `elective_slot` are mutually exclusive.
    """
    event_type: EventType
    start_date: date
    end_date: date
    subject_id: Optional[UUID] = None
    elective_slot: Optional[ElectiveSlot] = None
    class_type: Optional[ClassType] = None
    is_working_day: Optional[bool] = None
    substitution_schedule_override: Optional[str] = None
    note: Optional[str] = None
    active: bool = True

class AcademicEventUpdate(BaseModel):
    """Partial update payload. Absent fields are left unchanged."""
    event_type: Optional[EventType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    subject_id: Optional[UUID] = None
    elective_slot: Optional[ElectiveSlot] = None
    class_type: Optional[ClassType] = None
    is_working_day: Optional[bool] = None
    substitution_schedule_override: Optional[str] = None
    note: Optional[str] = None
    active: Optional[bool] = None

class AcademicDayResponse(BaseModel):
    date: date
    is_working_day: bool
    day_type: str
    is_teaching_day: bool
    original_day_of_week: str
    substitution_schedule_override: Optional[str] = None
    events: List[AcademicEventResponse] = []

class CalendarDayItem(AcademicDayResponse):
    """
    One calendar day in the month read model (Phase 6.2).

    Extends the day-resolution shape with two render-only fields so the
    future calendar UI never recomputes calendar semantics:
      - non_working_reason: why the day is non-working (dominant event title
        when an event is active on the day, else 'Weekend'); None when working.
      - session_count: scheduled class sessions for the authenticated student's
        enrolled subjects on this date (cancelled sessions are still scheduled
        rows and are included in the count).
    """
    non_working_reason: Optional[str] = None
    session_count: int = 0

class CalendarMonthResponse(BaseModel):
    """
    Month-bounded calendar read model (Phase 6.2).

    The requested month is clamped to the authenticated student's real
    academic semester (semester_start/semester_end). `effective_start` /
    `effective_end` are that intersection; when the month lies entirely
    outside the semester they are inverted (effective_start > effective_end)
    and `days` is empty — a truthful empty result, never invented dates.
    When the student has no academic context (no section/semester), all
    bounds are None and `days` is empty.
    """
    year: int
    month: int
    semester_start: Optional[date] = None
    semester_end: Optional[date] = None
    effective_start: Optional[date] = None
    effective_end: Optional[date] = None
    days: List[CalendarDayItem] = []
