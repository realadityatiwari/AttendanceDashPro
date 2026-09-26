import asyncio
import os
import sys
from pathlib import Path

# Setup paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import AsyncSessionLocal
from app.models.user import User, Section
from app.models.academic import Semester, Subject, StudentEnrollment, StudentElectiveChoice
from app.models.enums import ElectiveSlot
from app.services.enrollment_service import build_enrollment, plan_new_student_enrollments
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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

        # 4. Create StudentEnrollments — [Chunk 16] invariant-conformant.
        #
        # ROOT-CAUSE NOTE (Chunk 15 forensic audit): this section previously
        # enrolled EVERY Subject row for the target user WITHOUT an explicit
        # enrollment_type, so the SQLAlchemy model default 'COMPULSORY'
        # applied. For a freshly registered student (7 COMPULSORY + 2 ELECTIVE
        # rows already present) this added exactly the four UNSELECTED
        # elective-pool subjects (BCS-052/053/055/056) as COMPULSORY — the
        # phantom-enrollment pattern observed on 2026-09-25.
        #
        # The construction now routes through the centralized
        # EnrollmentService: only non-elective subjects PLUS the student's
        # StudentElectiveChoice-resolved selection per configured elective
        # slot are ever added, with an explicit EnrollmentType. Existing rows
        # are skipped; NOTHING is deleted or updated (this script never
        # normalizes existing students); an unresolvable elective slot is
        # skipped with a warning and never invented.
        result = await session.execute(select(Subject))
        subjects = list(result.scalars().all())
        print(f"Found {len(subjects)} subjects. Verifying invariant-conformant enrollments...")

        choices = (await session.execute(
            select(StudentElectiveChoice)
            .options(selectinload(StudentElectiveChoice.subject))
            .where(StudentElectiveChoice.user_id == user.id)
        )).scalars().all()
        choices_by_slot = {c.elective_slot: c for c in choices}
        for slot in (ElectiveSlot.ELECTIVE_I, ElectiveSlot.ELECTIVE_II):
            if slot not in choices_by_slot:
                print(f"WARNING: no {slot.value} choice recorded for user "
                      f"{user.roll_number}; that elective slot will NOT be enrolled.")

        existing_rows = (await session.execute(
            select(StudentEnrollment).where(StudentEnrollment.user_id == user.id)
        )).scalars().all()
        existing_enrollments = {e.subject_id for e in existing_rows}

        specs, missing_slots = plan_new_student_enrollments(subjects, choices_by_slot)
        for slot in missing_slots:
            print(f"WARNING: {slot.value} selection could not be resolved; skipping that slot.")

        new_enrollments = 0
        for subject, enrollment_type in specs:
            if subject.id in existing_enrollments:
                continue
            session.add(build_enrollment(user.id, subject, enrollment_type))
            new_enrollments += 1
            print(f"  + {subject.code} ({enrollment_type.value})")

        if new_enrollments > 0:
            print(f"Created {new_enrollments} invariant-conformant enrollment(s).")
        else:
            print("All invariant-conformant enrollments already exist. No new enrollments created.")

        await session.commit()
        print("Setup completed successfully.")

if __name__ == "__main__":
    asyncio.run(setup_single_user())
