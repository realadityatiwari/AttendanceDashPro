"""add user role column

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-14 11:00:00.000000

Why this change:
- Phase 6.5 introduces the first authorization role: STUDENT | ADMIN.
- The users table previously had no role concept; every authenticated user
  was treated identically (see docs/phase_6_0_calendar_events_audit.md §13).
- ADMIN is granted only through the explicit provisioning script
  (backend/scripts/provision_admin.py); it is never self-assignable and no
  endpoint assigns roles.
- Safe for existing users: the server default backfills every existing row
  with STUDENT. No users are deleted or modified beyond the role value.
- attendance_records, class_sessions, student_enrollment, subjects and the
  rest of the attendance architecture are untouched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    userrole = sa.Enum('STUDENT', 'ADMIN', name='userrole')
    userrole.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'users',
        sa.Column('role', userrole, nullable=False, server_default='STUDENT'),
    )


def downgrade() -> None:
    op.drop_column('users', 'role')
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)
