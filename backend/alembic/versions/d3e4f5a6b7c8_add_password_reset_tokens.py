"""Stage 3A: admin-assisted password-reset tokens

Revision ID: d3e4f5a6b7c8
Revises: c7d8e9f0a1b2
Create Date: 2026-10-10

Additive only — creates the single-use, admin-issued password-recovery token
persistence surface (Stage 3A):

- user_id: NOT NULL FK to users.id — the target student whose password is
  recoverable. Resolved server-side by the issuing endpoint.
- issued_by_id: NOT NULL FK to users.id — the administrator who issued the
  token (durable actor audit).
- token_hash: SHA-256 hex digest (64 chars) of the opaque reset secret. The
  RAW secret is NEVER persisted and never logged; lookup is on the hash of the
  presented token. UNIQUE index → one row per presented token.
- expires_at: absolute short-lived expiry (configuration-driven).
- redeemed_at: set exactly once on successful redemption (single-use state).
- is_revoked: competing-token invalidation flag.
- id / created_at / updated_at from the Base mixin convention.

Indexes: UNIQUE(token_hash) for presentation lookup; user_id for the
outstanding-token sweep (issuance invalidation / redemption); issued_by_id for
issuer audit.

Downgrade drops the table and its indexes; no other table is touched.

LOCAL DEV ONLY — not applied to production (operator boundary).
"""
from alembic import op
import sqlalchemy as sa

revision: str = "d3e4f5a6b7c8"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("issued_by_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["issued_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_issued_by_id", "password_reset_tokens", ["issued_by_id"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_issued_by_id", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_index("uq_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")