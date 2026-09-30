"""READ-ONLY reconciliation probe for the remediation-readiness phase.

Re-tests specific evidence claims from docs/SYSTEM_FUNCTIONAL_BACKEND_AUDIT_REPORT.md:
  1. M-6 claim: user 7777777777777 first_quiz_date is None (suspected WRONG).
  2. H-4 claim: 452 ACADEMIC_EVENT notifications reference missing events.
  3. H-5 claim: quiz dates are currently in chronological order per subject/slot.
  4. H-1 context: seeded policy thresholds.
  5. H-2 context: users.is_active current state.

Every statement is a SELECT. No INSERT/UPDATE/DELETE/DDL, no commit, no seed.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text

from app.db.session import AsyncSessionLocal

Q = {
    "users_state": """
        SELECT u.roll_number, u.role, u.is_active, u.name,
               (SELECT count(*) FROM student_elective_choices c WHERE c.user_id = u.id) choices,
               (SELECT count(*) FROM student_enrollments e WHERE e.user_id = u.id) enrollments
        FROM users u ORDER BY u.roll_number
    """,
    "choices_by_user": """
        SELECT u.roll_number, c.elective_slot, s.code
        FROM student_elective_choices c
        JOIN users u ON u.id = c.user_id
        JOIN subjects s ON s.id = c.subject_id
        ORDER BY u.roll_number, c.elective_slot
    """,
    "first_quiz_date_m6_probe": """
        -- Exact replication of user_repo.get_academic_context's first_quiz_date
        -- query (join via enrollment.subject_id only).
        SELECT u.roll_number, min(ev.start_date) AS first_quiz_date
        FROM users u
        JOIN student_enrollments e ON e.user_id = u.id
        JOIN academic_events ev ON ev.subject_id = e.subject_id
             AND ev.event_type = 'QUIZ_DAY' AND ev.active = true
        WHERE u.role = 'STUDENT'
        GROUP BY u.roll_number
        ORDER BY u.roll_number
    """,
    "first_quiz_date_slot_resolved": """
        -- What first_quiz_date WOULD be if elective-slot quiz events were
        -- resolved (slot events OR subject events for the enrolled subject).
        SELECT u.roll_number, min(ev.start_date) AS first_quiz_date_slot_resolved
        FROM users u
        JOIN student_enrollments e ON e.user_id = u.id
        JOIN student_elective_choices c ON c.user_id = u.id
        JOIN academic_events ev
             ON (ev.subject_id = e.subject_id
                 OR (ev.elective_slot = c.elective_slot))
             AND ev.event_type = 'QUIZ_DAY' AND ev.active = true
        WHERE u.role = 'STUDENT'
        GROUP BY u.roll_number
        ORDER BY u.roll_number
    """,
    "quiz_events_chronology": """
        -- Effective quiz dates as the eligibility engine ranks them, per
        -- subject and per slot, with the positional cycle number.
        SELECT COALESCE(s.code, ev.elective_slot::text) AS scope,
               ev.elective_slot IS NOT NULL AS is_slot_event,
               ev.start_date,
               row_number() OVER (
                   PARTITION BY COALESCE(ev.subject_id::text, ev.elective_slot::text)
                   ORDER BY ev.start_date, ev.id
               ) AS positional_cycle
        FROM academic_events ev
        LEFT JOIN subjects s ON s.id = ev.subject_id
        WHERE ev.event_type = 'QUIZ_DAY' AND ev.active = true
        ORDER BY scope, ev.start_date
    """,
    "slot_quiz_date_map": """
        SELECT ev.elective_slot::text AS slot_label, ev.start_date, s.code
        FROM academic_events ev
        LEFT JOIN subjects s ON s.id = ev.subject_id
        WHERE ev.event_type = 'QUIZ_DAY' AND ev.active = true
              AND ev.elective_slot IS NOT NULL
        ORDER BY ev.elective_slot, ev.start_date
    """,
    "policies": "SELECT qc.cycle_number, ep.lecture_threshold, ep.combined_threshold FROM eligibility_policies ep JOIN quiz_cycles qc ON qc.id = ep.quiz_cycle_id ORDER BY qc.cycle_number",
    "notifications_integrity": """
        SELECT n.kind,
               count(*) AS total,
               count(*) FILTER (WHERE n.event_id IS NOT NULL
                                 AND NOT EXISTS (SELECT 1 FROM academic_events ev WHERE ev.id = n.event_id)) AS orphan_event_refs,
               count(*) FILTER (WHERE n.is_read = false AND n.is_dismissed = false) AS unread
        FROM notifications n
        GROUP BY n.kind ORDER BY n.kind
    """,
    "notifications_by_user": """
        SELECT u.roll_number,
               count(*) FILTER (WHERE n.kind = 'ACADEMIC_EVENT') AS academic_event_rows,
               count(*) FILTER (WHERE n.kind = 'ACADEMIC_EVENT'
                                 AND NOT EXISTS (SELECT 1 FROM academic_events ev WHERE ev.id = n.event_id)) AS orphaned,
               count(*) FILTER (WHERE n.is_read = false AND n.is_dismissed = false) AS unread
        FROM notifications n JOIN users u ON u.id = n.user_id
        GROUP BY u.roll_number ORDER BY u.roll_number
    """,
}


def slot_label(e):
    if e is None:
        return None
    return str(e).split(".")[-1]


async def main():
    async with AsyncSessionLocal() as session:
        for name, sql in Q.items():
            print(f"=== {name} ===")
            result = await session.execute(text(sql))
            for row in result.mappings():
                print({k: str(v) for k, v in dict(row).items()})
            print()


if __name__ == "__main__":
    asyncio.run(main())
