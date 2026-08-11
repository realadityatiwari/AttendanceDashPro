from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.declarative import declared_attr
from datetime import datetime
from sqlalchemy import DateTime, func
from zoneinfo import ZoneInfo
import uuid
from sqlalchemy.dialects.postgresql import UUID

# Institutional timezone
IST = ZoneInfo("Asia/Kolkata")

class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(IST))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(IST), onupdate=lambda: datetime.now(IST))
