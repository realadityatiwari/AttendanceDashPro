from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index, text
from app.db.base_class import Base
import datetime
import uuid
from sqlalchemy.dialects.postgresql import UUID


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    # Owner is always resolved server-side (login/register/refresh) — the
    # client can never supply user_id.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    # SHA-256 hex digest of the opaque refresh secret. The RAW secret is NEVER
    # persisted; lookup happens on the hash of the presented token.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Rotation family: every token minted from one authentication session
    # (login/register) shares one family_id. Reuse of a rotated/revoked token
    # revokes the whole family (theft indicator).
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Rotation state: a token becomes used exactly once (at rotation) and
    # points at its replacement. Re-presenting a used/revoked token is
    # treated as theft and revokes the family.
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    # Replacement relationship: the row id of the token minted by rotating
    # this one (NULL for a token that has never been rotated).
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        # Lookup is always by hash of the presented token — unique, so a
        # token hash identifies at most one row.
        Index("uq_refresh_tokens_token_hash", "token_hash", unique=True),
        # Family-wide revocation (reuse detection / logout).
        Index("ix_refresh_tokens_family_id", "family_id"),
        # User-wide revocation (account deactivation / cleanup).
        Index("ix_refresh_tokens_user_id", "user_id"),
    )

    # id / created_at / updated_at come from the Base mixin. replaced_by is a
    # plain UUID reference (no FK constraint) so token rows are never blocked
    # from cleanup by referential ordering; it is set only by rotation.
