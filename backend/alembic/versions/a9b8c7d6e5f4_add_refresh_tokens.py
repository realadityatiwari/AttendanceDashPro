"""Phase 25.1: refresh-token session persistence

Revision ID: a9b8c7d6e5f4
Revises: c4d5e6f7a8b9
Create Date: 2026-09-02

Additive only — creates the opaque, rotating, revocable refresh-token
persistence surface (Phase 25.1, backend session renewal):

- user_id: NOT NULL FK to users.id; owner always resolved server-side
  (login/register/refresh) — the client never supplies it.
- token_hash: SHA-256 hex digest (64 chars) of the opaque refresh secret.
  The RAW secret is NEVER persisted and never logged; lookup happens on the
  hash of the presented token. UNIQUE index → one row per presented token.
- family_id: rotation family. Every token minted from one authentication
  session shares one family; reuse of a rotated/revoked token revokes the
  whole family (theft indicator).
- expires_at: absolute expiry (~30 days, configuration-driven).
- is_used / is_revoked: rotation/revocation state. A token becomes used
  exactly once (at rotation); a used/revoked token never yields a session.
- replaced_by: row id of the token minted by rotating this one (plain UUID
  reference, no FK — token rows stay cleanup-friendly).
- id / created_at / updated_at from the Base mixin convention.

Indexes: UNIQUE(token_hash) for presentation lookup; family_id and user_id
for family-wide / user-wide revocation.

Downgrade drops the table and both non-unique indexes; no other table is
touched.

LOCAL DEV ONLY — not applied to production (operator boundary).
"""
from alembic import op
import sqlalchemy as sa

revision: str = "a9b8c7d6e5f4"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("replaced_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True
    )
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("uq_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
