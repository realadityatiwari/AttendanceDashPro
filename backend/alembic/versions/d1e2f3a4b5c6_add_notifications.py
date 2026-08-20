"""Phase 11B: notifications table

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-08-20

Additive only — creates the notification persistence surface locked by the
Phase 11B scope (audit docs/phase_11/phase_11_architecture_audit.md §9-11B):

- user_id: NOT NULL FK to users.id; owner always derived server-side from the
  authenticated JWT (get_current_user) — the client never supplies it.
- kind: native PostgreSQL enum notificationkind (the Phase 11A NotificationKind
  values — the SAME enum, never a second one).
- occurrence_key: the deterministic natural-key reference of the Phase 11A
  projection (session id for CLASS_REMINDER, quiz cycle for
  QUIZ_APPROACHING, event id for ACADEMIC_EVENT, subject code for
  ATTENDANCE_THRESHOLD / MUST_ATTEND / SAFE_SKIP).
- UNIQUE(user_id, kind, occurrence_key): database-enforced idempotency —
  repeated generation of the same projection can never create a duplicate row.
- date: occurrence date (first-generation date; never rolled forward by
  regeneration).
- subject_code / subject_name: nullable presentation references (audit §8-9:
  rows store references + presentation text, never recomputed statistics).
- message: TEXT NOT NULL — the presentation text of the projection.
- session_id / quiz_cycle / event_id: nullable typed source references (the
  audit-named references; the same fields the Phase 11A item contract carries).
- is_read / is_dismissed: BOOLEAN NOT NULL DEFAULT FALSE — read/dismiss state
  (audit 11B objective: "PATCH ... (read/dismiss)"; both are preserved by
  regeneration upserts).
- id / created_at / updated_at from the Base mixin convention (IST
  timezone-aware, NOT NULL).
- No relationships to Attendance/Events/Quiz/Laboratory — notifications are an
  isolated inbox that consumes engine outputs at generation time.
"""
from alembic import op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "CLASS_REMINDER",
                "QUIZ_APPROACHING",
                "ATTENDANCE_THRESHOLD",
                "MUST_ATTEND",
                "SAFE_SKIP",
                "ACADEMIC_EVENT",
                name="notificationkind",
            ),
            nullable=False,
        ),
        sa.Column("occurrence_key", sa.String(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("subject_code", sa.String(), nullable=True),
        sa.Column("subject_name", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("quiz_cycle", sa.Integer(), nullable=True),
        sa.Column("event_id", sa.UUID(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_dismissed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "kind", "occurrence_key",
            name="uq_notifications_user_kind_occurrence_key",
        ),
    )


def downgrade() -> None:
    op.drop_table("notifications")
    sa.Enum(name="notificationkind").drop(op.get_bind(), checkfirst=True)