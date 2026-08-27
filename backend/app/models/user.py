from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Enum, text, UniqueConstraint, Integer
from app.db.base_class import Base
from app.models.enums import UserRole
from app.models.laboratory import LaboratoryRecord
from typing import List
import uuid
from sqlalchemy.dialects.postgresql import UUID

class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        # Phase 23.1 (Correction 7 gate preserved): section names are unique
        # within a semester, NOT globally. The same name may be reused across
        # semesters (and, once the Branch decision gate is resolved, across
        # branches). The current repository has exactly one section (CSE-51).
        UniqueConstraint("semester_id", "name", name="uq_sections_semester_name"),
    )
    name: Mapped[str] = mapped_column(String)
    # Cohort/program grouping the section belongs to (Phase 10B), e.g. "CSE"
    # for section "CSE-51". Stored data; never derived from section.name.
    # Note: the current model has NO Branch entity — `program` is the only
    # branch/program representation (Phase 23.1 DECISION GATE remains open).
    program: Mapped[str | None] = mapped_column(String, nullable=True)
    semester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("semesters.id"))

    users: Mapped[List["User"]] = relationship(back_populates="section")
    timetable_entries: Mapped[List["TimetableEntry"]] = relationship(back_populates="section")
    subsections: Mapped[List["Subsection"]] = relationship(back_populates="section")


class Subsection(Base):
    """Subsection of a Section (Phase 23.1 academic hierarchy foundation).

    A section is commonly divided into subsections (e.g. ~30 students each).
    This is a NULL-preserving schema foundation: ``users.subsection_id`` may be
    NULL and NULL means UNKNOWN/UNASSIGNED. NO subsection is fabricated for
    existing sections and NO student is automatically assigned (Phase 23.0
    Correction 9); controlled backfill belongs to later work.

    ``max_strength`` is NULLABLE configuration (no server default) — the
    authoritative capacity value is an open decision (report §36); NULL = unset,
    never a fabricated default.
    """

    __tablename__ = "subsections"
    __table_args__ = (
        # Subsection names are unique within a section only (NOT globally).
        UniqueConstraint("section_id", "name", name="uq_subsections_section_name"),
    )
    name: Mapped[str] = mapped_column(String)
    section_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sections.id"))
    max_strength: Mapped[int | None] = mapped_column(Integer, nullable=True)

    section: Mapped["Section"] = relationship(back_populates="subsections")
    users: Mapped[List["User"]] = relationship(back_populates="subsection")


class User(Base):
    __tablename__ = "users"
    roll_number: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)
    # Authorization role (Phase 6.5): every account is STUDENT by default;
    # ADMIN is granted only through the explicit provisioning script
    # (backend/scripts/provision_admin.py). Never self-assignable.
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.STUDENT, server_default=text("'STUDENT'")
    )
    
    section_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=True)
    # Phase 23.1: subsection membership (nullable). NULL = UNKNOWN/UNASSIGNED —
    # existing students are never auto-assigned to a subsection (Phase 23.0
    # Correction 9); controlled backfill belongs to later work.
    subsection_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subsections.id"), nullable=True)
    
    section: Mapped["Section"] = relationship(back_populates="users")
    subsection: Mapped["Subsection"] = relationship(back_populates="users")
    enrollments: Mapped[List["StudentEnrollment"]] = relationship(back_populates="user")
    elective_choices: Mapped[List["StudentElectiveChoice"]] = relationship(back_populates="user")
    attendance_records: Mapped[List["AttendanceRecord"]] = relationship(back_populates="user")
    # foreign_keys: laboratory_records has four FKs to users (user_id,
    # signed_by, created_by, updated_by) — explicit join required.
    lab_records: Mapped[List[LaboratoryRecord]] = relationship(
        back_populates="user",
        foreign_keys=[LaboratoryRecord.user_id],
    )
