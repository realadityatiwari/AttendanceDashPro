"""
Phase 24.12 — Attendance admin & analytics schemas (READ-ONLY).

Admin attendance reads per section, per subject roster, and per student,
computed server-side from the canonical class_sessions + attendance_records
pipeline (occurrence collapse, outcome application, elective resolution all
reuse the canonical engine). Attendance CORRECTION is a §25 decision gate and
is intentionally NOT exposed.

Scope (capability matrix "View analytics"): HEAD global; CLASS own sections
(section aggregates) and their semester's subjects; ELECTIVE own subject
roster (subject aggregates); SUBSECTION conservative-empty; STUDENT denied.
"""
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field
from datetime import date

from app.schemas.analytics import AnalyticsOverviewResponse


class AdminSectionAttendanceSummary(BaseModel):
    """Per-section attendance occurrence counts (each student's collapsed
    occurrences of their enrolled subjects) with ERP current/forecast
    percentages. Cancelled is its own state; pending is never converted to
    absent; extra occurrences count as conducted classes (attended/missed)
    and are additionally flagged. current_pct = attended/recorded,
    forecast_pct = (attended+pending)/total — not an average of students."""
    section_id: UUID
    section_name: str
    students: int = 0
    scheduled: int = 0
    cancelled: int = 0
    extra: int = 0
    attended: int = 0
    missed: int = 0
    pending: int = 0
    current_pct: Optional[float] = None
    forecast_pct: Optional[float] = None


class AdminSectionAttendanceListResponse(BaseModel):
    items: List[AdminSectionAttendanceSummary] = Field(default_factory=list)
    total: int = 0
    range_start: Optional[date] = None
    range_end: Optional[date] = None


class AdminSubjectAttendanceSummary(BaseModel):
    """Per-subject attendance occurrence counts over the scoped roster
    (students enrolled in the subject), ERP current/forecast semantics."""
    subject_id: UUID
    code: str
    name: str
    roster: int = 0
    scheduled: int = 0
    cancelled: int = 0
    extra: int = 0
    attended: int = 0
    missed: int = 0
    pending: int = 0
    current_pct: Optional[float] = None
    forecast_pct: Optional[float] = None


class AdminSubjectAttendanceListResponse(BaseModel):
    items: List[AdminSubjectAttendanceSummary] = Field(default_factory=list)
    total: int = 0
    range_start: Optional[date] = None
    range_end: Optional[date] = None


class AdminStudentAttendanceResponse(AnalyticsOverviewResponse):
    """Per-student attendance read: the canonical student analytics overview
    (overall + weekly + subject summaries) as viewed by an in-scope admin.
    The computation is exactly the student's own self-scoped analytics —
    the admin merely authorizes the read."""
    student_id: UUID
    roll_number: Optional[str] = None
    student_name: Optional[str] = None
    section_name: Optional[str] = None
