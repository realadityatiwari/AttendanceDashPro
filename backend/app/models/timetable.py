from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Time, Boolean, Date, ForeignKey, Enum
from app.db.base_class import Base
from app.models.enums import ClassType, SessionDesignation
import datetime
from typing import List
import uuid
from sqlalchemy.dialects.postgresql import UUID

class TimetableEntry(Base):
    __tablename__ = "timetable_entries"
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    day_of_week: Mapped[int] = mapped_column(Integer) # 0=Monday, 6=Sunday
    start_time: Mapped[datetime.time] = mapped_column(Time)
    end_time: Mapped[datetime.time] = mapped_column(Time)
    class_type: Mapped[ClassType] = mapped_column(Enum(ClassType))

    subject: Mapped["Subject"] = relationship(back_populates="timetable_entries")
    class_sessions: Mapped[List["ClassSession"]] = relationship(back_populates="timetable_entry")


class ClassSession(Base):
    __tablename__ = "class_sessions"
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    date: Mapped[datetime.date] = mapped_column(Date)
    class_type: Mapped[ClassType] = mapped_column(Enum(ClassType))
    is_extra: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    timetable_entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("timetable_entries.id"), nullable=True)
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
