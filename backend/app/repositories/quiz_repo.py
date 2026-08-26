from uuid import UUID
from typing import Optional, List, Dict, Tuple
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import or_
from app.models.quiz import QuizCycle, EligibilityPolicy, QuizSchedule
from app.models.event import AcademicEvent
from app.models.enums import EventType, ElectiveSlot

class QuizRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_quiz_cycle_with_policy(self, cycle_number: int) -> Optional[QuizCycle]:
        stmt = select(QuizCycle).options(
            selectinload(QuizCycle.policy)
        ).filter(QuizCycle.cycle_number == cycle_number)
        result = await self.db.execute(stmt)
        return result.scalars().first()
        
    async def get_quiz_schedules_for_subject(self, subject_id: UUID) -> List[QuizSchedule]:
        stmt = select(QuizSchedule).options(
            selectinload(QuizSchedule.quiz_cycle)
        ).filter(QuizSchedule.subject_id == subject_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_quiz_schedules_for_subjects(self, subject_ids) -> Dict[UUID, List[QuizSchedule]]:
        """All quiz schedules for many subjects in ONE query (dashboard
        quiz-snapshot N+1 fix), grouped by subject_id.

        NOTE (Phase 2): quiz_schedules is now a seed-time derived projection.
        Runtime quiz dates are authoritative from active QUIZ_DAY AcademicEvents
        (see get_effective_quiz_dates_for_subjects); this accessor remains only
        for projection/verifier compatibility.
        """
        stmt = select(QuizSchedule).options(
            selectinload(QuizSchedule.quiz_cycle)
        ).filter(QuizSchedule.subject_id.in_(subject_ids))
        result = await self.db.execute(stmt)
        grouped: Dict[UUID, List[QuizSchedule]] = {}
        for s in result.scalars().all():
            grouped.setdefault(s.subject_id, []).append(s)
        return grouped

    async def get_effective_quiz_dates_for_subjects(self, subject_ids, elective_scope: Optional[Dict[UUID, ElectiveSlot]] = None) -> Dict[UUID, List[Tuple[int, date]]]:
        """
        CANONICAL effective quiz dates (Phase 2 + Phase 22.4): active QUIZ_DAY
        AcademicEvents are the authoritative source of quiz dates for Quiz
        Eligibility.

        One query fetches the active QUIZ_DAY events for every requested
        subject; each subject's effective quiz dates are the distinct event
        start dates, deduplicated per (subject, date), ranked chronologically
        so the earliest active event is cycle 1, the next cycle 2, and so on.
        A subject with fewer active events than requested cycles is simply
        missing that cycle (the eligibility engine emits UNRESOLVED for it).

        Phase 22.4 `elective_scope`: subject_id -> the Departmental Elective
        slot that subject is the student's selection for. A subject in the
        scope resolves its quiz dates from the slot's QUIZ_DAY events (the
        shared departmental-elective quiz dates) instead of subject-scoped
        events; every other subject uses its own events as before. All
        subjects are resolved in the same single query.
        """
        if not subject_ids:
            return {}
        subject_ids = list(subject_ids)
        regular_ids = set(subject_ids)
        slots: set = set()
        if elective_scope:
            regular_ids.difference_update(elective_scope.keys())
            slots = {s for s in elective_scope.values()}

        scope_ors = []
        if regular_ids:
            scope_ors.append(AcademicEvent.subject_id.in_(regular_ids))
        if slots:
            scope_ors.append(AcademicEvent.elective_slot.in_(slots))
        if not scope_ors:
            return {}

        stmt = (
            select(AcademicEvent)
            .where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True),
                or_(*scope_ors),
            )
            .order_by(AcademicEvent.start_date, AcademicEvent.id)
        )
        result = await self.db.execute(stmt)

        by_slot: Dict[ElectiveSlot, List[AcademicEvent]] = {}
        by_subject: Dict[UUID, List[AcademicEvent]] = {}
        for e in result.scalars().all():
            if e.elective_slot is not None and e.elective_slot in slots:
                by_slot.setdefault(e.elective_slot, []).append(e)
            if e.subject_id in regular_ids:
                by_subject.setdefault(e.subject_id, []).append(e)

        def _rank(events: List[AcademicEvent]) -> List[Tuple[int, date]]:
            dates: List[Tuple[int, date]] = []
            for e in events:
                if dates and dates[-1][1] == e.start_date:
                    # Multiple active events for the same subject/date collapse
                    # to ONE effective quiz date (Phase 2 dedup semantics).
                    continue
                dates.append((len(dates) + 1, e.start_date))
            return dates

        grouped: Dict[UUID, List[Tuple[int, date]]] = {}
        for subject_id in subject_ids:
            if elective_scope and subject_id in elective_scope:
                candidates = by_slot.get(elective_scope[subject_id], [])
            else:
                candidates = by_subject.get(subject_id, [])
            grouped[subject_id] = _rank(candidates)
        return grouped

    async def get_effective_quiz_dates_for_subject(self, subject_id: UUID, elective_scope: Optional[Dict[UUID, ElectiveSlot]] = None) -> List[Tuple[int, date]]:
        """Effective quiz dates (cycle_number, quiz_date) for ONE subject —
        canonical derivation from active QUIZ_DAY AcademicEvents."""
        by_subject = await self.get_effective_quiz_dates_for_subjects(
            [subject_id], elective_scope=elective_scope
        )
        return by_subject.get(subject_id, [])
