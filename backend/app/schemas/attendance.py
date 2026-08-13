from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime
from app.models.enums import ClassType, AttendanceStatus

class AttendanceRecord(BaseModel):
    date: date
    subject_code: str
    class_type: ClassType
    status: AttendanceStatus
    
class AttendanceHistoryItem(BaseModel):
    """One scheduled class session in the authenticated student's semester,
    with the student's canonical attendance state (no record = Pending)."""
    id: str
    date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    subject_code: str
    subject_name: str
    class_type: ClassType
    status: AttendanceStatus
    is_cancelled: bool = False
    is_extra: bool = False
    marked_at: Optional[datetime] = None

class HistorySummary(BaseModel):
    """Counts over the filtered history result set (same canonical semantics
    as Track: cancelled sessions are their own state, never absent)."""
    total: int = 0
    attended: int = 0
    missed: int = 0
    pending: int = 0
    cancelled: int = 0
    pct: Optional[float] = None

class AttendanceHistoryResponse(BaseModel):
    semester_start: Optional[date] = None
    semester_end: Optional[date] = None
    range_start: Optional[date] = None
    range_end: Optional[date] = None
    items: List[AttendanceHistoryItem]
    total_count: int
    summary: HistorySummary = Field(default_factory=HistorySummary)

class ClassCounts(BaseModel):
    total: int = 0
    attended: int = 0
    missed: int = 0
    pending: int = 0

class SubjectAttendanceSummary(BaseModel):
    subject_code: str
    lecture: ClassCounts = Field(default_factory=ClassCounts)
    tutorial: ClassCounts = Field(default_factory=ClassCounts)
    practical: ClassCounts = Field(default_factory=ClassCounts)
    
    current_lecture_pct: Optional[float] = None
    current_tutorial_pct: Optional[float] = None
    current_avg_pct: Optional[float] = None
    
    forecast_lecture_pct: Optional[float] = None
    forecast_tutorial_pct: Optional[float] = None
    forecast_avg_pct: Optional[float] = None

class OptimizationResult(BaseModel):
    lecture_deficit: int = 0
    tutorial_deficit: int = 0
    safe_skip_lecture: int = 0
    safe_skip_tutorial: int = 0
    is_reachable: bool = True

class EligibilityResult(BaseModel):
    quiz_cycle: int
    subject_code: str
    window_start: date
    window_end: date
    
    # Policy evaluation
    lecture_threshold: Optional[float] = None
    combined_threshold: Optional[float] = None
    
    # Results
    is_eligible: bool
    optimization: Optional[OptimizationResult] = None
    
    # Document potential conflicts or ambiguities
    policy_ambiguity_notes: Optional[str] = None

class DailySessionResponse(BaseModel):
    id: str
    date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    subject_code: str
    subject_name: str
    class_type: ClassType
    status: AttendanceStatus
    is_cancelled: bool
    is_extra: bool

class DailySessionsResponse(BaseModel):
    date: date
    sessions: List[DailySessionResponse]
