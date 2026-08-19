from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, ForeignKey, Enum
from app.db.base_class import Base
from app.models.enums import FeedbackType
import uuid
from sqlalchemy.dialects.postgresql import UUID


class Feedback(Base):
    __tablename__ = "feedback"
    # Owner is always the authenticated user resolved from the JWT
    # (get_current_user) — the client can never supply user_id.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    # Values match the frontend FeedbackModal exactly (BUG/SUGGESTION/
    # QUESTION/PRAISE); never renamed or extended unilaterally.
    feedback_type: Mapped[FeedbackType] = mapped_column(Enum(FeedbackType))
    message: Mapped[str] = mapped_column(Text)
    # Optional free-form context (e.g. the screen the user was on). Nullable;
    # the frontend is not required to send it and nothing auto-captures it.
    context: Mapped[str | None] = mapped_column(String, nullable=True)

    # id / created_at / updated_at come from the Base mixin. No relationships
    # to any domain table (attendance/events/quiz/lab) — feedback is isolated.