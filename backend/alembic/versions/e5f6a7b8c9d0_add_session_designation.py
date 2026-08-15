"""add session designation column

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-15 14:00:00.000000

Why this change:
- Phase 8.2 introduces the laboratory mid-semester practical designation. The
  product workflow requires the mid-sem practical to be tied to an ACTUAL
  scheduled practical class session (faculty/admin designates a real session),
  never inferred from experiment counts or a fixed calendar date
  (docs/phase_8_2_implementation_report.md, "MID-SEM PRACTICAL DESIGN").
- The class_sessions table had no way to mark a specific session with such a
  designation. This migration adds an optional `designation` column (NULL =
  regular session; MID_SEM_PRACTICAL = the designated mid-sem practical).
- The column is nullable with no server default, so existing rows (all 691
  sessions) are untouched and every counting query keeps working unchanged.
- Designation does NOT alter attendance counting: attendance against a
  designated session flows through the exact same attendance_records mutation
  path. The event synchronizer, engines, and all other columns are untouched.
- No seed data is created: no experiment/title/date is fabricated (authoritative
  lab curriculum data remains unavailable).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sessiondesignation = sa.Enum('MID_SEM_PRACTICAL', name='sessiondesignation')
    sessiondesignation.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'class_sessions',
        sa.Column('designation', sessiondesignation, nullable=True),
    )


def downgrade() -> None:
    op.drop_column('class_sessions', 'designation')
    sa.Enum(name='sessiondesignation').drop(op.get_bind(), checkfirst=True)
