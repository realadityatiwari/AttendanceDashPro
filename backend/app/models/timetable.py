from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    Integer, Time, Boolean, Date, String, ForeignKey, ForeignKeyConstraint,
    CheckConstraint, Enum, text,
)
from app.db.base_class import Base
from app.models.enums import ClassType, SessionDesignation, ElectiveSlot
import datetime
from typing import List
import uuid
from sqlalchemy.dialects.postgresql import UUID

class TimetableEntry(Base):
    """A single weekly recurring timetable entry (EXPECTED schedule).

    Phase 24.7-A: this is the academic timetable DOMAIN CONTRACT, distinct
    from an actual class-session occurrence (``class_sessions``). It describes
    the expected institutional schedule at Section scope, with an optional
    Subsection scope, and is resolved per-student (via ``ElectiveResolver``)
    when student-facing data is generated — it is never duplicated per
    student.

    Existing Phase 22.x/23.x columns are retained unchanged (section/subject/
    day/time/class_type/elective_slot).  Phase 24.7-A adds:
      - ``subsection_id``  nullable scope refinement (NULL = section-wide)
      - ``room``           nullable physical room
      - ``is_active``      expected-schedule active flag (default true)
      - ``sort_order``     nullable deterministic ordering hint
    DB-level integrity guards:
      - ``end_time > start_time``
      - ``day_of_week`` in 0..6 (0=Monday, 6=Sunday)
      - a subsection, when set, MUST belong to the entry's section
        (composite FK ``(section_id, subsection_id)`` -> subsections).
    """
    __tablename__ = "timetable_entries"
    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="ck_timetable_entries_end_gt_start",
        ),
        CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="ck_timetable_entries_day_of_week_range",
        ),
        ForeignKeyConstraint(
            ["section_id", "subsection_id"],
            ["subsections.section_id", "subsections.id"],
            name="fk_timetable_entries_section_subsection",
        ),
    )

    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    day_of_week: Mapped[int] = mapped_column(Integer) # 0=Monday, 6=Sunday
    start_time: Mapped[datetime.time] = mapped_column(Time)
    end_time: Mapped[datetime.time] = mapped_column(Time)
    class_type: Mapped[ClassType] = mapped_column(Enum(ClassType))
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sections.id"))
    # Phase 24.7-A: optional Subsection scope. NULL = section-wide entry.
    # The composite FK above guarantees subsection.section_id == section_id.
    subsection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subsections.id"), nullable=True, default=None
    )
    # Phase 24.7-A: expected-schedule room (free text, nullable).
    room: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    # Phase 24.7-A: expected-schedule active flag. Existing entries default
    # active; deactivation belongs to later admin CRUD, never a destructive
    # delete.
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )
    # Phase 24.7-A: nullable deterministic ordering hint (admin-assigned).
    # NULL = no explicit order (fall back to day/time). No fabricated default.
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # Phase 22.3: the shared institutional timetable keeps concrete elective
    # subject slots (BCS-054 / BCS-058). `elective_slot` marks which shared
    # slot an entry belongs to so the application can resolve the entry to
    # each student's selected Department Elective-I / Elective-II subject.
    # NULL = a regular non-elective timetable entry (never resolved).
    elective_slot: Mapped["ElectiveSlot | None"] = mapped_column(
        Enum(ElectiveSlot), nullable=True, default=None
    )

    subject: Mapped["Subject"] = relationship(back_populates="timetable_entries")
    section: Mapped["Section"] = relationship(back_populates="timetable_entries")
    subsection: Mapped["Subsection"] = relationship(
        back_populates="timetable_entries",
        foreign_keys=[subsection_id],
    )
    class_sessions: Mapped[List["ClassSession"]] = relationship(back_populates="timetable_entry")


class ClassSession(Base):
    __tablename__ = "class_sessions"
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    date: Mapped[datetime.date] = mapped_column(Date)
    class_type: Mapped[ClassType] = mapped_column(Enum(ClassType))
    is_extra: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    timetable_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("timetable_entries.id"), nullable=True)
    # Phase 22.4: the logical elective slot a session belongs to. For
    # timetable-linked sessions this is redundant with the timetable entry's
    # elective_slot; for event-created sessions (extras, quiz-day) with no
    # timetable link, this marker ensures per-student resolution works.
    # NULL = a regular non-elective session.
    elective_slot: Mapped[ElectiveSlot | None] = mapped_column(
        Enum(ElectiveSlot), nullable=True, default=None
    )
    # Phase 8.2: optional ADMIN-controlled session designation (e.g.
    # MID_SEM_PRACTICAL). NULL = regular session. This is a session-level fact
    # tied to an actual scheduled ClassSession — it is never inferred from
    # experiment completion counts or a fixed calendar date, and it does not
    # alter attendance counting (the same canonical mutation records
    # attendance against the designated session).
    designation: Mapped[SessionDesignation | None] = mapped_column(
        Enum(SessionDesignation), nullable=True, default=None
    )

    subject: Mapped["Subject"] = relationship(back_populates="class_sessions")
    timetable_entry: Mapped["TimetableEntry"] = relationship(back_populates="class_sessions")
    attendance_records: Mapped[List["AttendanceRecord"]] = relationship(back_populates="class_session")
    laboratory_records: Mapped[List["LaboratoryRecord"]] = relationship(back_populates="class_session")
