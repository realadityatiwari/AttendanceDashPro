from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, Date, ForeignKey, Enum
from app.db.base_class import Base
from app.models.enums import EventType, ClassType
import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID

class AcademicEvent(Base):
    __tablename__ = "academic_events"
    event_type: Mapped[EventType] = mapped_column(Enum(EventType))
    start_date: Mapped[datetime.date] = mapped_column(Date)
    end_date: Mapped[datetime.date] = mapped_column(Date)
    
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    class_type: Mapped[ClassType | None] = mapped_column(Enum(ClassType), nullable=True)
    
    is_working_day: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    substitution_schedule_override: Mapped[str | None] = mapped_column(String, nullable=True)
    # Phase 9.1: optional student-entered note/reason (e.g. lab cancellation
    # reason, mid-sem remark). Additive metadata only — never read by any
    # attendance calculation. NULL for events without a note.
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
