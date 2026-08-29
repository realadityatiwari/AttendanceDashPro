import asyncio
import os
import sys

# Add backend to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from uuid import UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.models.user import User, Subsection
from app.models.academic import Subject
from app.models.enums import ElectiveSlot, UserRole
from app.services.admin_student_service import AdminStudentService

# Set up local DB connection
DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:55432/attendancedash"
engine = create_async_engine(DB_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with async_session() as db:
        # Find an admin
        admin_stmt = select(User).where(User.role == UserRole.ADMIN)
        admin = (await db.execute(admin_stmt)).scalars().first()
        if not admin:
            print("No ADMIN found")
            return
            
        print(f"Testing as Admin: {admin.name}")

        # Find a student
        student_stmt = select(User).where(User.role == UserRole.STUDENT)
        student = (await db.execute(student_stmt)).scalars().first()
        if not student:
            print("No STUDENT found")
            return
            
        print(f"Testing on Student: {student.name} (Active: {getattr(student, 'is_active', True)})")
        
        service = AdminStudentService(db)

        # 1. Test toggle status
        print("\n--- Test Set Status ---")
        new_status = not getattr(student, "is_active", True)
        res = await service.set_student_status(admin, student.id, new_status)
        print(f"Status changed to: {res.is_active}")

        # Revert status
        res = await service.set_student_status(admin, student.id, not new_status)
        print(f"Status reverted to: {res.is_active}")

        # 2. Test assign subsection
        print("\n--- Test Assign Subsection ---")
        if student.section_id:
            sub_stmt = select(Subsection).where(Subsection.section_id == student.section_id)
            subsection = (await db.execute(sub_stmt)).scalars().first()
            if subsection:
                res = await service.assign_subsection(admin, student.id, subsection.id)
                print(f"Assigned to subsection: {res.subsection_name}")
            else:
                print("No subsection found for student's section")
        else:
            print("Student not in a section")
            
        # 3. Test correct elective
        print("\n--- Test Correct Elective ---")
        ctx = await service.get_student_detail(admin, student.id)
        if ctx.semester_id:
            subj_stmt = select(Subject).where(Subject.semester_id == ctx.semester_id, Subject.elective_slot == ElectiveSlot.ELECTIVE_I)
            subject = (await db.execute(subj_stmt)).scalars().first()
            if subject:
                res = await service.correct_elective(admin, student.id, ElectiveSlot.ELECTIVE_I, subject.id)
                print(f"Assigned ELECTIVE_I to: {res.elective_choices.get('ELECTIVE_I')}")
            else:
                print("No ELECTIVE_I found for student's semester")
        else:
            print("Student not in a semester")

if __name__ == "__main__":
    asyncio.run(main())
