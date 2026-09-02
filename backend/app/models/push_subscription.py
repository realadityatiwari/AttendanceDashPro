from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, text
from app.db.base_class import Base
import uuid
from sqlalchemy.dialects.postgresql import UUID


class PushSubscription(Base):
    """Phase 11C-P2: an authenticated user's Web Push browser subscription.

    Stores exactly the information P3's PushDispatchService needs to deliver a
    push message to this browser endpoint: the Web Push endpoint URL and the
    browser-generated ``p256dh`` (public encryption key) and ``auth`` (secret)
    values. No tokens, JWTs, passwords, or VAPID keys are ever stored here.

    Ownership is always the authenticated user resolved from the JWT
    (get_current_user) — the client can never supply user_id.

    Idempotency is DB-enforced: the endpoint URL is UNIQUE, so registering the
    same browser endpoint again (multi-tab, repeated enable, page reload) can
    never create a duplicate row. Multiple subscriptions per user are fully
    supported (desktop + mobile + PWA + another browser are independent rows).
    """

    __tablename__ = "push_subscriptions"

    # Owner is always the authenticated user resolved from the JWT
    # (get_current_user) — the client can never supply user_id.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    # Web Push endpoint URL — the natural identity of a browser subscription.
    # UNIQUE(endpoint) makes registration idempotent at the database level.
    endpoint: Mapped[str] = mapped_column(Text)
    # Browser-generated push keys (URL-safe base64 strings) required to encrypt
    # payloads for this endpoint. Server-side data only — never logged.
    p256dh: Mapped[str] = mapped_column(String)
    auth: Mapped[str] = mapped_column(String)

    # id / created_at / updated_at come from the Base mixin (IST timezone-aware).
    __table_args__ = (
        UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    )
