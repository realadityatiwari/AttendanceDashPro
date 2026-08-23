from uuid import UUID
from typing import Optional, List
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from app.models.user import User, Section
from app.models.academic import StudentEnrollment, Subject, Semester, AcademicSession
from app.models.event import AcademicEvent
from app.models.enums import EventType

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_enrolled_subjects(self, user_id: UUID) -> List[Subject]:
        stmt = select(Subject).join(StudentEnrollment).filter(StudentEnrollment.user_id == user_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_academic_context(self, user: User) -> dict:
        """
        Resolves read-only academic context for the Profile UI:
        semester/session names, semester start date, and the student's
        first scheduled quiz date. Returns None-safe values; no data is
        invented when the academic chain is incomplete.
        """
        semester_name: Optional[str] = None
        academic_session: Optional[str] = None
        semester_start: Optional[date] = None
        semester_end: Optional[date] = None

        if user.section is not None and user.section.semester_id is not None:
            semester = await self.db.get(Semester, user.section.semester_id)
            if semester is not None:
                semester_name = semester.name
                semester_start = semester.start_date
                semester_end = semester.end_date
                session = await self.db.get(AcademicSession, semester.session_id)
                if session is not None:
                    academic_session = session.name

        first_quiz_date: Optional[date] = None
        if user.id is not None:
            # Quiz dates are authoritative from active QUIZ_DAY AcademicEvents
            # (Phase 2) — earliest active quiz date across enrolled subjects.
            stmt = select(func.min(AcademicEvent.start_date)).join(
                StudentEnrollment,
                StudentEnrollment.subject_id == AcademicEvent.subject_id,
            ).where(
                StudentEnrollment.user_id == user.id,
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True),
            )
            result = await self.db.execute(stmt)
            first_quiz_date = result.scalar_one_or_none()

        return {
            "program": user.section.program if user.section is not None else None,
            "semester_name": semester_name,
            "academic_session": academic_session,
            "semester_start": semester_start,
            "semester_end": semester_end,
            "first_quiz_date": first_quiz_date,
        }
