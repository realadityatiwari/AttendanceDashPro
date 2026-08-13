from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import date
from app.models.enums import ClassType, EventType

# Dashboard read model — additive, read-only aggregation contract consumed by
# the Home page. All values are computed by DashboardService from the existing
# attendance/eligibility/calendar services and engines; no business rule is
# re-implemented here.

class DashboardClassItem(BaseModel):
    session_id: UUID
    subject_code: str
    subject_name: str
    class_type: ClassType
    # ATTENDED | MISSED | PENDING | CANCELLED — mirrors AttendanceStatus plus
    # the explicit cancelled/unrecorded states the Home page must render.
    status: str
    is_extra: bool = False

class TodaySection(BaseModel):
    date: date
    is_working_day: bool = True
    is_teaching_day: bool = True
    day_note: Optional[str] = None
    classes: List[DashboardClassItem] = []
    attended: int = 0
    total: int = 0

class OverallSection(BaseModel):
    semester_start: Optional[date] = None
    overall_pct: Optional[float] = None
    attended: int = 0
    recorded: int = 0
    pending: int = 0
    # SAFE | WATCH | CRITICAL | None (no data)
    status: Optional[str] = None
    weekly_delta_pct: Optional[float] = None

class WeekDayItem(BaseModel):
    date: date
    day_label: str
    is_today: bool = False
    is_future: bool = False
    classes: int = 0
    attended: int = 0
    recorded: int = 0

class SubjectBrief(BaseModel):
    subject_code: str
    subject_name: str
    pct: Optional[float] = None

class WeeklySection(BaseModel):
    week_start: date
    week_end: date
    days: List[WeekDayItem] = []
    weekly_pct: Optional[float] = None
    recorded: int = 0
    previous_week_pct: Optional[float] = None
    delta_pct: Optional[float] = None
    best_subject: Optional[SubjectBrief] = None
    needs_attention_subject: Optional[SubjectBrief] = None

class QuizSnapshotSection(BaseModel):
    # None when no quiz cycle can be resolved for the student.
    quiz_cycle: Optional[int] = None
    quiz_label: Optional[str] = None
    quiz_date: Optional[date] = None
    threshold: Optional[float] = None
    eligible: int = 0
    attention: int = 0
    not_eligible: int = 0
    total_theory: int = 0
    has_snapshot: bool = False

class AttentionItem(BaseModel):
    subject_code: str
    subject_name: str
    current_pct: Optional[float] = None
    forecast_pct: Optional[float] = None
    # WATCH | CRITICAL (SAFE subjects are not surfaced here)
    status: str

class UpcomingEventItem(BaseModel):
    id: UUID
    event_type: EventType
    start_date: date
    end_date: date
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    class_type: Optional[ClassType] = None

class DashboardSummaryResponse(BaseModel):
    generated_at: date
    today: TodaySection
    overall: OverallSection
    weekly: WeeklySection
    quiz_snapshot: QuizSnapshotSection
    attention_required: List[AttentionItem] = []
    upcoming_events: List[UpcomingEventItem] = []