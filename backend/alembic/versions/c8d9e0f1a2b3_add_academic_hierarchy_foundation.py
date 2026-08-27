"""Phase 23.1: academic hierarchy & enrollment schema foundation

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-08-27

Phase 23.1 (Academic Hierarchy & Enrollment Schema Foundation) — schema/data
model foundation ONLY (reconciled Phase 23.0 governance; do NOT pull Phase
23.2/23.3 work forward).

Changes (all additive / constraint-only; preserves every existing row, UUID,
timestamp, FK):

1. Create ``subsections`` table (id, name, section_id FK -> sections.id,
   max_strength NULLABLE, created_at, updated_at) with
   UNIQUE(section_id, name) — subsection names are unique within a section
   only. **No rows are created**: no subsection is fabricated for existing
   sections (Phase 23.0 Correction 9; subsection creation is later work).
   ``max_strength`` is NULLABLE with no server default — the authoritative
   capacity value is an open decision (report §36); NULL = unset, never a
   fabricated default.

2. Add ``users.subsection_id`` (nullable FK -> subsections.id). Existing rows
   stay NULL = UNKNOWN/UNASSIGNED. **No backfill, no auto-assignment.**

3. Relax ``sections.name`` global-unique index to composite
   UNIQUE(semester_id, name) — the same section name may be reused across
   semesters (and, after the Branch decision gate, across branches). Guarded:
   refuses if duplicate (semester_id, name) pairs already exist (currently one
   section, CSE-51, so safe).

4. Add UNIQUE(user_id, subject_id) on ``student_enrollments`` (Correction 8
   gate): subject_id is semester-scoped, so this prevents duplicate current
   enrollment while preserving multi-semester history (the same subject code in
   a later semester is a different Subject row). Guarded: refuses if duplicate
   (user_id, subject_id) rows already exist (none per the Phase 17/21D.3
   integrity audits).

Deliberately NOT in Phase 23.1 (belong to later Phase 23 slices):
- timetable_entries.subsection_id / class_sessions.subsection_id (Phase 23.3)
- occurrence_outcomes / event-scope enum (Phase 23.4/23.7)
- admin_scopes / SECTION_ADMIN role (Phase 23.9)
- Branch entity (Phase 23.1 DECISION GATE — repository evidence shows NO Branch
  entity exists; Section.program is the only program representation; parentage
  remains unresolved)
- AcademicSession stays canonical (no second academic-year entity)
"""
from alembic import op, context
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None

UQ_SUBSECTIONS_SECTION_NAME = "uq_subsections_section_name"
UQ_SECTIONS_SEMESTER_NAME = "uq_sections_semester_name"
UQ_ENROLLMENTS_USER_SUBJECT = "uq_student_enrollments_user_subject"
FK_USERS_SUBSECTION = "users_subsection_id_fkey"
FK_SUBSECTIONS_SECTION = "subsections_section_id_fkey"


def upgrade() -> None:
    # 1. subsections table — no rows created (no fabrication, Correction 9).
    op.create_table(
        "subsections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("section_id", sa.UUID(), nullable=False),
        sa.Column("max_strength", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], name=FK_SUBSECTIONS_SECTION),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_id", "name", name=UQ_SUBSECTIONS_SECTION_NAME),
    )

    # 2. users.subsection_id — nullable FK; existing rows stay NULL (no
    #    backfill, no auto-assignment, Correction 9).
    op.add_column(
        "users",
        sa.Column("subsection_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        FK_USERS_SUBSECTION,
        "users",
        "subsections",
        ["subsection_id"],
        ["id"],
    )

    # 3. sections.name: drop the global-unique index; add composite unique
    #    (semester_id, name). Guarded against pre-existing duplicates.
    op.drop_index("ix_sections_name", table_name="sections")
    if not context.is_offline_mode():
        connection = op.get_bind()
        duplicates = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM (SELECT semester_id, name FROM sections "
                "GROUP BY semester_id, name HAVING COUNT(*) > 1) d"
            )
        ).scalar_one()
        if duplicates:
            raise RuntimeError(
                f"sections contains {duplicates} duplicate (semester_id, name) "
                "pair(s); refusing to add the composite unique constraint. "
                "Existing data must be reconciled before this migration."
            )
    op.create_unique_constraint(
        UQ_SECTIONS_SEMESTER_NAME,
        "sections",
        ["semester_id", "name"],
    )

    # 4. student_enrollments: UNIQUE(user_id, subject_id) — guarded against
    #    pre-existing duplicate rows.
    if not context.is_offline_mode():
        connection = op.get_bind()
        duplicates = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM (SELECT user_id, subject_id FROM "
                "student_enrollments GROUP BY user_id, subject_id "
                "HAVING COUNT(*) > 1) d"
            )
        ).scalar_one()
        if duplicates:
            raise RuntimeError(
                f"student_enrollments contains {duplicates} duplicate "
                "(user_id, subject_id) row(s); refusing to add the unique "
                "constraint. Existing data must be reconciled before this "
                "migration."
            )
    op.create_unique_constraint(
        UQ_ENROLLMENTS_USER_SUBJECT,
        "student_enrollments",
        ["user_id", "subject_id"],
    )


def downgrade() -> None:
    op.drop_constraint(UQ_ENROLLMENTS_USER_SUBJECT, "student_enrollments", type_="unique")
    op.drop_constraint(UQ_SECTIONS_SEMESTER_NAME, "sections", type_="unique")
    # Restore the historical global-unique index on sections.name.
    op.create_index("ix_sections_name", "sections", ["name"], unique=True)
    op.drop_constraint(FK_USERS_SUBSECTION, "users", type_="foreignkey")
    op.drop_column("users", "subsection_id")
    op.drop_table("subsections")
