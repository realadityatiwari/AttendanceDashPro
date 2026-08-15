"""Phase 9.2.1 Migration A: laboratory_experiments catalog columns

Revision ID: f1a2b3c4d5e6f
Revises: a1b2c3d4e5f6
Create Date: 2026-08-15

Additive only — adds the experiment catalog columns locked by the
Phase 9.2.0 audit:
- description: nullable free-text experiment description
- is_active: boolean catalog flag (server default TRUE); deactivation
  replaces hard deletion so historical lab records keep their FK intact
- UNIQUE(subject_id, experiment_number): enforces one experiment number
  per subject at the database level (duplicate ingestion → IntegrityError)

created_at / updated_at already exist on this table from the initial
schema migration (Base mixin), so they are NOT re-added here.
"""
from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6f"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "laboratory_experiments",
        sa.Column("description", sa.String(), nullable=True),
    )
    op.add_column(
        "laboratory_experiments",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_unique_constraint(
        "uq_subject_experiment",
        "laboratory_experiments",
        ["subject_id", "experiment_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_subject_experiment", "laboratory_experiments", type_="unique"
    )
    op.drop_column("laboratory_experiments", "is_active")
    op.drop_column("laboratory_experiments", "description")