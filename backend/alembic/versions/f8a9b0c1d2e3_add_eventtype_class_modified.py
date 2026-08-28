"""Phase 23.7 corrective migration: add CLASS_MODIFIED to the eventtype enum

Revision ID: f8a9b0c1d2e3
Revises: f7a8b9c0d1e2
Create Date: 2026-08-29

Corrective reconciliation (post-Phase 23.9 live-verifier discovery):

Phase 23.7 introduced ``EventType.CLASS_MODIFIED`` in the application layer
(Python enum, event registry, event service, event-session synchronizer) but
the original Phase 23.7 migration (`f7a8b9c0d1e2`) only added ``MODIFIED`` to
the ``occurrenceoutcometype`` enum and did NOT add ``CLASS_MODIFIED`` to the
existing PostgreSQL ``eventtype`` enum. The live Phase 23.9 verifier exposed
this: inserting an ``academic_events`` row with ``event_type='CLASS_MODIFIED'``
failed with ``invalid input value for enum eventtype: "CLASS_MODIFIED"``.

This corrective migration is ADDITIVE:
- ``ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'CLASS_MODIFIED'``.

No table is created/altered, no data is touched, no other enum value is added,
and no existing migration is rewritten. ``OccurrenceOutcomeType`` is complete
(no correction needed).

PostgreSQL cannot directly remove an enum value, so the downgrade is a
documented no-op (the value remains in the type but is unreferenced after an
application downgrade) — the same repository convention used by the Phase
23.6/23.7 enum migrations.
"""
from alembic import op

revision = "f8a9b0c1d2e3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'CLASS_MODIFIED'")


def downgrade() -> None:
    # PostgreSQL does not support removing an enum value. The value remains in
    # the type but is never referenced after an application downgrade.
    # Documented limitation, not a silent data change.
    pass
