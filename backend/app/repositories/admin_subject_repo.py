"""
Phase 24.6 — Admin Subject / Curriculum Repository.

Bounded, read-only (for reads) queries over the curriculum tables:
  Subject (semester-scoped) + dependent counts.

All queries use the async SQLAlchemy session passed from the service.
No authorization decisions are made here — that is the service/endpoint layer.
No attendance / enrollment / elective mathematics are re-implemented.

Dependent counts are computed in BATCH (one grouped query per list) rather
than one COUNT per row, avoiding the N+1 pattern used by earlier admin
list endpoints where practical.
"""

from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import (
    AcademicSession,
    Semester,
    StudentElectiveChoice,
    StudentEnrollment,
    Subject,
)
from app.models.laboratory import LaboratoryExperiment
from app.models.quiz import QuizSchedule
from app.models.timetable import ClassSession, TimetableEntry
from app.models.attendance import AttendanceRecord


class AdminSubjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Curriculum reads
    # ------------------------------------------------------------------

    async def list_subjects(self) -> List[Subject]:
        """All subjects ordered by semester start date then code."""
        result = await self.db.execute(
            select(Subject)
            .join(Semester, Semester.id == Subject.semester_id)
            .order_by(Semester.start_date, Subject.code)
        )
        return list(result.scalars().all())

    async def get_subject(self, subject_id: UUID) -> Optional[Subject]:
        result = await self.db.execute(
            select(Subject).where(Subject.id == subject_id)
        )
        return result.scalars().first()

    async def get_subjects_by_ids(self, subject_ids: List[UUID]) -> List[Subject]:
        if not subject_ids:
            return []
        result = await self.db.execute(
            select(Subject).where(Subject.id.in_(subject_ids))
        )
        return list(result.scalars().all())

    async def get_semester(self, semester_id: UUID) -> Optional[Semester]:
        result = await self.db.execute(
            select(Semester).where(Semester.id == semester_id)
        )
        return result.scalars().first()

    async def get_active_session(self) -> Optional[AcademicSession]:
        result = await self.db.execute(
            select(AcademicSession).where(AcademicSession.is_active.is_(True))
        )
        return result.scalars().first()

    async def subject_code_exists_in_semester(
        self, semester_id: UUID, code: str, exclude_id: Optional[UUID] = None
    ) -> bool:
        stmt = select(func.count()).select_from(Subject).where(
            Subject.semester_id == semester_id,
            Subject.code == code,
        )
        if exclude_id is not None:
            stmt = stmt.where(Subject.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    # ------------------------------------------------------------------
    # Bounded dependent counts (batch where practical)
    # ------------------------------------------------------------------

    async def count_enrollments_by_subject(self, subject_ids: List[UUID]) -> Dict[UUID, int]:
        """Enrollment counts keyed by subject_id — one grouped query."""
        if not subject_ids:
            return {}
        result = await self.db.execute(
            select(StudentEnrollment.subject_id, func.count())
            .where(StudentEnrollment.subject_id.in_(subject_ids))
            .group_by(StudentEnrollment.subject_id)
        )
        return {sid: count for sid, count in result.all()}

    async def count_elective_choices_by_subject(self, subject_ids: List[UUID]) -> Dict[UUID, int]:
        """StudentElectiveChoice counts keyed by subject_id — one grouped query."""
        if not subject_ids:
            return {}
        result = await self.db.execute(
            select(StudentElectiveChoice.subject_id, func.count())
            .where(StudentElectiveChoice.subject_id.in_(subject_ids))
            .group_by(StudentElectiveChoice.subject_id)
        )
        return {sid: count for sid, count in result.all()}

    async def count_enrollments(self, subject_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(StudentEnrollment).where(
                StudentEnrollment.subject_id == subject_id
            )
        )
        return result.scalar_one()

    async def count_elective_choices(self, subject_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(StudentElectiveChoice).where(
                StudentElectiveChoice.subject_id == subject_id
            )
        )
        return result.scalar_one()

    async def count_timetable_entries(self, subject_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(TimetableEntry).where(
                TimetableEntry.subject_id == subject_id
            )
        )
        return result.scalar_one()

    async def count_class_sessions(self, subject_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(ClassSession).where(
                ClassSession.subject_id == subject_id
            )
        )
        return result.scalar_one()

    async def count_quiz_schedules(self, subject_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(QuizSchedule).where(
                QuizSchedule.subject_id == subject_id
            )
        )
        return result.scalar_one()

    async def count_lab_experiments(self, subject_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(LaboratoryExperiment).where(
                LaboratoryExperiment.subject_id == subject_id
            )
        )
        return result.scalar_one()

    async def count_attendance_records(self, subject_id: UUID) -> int:
        """Attendance records referencing any class session of this subject.

        attendance_records reference class_sessions (not subjects directly),
        so this counts records via the class-session join — a bounded aggregate.
        """
        result = await self.db.execute(
            select(func.count())
            .select_from(AttendanceRecord)
            .join(ClassSession, ClassSession.id == AttendanceRecord.class_session_id)
            .where(ClassSession.subject_id == subject_id)
        )
        return result.scalar_one()
