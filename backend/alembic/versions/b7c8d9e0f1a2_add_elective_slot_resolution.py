"""Phase 22.4: elective_slot on quiz_schedules, academic_events, class_sessions + backfill

Revision ID: b7c8d9e0f1a2
Revises: a3b4c5d6e7f8
Create Date: 2026-08-26

Phase 22.4 (Departmental Elective Resolution) — adds the elective_slot marker
to the remaining shared schedule tables so per-student elective resolution
works for quiz schedules, academic events, and event-created class sessions.

Changes:
1. Add ``quiz_schedules.elective_slot`` (nullable ENUM) — marks which quiz
   schedule entries belong to the Departmental Elective-I / Elective-II logical
   slot. Backfilled from the subject's tag (BCS-054 → ELECTIVE_I, BCS-058 →
   ELECTIVE_II).
2. Add ``academic_events.elective_slot`` (nullable ENUM) — marks which events
   are scoped to a logical elective slot (shared admin events, not per-student).
   Backfilled from the subject's tag.
3. Add ``class_sessions.elective_slot`` (nullable ENUM) — marks class sessions
   materialized for an elective slot (ensures event-created extras/quiz-days
   with no timetable link still resolve per student). Backfilled from the
   subject's tag.

No timetable entry, class session date, quiz date, event date, or attendance
record is changed. Per-student resolution is handled at the application read
layer (the attendance repo predicates, quiz date resolution, event resolution).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

revision = "b7c8d9e0f1a2"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None

# Reuse the existing electiveslot enum type created by the Phase 22.3 migration.
ELECTIVE_SLOT_COL = ENUM("ELECTIVE_I", "ELECTIVE_II", name="electiveslot", create_type=False)


def upgrade() -> None:
    # 1. quiz_schedules.elective_slot
    op.add_column(
        "quiz_schedules",
        sa.Column("elective_slot", ELECTIVE_SLOT_COL, nullable=True),
    )
    op.execute(
        """
        UPDATE quiz_schedules qs
        SET elective_slot = CASE
            WHEN s.tag = 'Elective-I' THEN 'ELECTIVE_I'::electiveslot
            WHEN s.tag = 'Elective-II' THEN 'ELECTIVE_II'::electiveslot
        END
        FROM subjects s
        WHERE qs.subject_id = s.id
          AND s.tag IN ('Elective-I', 'Elective-II')
        """
    )

    # 2. academic_events.elective_slot
    op.add_column(
        "academic_events",
        sa.Column("elective_slot", ELECTIVE_SLOT_COL, nullable=True),
    )
    op.execute(
        """
        UPDATE academic_events ae
        SET elective_slot = CASE
            WHEN s.tag = 'Elective-I' THEN 'ELECTIVE_I'::electiveslot
            WHEN s.tag = 'Elective-II' THEN 'ELECTIVE_II'::electiveslot
        END
        FROM subjects s
        WHERE ae.subject_id = s.id
          AND s.tag IN ('Elective-I', 'Elective-II')
        """
    )

    # 3. class_sessions.elective_slot
    op.add_column(
        "class_sessions",
        sa.Column("elective_slot", ELECTIVE_SLOT_COL, nullable=True),
    )
    op.execute(
        """
        UPDATE class_sessions cs
        SET elective_slot = CASE
            WHEN s.tag = 'Elective-I' THEN 'ELECTIVE_I'::electiveslot
            WHEN s.tag = 'Elective-II' THEN 'ELECTIVE_II'::electiveslot
        END
        FROM subjects s
        WHERE cs.subject_id = s.id
          AND s.tag IN ('Elective-I', 'Elective-II')
        """
    )


def downgrade() -> None:
    op.drop_column("class_sessions", "elective_slot")
    op.drop_column("academic_events", "elective_slot")
    op.drop_column("quiz_schedules", "elective_slot")