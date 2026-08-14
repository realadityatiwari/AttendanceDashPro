"""
Controlled, idempotent academic-event seeding (Phase 6.5).

Source of truth: the quiz_schedules table (authoritative project data — the
real scheduled quiz dates). For every SCHEDULED quiz with a confirmed date a
single QUIZ_DAY academic event is created (subject-scoped, one-day range).
BCS-054 Quiz III is UNRESOLVED (no date) and is naturally excluded.

NOT seeded (no authoritative source exists in the repository):
- public/institute/festival holidays      (no institutional holiday list)
- semester/mid-semester breaks            (no institutional calendar)
- working Saturdays / emergency closures  (no institutional calendar)
See docs/phase_4_5_data_audit.md and docs/phase_6_0_calendar_events_audit.md:
the academic_events table is empty because the data gap is real, not a code
gap. This seed does NOT invent dates or infer university holidays.

Idempotency: an event is skipped when a row with the identical semantic
identity already exists (event_type, subject_id, start_date, end_date,
class_type, is_working_day, substitution_schedule_override). Re-running the
seed never duplicates rows and never resurrects a deliberately deactivated
event.

Transactional: all inserts happen in one transaction — either the full set is
persisted or none of it is. No attendance, no class_sessions, no user data.

Usage:
    python scripts/seed_academic_events.py
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.event import AcademicEvent
from app.models.enums import EventType
from app.models.quiz import QuizSchedule, ScheduleStatus
from sqlalchemy import select


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(QuizSchedule)
            .where(
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED,
                QuizSchedule.date.is_not(None),
            )
            .order_by(QuizSchedule.date, QuizSchedule.subject_id)
        )
        schedules = list(result.scalars().all())

        created = 0
        skipped = 0
        for schedule in schedules:
            if schedule.date is None:
                continue
            # Semantic identity of the desired event (deterministic seed key).
            identity = dict(
                event_type=EventType.QUIZ_DAY,
                subject_id=schedule.subject_id,
                start_date=schedule.date,
                end_date=schedule.date,
                class_type=None,
                is_working_day=None,
                substitution_schedule_override=None,
            )
            existing = await session.execute(
                select(AcademicEvent.id).where(
                    AcademicEvent.event_type == identity["event_type"],
                    AcademicEvent.subject_id == identity["subject_id"],
                    AcademicEvent.start_date == identity["start_date"],
                    AcademicEvent.end_date == identity["end_date"],
                )
            )
            if existing.scalars().first() is not None:
                skipped += 1
                continue
            session.add(AcademicEvent(**identity, active=True))
            created += 1

        if created:
            await session.commit()
            print(f"Seeded {created} QUIZ_DAY event(s).")
        else:
            print("No new events needed.")
        print(f"Skipped {skipped} already-present quiz-day identity(ies).")
        print(
            "Note: holidays/breaks are NOT seeded — no authoritative "
            "institutional dates exist in the repository (reported data gap)."
        )


if __name__ == "__main__":
    asyncio.run(main())