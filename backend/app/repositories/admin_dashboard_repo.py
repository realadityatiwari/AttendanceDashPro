"""
Read-only aggregate queries for the HEAD_ADMIN operational dashboard
(Phase 24.2).

Every method is a bounded COUNT / aggregate query over the authoritative
tables — no row materialization for counting, no N+1, no speculative data.
Nothing here mutates state and nothing re-implements attendance, eligibility,
or elective resolution mathematics: quiz dates remain authoritative from
active QUIZ_DAY AcademicEvents and all counts read the canonical models.
"""

from datetime import date
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import (
    AcademicSession,
    Semester,
    Subject,
    StudentEnrollment,
    StudentElectiveChoice,
)
from app.models.attendance import AttendanceRecord
from app.models.event import AcademicEvent
from app.models.occurrence import OccurrenceOutcome
from app.models.quiz import QuizCycle, QuizSchedule, ScheduleStatus
from app.models.timetable import ClassSession, TimetableEntry
from app.models.user import User, Section
from app.models.enums import (
    UserRole,
    SubjectCategory,
    ElectiveSlot,
    EnrollmentType,
    EventType,
    AttendanceStatus,
)


class AdminDashboardRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Academic structure
    # ------------------------------------------------------------------
    async def count_active_sessions(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(AcademicSession).where(
                AcademicSession.is_active.is_(True)
            )
        )
        return int(result.scalar_one())

    async def get_active_session(self) -> Optional[AcademicSession]:
        result = await self.db.execute(
            select(AcademicSession)
            .where(AcademicSession.is_active.is_(True))
            .order_by(AcademicSession.start_date)
            .limit(1)
        )
        return result.scalars().first()

    async def get_semesters_of_session(self, session_id: UUID) -> List[Semester]:
        result = await self.db.execute(
            select(Semester)
            .where(Semester.session_id == session_id)
            .order_by(Semester.start_date)
        )
        return list(result.scalars().all())

    async def count_sections(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Section)
        )
        return int(result.scalar_one())

    async def count_programs(self) -> int:
        """Distinct non-NULL section programs. NULL = unset (never fabricated)."""
        result = await self.db.execute(
            select(func.count(func.distinct(Section.program))).where(
                Section.program.isnot(None)
            )
        )
        return int(result.scalar_one())

    async def count_subjects(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Subject)
        )
        return int(result.scalar_one())

    async def count_students(self) -> int:
        """Registered student accounts (legacy role STUDENT)."""
        result = await self.db.execute(
            select(func.count()).select_from(User).where(User.role == UserRole.STUDENT)
        )
        return int(result.scalar_one())

    # ------------------------------------------------------------------
    # Curriculum
    # ------------------------------------------------------------------
    async def count_subjects_by_category(self) -> List[Tuple[SubjectCategory, int]]:
        result = await self.db.execute(
            select(Subject.category, func.count()).group_by(Subject.category)
        )
        return list(result.all())

    async def count_subjects_by_elective_slot(self) -> List[Tuple[ElectiveSlot, int]]:
        """The DB-backed elective catalog: subjects carrying a non-NULL
        elective_slot marker (Phase 23.5)."""
        result = await self.db.execute(
            select(Subject.elective_slot, func.count())
            .where(Subject.elective_slot.isnot(None))
            .group_by(Subject.elective_slot)
        )
        return list(result.all())

    async def count_enrollments_by_type(self) -> List[Tuple[EnrollmentType, int]]:
        result = await self.db.execute(
            select(StudentEnrollment.enrollment_type, func.count()).group_by(
                StudentEnrollment.enrollment_type
            )
        )
        return list(result.all())

    # ------------------------------------------------------------------
    # Students
    # ------------------------------------------------------------------
    async def count_students_placed(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(
                User.role == UserRole.STUDENT,
                User.section_id.isnot(None),
            )
        )
        return int(result.scalar_one())

    async def count_students_unplaced(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(
                User.role == UserRole.STUDENT,
                User.section_id.is_(None),
            )
        )
        return int(result.scalar_one())

    async def count_students_subsection_assigned(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(
                User.role == UserRole.STUDENT,
                User.subsection_id.isnot(None),
            )
        )
        return int(result.scalar_one())

    async def count_students_subsection_unassigned(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(
                User.role == UserRole.STUDENT,
                User.subsection_id.is_(None),
            )
        )
        return int(result.scalar_one())

    async def count_elective_choice_holders(self) -> int:
        """Distinct students with at least one StudentElectiveChoice row."""
        result = await self.db.execute(
            select(func.count(func.distinct(StudentElectiveChoice.user_id)))
        )
        return int(result.scalar_one())

    async def count_elective_choices(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(StudentElectiveChoice)
        )
        return int(result.scalar_one())

    async def count_placed_students_without_elective_choices(self) -> int:
        """Placed students (STUDENT role, section assigned) with NO elective
        choice rows at all — the objectively detectable unresolved state."""
        result = await self.db.execute(
            select(func.count(func.distinct(User.id)))
            .select_from(User)
            .outerjoin(
                StudentElectiveChoice,
                StudentElectiveChoice.user_id == User.id,
            )
            .where(
                User.role == UserRole.STUDENT,
                User.section_id.isnot(None),
                StudentElectiveChoice.id.is_(None),
            )
        )
        return int(result.scalar_one())

    # ------------------------------------------------------------------
    # Schedule / occurrences
    # ------------------------------------------------------------------
    async def count_timetable_entries(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(TimetableEntry)
        )
        return int(result.scalar_one())

    async def count_class_sessions(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(ClassSession)
        )
        return int(result.scalar_one())

    async def count_class_sessions_cancelled(self) -> int:
        """Anchor-level cancellations (class_sessions.is_cancelled). Per-subject
        effective cancellation may additionally be expressed by
        occurrence_outcomes rows (reported separately)."""
        result = await self.db.execute(
            select(func.count()).select_from(ClassSession).where(
                ClassSession.is_cancelled.is_(True)
            )
        )
        return int(result.scalar_one())

    async def count_class_sessions_extra(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(ClassSession).where(
                ClassSession.is_extra.is_(True)
            )
        )
        return int(result.scalar_one())

    async def count_class_sessions_on(self, day: date) -> int:
        """Non-cancelled anchor sessions dated exactly `day`."""
        result = await self.db.execute(
            select(func.count()).select_from(ClassSession).where(
                ClassSession.date == day,
                ClassSession.is_cancelled.is_(False),
            )
        )
        return int(result.scalar_one())

    async def count_class_sessions_from(self, day: date) -> int:
        """Non-cancelled anchor sessions dated `day` or later."""
        result = await self.db.execute(
            select(func.count()).select_from(ClassSession).where(
                ClassSession.date >= day,
                ClassSession.is_cancelled.is_(False),
            )
        )
        return int(result.scalar_one())

    async def count_occurrence_outcomes(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(OccurrenceOutcome)
        )
        return int(result.scalar_one())

    # ------------------------------------------------------------------
    # Events / quizzes
    # ------------------------------------------------------------------
    async def count_active_events(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(AcademicEvent).where(
                AcademicEvent.active.is_(True)
            )
        )
        return int(result.scalar_one())

    async def count_upcoming_active_events(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(AcademicEvent).where(
                AcademicEvent.active.is_(True),
                AcademicEvent.end_date >= date.today(),
            )
        )
        return int(result.scalar_one())

    async def get_upcoming_events(
        self, limit: int
    ) -> List[Tuple[AcademicEvent, Optional[str]]]:
        """Active events ending today or later, soonest first (bounded list).
        subject_code comes from a single outer join; NULL = global event."""
        result = await self.db.execute(
            select(AcademicEvent, Subject.code)
            .outerjoin(Subject, AcademicEvent.subject_id == Subject.id)
            .where(
                AcademicEvent.active.is_(True),
                AcademicEvent.end_date >= date.today(),
            )
            .order_by(AcademicEvent.start_date, AcademicEvent.id)
            .limit(limit)
        )
        return list(result.all())

    async def count_quiz_cycles(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(QuizCycle)
        )
        return int(result.scalar_one())

    async def count_quiz_schedules(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(QuizSchedule)
        )
        return int(result.scalar_one())

    async def count_quiz_schedules_by_status(self) -> List[Tuple[ScheduleStatus, int]]:
        result = await self.db.execute(
            select(QuizSchedule.schedule_status, func.count()).group_by(
                QuizSchedule.schedule_status
            )
        )
        return list(result.all())

    async def count_quiz_schedules_dated(self) -> int:
        """SCHEDULED schedules with a resolved date (the projection baseline)."""
        result = await self.db.execute(
            select(func.count()).select_from(QuizSchedule).where(
                QuizSchedule.date.isnot(None),
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED,
            )
        )
        return int(result.scalar_one())

    async def get_next_quiz_date(self, today: date) -> Optional[date]:
        """Next active QUIZ_DAY event at or after today — the authoritative
        quiz-date source (Phase 2); quiz_schedules is a seed-time projection."""
        result = await self.db.execute(
            select(func.min(AcademicEvent.start_date)).where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True),
                AcademicEvent.start_date >= today,
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Attendance (aggregate only — no mathematics re-implemented)
    # ------------------------------------------------------------------
    async def count_attendance_by_status(self) -> List[Tuple[AttendanceStatus, int]]:
        result = await self.db.execute(
            select(AttendanceRecord.status, func.count()).group_by(
                AttendanceRecord.status
            )
        )
        return list(result.all())

    async def count_attendance_participants(self) -> int:
        """Distinct users holding at least one attendance record."""
        result = await self.db.execute(
            select(func.count(func.distinct(AttendanceRecord.user_id)))
        )
        return int(result.scalar_one())
