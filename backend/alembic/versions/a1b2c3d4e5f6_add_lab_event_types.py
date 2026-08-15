"""add lab event types and event note column

Revision ID: a1b2c3d4e5f6
Revises: e5f6a7b8c9d0
Create Date: 2026-08-15 18:00:00.000000

Why this change (Phase 9.1 — Laboratory Attendance & Event Integration):
- Mid-Sem Practical and Lab Cancelled are NOT separate attendance systems:
  they are Academic Events the EventSessionSynchronizer resolves into the
  canonical ClassSession pipeline (AcademicEvent -> synchronizer ->
  ClassSession -> AttendanceRecord -> existing engines). The academic_events
  table stores event_type in a native PostgreSQL enum (`eventtype`); the two
  new event types therefore require ADD VALUE statements. No new tables are
  created — the existing AcademicEvent + ClassSession + AttendanceRecord
  architecture represents everything.
- A nullable `note` column is added so the two new event types can carry the
  optional student-entered note/reason shown in the Phase 9.1 event form.
  NULL for all existing rows (the 18 QUIZ_DAY events are untouched); purely
  additive metadata, never read by any attendance calculation.
- No data rows are changed. No experiment curriculum is fabricated.

Note: ALTER TYPE ... ADD VALUE is allowed inside the migration transaction on
PostgreSQL 12+; the new values are not used within this same transaction.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'MID_SEM_PRACTICAL'"
    )
    op.execute(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'LAB_CANCELLED'"
    )
    op.add_column(
        'academic_events',
        sa.Column('note', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('academic_events', 'note')
    # PostgreSQL cannot remove an enum value; the two added labels remain as
    # unused dead values after a downgrade (documented PG limitation — they
    # are never referenced once the Python enum reverts).
