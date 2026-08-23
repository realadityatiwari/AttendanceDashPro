import asyncio
import os
import sys
from pathlib import Path

# Setup paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.user import User, Section
from app.models.academic import Semester, Subject, StudentEnrollment
from sqlalchemy import select

async def setup_single_user():
    print("Starting single-user academic setup...")
    
    async with AsyncSessionLocal() as session:
        # 1. Get Semester
        result = await session.execute(select(Semester).where(Semester.name == "V Semester"))
        semester = result.scalars().first()
        if not semester:
            print("ERROR: 'V Semester' not found in database. Run seed_academic_baseline.py first.")
            return

        # 2. Get or Create Section
        result = await session.execute(select(Section).where(Section.name == "CSE-51", Section.semester_id == semester.id))
        section = result.scalars().first()
        
        if not section:
            print("Creating Section 'CSE-51'...")
            section = Section(name="CSE-51", semester_id=semester.id, program="CSE")
            session.add(section)
            await session.flush()
        else:
            print(f"Reusing existing Section 'CSE-51' (ID: {section.id})")
            if not section.program:
                section.program = "CSE"
                print("  Setting program = 'CSE' on existing section")

        # 3. Update User
        roll_number = "2401220100027"
        result = await session.execute(select(User).where(User.roll_number == roll_number))
        user = result.scalars().first()
        
        if not user:
            print(f"ERROR: User with roll_number '{roll_number}' not found.")
            return
            
        print(f"Restoring identity for User {user.id}...")
        user.name = "Aditya Tiwari"
        user.roll_number = "2401220100027"
        user.section_id = section.id
        await session.flush()

        # 4. Create StudentEnrollments
        result = await session.execute(select(Subject))
        subjects = result.scalars().all()
        print(f"Found {len(subjects)} subjects. Verifying enrollments...")
        
        # Get existing enrollments
        result = await session.execute(
            select(StudentEnrollment).where(StudentEnrollment.user_id == user.id)
        )
        existing_enrollments = {e.subject_id: e for e in result.scalars().all()}
        
        new_enrollments = 0
        for subject in subjects:
            if subject.id not in existing_enrollments:
                enrollment = StudentEnrollment(
                    user_id=user.id,
                    subject_id=subject.id
                )
                session.add(enrollment)
                new_enrollments += 1
                
        if new_enrollments > 0:
            print(f"Created {new_enrollments} new enrollments.")
        else:
            print("All enrollments already exist. No new enrollments created.")
            
        await session.commit()
        print("Setup completed successfully.")

if __name__ == "__main__":
    asyncio.run(setup_single_user())
