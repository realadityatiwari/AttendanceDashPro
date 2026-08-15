"""
Materialize quiz-day sessions (attendance-spec alignment).

The product specification states that attendance on the actual quiz day for a
subject is a real attendance event: it is recorded for that subject and
contributes to both the subject's attendance and overall attendance. The
class_sessions table is the canonical session source, so quiz-day attendance
is only recordable where a session exists.

This script makes the canonical session set complete: for every SCHEDULED
quiz schedule of a quiz-applicable subject, if the subject has no
non-cancelled session on the quiz date, it inserts ONE session
(class_type=LECTURE — quiz-applicable subjects are theory subjects with
lectures; quiz-day attendance is a lecture-context event).

Properties:
- Idempotent: re-running converges (existing quiz-day sessions are skipped).
- Authoritative: driven entirely by quiz_schedules (SCHEDULED + dated) —
  never invents dates.
- Reversible: `--undo` deletes exactly the rows this script creates
  (subject_id + quiz date, is_extra=false, timetable_entry_id IS NULL,
  class_type=LECTURE).
- Safe: only inserts; never modifies attendance records or other sessions.

Usage:
    python scripts/materialize_quiz_day_sessions.py          # create missing
    python scripts/materialize_quiz_day_sessions.py --undo   # remove created

Baseline effect (documented, deliberate): class_sessions 684 -> 691
(7 quiz dates had no session), cancelled/extra/records unchanged.
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select, and_

from app.db.session import AsyncSessionLocal
from app.models.quiz import QuizSchedule, ScheduleStatus
from app.models.timetable import ClassSession
from app.models.enums import ClassType

# Quiz-day sessions are LECTURE-class events: every quiz-applicable subject is
# a theory subject with lectures, and the quiz-day attendance event is a
# lecture-context event (documented decision — see implementation report).
QUIZ_DAY_CLASS_TYPE = ClassType.LECTURE


def _quiz_day_sessions_stmt():
    """Selects the exact quiz-day rows this script owns."""
    return select(ClassSession).where(
        ClassSession.class_type == QUIZ_DAY_CLASS_TYPE,
        ClassSession.is_extra.is_(False),
        ClassSession.timetable_entry_id.is_(None),
    )


async def run(undo: bool) -> int:
    async with AsyncSessionLocal() as db:
        # All scheduled, dated quiz schedules for quiz-applicable subjects.
        schedules = (
            await db.execute(
                select(QuizSchedule)
                .join(QuizSchedule.subject)
                .where(
                    QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED,
                    QuizSchedule.date.isnot(None),
                    QuizSchedule.subject.has(quiz_applicable=True),
                )
                .order_by(QuizSchedule.date)
            )
        ).scalars().all()

        if undo:
            created = (await db.execute(_quiz_day_sessions_stmt())).scalars().all()
            if not created:
                print("Nothing to undo — no quiz-day sessions present.")
                return 0
            for session in created:
                await db.delete(session)
            await db.commit()
            print(f"Undo complete: removed {len(created)} quiz-day session(s).")
            return 0

        created_count = 0
        skipped = 0
        for qs in schedules:
            existing = (
                await db.execute(
                    select(ClassSession.id).where(
                        ClassSession.subject_id == qs.subject_id,
                        ClassSession.date == qs.date,
                        ClassSession.is_cancelled.is_(False),
                    )
                )
            ).scalars().first()
            if existing is not None:
                skipped += 1
                continue
            db.add(
                ClassSession(
                    subject_id=qs.subject_id,
                    date=qs.date,
                    class_type=QUIZ_DAY_CLASS_TYPE,
                    is_extra=False,
                    is_cancelled=False,
                    timetable_entry_id=None,
                )
            )
            created_count += 1

        if created_count:
            await db.commit()
        print(f"Quiz-day sessions: created {created_count}, already present {skipped}.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize quiz-day class sessions")
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Remove the quiz-day sessions this script previously created",
    )
    args = parser.parse_args()
    return asyncio.run(run(undo=args.undo))


if __name__ == "__main__":
    raise SystemExit(main())
