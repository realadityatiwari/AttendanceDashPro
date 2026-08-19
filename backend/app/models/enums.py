from enum import Enum

class ClassType(str, Enum):
    LECTURE = "L"
    TUTORIAL = "T"
    PRACTICAL = "P"

class AttendanceStatus(str, Enum):
    ATTENDED = "Attended"
    MISSED = "Missed"
    PENDING = "Pending"

class EventType(str, Enum):
    EXTRA_LECTURE = "EXTRA_LECTURE"
    EXTRA_TUTORIAL = "EXTRA_TUTORIAL"
    EXTRA_PRACTICAL = "EXTRA_PRACTICAL"
    CLASS_CANCELLED = "CLASS_CANCELLED"
    SURPRISE_QUIZ = "SURPRISE_QUIZ"
    QUIZ_DAY = "QUIZ_DAY"
    # Unified holiday (closure family): one user-facing event for any
    # non-working holiday day/range with a reason/occasion note. Backend
    # compatibility: the legacy PUBLIC_HOLIDAY / INSTITUTE_HOLIDAY /
    # FESTIVAL_HOLIDAY types remain fully supported (same closure semantics);
    # HOLIDAY is the consolidated creation path.
    HOLIDAY = "HOLIDAY"
    PUBLIC_HOLIDAY = "PUBLIC_HOLIDAY"
    INSTITUTE_HOLIDAY = "INSTITUTE_HOLIDAY"
    WORKING_DAY_OVERRIDE = "WORKING_DAY_OVERRIDE"
    WORKING_SATURDAY = "WORKING_SATURDAY"
    EMERGENCY_CLOSURE = "EMERGENCY_CLOSURE"
    FESTIVAL_HOLIDAY = "FESTIVAL_HOLIDAY"
    SEMESTER_BREAK = "SEMESTER_BREAK"
    MID_SEMESTER_BREAK = "MID_SEMESTER_BREAK"
    # Phase 9.1 laboratory attendance events (event-driven, canonical pipeline).
    # These are NOT separate attendance systems: they are Academic Events the
    # EventSessionSynchronizer resolves into canonical ClassSession state.
    # MID_SEM_PRACTICAL marks the resolved practical occurrence as the subject's
    # mid-semester practical (ClassSession.designation); LAB_CANCELLED cancels
    # the matching practical occurrence (is_cancelled), identical in session
    # semantics to CLASS_CANCELLED but restricted to practical subjects.
    MID_SEM_PRACTICAL = "MID_SEM_PRACTICAL"
    LAB_CANCELLED = "LAB_CANCELLED"

class UserRole(str, Enum):
    STUDENT = "STUDENT"
    ADMIN = "ADMIN"

class SubjectCategory(str, Enum):
    THEORY = "theory"
    LAB = "lab"

class SessionDesignation(str, Enum):
    """Session-level designation for a scheduled class session (Phase 8.2).

    A designation is an ADMIN-controlled fact tied to an ACTUAL scheduled
    session (never inferred from experiment counts or a fixed date). Today the
    only designation is MID_SEM_PRACTICAL: a specific PRACTICAL class session
    the faculty/admin designates as the mid-semester practical for its
    subject. Attendance against that session flows through the normal
    attendance mutation — designation changes nothing about counting.
    """
    MID_SEM_PRACTICAL = "MID_SEM_PRACTICAL"

class FeedbackType(str, Enum):
    """User feedback categories (Phase 10C). Values MUST match the frontend
    FeedbackModal exactly — never renamed, never extended without a
    coordinated frontend contract change."""
    BUG = "BUG"
    SUGGESTION = "SUGGESTION"
    QUESTION = "QUESTION"
    PRAISE = "PRAISE"

class WeekStartsOn(str, Enum):
    """User preference: the weekday the calendar week is considered to start
    (Phase 10D). STORAGE/PREFERENCE DATA ONLY — nothing in the current
    architecture consumes this value; Phase 11 wiring is out of scope."""
    SUNDAY = "SUNDAY"
    MONDAY = "MONDAY"
