"""Phase 23.5: subjects.elective_slot — DB-backed authoritative elective catalog

Revision ID: f5a6b7c8d9e0
Revises: e3f4a5b6c7d8
Create Date: 2026-08-28

Phase 23.5 (Elective/Catalog Redesign) — normalizes the elective catalog into
the database so it becomes the authoritative source of what can be selected,
instead of being hardcoded in `ElectiveResolver` code constants (which were
duplicated with the free-form `subjects.tag` string — the 23.2 discovery
flagged this duplication risk).

The smallest correct model (no new tables): `subjects` is ALREADY the
semester-scoped catalog of concrete subjects (semester_id NOT NULL,
UNIQUE(code, semester_id) since 23.2). Adding a typed, nullable
``elective_slot`` column makes slot membership authoritative and type-safe:

  - NULL             = common / practical subject (never an elective)
  - ELECTIVE_I       = DE-I allowed subjects (BCS-052 / BCS-053 / BCS-054)
  - ELECTIVE_II      = DE-II allowed subjects (BCS-055 / BCS-056 / BCS-058)

A single column guarantees one slot per subject — a subject can never silently
belong to both slots (a separate catalog table would permit that, so it would
be LESS normalized).

Changes (additive + deterministic, no destructive operation):
1. Add ``subjects.elective_slot`` (nullable ``electiveslot`` enum — the type
   already exists from Phase 22.3).
2. Backfill from the existing authoritative ``tag`` marker:
   'Elective-I' -> ELECTIVE_I, 'Elective-II' -> ELECTIVE_II (1:1 today).

No subject, student choice, enrollment, attendance, session, event, quiz, or
timetable data is created, rewritten, or deleted. Downgrade drops the column.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

revision = "f5a6b7c8d9e0"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None

# Reuse the existing electiveslot enum type created by the Phase 22.3 migration.
ELECTIVE_SLOT_COL = ENUM("ELECTIVE_I", "ELECTIVE_II", name="electiveslot", create_type=False)


def upgrade() -> None:
    op.add_column(
        "subjects",
        sa.Column("elective_slot", ELECTIVE_SLOT_COL, nullable=True),
    )
    # Deterministic backfill from the existing authoritative tag marker.
    # Guards: only subjects whose tag is exactly an elective marker are tagged;
    # anything else stays NULL (never fabricated).
    op.execute(
        """
        UPDATE subjects
        SET elective_slot = CASE
            WHEN tag = 'Elective-I' THEN 'ELECTIVE_I'::electiveslot
            WHEN tag = 'Elective-II' THEN 'ELECTIVE_II'::electiveslot
            ELSE NULL
        END
        WHERE tag IN ('Elective-I', 'Elective-II')
        """
    )


def downgrade() -> None:
    op.drop_column("subjects", "elective_slot")
