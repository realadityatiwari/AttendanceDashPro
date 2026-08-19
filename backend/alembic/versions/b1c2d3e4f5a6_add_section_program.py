"""Phase 10B: sections.program column + CSE-51 backfill

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-08-19

Additive only — adds the program field locked by the Phase 10B scope:
- program: nullable String on sections — the cohort/program grouping the
  section belongs to (e.g. "CSE" for section "CSE-51"). Stored data;
  never derived from section.name at runtime.
- Guarded backfill: the single existing section CSE-51 receives 'CSE'.
  The guard (program IS NULL) keeps the migration idempotent and never
  overwrites a differently-provisioned program.

Section identity, relationships, and all other tables are untouched.
"""
from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5a6"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sections",
        sa.Column("program", sa.String(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE sections SET program = 'CSE' "
            "WHERE name = 'CSE-51' AND program IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("sections", "program")