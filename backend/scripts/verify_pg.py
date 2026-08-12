import sys
import asyncio
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.academic import Subject, AcademicSession, Semester, StudentEnrollment
from app.models.timetable import TimetableEntry, ClassSession
from app.models.attendance import AttendanceRecord
from app.models.laboratory import LaboratoryExperiment, LaboratoryRecord
from app.models.user import User
from app.models.quiz import QuizSchedule, QuizCycle, ScheduleStatus
from sqlalchemy import select

async def verify_pg():
    print("Testing PostgreSQL Read Access...")
    async with AsyncSessionLocal() as session:
        # User
        await session.execute(select(User))
        # Subject
        result = await session.execute(select(Subject))
        subjects = {s.code: s for s in result.scalars().all()}
        # ClassSession
        await session.execute(select(ClassSession))
        # LaboratoryExperiment
        await session.execute(select(LaboratoryExperiment))
        # QuizCycle
        await session.execute(select(QuizCycle))
        # QuizSchedule
        await session.execute(select(QuizSchedule))
        
        print("Successfully resolved base models.")

        # Check BCS-054 invariant
        bcs_054 = subjects.get("BCS-054")
        if not bcs_054:
            print("CRITICAL BASELINE DISCREPANCY: BCS-054 not found.")
            sys.exit(1)
        
        result = await session.execute(
            select(QuizSchedule)
            .join(QuizCycle)
            .where(QuizSchedule.subject_id == bcs_054.id)
            .where(QuizCycle.cycle_number == 3)
        )
        q3 = result.scalars().first()
        if not q3:
            print("CRITICAL BASELINE DISCREPANCY: BCS-054 Quiz III not found.")
            sys.exit(1)
            
        if q3.date is not None or q3.schedule_status.value != "UNRESOLVED":
            print(f"CRITICAL BASELINE DISCREPANCY: BCS-054 Quiz III invariant violated. Date: {q3.date}, Status: {q3.schedule_status.value}")
            sys.exit(1)
            
        print("BCS-054 Invariant Verified: date=NULL, status=UNRESOLVED")

if __name__ == "__main__":
    asyncio.run(verify_pg())
