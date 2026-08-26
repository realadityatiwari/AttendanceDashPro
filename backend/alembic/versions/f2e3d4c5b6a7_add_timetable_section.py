"""Phase 22.1: add section_id to timetable_entries

Revision ID: f2e3d4c5b6a7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-26

Phase 22.1 (Timetable Data-Scope Correction) — explicit Section ownership on
timetable entries.

Why this change:
- ``GET /api/v1/timetable`` is documented and intended to return the
  authenticated student's section timetable, but ``TimetableEntry`` had no
  section linkage and the repository query ignored the section_id argument —
  every section's schedule was returned to any authenticated student. The
  defect is masked by the current single-section production state (1 section,
  28 timetable entries) but becomes a cross-section data exposure the moment a
  second section exists.
- This migration adds ``timetable_entries.section_id`` (NOT NULL FK to
  sections.id) so every timetable entry is explicitly owned by a Section and
  the query can be scoped correctly.

Backfill strategy:
- The current state has exactly one Section. The migration resolves the
  Section from existing database state (the active AcademicSession → its
  Semester → its Section, falling back to a single existing Section) — it
  never hardcodes a UUID and never creates a new Section.
- After the backfill a guard verifies no row remains NULL before the NOT NULL
  constraint is enforced.

This migration:
- adds timetable_entries.section_id (FK → sections.id)
- backfills all existing rows to the resolved current Section
- enforces NOT NULL (guarded)
- preserves all existing rows, UUIDs, and timestamps; deletes nothing

Downgrade:
- drops the FK constraint and the column (reversible to the exact pre-22.1
  schema state).
"""
from alembic import op, context
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "f2e3d4c5b6a7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None

FK_NAME = "timetable_entries_section_id_fkey"


def upgrade() -> None:
    # 1. Add the column as nullable so existing rows can be backfilled.
    op.add_column(
        "timetable_entries",
        sa.Column("section_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        FK_NAME,
        "timetable_entries",
        "sections",
        ["section_id"],
        ["id"],
    )

    # 2. Backfill every existing row to the current Section, resolved from
    #    existing database state: the active AcademicSession → its Semester →
    #    its Section, falling back to a single existing Section. Never
    #    hardcodes a UUID and never creates a new Section.
    op.execute(
        """
        UPDATE timetable_entries te
        SET section_id = COALESCE(
            (
                SELECT sec.id
                FROM academic_sessions a
                JOIN semesters sem ON sem.session_id = a.id
                JOIN sections sec ON sec.semester_id = sem.id
                WHERE a.is_active = true
                LIMIT 1
            ),
            (
                SELECT sec2.id
                FROM sections sec2
                LIMIT 1
            )
        )
        WHERE te.section_id IS NULL
        """
    )

    # 3. Guard: refuse to enforce NOT NULL if any row could not be assigned a
    #    section (no Section exists in the database). The guard executes the
    #    check against the live connection in online mode only; offline SQL
    #    generation (--sql) emits the statements without executing them.
    if not context.is_offline_mode():
        connection = op.get_bind()
        remaining = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM timetable_entries WHERE section_id IS NULL"
            )
        ).scalar_one()
        if remaining:
            raise RuntimeError(
                f"timetable_entries backfill left {remaining} row(s) without a "
                "section; refusing to enforce NOT NULL. A Section row must exist "
                "before applying this migration."
            )

    # 4. Enforce NOT NULL — every timetable entry must belong to a Section.
    op.alter_column("timetable_entries", "section_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint(FK_NAME, "timetable_entries", type_="foreignkey")
    op.drop_column("timetable_entries", "section_id")
