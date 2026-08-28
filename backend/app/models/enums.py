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
    # Phase 23.7: subject-scoped event representing a MODIFIED actual
    # occurrence — the scheduled class happened but was modified (time/room/
    # delivery). It is subject-scoped ONLY (never a whole elective slot) and
    # resolves to an OccurrenceOutcomeType.MODIFIED occurrence outcome on the
    # shared anchor session for the concrete subject. It is NOT an extra, NOT a
    # cancellation, NOT a quiz: the occurrence still counts as a conducted
    # class in every attendance/eligibility read.
    CLASS_MODIFIED = "CLASS_MODIFIED"

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

class ElectiveSlot(str, Enum):
    """Timetable slot type for per-student elective resolution (Phase 22.3)."""
    ELECTIVE_I = "ELECTIVE_I"
    ELECTIVE_II = "ELECTIVE_II"

class OccurrenceOutcomeType(str, Enum):
    """Subject-specific outcome override for a class session (Phase 23.6).

    A single actual occurrence (``class_sessions`` row) may have different
    outcomes for different concrete subjects in the same elective slot. The
    session row represents the anchor (shared default) state; an
    ``occurrence_outcomes`` row overrides the effective type for one subject.

    - EXTRA_LECTURE / EXTRA_TUTORIAL / EXTRA_PRACTICAL / SURPRISE_QUIZ:
      the subject sees the session as an extra occurrence (effective
      ``is_extra`` = True).
    - CANCELLED: the subject sees the session as cancelled (effective
      ``is_cancelled`` = True).
    - MODIFIED (Phase 23.7): the subject sees the session as modified
      (the scheduled class happened but was modified). It is NOT extra or
      cancelled — the occurrence still counts as a conducted class in every
      attendance/eligibility read. The effective ``is_extra`` / ``is_cancelled``
      flags are UNCHANGED; the ``outcome_type`` value is exposed to consumers.

    Subjects with no outcome row follow the anchor session's own
    ``is_extra`` / ``is_cancelled`` flags.
    """
    EXTRA_LECTURE = "EXTRA_LECTURE"
    EXTRA_TUTORIAL = "EXTRA_TUTORIAL"
    EXTRA_PRACTICAL = "EXTRA_PRACTICAL"
    SURPRISE_QUIZ = "SURPRISE_QUIZ"
    CANCELLED = "CANCELLED"
    # Phase 23.7: the scheduled occurrence was modified for this subject
    # (e.g. time, room, or delivery changed). Not extra, not cancelled.
    MODIFIED = "MODIFIED"

class EnrollmentType(str, Enum):
    """Whether a student's subject enrollment is a program requirement or an
    elective selection (Phase 23.3 — Student Academic Assignment).

    - COMPULSORY: the student is academically enrolled in this subject regardless
      of any elective selection (common theory + practical subjects).
    - ELECTIVE: this enrollment corresponds to the concrete subject the student
      selected for a Department Elective slot (DE-I / DE-II). The logical slot
      itself is never an enrollment; the concrete subject is.

    This makes the compulsory-vs-elective enrollment distinction EXPLICIT and
    authoritative on the enrollment row. It does NOT replace the authoritative
    `StudentElectiveChoice` + `ElectiveResolver` (Phase 22.3/22.4) — that system
    remains the single source of truth for elective selection. The type is
    additive and defaulted to COMPULSORY for backward compatibility.
    """
    COMPULSORY = "COMPULSORY"
    ELECTIVE = "ELECTIVE"

class WeekStartsOn(str, Enum):
    """User preference: the weekday the calendar week is considered to start
    (Phase 10D). STORAGE/PREFERENCE DATA ONLY — nothing in the current
    architecture consumes this value; Phase 11 wiring is out of scope."""
    SUNDAY = "SUNDAY"
    MONDAY = "MONDAY"

class NotificationKind(str, Enum):
    """Phase 11A notification kinds. ADDITIVE — new kinds may be appended;
    existing values are never renamed. Each kind is emitted by
    NotificationService as a read-only projection of existing engine/service
    outputs; notifications never compute attendance themselves."""
    CLASS_REMINDER = "CLASS_REMINDER"
    QUIZ_APPROACHING = "QUIZ_APPROACHING"
    ATTENDANCE_THRESHOLD = "ATTENDANCE_THRESHOLD"
    MUST_ATTEND = "MUST_ATTEND"
    SAFE_SKIP = "SAFE_SKIP"
    ACADEMIC_EVENT = "ACADEMIC_EVENT"
