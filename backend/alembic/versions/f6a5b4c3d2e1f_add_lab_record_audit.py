"""Phase 9.2.1 Migration B: laboratory_records session linkage + audit FKs

Revision ID: f6a5b4c3d2e1f
Revises: f1a2b3c4d5e6f
Create Date: 2026-08-15

Additive only — adds the record columns locked by the Phase 9.2.0 audit:
- class_session_id: nullable FK to class_sessions.id; links a record to
  the canonical practical session it was conducted in (audit must stay
  truthful: a record may exist without a session link)
- signed_by: nullable FK to users.id; the ADMIN who signed the record
- created_by / updated_by: nullable FK to users.id; creation + last
  modification audit trail

created_at / updated_at already exist on this table from the initial
schema migration (Base mixin), so they are NOT re-added here.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f6a5b4c3d2e1f"
down_revision = "f1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "laboratory_records",
        sa.Column(
            "class_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("class_sessions.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "laboratory_records",
        sa.Column(
            "signed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "laboratory_records",
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "laboratory_records",
        sa.Column(
            "updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("laboratory_records", "updated_by")
    op.drop_column("laboratory_records", "created_by")
    op.drop_column("laboratory_records", "signed_by")
    op.drop_column("laboratory_records", "class_session_id")