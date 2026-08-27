"""Phase 23.6: occurrence_outcomes — subject-specific actual-occurrence overrides

Revision ID: f6a7b8c9d0e1
Revises: f5a6b7c8d9e0
Create Date: 2026-08-28

Phase 23.6 (Actual Occurrence Architecture) — separates the EXPECTED schedule
(timetable_entries) from the ACTUAL occurrence (class_sessions) and adds the
ability for one actual occurrence to have DIFFERENT effective types for
different concrete subjects in the same Departmental Elective slot.

Why: a single ``class_sessions`` row has single-valued ``is_extra`` /
``is_cancelled``. For the shared DE-II slot it cannot express:

    BCS-058 -> Surprise Quiz
    BCS-055 -> Normal Lecture
    BCS-056 -> Cancelled

The ``occurrence_outcomes`` table stores per-subject overrides keyed by
(class_session_id, subject_id). The session row remains the anchor (shared
default); subjects WITHOUT an outcome row follow the anchor's own flags.

Additive + deterministic + non-destructive:
- New table ``occurrence_outcomes`` (UNIQUE(class_session_id, subject_id)).
- New enum type ``occurrenceoutcometype`` (EXTRA_LECTURE, EXTRA_TUTORIAL,
  EXTRA_PRACTICAL, SURPRISE_QUIZ, CANCELLED).
- No existing table, row, constraint, attendance record, session, event,
  quiz, or timetable entry is modified. The table starts EMPTY (no backfill).

Downgrade drops the table then the enum type.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

revision = "f6a7b8c9d0e1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None

OUTCOME_ENUM = ENUM(
    "EXTRA_LECTURE",
    "EXTRA_TUTORIAL",
    "EXTRA_PRACTICAL",
    "SURPRISE_QUIZ",
    "CANCELLED",
    name="occurrenceoutcometype",
)
OUTCOME_COL = ENUM(
    "EXTRA_LECTURE",
    "EXTRA_TUTORIAL",
    "EXTRA_PRACTICAL",
    "SURPRISE_QUIZ",
    "CANCELLED",
    name="occurrenceoutcometype",
    create_type=False,
)


def upgrade() -> None:
    OUTCOME_ENUM.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "occurrence_outcomes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
        sa.Column("class_session_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("outcome_type", OUTCOME_COL, nullable=False),
        sa.ForeignKeyConstraint(
            ["class_session_id"], ["class_sessions.id"],
            name="fk_occurrence_outcome_session",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"],
            name="fk_occurrence_outcome_subject",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "class_session_id",
            "subject_id",
            name="uq_occurrence_outcome_session_subject",
        ),
    )
    op.create_index(
        "ix_occurrence_outcomes_class_session_id",
        "occurrence_outcomes",
        ["class_session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_occurrence_outcomes_class_session_id",
        table_name="occurrence_outcomes",
    )
    op.drop_table("occurrence_outcomes")
    OUTCOME_ENUM.drop(op.get_bind(), checkfirst=True)
