from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Date, ForeignKey, Enum, UniqueConstraint, text
from app.db.base_class import Base
from app.models.enums import SubjectCategory, ElectiveSlot, EnrollmentType
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
    """A subject belonging to a semester.

    Phase 23.2 (Curriculum model): UNIQUE(code, semester_id) ensures the same
    subject code may appear in different semesters (different rows, different
    UUIDs), but the same code may not occur twice within the same semester.
    This is a schema-hardening constraint — the seed/migration pipelines
    already prevent duplicates via application-level guards, but the database
    is now the authoritative enforcement point.
    """
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("code", "semester_id", name="uq_subjects_code_semester"),
    )
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
    """A student's enrollment in a subject of a semester.

    Uniqueness (Phase 23.1, Correction 8 gate): UNIQUE(user_id, subject_id) is
    the correct enrollment key. `Subject` is scoped to a semester
    (subjects.semester_id NOT NULL), so `subject_id` already encodes the
    semester: a student can be enrolled once per subject row (duplicate current
    enrollment is prevented), while the SAME subject CODE across different
    semesters is a DIFFERENT subject row, so multi-semester historical
    enrollment coexists. This does NOT make a student globally unique to one
    section. Duplicate prevention was previously service-layer only.
    """
    __tablename__ = "student_enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "subject_id", name="uq_student_enrollments_user_subject"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    # Phase 23.3: whether this enrollment is a program requirement (COMPULSORY)
    # or the student's elective selection (ELECTIVE). Additive discriminator —
    # the authoritative elective selection remains StudentElectiveChoice +
    # ElectiveResolver (Phase 22.3/22.4). Existing rows default to COMPULSORY.
    enrollment_type: Mapped[EnrollmentType] = mapped_column(
        Enum(EnrollmentType),
        default=EnrollmentType.COMPULSORY,
        server_default=text("'COMPULSORY'"),
    )

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
