"""EVT-004 — DB-authoritative natural-key uniqueness for events and sessions.

The audit (docs/EVENTS_BACKEND_DEEP_AUDIT_REPORT.md, EVT-004) established
that duplicate prevention was application-only (check-then-insert), so two
concurrent transactions could materialize the same canonical reality twice.

DERIVED IDENTITIES (from the code and the pinned contracts — never assumed):

* Flexible extra-family events (EXTRA_LECTURE/TUTORIAL/PRACTICAL,
  SURPRISE_QUIZ, CLASS_CANCELLED, LAB_CANCELLED, MID_SEM_PRACTICAL,
  CLASS_MODIFIED) deliberately support MULTIPLE active same-key rows: the
  reconciler's count-based extras semantics give each event its own
  provenance-linked session
  (tests/test_extra_lifecycle_foundation.py::
   test_two_active_same_key_events_each_get_own_linked_session, docstring:
   "The DB allows two ACTIVE same-key extra events"). A uniqueness
  constraint over their identity would contradict that pinned contract, so
  they are intentionally NOT constrained. Their worst-case API race outcome
  (two extra occurrences instead of one) is a consistent state the
  reconciler handles by design.

* QUIZ_DAY is deduplicated EVERYWHERE by (subject_id, elective_slot,
  start_date): the quiz-manager find-first path, the synchronizer's
  set-based quiz-day bucket, and eligibility's (subject, date) dedup.
  Multiplicity is never legitimate (a second quiz-day occurrence for the
  same subject/date cannot exist — Option A coexistence is with the
  REGULAR class, not with another quiz-day occurrence). Active QUIZ_DAY
  rows are therefore unique per that identity.

* Global events (subject_id IS NULL — closures, breaks, working-day
  overrides, working Saturdays) are broadcast to every user and dominate
  day resolution. Two same-type identical-range global rows are pure
  duplicates (the engine honors only the dominant one); multiplicity is
  never legitimate. They are unique per (event_type, start_date,
  end_date). Global rows always carry NULL class_type; elective_slot is
  not applicable (slot events always carry the anchor subject).

* class_sessions canonical occurrences:
  - one scheduled occurrence per (timetable_entry_id, date) — the
    synchronizer creates exactly `desired_scheduled - existing`;
  - one event-created extra per (source_event_id, date) — the provenance
    identity the synchronizer's identity pass reconciles (attended extras
    are preserved and RESTORED, never duplicated); legacy NULL-provenance
    extras are excluded by the predicate and remain unconstrained on
    purpose (their true event is unknowable and is never guessed);
  - one quiz-day attendance-bearing occurrence per (subject_id, date)
    within the quiz-day shape (timetable_entry_id IS NULL AND
    is_extra = false AND class_type = 'LECTURE') — shared by the
    synchronizer bucket and materialize_quiz_day_sessions.py. The
    predicate keeps extras and timetable-linked sessions outside the key,
    so Option A coexistence (regular + quiz-day occurrence on one date)
    is never blocked.

All predicates use partial indexes so NULL identity columns never enter
the keys (no NULL==NULL ambiguity to engineer around), and deactivation
naturally frees an identity (soft-delete semantics; reactivation races are
rejected by the index and translated to 409 by the application).

Pre-migration duplicate audit (2026-10-02, dev DB): 0 groups under every
key. No data is modified: upgrade re-runs the audit and refuses (with the
offending groups) if violations appeared after authoring. Reversible.
"""

import sqlalchemy as sa
from alembic import op

revision = "b9c0d1e2f3a4"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None

# (label, duplicate-audit SQL) — the same queries the pre-migration audit ran.
_DUPLICATE_CHECKS = (
    ("academic_events active QUIZ_DAY identity",
     "SELECT subject_id, elective_slot, start_date, count(*) "
     "FROM academic_events WHERE active AND event_type = 'QUIZ_DAY' "
     "GROUP BY 1, 2, 3 HAVING count(*) > 1"),
    ("academic_events active global range identity",
     "SELECT event_type, start_date, end_date, count(*) "
     "FROM academic_events WHERE active AND subject_id IS NULL "
     "GROUP BY 1, 2, 3 HAVING count(*) > 1"),
    ("class_sessions (timetable_entry_id, date)",
     "SELECT timetable_entry_id, date, count(*) FROM class_sessions "
     "WHERE timetable_entry_id IS NOT NULL GROUP BY 1, 2 HAVING count(*) > 1"),
    ("class_sessions (source_event_id, date)",
     "SELECT source_event_id, date, count(*) FROM class_sessions "
     "WHERE source_event_id IS NOT NULL GROUP BY 1, 2 HAVING count(*) > 1"),
    ("class_sessions quiz-day shape (subject, date)",
     "SELECT subject_id, date, count(*) FROM class_sessions "
     "WHERE timetable_entry_id IS NULL AND is_extra = false "
     "AND class_type = 'LECTURE' GROUP BY 1, 2 HAVING count(*) > 1"),
)

