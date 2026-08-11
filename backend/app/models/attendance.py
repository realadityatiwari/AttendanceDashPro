from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Enum, UniqueConstraint
from app.db.base_class import Base
from app.models.enums import AttendanceStatus
import uuid
from sqlalchemy.dialects.postgresql import UUID

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint('user_id', 'class_session_id', name='uq_user_class_session'),
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    class_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("class_sessions.id"))
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus))

    user: Mapped["User"] = relationship(back_populates="attendance_records")
    class_session: Mapped["ClassSession"] = relationship(back_populates="attendance_records")
