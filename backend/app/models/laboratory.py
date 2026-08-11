from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, Integer, Date, ForeignKey, Enum, UniqueConstraint, DateTime
from app.db.base_class import Base
import datetime
from typing import List
import uuid
from sqlalchemy.dialects.postgresql import UUID
import enum

class SignatureStatus(str, enum.Enum):
    PENDING = "pending"
    SIGNED = "signed"

class LaboratoryExperiment(Base):
    __tablename__ = "laboratory_experiments"
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    experiment_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String, nullable=True)

    subject: Mapped["Subject"] = relationship(back_populates="lab_experiments")
    records: Mapped[List["LaboratoryRecord"]] = relationship(back_populates="experiment")


class LaboratoryRecord(Base):
    __tablename__ = "laboratory_records"
    __table_args__ = (
        UniqueConstraint('user_id', 'experiment_id', name='uq_user_experiment'),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("laboratory_experiments.id"))
    
    date_conducted: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    signature_status: Mapped[SignatureStatus] = mapped_column(Enum(SignatureStatus), default=SignatureStatus.PENDING)
    signed_on: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    remarks: Mapped[str | None] = mapped_column(String, nullable=True)

    user: Mapped["User"] = relationship(back_populates="lab_records")
    experiment: Mapped["LaboratoryExperiment"] = relationship(back_populates="records")