_UQ_EVENTS_QUIZ_DAY = "uq_academic_events_quiz_day_identity"
_UQ_EVENTS_GLOBAL = "uq_academic_events_global_range"
_UQ_SESSION_ENTRY = "uq_class_sessions_entry_date"
_UQ_SESSION_SOURCE = "uq_class_sessions_source_event_date"
_UQ_SESSION_QUIZ_DAY = "uq_class_sessions_quiz_day_subject_date"


def _assert_no_duplicates(conn) -> None:
    """Refuse to apply the constraints over violating data (EVT-004 safety
    requirement: never silently remediate; surface the offending groups)."""
    for label, sql in _DUPLICATE_CHECKS:
        rows = conn.execute(sa.text(sql)).fetchall()
        if rows:
            raise RuntimeError(
                "EVT-004 migration refused: duplicate group(s) exist for "
                f"{label}: {rows!r}. Resolve the duplicates explicitly "
                "(they may be legitimate history or true races) before "
                "applying the natural-key uniqueness."
            )


def upgrade() -> None:
    conn = op.get_bind()
    _assert_no_duplicates(conn)

    # 1. QUIZ_DAY identity (active): one quiz per (subject, slot, start date).
    #    NULLS NOT DISTINCT makes a NULL elective_slot (common-subject quiz)
    #    compare equal to itself (PostgreSQL 15+; dev runs PG 16).
    op.create_index(
        _UQ_EVENTS_QUIZ_DAY,
        "academic_events",
        ["subject_id", "elective_slot", "start_date"],
        unique=True,
        postgresql_where=sa.text(
            "active AND event_type = 'QUIZ_DAY'"
        ),
        postgresql_nulls_not_distinct=True,
    )

    # 2. Global events (active): one row per (type, date range). NULLS NOT
    #    DISTINCT is harmless here (all key columns are non-nullable).
    op.create_index(
        _UQ_EVENTS_GLOBAL,
        "academic_events",
        ["event_type", "start_date", "end_date"],
        unique=True,
        postgresql_where=sa.text("active AND subject_id IS NULL"),
        postgresql_nulls_not_distinct=True,
    )

    # 3. Timetable-linked canonical occurrences.
    op.create_index(
        _UQ_SESSION_ENTRY,
        "class_sessions",
        ["timetable_entry_id", "date"],
        unique=True,
        postgresql_where=sa.text("timetable_entry_id IS NOT NULL"),
    )

    # 4. Event-created extra occurrences (provenance identity).
    op.create_index(
        _UQ_SESSION_SOURCE,
        "class_sessions",
        ["source_event_id", "date"],
        unique=True,
        postgresql_where=sa.text("source_event_id IS NOT NULL"),
    )

    # 5. Quiz-day attendance-bearing occurrences.
    op.create_index(
        _UQ_SESSION_QUIZ_DAY,
        "class_sessions",
        ["subject_id", "date"],
        unique=True,
        postgresql_where=sa.text(
            "timetable_entry_id IS NULL AND is_extra = false "
            "AND class_type = 'LECTURE'"
        ),
    )


def downgrade() -> None:
    op.drop_index(_UQ_SESSION_QUIZ_DAY, table_name="class_sessions")
    op.drop_index(_UQ_SESSION_SOURCE, table_name="class_sessions")
    op.drop_index(_UQ_SESSION_ENTRY, table_name="class_sessions")
    op.drop_index(_UQ_EVENTS_GLOBAL, table_name="academic_events")
    op.drop_index(_UQ_EVENTS_QUIZ_DAY, table_name="academic_events")
