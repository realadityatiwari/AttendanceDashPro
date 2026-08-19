from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, ForeignKey, Enum, text
from app.db.base_class import Base
from app.models.enums import WeekStartsOn
import uuid
from sqlalchemy.dialects.postgresql import UUID


class UserPreference(Base):
    __tablename__ = "userpreferences"

    # One preference row per user: user_id IS the primary key, so the Base
    # mixin's surrogate `id` column is removed for this table (assignment of
    # `None` shadows the inherited mapped attribute; the table then contains
    # exactly the columns below plus the Base timestamps).
    id = None  # type: ignore[assignment]

    # Owner is always the authenticated user resolved from the JWT
    # (get_current_user) — the client can never supply user_id.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    # Phase 10D: STORAGE/PREFERENCE DATA ONLY. These booleans never send
    # reminders and never create attendance records — Phase 11 consumes them.
    class_reminders: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    auto_mark_present: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    # Week-start convention the user prefers. STORAGE/PREFERENCE DATA ONLY:
    # it never alters calendar/analytics/attendance calculations yet.
    week_starts_on: Mapped[WeekStartsOn] = mapped_column(
        Enum(WeekStartsOn),
        default=WeekStartsOn.MONDAY,
        server_default=text("'MONDAY'"),
    )

    # created_at / updated_at come from the Base mixin (IST timezone-aware).
    # No relationships to attendance/events/quiz/laboratory tables —
    # preferences are isolated personal settings for STUDENT and ADMIN alike.
