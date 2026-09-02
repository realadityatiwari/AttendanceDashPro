"""Phase 11C-P2: push_subscriptions — authenticated owner-scoped Web Push registry

Revision ID: f0e1d2c3b4a5
Revises: a9b8c7d6e5f4
Create Date: 2026-09-02

Phase 11C-P2 establishes the persistent subscription layer required by P3
(VAPID + backend dispatch). The table stores the browser PushSubscription
(endpoint + p256dh + auth) needed to deliver push messages to authenticated
user devices.

Why a schema change is genuinely required:
  - There is NO existing push-subscription table anywhere in the repository.
  - The existing ``notifications`` table (Phase 11B) is an in-app inbox, not a
    push delivery registry — it stores projection rows, not endpoint data.
  - A new table is required because push subscriptions are a fundamentally
    different resource: they are per-device, endpoint-identified, user-owned
    registry entries with no overlap with the notification inbox.

Changes (additive, non-destructive):
  1. New table ``push_subscriptions``:
       - id            UUID PK (from Base mixin)
       - created_at    IST timestamptz
       - updated_at    IST timestamptz
       - user_id       FK users.id (NOT NULL, indexed)
       - endpoint      Text (NOT NULL, UNIQUE — natural idempotency key)
       - p256dh        String (NOT NULL — browser encryption key)
       - auth          String (NOT NULL — browser auth secret)

Backward compatibility:
  - Zero existing tables, rows, enums, or constraints are modified.
  - ``notifications`` table, in-app notification behavior, and notification
    generation are untouched.
  - No existing API endpoint or contract changes.

Downgrade drops the table and its indexes. No data is lost beyond the new
table's own rows.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "f0e1d2c3b4a5"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(), nullable=False),
        sa.Column("auth", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_push_subscription_user"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")