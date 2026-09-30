"""READ-ONLY forensic DB evidence for the system audit (discovery only).

Every statement below is a SELECT (or PRAGMA-equivalent catalog read).
No INSERT/UPDATE/DELETE/DDL, no commit, no seed, no repair.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text

from app.db.session import AsyncSessionLocal

Q = {
    "table_counts": """
        SELECT 'users' t, count(*) FROM users
        UNION ALL SELECT 'sections', count(*) FROM sections
        UNION ALL SELECT 'subsections', count(*) FROM subsections
        UNION ALL SELECT 'semesters', count(*) FROM semesters
        UNION ALL SELECT 'academic_sessions', count(*) FROM academic_sessions
        UNION ALL SELECT 'subjects', count(*) FROM subjects
        UNION ALL SELECT 'timetable_entries', count(*) FROM timetable_entries
        UNION ALL SELECT 'class_sessions', count(*) FROM class_sessions
        UNION ALL SELECT 'attendance_records', count(*) FROM attendance_records
        UNION ALL SELECT 'student_enrollments', count(*) FROM student_enrollments
        UNION ALL SELECT 'student_elective_choices', count(*) FROM student_elective_choices
        UNION ALL SELECT 'academic_events', count(*) FROM academic_events
        UNION ALL SELECT 'quiz_cycles', count(*) FROM quiz_cycles
        UNION ALL SELECT 'eligibility_policies', count(*) FROM eligibility_policies
        UNION ALL SELECT 'quiz_schedules', count(*) FROM quiz_schedules
        UNION ALL SELECT 'occurrence_outcomes', count(*) FROM occurrence_outcomes
        UNION ALL SELECT 'notifications', count(*) FROM notifications
        UNION ALL SELECT 'refresh_tokens', count(*) FROM refresh_tokens
        UNION ALL SELECT 'push_subscriptions', count(*) FROM push_subscriptions
        UNION ALL SELECT 'feedback', count(*) FROM feedback
        UNION ALL SELECT 'userpreferences', count(*) FROM userpreferences
        UNION ALL SELECT 'admin_scopes', count(*) FROM admin_scopes
        UNION ALL SELECT 'laboratory_experiments', count(*) FROM laboratory_experiments
        UNION ALL SELECT 'laboratory_records', count(*) FROM laboratory_records
        ORDER BY 1
    """,
    "class_session_flags": """
        SELECT is_extra, is_cancelled, is_deactivated, count(*)
        FROM class_sessions GROUP BY 1,2,3 ORDER BY 1,2,3
    """,
    "class_session_span": """
        SELECT min(date), max(date),
               count(*) FILTER (WHERE timetable_entry_id IS NULL) AS unlinked,
               count(*) FILTER (WHERE source_event_id IS NOT NULL) AS with_provenance
        FROM class_sessions
    """,
    "enrollment_types": """
        SELECT enrollment_type, count(*) FROM student_enrollments GROUP BY 1
    """,
    "enrollments_per_user": """
        SELECT u.roll_number, u.role, count(se.id) n
        FROM users u LEFT JOIN student_enrollments se ON se.user_id = u.id
        GROUP BY 1,2 ORDER BY 1
    """,
    "elective_choices": """
        SELECT u.roll_number, c.elective_slot, s.code, s.elective_slot AS subject_slot
        FROM student_elective_choices c
        JOIN users u ON u.id = c.user_id
        JOIN subjects s ON s.id = c.subject_id
        ORDER BY 1, 2
    """,
    "elective_choice_slot_mismatch": """
        SELECT c.id, u.roll_number, s.code, c.elective_slot AS chosen_slot, s.elective_slot AS subject_slot
        FROM student_elective_choices c
        JOIN users u ON u.id = c.user_id
        JOIN subjects s ON s.id = c.subject_id
        WHERE s.elective_slot IS DISTINCT FROM c.elective_slot
    """,
    "elective_enrollments_without_matching_choice": """
        SELECT u.roll_number, s.code, se.enrollment_type
        FROM student_enrollments se
        JOIN users u ON u.id = se.user_id
        JOIN subjects s ON s.id = se.subject_id
        WHERE s.elective_slot IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM student_elective_choices c
            WHERE c.user_id = se.user_id AND c.subject_id = se.subject_id)
    """,
    "elective_subject_enrollments_that_are_compulsory": """
        SELECT u.roll_number, s.code
        FROM student_enrollments se
        JOIN users u ON u.id = se.user_id
        JOIN subjects s ON s.id = se.subject_id
        WHERE s.elective_slot IS NOT NULL AND se.enrollment_type = 'COMPULSORY'
    """,
    "events_by_type": """
        SELECT event_type, active, count(*) FROM academic_events
        GROUP BY 1,2 ORDER BY 1,2
    """,
    "quiz_day_events_vs_schedules": """
        SELECT s.code, qs.quiz_cycle_id::text, qs.date AS schedule_date, qs.schedule_status,
               qs.elective_slot AS schedule_slot,
               (SELECT count(*) FROM academic_events e
                 WHERE e.event_type='QUIZ_DAY' AND e.active
                   AND e.subject_id = qs.subject_id AND e.start_date = qs.date) AS active_event_cnt
        FROM quiz_schedules qs JOIN subjects s ON s.id = qs.subject_id
        ORDER BY s.code, qs.date NULLS LAST
    """,
    "quiz_cycles_policies": """
        SELECT qc.cycle_number, qc.label, ep.lecture_threshold, ep.combined_threshold
        FROM quiz_cycles qc LEFT JOIN eligibility_policies ep ON ep.quiz_cycle_id = qc.id
        ORDER BY qc.cycle_number
    """,
    "duplicate_timetable_entries": """
        SELECT section_id, day_of_week, start_time, end_time, class_type, count(*) n,
               string_agg(subject_id::text, ',') subjects
        FROM timetable_entries
        GROUP BY 1,2,3,4,5 HAVING count(*) > 1
    """,
    "duplicate_class_sessions_same_entry": """
        SELECT timetable_entry_id, date, count(*) n
        FROM class_sessions WHERE timetable_entry_id IS NOT NULL
        GROUP BY 1,2 HAVING count(*) > 1
    """,
    "attendance_on_cancelled_or_deactivated": """
        SELECT ar.id::text, ar.user_id::text, cs.is_cancelled, cs.is_deactivated, cs.date
        FROM attendance_records ar JOIN class_sessions cs ON cs.id = ar.class_session_id
        WHERE cs.is_cancelled OR cs.is_deactivated
        ORDER BY cs.date
    """,
    "attendance_on_future_sessions": """
        SELECT count(*) FROM attendance_records ar
        JOIN class_sessions cs ON cs.id = ar.class_session_id
        WHERE cs.date > (now() AT TIME ZONE 'Asia/Kolkata')::date
    """,
    "occurrence_outcomes_detail": """
        SELECT o.outcome_type, s.code, cs.date, cs.is_extra, cs.is_cancelled, cs.timetable_entry_id IS NULL AS unlinked
        FROM occurrence_outcomes o
        JOIN subjects s ON s.id = o.subject_id
        JOIN class_sessions cs ON cs.id = o.class_session_id
        ORDER BY cs.date
    """,
    "outcome_on_non_elective_subject": """
        SELECT o.id::text FROM occurrence_outcomes o
        JOIN subjects s ON s.id = o.subject_id
        WHERE s.elective_slot IS NULL
    """,
    "unindexed_foreign_keys": """
        SELECT c.conrelid::regclass AS table_name, a.attname AS column_name
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE c.contype = 'f'
          AND NOT EXISTS (
            SELECT 1 FROM pg_index i
            WHERE i.indrelid = c.conrelid AND a.attnum = ANY(i.indkey::int2[]) AND i.indkey[0] = a.attnum)
        ORDER BY 1, 2
    """,
    "duplicate_attendance_rows": """
        SELECT user_id, class_session_id, count(*) n FROM attendance_records
        GROUP BY 1,2 HAVING count(*) > 1
    """,
    "duplicate_notifications": """
        SELECT user_id, kind, occurrence_key, count(*) n FROM notifications
        GROUP BY 1,2,3 HAVING count(*) > 1
    """,
    "sections_semesters": """
        SELECT s.id::text, s.name, s.semester_id::text, s.program,
               (SELECT count(*) FROM users u WHERE u.section_id = s.id) users
        FROM sections s
    """,
    "students_without_section": """
        SELECT roll_number, role FROM users WHERE section_id IS NULL
    """,
    "enrollments_outside_active_session": """
        SELECT u.roll_number, s.code, sess.name AS session_name, sess.is_active
        FROM student_enrollments se
        JOIN users u ON u.id = se.user_id
        JOIN subjects s ON s.id = se.subject_id
        JOIN semesters sem ON sem.id = s.semester_id
        JOIN academic_sessions sess ON sess.id = sem.session_id
        WHERE NOT sess.is_active
    """,
    "subjects_slot_summary": """
        SELECT code, category, quiz_applicable, attendance_applicable, elective_slot, tag
        FROM subjects ORDER BY code
    """,
    "timetable_slot_vs_subject_slot": """
        SELECT te.id::text, s.code AS entry_subject, te.elective_slot AS entry_slot, s.elective_slot AS subject_slot
        FROM timetable_entries te JOIN subjects s ON s.id = te.subject_id
        WHERE (te.elective_slot IS NULL) <> (s.elective_slot IS NULL)
           OR (te.elective_slot IS NOT NULL AND te.elective_slot IS DISTINCT FROM s.elective_slot)
    """,
    "class_sessions_slot_vs_subject_slot": """
        SELECT cs.id::text, s.code, cs.elective_slot AS session_slot, s.elective_slot AS subject_slot
        FROM class_sessions cs JOIN subjects s ON s.id = cs.subject_id
        WHERE cs.elective_slot IS NOT NULL AND cs.elective_slot IS DISTINCT FROM s.elective_slot
    """,
    "event_dates_outside_session_span": """
        SELECT e.id::text, e.event_type, e.start_date, e.end_date
        FROM academic_events e
        WHERE e.active AND (
          e.start_date < (SELECT min(date) FROM class_sessions WHERE timetable_entry_id IS NOT NULL)
          OR e.end_date > (SELECT max(date) FROM class_sessions WHERE timetable_entry_id IS NOT NULL))
    """,
    "refresh_token_state": """
        SELECT count(*) FILTER (WHERE NOT is_used AND NOT is_revoked) active,
               count(*) FILTER (WHERE is_used) used,
               count(*) FILTER (WHERE is_revoked) revoked
        FROM refresh_tokens
    """,
    "notifications_by_kind": """
        SELECT kind, count(*) FROM notifications GROUP BY 1 ORDER BY 1
    """,
    "orphan_quiz_events_no_session": """
        SELECT e.id::text, s.code, e.start_date
        FROM academic_events e
        JOIN subjects s ON s.id = e.subject_id
        WHERE e.event_type = 'QUIZ_DAY' AND e.active
          AND NOT EXISTS (
            SELECT 1 FROM class_sessions cs
            WHERE cs.subject_id = e.subject_id AND cs.date = e.start_date)
    """,
    "constraints_of_interest": """
        SELECT conname, conrelid::regclass, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conname LIKE 'uq_%' OR conname LIKE 'ck_%'
        ORDER BY conrelid::regclass::text, conname
    """,
    "admin_scopes_rows": """
        SELECT u.roll_number, a.role, a.active,
               a.section_id IS NOT NULL AS has_section,
               a.subsection_id IS NOT NULL AS has_subsection,
               a.subject_id IS NOT NULL AS has_subject
        FROM admin_scopes a JOIN users u ON u.id = a.user_id
    """,
    "user_roles": """
        SELECT role, count(*) FROM users GROUP BY 1
    """,
    "sessions_today_and_upcoming": """
        SELECT count(*) FILTER (WHERE date = (now() AT TIME ZONE 'Asia/Kolkata')::date) today,
               count(*) FILTER (WHERE date > (now() AT TIME ZONE 'Asia/Kolkata')::date) future
        FROM class_sessions
    """,
}


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for name, sql in Q.items():
            print(f"\n=== {name} ===")
            try:
                result = await db.execute(text(sql))
                rows = result.fetchall()
                if not rows:
                    print("  (no rows)")
                for r in rows:
                    print("  " + " | ".join("" if v is None else str(v) for v in r))
            except Exception as exc:  # pragma: no cover - evidence tooling
                print(f"  ERROR: {exc}")
    print("\nDONE (read-only).")


if __name__ == "__main__":
    asyncio.run(main())
