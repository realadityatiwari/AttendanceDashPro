"""OCC-1 — occurrence-specific cancellation reference on academic events.

A CLASS_CANCELLED / LAB_CANCELLED event now carries the exact scheduled
TimetableEntry it cancels (``academic_events.timetable_entry_id``), so the
EventSessionSynchronizer removes THAT occurrence instead of guessing a
matching (subject, class_type) entry at sync time. Admin creation is expected
to send the reference picked from the occurrence-options read model
(GET /admin/events/occurrence-options); the EventService validates it against
the real timetable (existence, active state, weekday of the selected date,
subject/class-type consistency, admin scope) before persisting.

Additive and nullable: legacy rows keep NULL (never backfilled, never
guessed — the same philosophy as class_sessions.source_event_id). Legacy
cancellation rows remain readable and DEACTIVATABLE; editing one now requires
re-selecting a real occurrence (the registry requires the reference for
cancellation types), which is the new architecture's strictness — a
cancellation must identify a real scheduled occurrence.

No data is modified. Reversible.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "c7d8e9f0a1b2"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "academic_events",
        sa.Column("timetable_entry_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_academic_events_timetable_entry",
        "academic_events",
        "timetable_entries",
        ["timetable_entry_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_academic_events_timetable_entry", "academic_events", type_="foreignkey"
    )
    op.drop_column("academic_events", "timetable_entry_id")
