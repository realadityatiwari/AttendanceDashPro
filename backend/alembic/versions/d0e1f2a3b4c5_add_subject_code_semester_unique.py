"""Phase 23.2: UNIQUE(code, semester_id) on subjects

Revision ID: d0e1f2a3b4c5
Revises: c8d9e0f1a2b3
Create Date: 2026-08-27

Phase 23.2 (Curriculum Model) — schema hardening only.

The intended invariant: a subject code may appear in different semesters, but
the same code may not occur twice within the same semester.

Changes:
1. Add ``UNIQUE(code, semester_id)`` (constraint ``uq_subjects_code_semester``)
   on ``subjects``. This is the authoritative database-level enforcement point
   (seed/migration pipelines already prevent duplicates via application-level
   guards, but the database now owns the invariant).

The existing single-column index ``ix_subjects_code`` is PRESERVED — it has an
independent consumer (``SubjectRepository.get_by_code``, used by the quiz
eligibility endpoint, registration, and elective-resolver anchor lookups).
Removing it would be an unnecessary change; the composite unique constraint
serves ``(code, semester_id)`` access patterns, the single-column index serves
``code``-only lookups.

Guarded: the migration refuses to add the constraint if duplicate
(code, semester_id) pairs already exist (currently none — the seed and Phase
22.3 migration each insert per-code idempotently, and the Phase 21D.3/17
integrity audits found zero duplicate subjects).

No Subject data, enrollment, attendance, session, user, event, quiz, or
timetable data is modified. Downgrade drops the constraint (reversible to the
exact pre-23.2 schema state).
"""
from alembic import op, context
import sqlalchemy as sa

revision = "d0e1f2a3b4c5"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None

UQ_SUBJECTS_CODE_SEMESTER = "uq_subjects_code_semester"


def upgrade() -> None:
    # Preflight duplicate check (online mode only; offline --sql generation
    # emits the statements without executing them). The invariant must already
    # hold in the existing data before the constraint is added.
    if not context.is_offline_mode():
        connection = op.get_bind()
        duplicates = connection.execute(
            sa.text(
                "SELECT COUNT(*) FROM (SELECT code, semester_id FROM subjects "
                "GROUP BY code, semester_id HAVING COUNT(*) > 1) d"
            )
        ).scalar_one()
        if duplicates:
            raise RuntimeError(
                f"subjects contains {duplicates} duplicate (code, semester_id) "
                "pair(s); refusing to add the composite unique constraint. "
                "Existing data must be reconciled before this migration."
            )

    op.create_unique_constraint(
        UQ_SUBJECTS_CODE_SEMESTER,
        "subjects",
        ["code", "semester_id"],
    )


def downgrade() -> None:
    op.drop_constraint(UQ_SUBJECTS_CODE_SEMESTER, "subjects", type_="unique")
