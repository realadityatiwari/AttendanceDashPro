"""add class_session lifecycle + provenance columns

Revision ID: a7b8c9d0e1f2
Revises: f0e1d2c3b4a5
Create Date: 2026-09-27

Deactivated-attended-extra lifecycle foundation (Chunk — lifecycle only):

  - class_sessions.is_deactivated (Boolean, NOT NULL, server_default false):
    the source EXTRA_* event was withdrawn after this occurrence existed;
    the historical row (and any attendance record) is preserved — never
    deleted, never is_cancelled — and the read layer will later exclude it
    from logical attendance. Default false keeps every legacy row logically
    active: zero behavior change on deploy, no backfill, fully reversible.

  - class_sessions.source_event_id (UUID, nullable, FK -> academic_events.id,
    indexed): provenance for event-created EXTRA_* sessions. Populated at
    creation by the synchronizer for NEW rows only. NULL for timetable-linked
    sessions and for legacy rows (historical provenance was never recorded
    and is never guessed or backfilled).

No existing row is modified: attendance_records, users, enrollments and all
pre-existing class_sessions keep their exact state.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'f0e1d2c3b4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'class_sessions',
        sa.Column('is_deactivated', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
    )
    op.add_column(
        'class_sessions',
        sa.Column('source_event_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'fk_class_sessions_source_event_id',
        'class_sessions', 'academic_events',
        ['source_event_id'], ['id'],
    )
    op.create_index(
        'ix_class_sessions_source_event_id',
        'class_sessions', ['source_event_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_class_sessions_source_event_id', table_name='class_sessions')
    op.drop_constraint('fk_class_sessions_source_event_id', 'class_sessions',
                       type_='foreignkey')
    op.drop_column('class_sessions', 'source_event_id')
    op.drop_column('class_sessions', 'is_deactivated')
