"""Phase 10D: user preferences table

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a7
Create Date: 2026-08-19

Additive only — creates the user-preferences persistence surface locked by
the Phase 10D scope:

- user_id: UUID PRIMARY KEY + NOT NULL FK to users.id; one preference row
  per user (1:1). The owner is always derived server-side from the
  authenticated JWT (get_current_user) — the client never supplies it.
- class_reminders: BOOLEAN NOT NULL DEFAULT FALSE — STORAGE/PREFERENCE DATA
  ONLY; it never sends reminders (Phase 11 consumes it later).
- auto_mark_present: BOOLEAN NOT NULL DEFAULT FALSE — STORAGE/PREFERENCE DATA
  ONLY; it never creates attendance records (Phase 11 consumes it later).
- week_starts_on: native PostgreSQL enum SUNDAY/MONDAY NOT NULL DEFAULT
  MONDAY — STORAGE/PREFERENCE DATA ONLY; it never alters calendar/analytics/
  attendance calculations (Phase 11 consumes it later).
- created_at / updated_at from the Base mixin convention (IST timezone-aware,
  NOT NULL; the ORM supplies them on insert, matching the feedback table).

Lazy-default semantics (Phase 10A decision): DB/server defaults only. No
backfill migration runs for existing users — a GET for a user with no row
materializes the defaults on demand. No relationships to
attendance/events/quiz/laboratory — preferences are fully isolated.
"""
from alembic import op
import sqlalchemy as sa


revision = "c1d2e3f4a5b6"
down_revision = "b1c2d3e4f5a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "userpreferences",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("class_reminders", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("auto_mark_present", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "week_starts_on",
            sa.Enum("SUNDAY", "MONDAY", name="weekstartson"),
            nullable=False,
            server_default="MONDAY",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("userpreferences")
    sa.Enum(name="weekstartson").drop(op.get_bind(), checkfirst=True)