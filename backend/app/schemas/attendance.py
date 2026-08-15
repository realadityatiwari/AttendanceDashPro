from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime
from enum import Enum
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
    # Phase 9.1: session designation (e.g. "MID_SEM_PRACTICAL") — an additive
    # presentation field read from ClassSession.designation. NULL for regular
    # sessions. Never used in any attendance calculation.
    designation: Optional[str] = None
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

class OptimizationResult(BaseModel):
    lecture_deficit: int = 0
    tutorial_deficit: int = 0
    safe_skip_lecture: int = 0
    safe_skip_tutorial: int = 0
    is_reachable: bool = True

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

    # Phase 8.1 additive analytics (Phase 8.0 contract §H/§L-2): practical
    # attendance percentages use the canonical class-session pipeline (no
    # quiz-window dependency); the subject-level 75% optimization reuses the
    # attendance engine's own optimizer against the subject's semester-to-date
    # counts (same counting as the summary itself). No new formula.
    current_practical_pct: Optional[float] = None
    forecast_practical_pct: Optional[float] = None
    optimization: Optional[OptimizationResult] = None

    # Attendance UI refinement (spec alignment): the required attendance target
    # the subject-level optimizer reasons about (75%) and the canonical current
    # status band (SAFE | WATCH | CRITICAL | None) derived from the same
    # engine banding the dashboard/analytics use. Both are additive, backend-
    # emitted values — the frontend renders them and never recomputes banding.
    # NOTE (Phase 8.2): `status` (legacy SAFE/WATCH/CRITICAL) stays emitted for
    # backwards compatibility; the Attendance page consumes `health` instead.
    required_pct: float = 75.0
    status: Optional[str] = None

    # Phase 8.2 Attendance Health: the canonical 4-state classification for the
    # subject's OVERALL attendance (HEALTHY | WATCH | AT_RISK | CRITICAL |
    # None), emitted by the backend from the attendance engine's own
    # classification (thresholds documented in
    # docs/phase_8_2_implementation_report.md). The Attendance page renders it;
    # React never bands attendance. None when nothing is recorded.
    health: Optional[str] = None

    # Phase 8.2 mid-semester practical designation (lab domain): the actual
    # scheduled PRACTICAL class session the admin/faculty designated as the
    # subject's mid-semester practical, if any. Always None until such a
    # session is explicitly designated — the designation is a session-level
    # fact (ClassSession.designation), never inferred from experiment counts
    # or a computed date. Attendance against it is recorded through the normal
    # attendance mutation.
    mid_sem_session_id: Optional[str] = None
    mid_sem_session_date: Optional[date] = None

class EligibilityState(str, Enum):
    """Canonical quiz eligibility state for a subject/cycle pair.

    ELIGIBLE      — the current attendance percentage satisfies the policy.
    RECOVERABLE   — currently below the requirement but reachable by attending
                    the remaining (pending) classes.
    NOT_ELIGIBLE  — the requirement cannot be reached within the remaining
                    attendance window.
    UNRESOLVED    — no confirmed quiz date/policy (e.g. an unresolved cycle),
                    so no result can be determined.
    """
    ELIGIBLE = "ELIGIBLE"
    RECOVERABLE = "RECOVERABLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    UNRESOLVED = "UNRESOLVED"

class CriterionResult(BaseModel):
    """One qualifying route of the official policy (S4 PRODUCT SPEC §5):
    Criterion I — Lecture attendance; Criterion II — Combined average."""
    name: str
    value: Optional[float] = None
    threshold: float
    passed: bool
    explanation: str

class FinalCriterionResult(BaseModel):
    """Combination of the qualifying routes:
    (Criterion 1 qualifies) OR (Criterion 2 qualifies) = Eligible."""
    combination: str
    passed: bool
    explanation: str

class CurrentQuizCycle(BaseModel):
    """Canonical 'currently relevant' quiz cycle for the authenticated student.

    Derived solely from the authoritative quiz_schedules table (SCHEDULED +
    dated): the cycle of the next quiz at/after today; when none remains, the
    highest-numbered resolved cycle; otherwise the documented fallback (Quiz I)
    with has_schedule=False. The Quiz Eligibility page uses this only to
    preselect a default tab — it never invents quiz dates, and manual tab
    selection is unaffected (tab state stays client-side).

    basis: "next_upcoming" | "latest_resolved" | "fallback".
    """
    quiz_cycle: int
    quiz_label: Optional[str] = None
    quiz_date: Optional[date] = None
    has_schedule: bool
    basis: str

class EligibilityResult(BaseModel):
    quiz_cycle: int
    subject_code: str
    subject_name: Optional[str] = None
    category: Optional[str] = None
    quiz_date: Optional[date] = None
    window_start: date
    window_end: date
    
    # Policy evaluation
    lecture_threshold: Optional[float] = None
    combined_threshold: Optional[float] = None
    required_percentage: Optional[float] = None
    
    # Window analytics (same canonical counting as Track)
    lecture: ClassCounts = Field(default_factory=ClassCounts)
    tutorial: ClassCounts = Field(default_factory=ClassCounts)
    lecture_pct: Optional[float] = None
    tutorial_pct: Optional[float] = None
    average_pct: Optional[float] = None
    
    # Canonical eligibility state + qualifying routes
    state: EligibilityState = EligibilityState.UNRESOLVED
    recoverable: bool = False
    criterion_i: Optional[CriterionResult] = None
    criterion_ii: Optional[CriterionResult] = None
    final_criterion: Optional[FinalCriterionResult] = None
    
    # Results
    is_eligible: bool
    optimization: Optional[OptimizationResult] = None
    explanation: Optional[str] = None
    
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
    # Phase 9.1: session designation (e.g. "MID_SEM_PRACTICAL") — additive
    # presentation field from ClassSession.designation. NULL for regular
    # sessions; never used in any attendance calculation.
    designation: Optional[str] = None

class DailySessionsResponse(BaseModel):
    date: date
    sessions: List[DailySessionResponse]
