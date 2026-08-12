import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text
from app.repositories.quiz_repo import QuizRepository
from app.repositories.subject_repo import SubjectRepository

async def verify_bcs054():
    try:
        async with AsyncSessionLocal() as session:
            subject_repo = SubjectRepository(session)
            subject = await subject_repo.get_by_code("BCS-054")
            if not subject:
                print("BCS-054 NOT FOUND")
                return
                
            quiz_repo = QuizRepository(session)
            schedules = await quiz_repo.get_quiz_schedules_for_subject(subject.id)
            print(f"Schedules for BCS-054:")
            for s in schedules:
                print(f"Cycle {s.quiz_cycle.cycle_number}: Date={s.date}, Status={s.schedule_status}")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(verify_bcs054())
