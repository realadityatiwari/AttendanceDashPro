import sys
import asyncio
from pathlib import Path
from datetime import date

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.timetable import ClassSession
from app.models.academic import Subject
from app.models.laboratory import LaboratoryExperiment
from sqlalchemy import select

async def main():
    print("--- BASELINE POSTGRESQL DIAGNOSTICS ---")
    async with AsyncSessionLocal() as session:
        # Check ClassSessions
        result = await session.execute(select(ClassSession, Subject).join(Subject))
        sessions = result.all()
        print(f"Total ClassSessions in PostgreSQL: {len(sessions)}")
        if len(sessions) > 0:
            print("Sample ClassSessions:")
            for cs, subj in sessions[:15]:
                print(f"  {cs.date} | {subj.code} | {cs.class_type.name}")
        else:
            print("  No ClassSessions found. The baseline likely only contains recurring timetable structures, not historical occurrences.")

        # Check LaboratoryExperiments
        result = await session.execute(select(LaboratoryExperiment, Subject).join(Subject))
        exps = result.all()
        print(f"\nTotal LaboratoryExperiments in PostgreSQL: {len(exps)}")
        if exps:
            print("All LaboratoryExperiments:")
            for exp, subj in exps:
                print(f"  {subj.code} | Exp No: {exp.experiment_number} | {exp.title}")

if __name__ == "__main__":
    asyncio.run(main())
