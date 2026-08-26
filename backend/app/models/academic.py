from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Date, ForeignKey, Enum, UniqueConstraint
from app.db.base_class import Base
from app.models.enums import SubjectCategory, ElectiveSlot
import datetime
from typing import List
import uuid
from sqlalchemy.dialects.postgresql import UUID

class AcademicSession(Base):
    __tablename__ = "academic_sessions"
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    start_date: Mapped[datetime.date] = mapped_column(Date)
    end_date: Mapped[datetime.date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    semesters: Mapped[List["Semester"]] = relationship(back_populates="session")


class Semester(Base):
    __tablename__ = "semesters"
    name: Mapped[str] = mapped_column(String)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("academic_sessions.id"))
    start_date: Mapped[datetime.date] = mapped_column(Date)
    end_date: Mapped[datetime.date] = mapped_column(Date)
    
    session: Mapped["AcademicSession"] = relationship(back_populates="semesters")
    subjects: Mapped[List["Subject"]] = relationship(back_populates="semester")


class Subject(Base):
    __tablename__ = "subjects"
    code: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    tag: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[SubjectCategory] = mapped_column(Enum(SubjectCategory))
    quiz_applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    attendance_applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    semester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("semesters.id"))

    semester: Mapped["Semester"] = relationship(back_populates="subjects")
    enrollments: Mapped[List["StudentEnrollment"]] = relationship(back_populates="subject")
    timetable_entries: Mapped[List["TimetableEntry"]] = relationship(back_populates="subject")
    class_sessions: Mapped[List["ClassSession"]] = relationship(back_populates="subject")
    quiz_schedules: Mapped[List["QuizSchedule"]] = relationship(back_populates="subject")
    lab_experiments: Mapped[List["LaboratoryExperiment"]] = relationship(back_populates="subject")


class StudentEnrollment(Base):
    __tablename__ = "student_enrollments"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))

    user: Mapped["User"] = relationship(back_populates="enrollments")
    subject: Mapped["Subject"] = relationship(back_populates="enrollments")


class StudentElectiveChoice(Base):
    """Per-student selection of one Department Elective-I and one Elective-II
    subject. Each student may have at most one choice per elective slot; the
    absence of a row means the student has not yet made the selection.
    FK constraints ensure the chosen subject exists and belongs to the
    correct elective group (tag matches the slot)."""
    __tablename__ = "student_elective_choices"
    __table_args__ = (
        UniqueConstraint("user_id", "elective_slot", name="uq_user_elective_slot"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    elective_slot: Mapped[ElectiveSlot] = mapped_column(Enum(ElectiveSlot))
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))

    user: Mapped["User"] = relationship(back_populates="elective_choices")
    subject: Mapped["Subject"] = relationship()
