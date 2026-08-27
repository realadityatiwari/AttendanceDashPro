"""Phase 23.3: enrollment_type discriminator on student_enrollments

Revision ID: e3f4a5b6c7d8
Revises: d0e1f2a3b4c5
Create Date: 2026-08-28

Phase 23.3 (Student Academic Assignment) — additive, backward-safe normalization
that makes the COMPULSORY vs ELECTIVE enrollment distinction explicit and
authoritative on the enrollment row. It does NOT redesign or replace the
authoritative elective-selection system (StudentElectiveChoice + ElectiveResolver,
Phase 22.3/22.4) and it does NOT alter attendance/eligibility/event/timetable/
quiz engines or any existing student data.

Conceptual separation this establishes (per the 23.3 requirement):

  A. Academic placement   = users.section_id (+ subsection_id) -> Section ->
                            Semester -> AcademicSession (branch = Section.program)
  B. Compulsory enrollment= student_enrollments rows with enrollment_type
                            = COMPULSORY (program requirements, e.g. common
                            theory + practical subjects)
  C. Elective selection   = StudentElectiveChoice (logical slot -> concrete
                            subject) — the authoritative resolver; the chosen
                            concrete subject is ALSO enrolled, and that
                            enrollment row is tagged enrollment_type = ELECTIVE.

A logical slot (DE-I / DE-II) is never itself an enrollment; only the concrete
subject the student selected is enrolled (ELECTIVE).

Changes (all additive / deterministic / non-destructive):

1. Create native PostgreSQL enum ``enrollmenttype`` (COMPULSORY, ELECTIVE).
2. Add ``student_enrollments.enrollment_type`` with server_default 'COMPULSORY'
   (backward compatible — every existing row is initialized to COMPULSORY).
3. Deterministic backfill: set 'ELECTIVE' on every existing enrollment that has
   a matching StudentElectiveChoice for an Elective-I / Elective-II subject.
   (In this repository a choice row only ever references an elective subject,
   so the existence of the matching choice is both necessary and sufficient.)
4. Enforce NOT NULL after backfill (every row now has an authoritative value).

No student, enrollment, subject, choice, attendance, session, event, quiz, or
timetable data is created, rewritten, or deleted. Downgrade reverses the column
and enum exactly.
"""
from alembic import op
import sqlalchemy as sa

revision = "e3f4a5b6c7d8"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None

ENUM_NAME = "enrollmenttype"


def upgrade() -> None:
    enrollment_type = sa.Enum(
        "COMPULSORY",
        "ELECTIVE",
        name=ENUM_NAME,
    )
    # Create the enum type BEFORE adding the column (follows the established
    # pattern from the userrole migration — explicit create() + add_column).
    enrollment_type.create(op.get_bind(), checkfirst=True)

    # Add column (server_default COMPULSORY so every existing row is valid
    # and backward compatible).
    op.add_column(
        "student_enrollments",
        sa.Column(
            "enrollment_type",
            enrollment_type,
            nullable=True,
            server_default="COMPULSORY",
        ),
    )

    # 3. Deterministic backfill: an enrollment that corresponds to a recorded
    # Department Elective choice is an ELECTIVE enrollment. The choice's subject
    # is restricted to the Elective-I / Elective-II tags so only genuine
    # elective enrollments are tagged (defensive; never assumes a stray choice).
    op.execute(
        sa.text(
            """
            UPDATE student_enrollments se
            SET enrollment_type = 'ELECTIVE'
            FROM student_elective_choices sec
            JOIN subjects subj ON subj.id = sec.subject_id
            WHERE sec.user_id = se.user_id
              AND sec.subject_id = se.subject_id
              AND subj.tag IN ('Elective-I', 'Elective-II')
            """
        )
    )

    # 4. Enforce NOT NULL — every row now has an authoritative value.
    op.alter_column(
        "student_enrollments",
        "enrollment_type",
        existing_type=enrollment_type,
        existing_server_default="COMPULSORY",
        nullable=False,
    )


def downgrade() -> None:
    enrollment_type = sa.Enum("COMPULSORY", "ELECTIVE", name=ENUM_NAME)
    op.alter_column(
        "student_enrollments",
        "enrollment_type",
        existing_type=enrollment_type,
        nullable=True,
    )
    op.drop_column("student_enrollments", "enrollment_type")
    # Drop the enum type only if no other table uses it (it is exclusive to
    # student_enrollments.enrollment_type).
    enrollment_type.drop(op.get_bind(), checkfirst=True)
