import asyncio
import json
import os
import sys
from datetime import date, timedelta

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import AsyncSessionLocal
from app.models.timetable import TimetableEntry, ClassSession
from app.models.event import AcademicEvent
from app.models.quiz import QuizSchedule, ScheduleStatus
from app.models.enums import ClassType
from app.engines.calendar_engine import get_academic_day, DEFAULT_WEEKENDS
from sqlalchemy import select, and_

TIMETABLE_PATH = os.path.join(os.path.dirname(__file__), '../../timetable.json')

async def expand_baseline():
    print("Loading timetable.json...")
    with open(TIMETABLE_PATH, 'r') as f:
        data = json.load(f)

    start_date = date.fromisoformat(data['start_date'])
    end_date = date.fromisoformat(data['end_date'])
    # default weekends from the calendar engine's single source of truth
    # (JS getDay() indices: 0=Sunday, 6=Saturday). The engine maps Python
    # weekday() to JS getDay() before checking weekend membership.
    default_weekends = DEFAULT_WEEKENDS

    async with AsyncSessionLocal() as db:
        # Pre-flight Check: BCS-054 invariant
        stmt_bcs054 = select(QuizSchedule).join(QuizSchedule.subject).join(QuizSchedule.quiz_cycle).where(
            and_(
                QuizSchedule.subject.has(code="BCS-054"),
                QuizSchedule.quiz_cycle.has(cycle_number=3)
            )
        )
        bcs054_qs = (await db.execute(stmt_bcs054)).scalars().first()
        if bcs054_qs and (bcs054_qs.date is not None or bcs054_qs.schedule_status != ScheduleStatus.UNRESOLVED):
            print("CRITICAL: Pre-flight BCS-054 invariant failed! Aborting.")
            return

        # 1. Fetch all TimetableEntries
        print("Fetching TimetableEntries...")
        stmt_tt = select(TimetableEntry)
        tt_entries = (await db.execute(stmt_tt)).scalars().all()
        print(f"Found {len(tt_entries)} recurring entries.")

        # 2. Fetch all AcademicEvents
        stmt_events = select(AcademicEvent)
        events = (await db.execute(stmt_events)).scalars().all()

        # 3. Iterate over the date range
        current = start_date
        total_created = 0
        total_skipped = 0

        # Also count before
        stmt_before = select(ClassSession)
        sessions_before = len((await db.execute(stmt_before)).scalars().all())
        print(f"ClassSessions before: {sessions_before}")

        subjects_covered = set()
        class_types_generated = set()
        non_teaching_days_excluded = 0

        while current <= end_date:
            day_info = get_academic_day(current, events, default_weekends)
            
            if not day_info.is_teaching_day:
                non_teaching_days_excluded += 1
                current += timedelta(days=1)
                continue

            # Day of week to match timetable_entries
            # timetable.json: 0=Monday, ..., 6=Sunday
            # day_info.original_day_of_week is a string like "MONDAY", but TimetableEntry uses integer 0=Monday.
            # Python weekday() gives 0=Monday, so we can use current.weekday()
            
            target_dow = current.weekday()
            # If there's a substitution, we would need to map the string to integer
            if day_info.substitution_schedule_override:
                day_names = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']
                try:
                    target_dow = day_names.index(day_info.substitution_schedule_override)
                    print(f"Substitution on {current}: acting as {day_info.substitution_schedule_override}")
                except ValueError:
                    pass

            # Find matching entries
            day_entries = [te for te in tt_entries if te.day_of_week == target_dow]
            
            for te in day_entries:
                # Check idempotency
                stmt_check = select(ClassSession).filter_by(
                    timetable_entry_id=te.id,
                    date=current
                )
                existing = (await db.execute(stmt_check)).scalars().first()
                if existing:
                    total_skipped += 1
                else:
                    cs = ClassSession(
                        subject_id=te.subject_id,
                        date=current,
                        class_type=te.class_type,
                        is_extra=False,
                        is_cancelled=False,
                        timetable_entry_id=te.id
                    )
                    db.add(cs)
                    total_created += 1
                    subjects_covered.add(str(te.subject_id))
                    class_types_generated.add(te.class_type.name)

            current += timedelta(days=1)

        # Post-flight Check: BCS-054 invariant
        bcs054_qs = (await db.execute(stmt_bcs054)).scalars().first()
        if bcs054_qs and (bcs054_qs.date is not None or bcs054_qs.schedule_status != ScheduleStatus.UNRESOLVED):
            print("CRITICAL: Post-flight BCS-054 invariant failed! Rolling back.")
            await db.rollback()
            return
            
        await db.commit()

        # Count after
        sessions_after = len((await db.execute(stmt_before)).scalars().all())

        print("--- EXPANSION REPORT ---")
        print(f"ClassSessions before: {sessions_before}")
        print(f"ClassSessions created: {total_created}")
        print(f"ClassSessions after: {sessions_after}")
        print(f"Duplicate candidates skipped: {total_skipped}")
        print(f"Dates covered: {start_date} to {end_date}")
        print(f"Subjects covered (count): {len(subjects_covered)}")
        print(f"Class types generated: {', '.join(class_types_generated)}")
        print(f"Excluded non-teaching days: {non_teaching_days_excluded}")

if __name__ == "__main__":
    asyncio.run(expand_baseline())
