from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Boolean, Date, Integer, ForeignKey, Enum, UniqueConstraint, text
from app.db.base_class import Base
from app.models.enums import NotificationKind
import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID


class Notification(Base):
    __tablename__ = "notifications"

    # Owner is always the authenticated user resolved from the JWT
    # (get_current_user) — the client can never supply user_id.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    # The Phase 11A kind — the SAME enum (never a second notification-kind enum).
    kind: Mapped[NotificationKind] = mapped_column(Enum(NotificationKind))
    # Deterministic natural-key reference of the Phase 11A projection: the
    # session id (CLASS_REMINDER), quiz cycle (QUIZ_APPROACHING), event id
    # (ACADEMIC_EVENT), or subject code (ATTENDANCE_THRESHOLD / MUST_ATTEND /
    # SAFE_SKIP). Combined with (user_id, kind) it is the DB-enforced
    # idempotency key: repeated generation of the SAME occurrence can never
    # create a duplicate row, while genuinely distinct occurrences keep
    # distinct rows. Derivation mirrors NotificationService's natural-key `id`.
    occurrence_key: Mapped[str] = mapped_column(String)
    # Occurrence date (first-generation date; regeneration never rolls it).
    date: Mapped[datetime.date] = mapped_column(Date)
    # Nullable presentation references (audit §8-9: rows store references +
    # presentation text, never recomputed statistics).
    subject_code: Mapped[str | None] = mapped_column(String, nullable=True)
    subject_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Presentation text of the projection (refreshed by regeneration upserts).
    message: Mapped[str] = mapped_column(Text)
    # Typed source references (the same fields the Phase 11A item carries).
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    quiz_cycle: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Read/dismiss state (audit 11B objective). Both are preserved across
    # regeneration upserts, so a read/dismissed notification never re-appears
    # or resets while its source condition still holds.
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_dismissed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    # id / created_at / updated_at come from the Base mixin. No relationships
    # to any domain table (attendance/events/quiz/lab) — notifications are an
    # isolated inbox that consumes engine outputs at generation time.
    __table_args__ = (
        UniqueConstraint(
            "user_id", "kind", "occurrence_key",
            name="uq_notifications_user_kind_occurrence_key",
        ),
    )