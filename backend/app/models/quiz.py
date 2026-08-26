from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, Integer, Date, ForeignKey, Enum
from app.db.base_class import Base
from app.models.enums import ElectiveSlot
import datetime
from typing import List
import uuid
from sqlalchemy.dialects.postgresql import UUID
import enum

class ScheduleStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    UNRESOLVED = "UNRESOLVED"
    CANCELLED = "CANCELLED"

class QuizCycle(Base):
    __tablename__ = "quiz_cycles"
    cycle_number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    label: Mapped[str] = mapped_column(String)
    
    policy: Mapped["EligibilityPolicy"] = relationship(back_populates="quiz_cycle")
    schedules: Mapped[List["QuizSchedule"]] = relationship(back_populates="quiz_cycle")


class EligibilityPolicy(Base):
    __tablename__ = "eligibility_policies"
    quiz_cycle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quiz_cycles.id"))
    lecture_threshold: Mapped[float] = mapped_column(Float)
    combined_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    quiz_cycle: Mapped["QuizCycle"] = relationship(back_populates="policy")


class QuizSchedule(Base):
    __tablename__ = "quiz_schedules"
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    quiz_cycle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quiz_cycles.id"))
    
    # Phase 22.4: the shared institutional quiz schedule keeps the anchor
    # subjects (BCS-054 / BCS-058) for the Departmental Elective slots.
    # `elective_slot` marks which logical slot a schedule entry belongs to so
    # per-student resolution can map it to the student's selected subject.
    # NULL = a regular (non-elective) quiz schedule entry.
    elective_slot: Mapped["ElectiveSlot | None"] = mapped_column(
        Enum(ElectiveSlot), nullable=True, default=None
    )

    date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    schedule_status: Mapped[ScheduleStatus] = mapped_column(Enum(ScheduleStatus), default=ScheduleStatus.SCHEDULED)
    
    subject: Mapped["Subject"] = relationship(back_populates="quiz_schedules")
    quiz_cycle: Mapped["QuizCycle"] = relationship(back_populates="schedules")
