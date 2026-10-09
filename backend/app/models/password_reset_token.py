from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index, text
from app.db.base_class import Base
import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID


class PasswordResetToken(Base):
    """Stage 3A: admin-issued, single-use password-recovery token.

    Mirrors the security shape of ``refresh_tokens``: only the SHA-256 hex
    digest of the opaque secret is persisted; the RAW token is returned to the
    issuing administrator exactly once and never stored or logged.

    Lifecycle: a token is redeemable only while it is neither redeemed,
    revoked, nor expired. ``redeemed_at``/``is_revoked`` are the durable state;
    ``issued_by_id`` and the timestamps are the audit trail.

    Owner/target semantics: ``user_id`` is the student whose password may be
    reset; ``issued_by_id`` is the administrator who issued it. Both are
    resolved server-side — the client never supplies either.
    """

    __tablename__ = "password_reset_tokens"

    # Target student (the account whose password is recoverable).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # Issuing administrator (audit). Nullable FK is not used — issuance is
    # always performed by an authenticated admin, so this is NOT NULL.
    issued_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # SHA-256 hex digest (64 chars) of the opaque reset secret. The RAW secret
    # is NEVER persisted; lookup is by the hash of the presented token.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Single-use state: set to the redemption instant exactly once. A token
    # with a non-null redeemed_at can never be redeemed again.
    redeemed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Competing-token invalidation: when a new token is issued for a student
    # (or a redemption completes), any other outstanding token for that
    # student is revoked so only one recovery path is ever live.
    is_revoked: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    __table_args__ = (
        # Lookup is always by hash of the presented token — unique.
        Index("uq_password_reset_tokens_token_hash", "token_hash", unique=True),
        # Outstanding-token sweep by student (issuance invalidation / redemption).
        Index("ix_password_reset_tokens_user_id", "user_id"),
        # Issuer audit lookup.
        Index("ix_password_reset_tokens_issued_by_id", "issued_by_id"),
    )