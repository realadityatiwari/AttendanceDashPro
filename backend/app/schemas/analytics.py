from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from app.schemas.attendance import SubjectAttendanceSummary

# Phase 8.1 analytics read model (Phase 8.0 contract §L-1). A pure read model:
# every value is derived from the canonical attendance/eligibility services and
# engines; no analytics mathematics is re-implemented here.


class OverallAnalytics(BaseModel):
    """Overall attendance (ERP semantics, Phase 8.0 contract §7/§8).

    current_pct = Σ attended / Σ recorded × 100 over [semester_start, as_of]
    (recorded-only: pending excluded from the current denominator, never
    converted to absent). forecast_pct = Σ (attended + pending) / Σ total × 100
    (pending treated as attended — the canonical forecast semantics). Cancelled
    sessions are excluded. Not an average of subject percentages.
    """
    current_pct: Optional[float] = None
    forecast_pct: Optional[float] = None
    attended: int = 0
    recorded: int = 0
    pending: int = 0
    cancelled: int = 0
    # SAFE | WATCH | CRITICAL | None (canonical 3-state current banding;
    # AT-RISK is NOT defined by Phase 8.0 and is never emitted).
    status: Optional[str] = None


class WeeklyAnalyticsItem(BaseModel):
    """One Monday-start week bucket of the weekly read-model series.

    A backend read-model structure only (Phase 8.0 contract §I/§L-1): recorded-
    only Σatt/Σrecorded per week with pending surfaced separately; no trend
    semantics, no rolling windows, no AT-RISK. current_pct is None (a gap) when
    nothing was recorded in the week.
    """
    week_start: date
    current_pct: Optional[float] = None
    attended: int = 0
    recorded: int = 0
    pending: int = 0


class AnalyticsSubjectItem(SubjectAttendanceSummary):
    """Per-subject analytics: the canonical extended SubjectAttendanceSummary
    (incl. practical %, subject-level 75% optimization) plus identity."""

    subject_name: Optional[str] = None


class AnalyticsOverviewResponse(BaseModel):
    as_of: date
    semester_start: Optional[date] = None
    semester_end: Optional[date] = None
    overall: OverallAnalytics
    weekly: List[WeeklyAnalyticsItem] = []
    subjects: List[AnalyticsSubjectItem] = []
