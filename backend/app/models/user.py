from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey
from app.db.base_class import Base
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
    firebase_uid: Mapped[str] = mapped_column(String, unique=True, index=True)
    roll_number: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    
    section_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=True)
    
    section: Mapped["Section"] = relationship(back_populates="users")
    enrollments: Mapped[List["StudentEnrollment"]] = relationship(back_populates="user")
    attendance_records: Mapped[List["AttendanceRecord"]] = relationship(back_populates="user")
    lab_records: Mapped[List["LaboratoryRecord"]] = relationship(back_populates="user")
