"""add unified HOLIDAY event type

Revision ID: a7b8c9d0e1f2
Revises: f6a5b4c3d2e1f
Create Date: 2026-08-16 20:00:00.000000

Why this change (Events system — Working Saturday + Unified Holiday):
- The user-facing Events UI exposes ONE holiday creation flow (single day or
  date range with a reason/occasion note). The backend represents it as the
  new HOLIDAY event type, a member of the existing closure family (day
  becomes non-working; scheduled sessions are cancelled through the canonical
  synchronizer). The legacy PUBLIC_HOLIDAY / INSTITUTE_HOLIDAY /
  FESTIVAL_HOLIDAY types remain fully supported and readable — this is purely
  additive.
- academic_events.event_type is a native PostgreSQL enum (`eventtype`); the
  new value therefore requires an ALTER TYPE ... ADD VALUE. No tables are
  created, no data rows are changed, and no attendance/session semantics are
  touched by this migration.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a5b4c3d2e1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'HOLIDAY'"
    )


def downgrade() -> None:
    # PostgreSQL cannot remove an enum value; the added label remains as an
    # unused dead value after a downgrade (documented PG limitation — it is
    # never referenced once the Python enum reverts).
    pass
