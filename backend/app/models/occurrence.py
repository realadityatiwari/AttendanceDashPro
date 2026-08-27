from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, Enum, UniqueConstraint
from app.db.base_class import Base
from app.models.enums import OccurrenceOutcomeType
import uuid
from sqlalchemy.dialects.postgresql import UUID


class OccurrenceOutcome(Base):
    """Subject-specific actual-occurrence outcome override (Phase 23.6).

    Distinguishes the EXPECTED schedule (``timetable_entries``) from the ACTUAL
    occurrence (``class_sessions``) and allows one actual occurrence to have
    DIFFERENT effective types for different concrete subjects in the same
    Departmental Elective slot.

    Semantics:
      - ``class_sessions`` is the ANCHOR occurrence: its own ``is_extra`` /
        ``is_cancelled`` flags are the shared default for subjects WITHOUT an
        outcome row.
      - An ``occurrence_outcomes`` row overrides the effective type for ONE
        concrete subject (e.g. ``BCS-058`` on the shared DE-II slot):
          EXTRA_* / SURPRISE_QUIZ -> effective ``is_extra`` = True;
          CANCELLED               -> effective ``is_cancelled`` = True.
      - UNIQUE(class_session_id, subject_id): one outcome per (occurrence,
        subject) — a subject can never carry two conflicting outcomes.

    Example (DE-II slot, same date):
      anchor session (BCS-058, normal lecture)
      + outcome (session, BCS-058, SURPRISE_QUIZ)  -> Student A sees a quiz
      + outcome (session, BCS-056, CANCELLED)      -> Student C sees cancelled
      BCS-055 has no outcome                        -> Student B sees normal

    This NEVER duplicates timetable/session/event infrastructure per student,
    NEVER fabricates a student's elective, and NEVER modifies the session row,
    attendance records, or historical data. ``OccurrenceOutcomeType.MODIFIED``
    is intentionally absent — session-level "modified/substitution" semantics
    belong to the Phase 23.7 event-scope design (deferred).
    """

    __tablename__ = "occurrence_outcomes"
    __table_args__ = (
        UniqueConstraint(
            "class_session_id",
            "subject_id",
            name="uq_occurrence_outcome_session_subject",
        ),
    )
    class_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_sessions.id"), index=True
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id")
    )
    outcome_type: Mapped[OccurrenceOutcomeType] = mapped_column(
        Enum(OccurrenceOutcomeType)
    )
