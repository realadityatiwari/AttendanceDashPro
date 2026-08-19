"""Phase 10C: feedback table

Revision ID: b1c2d3e4f5a7
Revises: b1c2d3e4f5a6
Create Date: 2026-08-19

Additive only — creates the feedback persistence surface locked by the
Phase 10C scope:
- user_id: NOT NULL FK to users.id; always derived server-side from the
  authenticated JWT (get_current_user) — the client never supplies it.
- feedback_type: enum BUG/SUGGESTION/QUESTION/PRAISE, values matching the
  frontend FeedbackModal exactly.
- message: TEXT, NOT NULL (server-side length/whitespace validation).
- context: nullable String — optional, no automatic capture.
- id / created_at / updated_at from the Base mixin (IST timezone-aware).

No relationships to Attendance/Events/Quiz/Laboratory — fully isolated.
"""
from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5a7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "feedback_type",
            sa.Enum("BUG", "SUGGESTION", "QUESTION", "PRAISE", name="feedbacktype"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.String(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("feedback")