"""make firebase_uid nullable

Revision ID: c3d4e5f6a7b8
Revises: 8a2b3c4d5e6f
Create Date: 2026-08-14 10:00:00.000000

Why this change:
- Firebase is retired from runtime authentication (PostgreSQL + JWT only).
- New students register through POST /api/v1/auth/register and have no
  Firebase identity.
- The column is made nullable so PostgreSQL-native users can exist without
  a Firebase UID, while every existing firebase_uid value is preserved.
- The column is NOT dropped yet: legacy identity data remains intact and
  Phase 14 (Firebase Retirement) owns any eventual removal.
- The unique index ix_users_firebase_uid remains; PostgreSQL allows
  multiple NULLs in a unique index, so it keeps protecting legacy values.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = '8a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'firebase_uid', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Only safe if no NULL firebase_uid rows exist (all users are legacy).
    op.alter_column('users', 'firebase_uid', existing_type=sa.String(), nullable=False)