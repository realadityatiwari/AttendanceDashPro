from pydantic import BaseModel
from typing import Optional
from datetime import date
from uuid import UUID


class AcademicOverview(BaseModel):
    """Current academic session/semester and structural counts."""
    active_session: Optional[str] = None
    session_start: Optional[date] = None
    session_end: Optional[date] = None
    active_session_count: int = 0
    semester_count: int = 0
    semester_name: Optional[str] = None
    semester_start: Optional[date] = None
    semester_end: Optional[date] = None
    section_count: int = 0
    program_count: int = 0
    subject_count: int = 0
    student_count: int = 0


class CurriculumOverview(BaseModel):
    """Subject catalog and enrollment distribution."""
    theory_subjects: int = 0
    lab_subjects: int = 0
    elective_i_subjects: int = 0
    elective_ii_subjects: int = 0
    compulsory_enrollments: int = 0
    elective_enrollments: int = 0


class StudentOverview(BaseModel):
    """Student body counts and assignment status.
    All counts are scoped to the legacy role STUDENT.
    ``subsection_assigned`` / ``subsection_unassigned`` are independent of
    ``placed`` / ``unplaced``: a student may be placed (has a section) but
    without a subsection assignment (NULL = UNKNOWN/UNASSIGNED per Phase 23.1).
    ``elective_choice_holders`` is the number of distinct students with at
    least one StudentElectiveChoice row; ``elective_choices_total`` is the
    total row count (one per slot per student)."""
    total: int = 0
    placed: int = 0
    unplaced: int = 0
    subsection_assigned: int = 0
    subsection_unassigned: int = 0
    elective_choice_holders: int = 0
    elective_choices_total: int = 0


class ScheduleOverview(BaseModel):
    """Timetable and class-session counts.
    ``class_sessions_cancelled`` counts anchor-level cancellations
    (``class_sessions.is_cancelled``). Per-subject effective cancellation
    may additionally be expressed by ``occurrence_outcomes`` rows (reported
    separately). ``sessions_today`` and ``upcoming_sessions`` exclude
    anchor-cancelled rows."""
    timetable_entry_count: int = 0
    class_session_total: int = 0
    class_sessions_cancelled: int = 0
    class_sessions_extra: int = 0
    sessions_today: int = 0
    upcoming_sessions: int = 0
    occurrence_outcomes: int = 0


class UpcomingEventItem(BaseModel):
    """A single active academic event with an end_date at or after today."""
    id: UUID
    event_type: str
    start_date: date
    end_date: date
    subject_code: Optional[str] = None
    elective_slot: Optional[str] = None


class EventsOverview(BaseModel):
    """Academic event counts and the next few upcoming events."""
    total_active: int = 0
    upcoming_active: int = 0
    upcoming: list[UpcomingEventItem] = []


class QuizOverview(BaseModel):
    """Quiz cycle and schedule status.
    ``scheduled_dated`` counts SCHEDULED schedules with a resolved date
    (the projection baseline). ``next_quiz_date`` is the earliest active
    QUIZ_DAY AcademicEvent at or after today — the authoritative quiz-date
    source (Phase 2); ``quiz_schedules`` table is a seed-time projection."""
    cycle_count: int = 0
    schedule_total: int = 0
    scheduled_dated: int = 0
    unresolved: int = 0
    cancelled: int = 0
    next_quiz_date: Optional[date] = None


class AttendanceOverview(BaseModel):
    """Aggregate attendance records.
    ``total_records`` = ``attended`` + ``missed`` (PENDING is not stored in
    the DB; it is derived per-session by the absence of a record row).
    ``recorded_pct`` = (attended / recorded) × 100 when recorded > 0,
    compatible with the canonical ERP recorded-only denominator."""
    total_records: int = 0
    attended: int = 0
    missed: int = 0
    recorded_pct: Optional[float] = None
    participants: int = 0


class AdminDashboardWarning(BaseModel):
    """An objectively detectable operational condition.
    ``severity`` is ``"info"`` or ``"warning"``.
    All warnings are factual — no defaults fabricated, no repairs suggested."""
    code: str
    severity: str
    message: str


class AdminDashboardResponse(BaseModel):
    """HEAD_ADMIN operational dashboard read model (Phase 24.2).
    Read-only, current-state based, derived from the authoritative tables;
    consumed by the Admin Portal frontend for presentation only.
    The backend remains the sole authorization boundary."""
    generated_at: date
    academic: AcademicOverview
    curriculum: CurriculumOverview
    students: StudentOverview
    schedule: ScheduleOverview
    events: EventsOverview
    quizzes: QuizOverview
    attendance: AttendanceOverview
    warnings: list[AdminDashboardWarning]