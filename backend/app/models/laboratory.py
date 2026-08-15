from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, Integer, Date, ForeignKey, Enum, UniqueConstraint, DateTime, Boolean
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
    __table_args__ = (
        # Phase 9.2.1: one experiment number per subject enforced at the
        # database level; duplicate ingestion raises IntegrityError.
        UniqueConstraint('subject_id', 'experiment_number', name='uq_subject_experiment'),
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subjects.id"))
    experiment_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    # Phase 9.2.1: catalog flag. Deactivation replaces hard deletion so
    # historical laboratory records keep their FK intact. The curriculum
    # endpoint exposes active experiments only.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

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
    # Phase 9.2.1: optional linkage to the canonical practical ClassSession
    # the record was conducted in. NULL is allowed — the record simply has
    # no session link (truthful; the audit must not infer sessions).
    class_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("class_sessions.id"), nullable=True)
    # Phase 9.2.1: audit trail. signed_by is the ADMIN who signed the record
    # (never a student — forging is rejected in the service layer).
    signed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # foreign_keys: laboratory_records now has FOUR FKs to users (user_id,
    # signed_by, created_by, updated_by) — the ORM needs the explicit join.
    user: Mapped["User"] = relationship(back_populates="lab_records",
                                        foreign_keys=[user_id])
    experiment: Mapped["LaboratoryExperiment"] = relationship(back_populates="records")
    class_session: Mapped["ClassSession"] = relationship(back_populates="laboratory_records")