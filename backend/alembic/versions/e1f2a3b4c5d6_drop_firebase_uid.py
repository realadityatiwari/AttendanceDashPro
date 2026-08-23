"""drop firebase_uid from users

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-08-23

Phase 14D (Firebase Retirement) — final application identity residue removal.

Why this change:
- Firebase Auth is fully retired (Phases 14A/14B); PostgreSQL + JWT is the
  authoritative authentication architecture. JWT authentication resolves
  users by ``id`` (UUID via ``sub``); login and registration use
  ``roll_number``. Nothing at runtime reads or writes ``firebase_uid``.
- The column was made nullable in c3d4e5f6a7b8 (Phase 4.5.3) so PostgreSQL-native
  registrations could exist without a Firebase UID. Phase 14D now owns the
  actual removal.

This migration:
- drops the unique index ix_users_firebase_uid
- drops the column users.firebase_uid

No user rows are modified; no Firebase UID values are copied, transformed, or
repurposed. Downgrade re-creates the column as NULLABLE (matching the schema
state established by c3d4e5f6a7b8) with its unique index; it does NOT invent
historical Firebase values.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f('ix_users_firebase_uid'), table_name='users')
    op.drop_column('users', 'firebase_uid')


def downgrade() -> None:
    op.add_column('users', sa.Column('firebase_uid', sa.String(), nullable=True))
    op.create_index(op.f('ix_users_firebase_uid'), 'users', ['firebase_uid'], unique=True)
