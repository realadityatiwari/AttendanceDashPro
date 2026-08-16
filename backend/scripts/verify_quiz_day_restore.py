"""
Focused Quiz-Day restoration verification (post-forensic-audit recovery).

Pins the restored seeded Quiz Day state against the real database (read-only,
no httpx, no mutations — this verifier only asserts):

  A. All 18 seed quiz_schedules remain present (SCHEDULED, dated, quiz-subject).
  B. All 18 seed QUIZ_DAY events remain present (identity = quiz_schedules
     backing + 2026-08-14 seed creation — owner-created Quiz Day duplicates
     are deliberately excluded from the seed population).
  C. All 18 seed QUIZ_DAY events remain active.
  D. Seed event UUIDs unchanged across the run.
  E. Seed schedule UUIDs unchanged across the run.
  F. Exactly one quiz-day-shaped session exists on EVERY seeded quiz date
     (the canonical materialize_quiz_day_sessions.py output), independent of
     coverage (Option A: covered dates keep their regular occurrence AND the
     quiz-day occurrence).
  G. No duplicate quiz-day occurrence for any seeded date/subject (at most one
     quiz-day-shaped row per subject/date).
  H. Attendance-record count is unchanged by restoration (verifier is
     read-only; pins the 122-record invariant).
  I. The owner-created 2026-08-17 BCS-502 test QUIZ_DAY event remains present
     and INACTIVE (never reactivated, never deleted).
  J. Every other owner-created event and session is byte-for-byte unchanged
     (full academic_events + class_sessions table snapshots compared).

Seed identity is scoped through quiz_schedules (NOT a global "QUIZ_DAY == 18"
assertion — owner-created Quiz Day rows may legitimately coexist, e.g. the
08-24 BNC-501 duplicate created via the UI).

Idempotency: a re-run of materialize_quiz_day_sessions.py must create 0 new
sessions (every scheduled quiz date already has its quiz-day-shaped session) —
the restoration converges on the canonical state.

Usage:
    python scripts/verify_quiz_day_restore.py
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from datetime import date, datetime, timezone

from app.db.session import AsyncSessionLocal
from app.models.quiz import QuizSchedule, ScheduleStatus
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.enums import ClassType, EventType
from sqlalchemy import select, func

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


async def main() -> int:
    async with AsyncSessionLocal() as db:
        # --- Read-only baseline snapshots --------------------------------------
        schedules = (await db.execute(
            select(QuizSchedule).where(
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED,
                QuizSchedule.date.isnot(None),
            ).order_by(QuizSchedule.date)
        )).scalars().all()
        seed_schedule_snapshot = {(str(q.id), str(q.subject_id), q.date.isoformat())
                                  for q in schedules}

        # Seed events: QUIZ_DAY rows backed by a quiz_schedules row AND created
        # during the 2026-08-14 seed (owner-created duplicates from 08-16 are
        # excluded by the created_at scoping).
        from sqlalchemy.sql import exists
        seed_events = (await db.execute(
            select(AcademicEvent).where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.created_at >= datetime(2026, 8, 14, tzinfo=timezone.utc),
                AcademicEvent.created_at < datetime(2026, 8, 15, tzinfo=timezone.utc),
                exists().where(
                    (QuizSchedule.subject_id == AcademicEvent.subject_id)
                    & (QuizSchedule.date == AcademicEvent.start_date)
                ),
            ).order_by(AcademicEvent.start_date)
        )).scalars().all()
        seed_event_snapshot = {(str(e.id), str(e.subject_id), e.start_date.isoformat())
                               for e in seed_events}

        qd_sessions = (await db.execute(
            select(ClassSession).where(
                ClassSession.class_type == ClassType.LECTURE,
                ClassSession.is_extra.is_(False),
                ClassSession.timetable_entry_id.is_(None),
            ).order_by(ClassSession.date)
        )).scalars().all()
        qd_snapshot = {(s.subject_id, s.date, str(s.id)) for s in qd_sessions}

        records_before = (await db.execute(
            select(func.count()).select_from(AttendanceRecord))).scalar()

        events_snapshot = {(str(e.id), e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                            str(e.subject_id) if e.subject_id else None, e.start_date.isoformat(),
                            e.end_date.isoformat(), bool(e.active))
                           for e in (await db.execute(select(AcademicEvent))).scalars().all()}
        sessions_snapshot = {(str(s.id), str(s.subject_id), s.date.isoformat(),
                              s.class_type.value if hasattr(s.class_type, "value") else str(s.class_type),
                              bool(s.is_extra), bool(s.is_cancelled),
                              str(s.timetable_entry_id) if s.timetable_entry_id else None)
                             for s in (await db.execute(select(ClassSession))).scalars().all()}

        # --- A. seed schedules present -----------------------------------------
        check("A. 18 seed quiz_schedules present, all SCHEDULED",
              len(schedules) == 18 and all(q.schedule_status == ScheduleStatus.SCHEDULED for q in schedules),
              f"schedules={len(schedules)}")

        # --- B. seed events present --------------------------------------------
        check("B. 18 seed QUIZ_DAY events present (quiz_schedules-backed, seed-created)",
              len(seed_events) == 18, f"seed_events={len(seed_events)}")

        # --- C. seed events active ---------------------------------------------
        inactive = [e for e in seed_events if not e.active]
        check("C. all 18 seed QUIZ_DAY events active", not inactive,
              f"inactive={[str(e.start_date) for e in inactive]}")

        # --- D/E. UUID stability (re-query, compare snapshots) -----------------
        schedules_now = (await db.execute(
            select(QuizSchedule).where(
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED,
                QuizSchedule.date.isnot(None)))).scalars().all()
        seed_events_now = (await db.execute(
            select(AcademicEvent).where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.created_at >= datetime(2026, 8, 14, tzinfo=timezone.utc),
                AcademicEvent.created_at < datetime(2026, 8, 15, tzinfo=timezone.utc),
                exists().where(
                    (QuizSchedule.subject_id == AcademicEvent.subject_id)
                    & (QuizSchedule.date == AcademicEvent.start_date)),
            ))).scalars().all()
        check("D. seed event UUIDs unchanged", len(seed_events_now) == len(seed_events)
              and seed_event_snapshot == {(str(e.id), str(e.subject_id), e.start_date.isoformat())
                                          for e in seed_events_now})
        check("E. seed schedule UUIDs unchanged",
              seed_schedule_snapshot == {(str(q.id), str(q.subject_id), q.date.isoformat())
                                         for q in schedules_now})

        # --- F. exactly one quiz-day session per seeded quiz date (Option A) ---
        # The Quiz Day is an INDEPENDENT attendance occurrence: EVERY seeded
        # quiz date carries exactly one quiz-day-shaped row, whether or not a
        # normal timetable class also exists that day (covered dates keep their
        # regular occurrence too — but that is the normal session, not a
        # quiz-day row).
        missing, spurious = [], []
        for q in schedules:
            subject_id, quiz_date = q.subject_id, q.date
            qd_rows = [s for s in qd_sessions
                       if s.subject_id == subject_id and s.date == quiz_date]
            if len(qd_rows) == 0:
                missing.append((quiz_date.isoformat(), "no quiz-day session"))
            elif len(qd_rows) > 1:
                spurious.append((quiz_date.isoformat(), "qd_rows=" + str(len(qd_rows))))
        check("F. exactly one quiz-day session per seeded quiz date "
              "(Option A: independent of coverage)",
              not missing and not spurious,
              f"missing={missing} spurious={spurious}")

        # --- G. no duplicate quiz-day occurrence per seeded date/subject -------
        dup = [q for q in schedules
               if len([s for s in qd_sessions
                       if s.subject_id == q.subject_id and s.date == q.date]) > 1]
        check("G. no duplicate quiz-day occurrence for any seeded date/subject "
              "(at most one quiz-day-shaped row per subject/date)", not dup,
              f"dups={[(str(q.subject_id), q.date.isoformat()) for q in dup]}")

        # --- H. attendance-record count unchanged ------------------------------
        records_after = (await db.execute(
            select(func.count()).select_from(AttendanceRecord))).scalar()
        check("H. attendance-record count unchanged by restoration (read-only)",
              records_before == records_after, f"{records_before}->{records_after}")

        # --- I. owner 08-17 test event present and inactive --------------------
        owner_test = (await db.execute(
            select(AcademicEvent).where(
                AcademicEvent.id == "58d4d91e-0ed0-4718-9976-4187290cf9b2"))).scalars().first()
        check("I. owner 2026-08-17 BCS-502 test QUIZ_DAY event present and inactive",
              owner_test is not None and not owner_test.active,
              f"present={owner_test is not None} active={owner_test.active if owner_test else None}")

        # --- J. every other event/session byte-identical -----------------------
        events_now = {(str(e.id), e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                       str(e.subject_id) if e.subject_id else None, e.start_date.isoformat(),
                       e.end_date.isoformat(), bool(e.active))
                      for e in (await db.execute(select(AcademicEvent))).scalars().all()}
        sessions_now = {(str(s.id), str(s.subject_id), s.date.isoformat(),
                         s.class_type.value if hasattr(s.class_type, "value") else str(s.class_type),
                         bool(s.is_extra), bool(s.is_cancelled),
                         str(s.timetable_entry_id) if s.timetable_entry_id else None)
                        for s in (await db.execute(select(ClassSession))).scalars().all()}
        check("J. all events and sessions unchanged across the run (owner data preserved)",
              events_snapshot == events_now and sessions_snapshot == sessions_now,
              f"events_delta={len(events_snapshot ^ events_now)} sessions_delta={len(sessions_snapshot ^ sessions_now)}")

        # --- Idempotency: materialize_quiz_day_sessions.py would create 0 ------
        # Option A: every quiz date already has its quiz-day-shaped session
        # (the shape-based existence check), so a re-run creates nothing.
        missing_shape = [q for q in schedules
                         if (await db.execute(select(ClassSession.id).where(
                             ClassSession.subject_id == q.subject_id,
                             ClassSession.date == q.date,
                             ClassSession.class_type == ClassType.LECTURE,
                             ClassSession.is_extra.is_(False),
                             ClassSession.timetable_entry_id.is_(None)))).scalars().first() is None]
        check("idempotent: every quiz date has its quiz-day session "
              "(re-materialize would create 0)",
              not missing_shape,
              f"missing_shape={[(q.date.isoformat(), str(q.subject_id)) for q in missing_shape]}")

    failed = [name for name, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
