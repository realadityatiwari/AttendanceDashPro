"""
Phase 24.8 — Admin Quiz Management repository.

Bounded queries over the canonical quiz configuration:
  - QuizSchedule (subject, cycle, elective_slot, date, status) — the admin
    configuration/plan;
  - QuizCycle + EligibilityPolicy (read);
  - the QUIZ_DAY AcademicEvent derived from a schedule (the canonical runtime
    quiz-date authority).

The runtime quiz-date authority remains ACTIVE QUIZ_DAY AcademicEvents
(consumed by eligibility via `QuizRepository.get_effective_quiz_dates_for_subjects`).
QuizSchedule is the derived projection/plan this repository manages.
"""
from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Subject
from app.models.event import AcademicEvent
from app.models.enums import ElectiveSlot, EventType
from app.models.quiz import EligibilityPolicy, QuizCycle, QuizSchedule


class AdminQuizRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Quiz schedules (admin configuration/plan)
    # ------------------------------------------------------------------

    async def list_quiz_schedules(
        self,
        *,
        cycle_number: Optional[int] = None,
        semester_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
    ) -> List[QuizSchedule]:
        """All quiz schedules with subject + cycle eager-loaded.  Filters are
        additive narrowing (semester/session resolved through the subject's
        semester)."""
        stmt = (
            select(QuizSchedule)
            .options(
                selectinload(QuizSchedule.subject),
                selectinload(QuizSchedule.quiz_cycle),
            )
            .order_by(QuizSchedule.date, QuizSchedule.subject_id)
        )
        if cycle_number is not None:
            stmt = stmt.join(QuizCycle, QuizCycle.id == QuizSchedule.quiz_cycle_id).where(
                QuizCycle.cycle_number == cycle_number
            )
        if semester_id is not None or session_id is not None:
            stmt = stmt.join(Subject, Subject.id == QuizSchedule.subject_id)
            if semester_id is not None:
                stmt = stmt.where(Subject.semester_id == semester_id)
            if session_id is not None:
                from app.models.academic import Semester
                stmt = stmt.join(Semester, Semester.id == Subject.semester_id).where(
                    Semester.session_id == session_id
                )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_quiz_schedule(self, schedule_id: UUID) -> Optional[QuizSchedule]:
        result = await self.db.execute(
            select(QuizSchedule)
            .options(
                selectinload(QuizSchedule.subject),
                selectinload(QuizSchedule.quiz_cycle),
            )
            .where(QuizSchedule.id == schedule_id)
        )
        return result.scalars().first()

    async def schedule_exists_for_subject_cycle(
        self, subject_id: UUID, quiz_cycle_id: UUID, exclude_id: Optional[UUID] = None
    ) -> bool:
        """Duplicate identity guard: one schedule per (subject, cycle)."""
        stmt = select(func.count()).select_from(QuizSchedule).where(
            QuizSchedule.subject_id == subject_id,
            QuizSchedule.quiz_cycle_id == quiz_cycle_id,
        )
        if exclude_id is not None:
            stmt = stmt.where(QuizSchedule.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    # ------------------------------------------------------------------
    # Cycles + policies (read)
    # ------------------------------------------------------------------

    async def list_quiz_cycles(self) -> List[QuizCycle]:
        result = await self.db.execute(
            select(QuizCycle)
            .options(selectinload(QuizCycle.policy))
            .order_by(QuizCycle.cycle_number)
        )
        return list(result.scalars().all())

    async def get_quiz_cycle(self, cycle_id: UUID) -> Optional[QuizCycle]:
        result = await self.db.execute(
            select(QuizCycle)
            .options(selectinload(QuizCycle.policy))
            .where(QuizCycle.id == cycle_id)
        )
        return result.scalars().first()

    async def get_policy_for_cycle(self, cycle_id: UUID) -> Optional[EligibilityPolicy]:
        result = await self.db.execute(
            select(EligibilityPolicy).where(EligibilityPolicy.quiz_cycle_id == cycle_id)
        )
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Subjects / context
    # ------------------------------------------------------------------

    async def get_subject(self, subject_id: UUID) -> Optional[Subject]:
        result = await self.db.execute(
            select(Subject).where(Subject.id == subject_id)
        )
        return result.scalars().first()

    # ------------------------------------------------------------------
    # QUIZ_DAY AcademicEvent identity (canonical derivation link)
    # ------------------------------------------------------------------

    async def find_quiz_day_event(
        self,
        subject_id: UUID,
        quiz_date: date,
        elective_slot: Optional[ElectiveSlot],
        active_only: bool = False,
    ) -> Optional[AcademicEvent]:
        """The QUIZ_DAY AcademicEvent matching a schedule's identity:
        (event_type, subject_id, start_date, elective_slot) — the same
        deterministic identity the seed script uses."""
        stmt = select(AcademicEvent).where(
            AcademicEvent.event_type == EventType.QUIZ_DAY,
            AcademicEvent.subject_id == subject_id,
            AcademicEvent.start_date == quiz_date,
            AcademicEvent.end_date == quiz_date,
        )
        if elective_slot is None:
            stmt = stmt.where(AcademicEvent.elective_slot.is_(None))
        else:
            stmt = stmt.where(AcademicEvent.elective_slot == elective_slot)
        if active_only:
            stmt = stmt.where(AcademicEvent.active.is_(True))
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def count_active_quiz_day_events(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(AcademicEvent).where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True),
            )
        )
        return result.scalar_one()
