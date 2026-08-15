from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Enum, text
from app.db.base_class import Base
from app.models.enums import UserRole
from app.models.laboratory import LaboratoryRecord
from typing import List
import uuid
from sqlalchemy.dialects.postgresql import UUID

class Section(Base):
    __tablename__ = "sections"
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    semester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("semesters.id"))

    users: Mapped[List["User"]] = relationship(back_populates="section")


class User(Base):
    __tablename__ = "users"
    # Firebase identity is retired: nullable since 4.5.3 so PostgreSQL-native
    # registrations can exist without a Firebase UID. Legacy values preserved.
    firebase_uid: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
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
    
    section: Mapped["Section"] = relationship(back_populates="users")
    enrollments: Mapped[List["StudentEnrollment"]] = relationship(back_populates="user")
    attendance_records: Mapped[List["AttendanceRecord"]] = relationship(back_populates="user")
    # foreign_keys: laboratory_records has four FKs to users (user_id,
    # signed_by, created_by, updated_by) — explicit join required.
    lab_records: Mapped[List[LaboratoryRecord]] = relationship(
        back_populates="user",
        foreign_keys=[LaboratoryRecord.user_id],
    )
