"""Phase 24.7-A: timetable domain foundation

Revision ID: c4d5e6f7a8b9
Revises: eb880e108f19
Create Date: 2026-08-29

Phase 24.7-A — Timetable Domain Foundation.

Extends ``timetable_entries`` (the EXPECTED academic schedule, distinct from
actual ``class_sessions`` occurrences) with the Phase 24.7 admin contract:

  - ``subsection_id`` (nullable FK -> subsections.id): optional Subsection
    scope; NULL = section-wide entry.
  - ``room`` (nullable String): expected-schedule room.
  - ``is_active`` (NOT NULL, server default true): expected-schedule active
    flag. Existing rows deterministically become active — no fabricated data.
  - ``sort_order`` (nullable Integer): deterministic ordering hint.

DB-level integrity guards added:

  - CHECK ``end_time > start_time``
    (``ck_timetable_entries_end_gt_start``)
  - CHECK ``day_of_week`` in 0..6
    (``ck_timetable_entries_day_of_week_range``)
  - UNIQUE on subsections ``(section_id, id)``
    (``uq_subsections_section_id``) — required target for the composite FK.
  - composite FK ``(section_id, subsection_id)`` -> subsections
    ``(section_id, id)`` (``fk_timetable_entries_section_subsection``):
    guarantees that a timetable entry's subsection, when set, belongs to the
    entry's section.

Additive only: all 28 existing timetable rows are preserved byte-for-byte
(no backfill of academic data, no deletions, UUIDs/timestamps untouched).

Downgrade removes every added column/constraint and restores the exact
pre-24.7-A schema.

LOCAL ONLY — this migration must never be applied to production by an
automated process; production application is an operator decision.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = 'c4d5e6f7a8b9'
down_revision = 'eb880e108f19'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Additive columns (all nullable or server-defaulted so existing rows
    #    are preserved without any backfill of invented academic data).
    op.add_column(
        "timetable_entries",
        sa.Column("subsection_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "timetable_entries",
        sa.Column("room", sa.String(100), nullable=True),
    )
    op.add_column(
        "timetable_entries",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "timetable_entries",
        sa.Column("sort_order", sa.Integer(), nullable=True),
    )

    # 2. Integrity guards.
    op.create_check_constraint(
        "ck_timetable_entries_end_gt_start",
        "timetable_entries",
        "end_time > start_time",
    )
    op.create_check_constraint(
        "ck_timetable_entries_day_of_week_range",
        "timetable_entries",
        "day_of_week >= 0 AND day_of_week <= 6",
    )

    # 3. Composite-FK target uniqueness on subsections (section_id, id) —
    #    required by PostgreSQL for the composite FK reference. id is already
    #    the PK, so this is a supporting unique index, not a semantic change.
    op.create_unique_constraint(
        "uq_subsections_section_id",
        "subsections",
        ["section_id", "id"],
    )

    # 4. Composite FK: subsection (when set) must belong to the entry's section.
    op.create_foreign_key(
        "fk_timetable_entries_section_subsection",
        "timetable_entries",
        "subsections",
        ["section_id", "subsection_id"],
        ["section_id", "id"],
    )

    # 5. Simple FK for the subsection_id column itself (existence).
    op.create_foreign_key(
        "timetable_entries_subsection_id_fkey",
        "timetable_entries",
        "subsections",
        ["subsection_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "timetable_entries_subsection_id_fkey",
        "timetable_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_timetable_entries_section_subsection",
        "timetable_entries",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_subsections_section_id",
        "subsections",
        type_="unique",
    )
    op.drop_constraint(
        "ck_timetable_entries_day_of_week_range",
        "timetable_entries",
        type_="check",
    )
    op.drop_constraint(
        "ck_timetable_entries_end_gt_start",
        "timetable_entries",
        type_="check",
    )
    op.drop_column("timetable_entries", "sort_order")
    op.drop_column("timetable_entries", "is_active")
    op.drop_column("timetable_entries", "room")
    op.drop_column("timetable_entries", "subsection_id")
