"""
Chunk 16 — READ-ONLY state snapshot for existing-student immutability proof.

Captures every table relevant to the existing tracked students (users,
elective choices, enrollments, attendance, events, class sessions, quiz
schedules) at the row level. Run before and after chunk-16 work and diff the
two JSON files: any difference is a violation of the immutability requirement
(DETECT -> REPORT -> LEAVE UNTOUCHED). This script performs NO writes.
"""
import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.academic import StudentEnrollment, StudentElectiveChoice, Subject
from app.models.attendance import AttendanceRecord
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.quiz import QuizSchedule
from sqlalchemy import select, func

OUT = Path(__file__).resolve().parent / "c16_state.json"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        subs = {s.id: s.code for s in (await db.execute(select(Subject))).scalars().all()}
        rolls = {u.id: u.roll_number for u in (await db.execute(select(User))).scalars().all()}
        out = {
            "counts": {
                "users": (await db.execute(select(func.count()).select_from(User))).scalar(),
                "enrollments": (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar(),
                "choices": (await db.execute(select(func.count()).select_from(StudentElectiveChoice))).scalar(),
                "attendance_records": (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar(),
                "events": (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar(),
                "class_sessions": (await db.execute(select(func.count()).select_from(ClassSession))).scalar(),
                "quiz_schedules": (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar(),
            },
            "users": sorted(
                (str(u.id), u.roll_number, u.name, str(u.created_at), str(u.updated_at), u.is_active)
                for u in (await db.execute(select(User))).scalars().all()
            ),
            "choices": sorted(
                (str(c.user_id), str(c.subject_id), getattr(c.elective_slot, "value", c.elective_slot),
                 str(c.created_at), str(c.updated_at))
                for c in (await db.execute(select(StudentElectiveChoice))).scalars().all()
            ),
            "enrollments": sorted(
                (str(e.user_id), str(e.subject_id), getattr(e.enrollment_type, "value", e.enrollment_type),
                 str(e.created_at), str(e.updated_at))
                for e in (await db.execute(select(StudentEnrollment))).scalars().all()
            ),
            "attendance": sorted(
                (str(r.user_id), str(r.class_session_id), getattr(r.status, "value", r.status),
                 str(r.created_at), str(r.updated_at))
                for r in (await db.execute(select(AttendanceRecord))).scalars().all()
            ),
            "events": sorted(
                (str(e.id), getattr(e.event_type, "value", e.event_type), str(e.start_date), str(e.end_date),
                 bool(e.active), (e.subject_id and str(e.subject_id)),
                 (e.elective_slot and getattr(e.elective_slot, "value", None)), (e.note or None))
                for e in (await db.execute(select(AcademicEvent))).scalars().all()
            ),
            "class_sessions": sorted(
                (str(s.id), str(s.subject_id), str(s.date), s.is_cancelled, s.is_extra)
                for s in (await db.execute(select(ClassSession))).scalars().all()
            ),
            "_subject_names": {str(k): v for k, v in subs.items()},
            "_user_rolls": {str(k): v for k, v in rolls.items()},
        }
    OUT.write_text(json.dumps(out, indent=1, default=str))
    print(f"snapshot written: {OUT}")
    print(json.dumps(out["counts"]))


if __name__ == "__main__":
    asyncio.run(main())
