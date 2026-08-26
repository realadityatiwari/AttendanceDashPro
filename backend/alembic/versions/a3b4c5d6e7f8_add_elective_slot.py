"""Phase 22.3: elective_slot on timetable_entries + StudentElectiveChoice + elective subjects

Revision ID: a3b4c5d6e7f8
Revises: f2e3d4c5b6a7
Create Date: 2026-08-26

Phase 22.3 (Student Elective Selection & Timetable Resolution) — adds the
infrastructure for per-student elective subject selection.

Changes:
1. Add ``timetable_entries.elective_slot`` (nullable enum ELECTIVE_I /
   ELECTIVE_II) — marks shared timetable entries whose subject is a Department
   Elective slot. NULL = a regular entry. Backfilled from the subject's tag
   ("Elective-I" → ELECTIVE_I, "Elective-II" → ELECTIVE_II).
2. Create ``student_elective_choices`` table — one row per (user, elective
   slot) with a UNIQUE constraint. Absence of a row = no selection made.
3. Insert the four missing Department Elective subjects (BCS-052, BCS-053,
   BCS-055, BCS-056) into the ``subjects`` table, scoped to the active
   semester. These are authoritative CSE-51 V Semester CTT subjects.

No timetable entry's subject_id, ClassSession's subject_id, or attendance
record is changed. Per-student elective resolution is handled at the
application read layer (attendance repo queries, timetable endpoint).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

revision = "a3b4c5d6e7f8"
down_revision = "f2e3d4c5b6a7"
branch_labels = None
depends_on = None

ELECTIVE_SLOT_ENUM = ENUM("ELECTIVE_I", "ELECTIVE_II", name="electiveslot")
# Column-level ENUM instances reference the already-created type; they never
# issue CREATE TYPE themselves (the type is created explicitly in upgrade()).
ELECTIVE_SLOT_COL = ENUM("ELECTIVE_I", "ELECTIVE_II", name="electiveslot", create_type=False)


def upgrade() -> None:
    # 1. Create the ElectiveSlot enum type once
    ELECTIVE_SLOT_ENUM.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "timetable_entries",
        sa.Column("elective_slot", ELECTIVE_SLOT_COL, nullable=True),
    )

    # 2. Backfill elective_slot from the subject's tag (the existing marker).
    #    BCS-054 / tagged "Elective-I" → ELECTIVE_I
    #    BCS-058 / tagged "Elective-II" → ELECTIVE_II
    op.execute(
        """
        UPDATE timetable_entries te
        SET elective_slot = CASE
            WHEN s.tag = 'Elective-I' THEN 'ELECTIVE_I'::electiveslot
            WHEN s.tag = 'Elective-II' THEN 'ELECTIVE_II'::electiveslot
        END
        FROM subjects s
        WHERE te.subject_id = s.id
          AND s.tag IN ('Elective-I', 'Elective-II')
        """
    )

    # 3. Create student_elective_choices table
    op.create_table(
        "student_elective_choices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("elective_slot", ELECTIVE_SLOT_COL, nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_sec_user_id"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name="fk_sec_subject_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "elective_slot", name="uq_user_elective_slot"),
    )

    # 4. Insert the four missing Department Elective subjects (authoritative
    #    CSE-51 V Semester CTT). Resolve the active semester idempotently.
    #    These subjects are NOT in timetable.json (the shared timetable uses
    #    BCS-054 / BCS-058 as slot anchors). Per-student resolution maps the
    #    shared slot to the chosen subject.
    op.execute(
        """
        INSERT INTO subjects (id, code, name, tag, category, quiz_applicable, attendance_applicable, semester_id, created_at, updated_at)
        SELECT
            gen_random_uuid(), v.code, v.name, v.tag, 'THEORY', true, true, sem.id, now(), now()
        FROM (VALUES
            ('BCS-052', 'Data Analytics', 'Elective-I'),
            ('BCS-053', 'Computer Graphics', 'Elective-I'),
            ('BCS-055', 'Machine Learning Techniques', 'Elective-II'),
            ('BCS-056', 'Application of Soft Computing', 'Elective-II')
        ) AS v(code, name, tag)
        CROSS JOIN (
            SELECT sem.id
            FROM academic_sessions acs
            JOIN semesters sem ON sem.session_id = acs.id
            WHERE acs.is_active = true
            LIMIT 1
        ) sem
        WHERE NOT EXISTS (
            SELECT 1 FROM subjects s WHERE s.code = v.code
        )
        """
    )


def downgrade() -> None:
    # 1. Remove the inserted subjects
    op.execute(
        "DELETE FROM subjects WHERE code IN ('BCS-052', 'BCS-053', 'BCS-055', 'BCS-056')"
    )
    # 2. Drop student_elective_choices
    op.drop_table("student_elective_choices")
    # 3. Drop elective_slot column
    op.drop_column("timetable_entries", "elective_slot")
    # 4. Drop the enum type (only if no other column uses it)
    ELECTIVE_SLOT_ENUM.drop(op.get_bind(), checkfirst=True)