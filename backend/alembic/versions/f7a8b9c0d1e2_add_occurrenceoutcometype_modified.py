"""Phase 23.7: add MODIFIED to the occurrenceoutcometype enum

Revision ID: f7a8b9c0d1e2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-28

Phase 23.7 (Event-Scope Redesign + MODIFIED) — adds the ``MODIFIED`` value to
the existing ``occurrenceoutcometype`` PostgreSQL enum introduced by Phase 23.6.

``MODIFIED`` is an event-scope-level occurrence outcome produced by the new
subject-scoped ``CLASS_MODIFIED`` event: the scheduled occurrence happened but
was modified (time/room/delivery) for one concrete subject within a shared
elective slot. It is NOT extra, NOT cancelled, and it changes no attendance/
eligibility/calendar/quiz mathematics — the occurrence still counts as a
conducted class.

Change (additive, non-destructive):
- ``ALTER TYPE occurrenceoutcometype ADD VALUE 'MODIFIED'``.

No table rows are created, modified, or deleted; the value is simply appended
to the enum. PostgreSQL cannot REMOVE an enum value, so the downgrade is a
documented no-op (the unused value remains; nothing references it).
"""
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE occurrenceoutcometype ADD VALUE 'MODIFIED'")


def downgrade() -> None:
    # PostgreSQL does not support removing an enum value. The value remains in
    # the type but is never referenced (no rows use it after a downgrade of the
    # application layer). Documented limitation, not a silent data change.
    pass
