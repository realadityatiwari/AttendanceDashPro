from uuid import UUID
from typing import List, Dict, Any
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.repositories.quiz_repo import QuizRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.subject_repo import SubjectRepository
from app.repositories.calendar_repo import CalendarRepository
from app.repositories.user_repo import UserRepository
from app.schemas.attendance import EligibilityResult
from app.engines.eligibility_engine import evaluate_quiz_eligibility
from app.engines.calendar_engine import (
    get_attendance_window, get_cumulative_attendance_window, DEFAULT_WEEKENDS,
)
from app.models.enums import AttendanceStatus
from app.engines.attendance_engine import normalize_class_type
from app.schemas.academic import Subject as SubjectSchema, Milestone, Timeline

class EligibilityService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.quiz_repo = QuizRepository(db)
        self.attendance_repo = AttendanceRepository(db)
        self.subject_repo = SubjectRepository(db)
        self.calendar_repo = CalendarRepository(db)
        self.user_repo = UserRepository(db)
        
    async def get_quiz_eligibility(self, user_id: UUID, subject_id: UUID, quiz_cycle: int, semester_start: date | None = None) -> EligibilityResult:
        # 1. Fetch Subject
        subject_model = await self.subject_repo.get_by_id(subject_id)
        if not subject_model:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Practicals/labs are strictly excluded from quiz eligibility
        # (S4 PRODUCT SPEC §5). The persisted subject flag is authoritative.
        if not subject_model.quiz_applicable:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Quiz dates are authoritative from active QUIZ_DAY AcademicEvents
        # (Phase 2): positional cycles over the subject's effective quiz dates.
        effective_dates = await self.quiz_repo.get_effective_quiz_dates_for_subject(subject_id)

        # 2. Fetch Quiz Cycle Policy (persisted configuration is authoritative;
        # the engine's hardcoded 70/75/75 is only the fallback).
        cycle_model = await self.quiz_repo.get_quiz_cycle_with_policy(quiz_cycle)
        if not cycle_model or not cycle_model.policy:
            raise HTTPException(status_code=404, detail="Quiz cycle or policy not found")

        # 3. Fetch Events (needed to resolve the attendance window)
        events = await self.calendar_repo.get_all_events()

        return await self._evaluate_subject(
            user_id, subject_model, effective_dates, cycle_model, events,
            quiz_cycle, semester_start,
        )

    async def get_quiz_eligibility_for_subjects(
        self,
        user_id: UUID,
        subjects,
        quiz_cycle: int,
        semester_start: date | None = None,
    ) -> List[EligibilityResult]:
        """
        Batched quiz eligibility for many subjects (dashboard quiz-snapshot
        N+1 fix). Fetches the cycle policy, events, and every subject's
        effective quiz dates (from active QUIZ_DAY AcademicEvents) ONCE, then
        evaluates each subject through the exact same canonical engine path as
        get_quiz_eligibility (via _evaluate_subject). Non-quiz-applicable
        subjects are skipped (mirroring the single-call 404; callers filter
        first). No eligibility mathematics is duplicated.
        """
        cycle_model = await self.quiz_repo.get_quiz_cycle_with_policy(quiz_cycle)
        if not cycle_model or not cycle_model.policy:
            raise HTTPException(status_code=404, detail="Quiz cycle or policy not found")
        events = await self.calendar_repo.get_all_events()
        effective_by_subject = await self.quiz_repo.get_effective_quiz_dates_for_subjects(
            [s.id for s in subjects]
        )
        results: List[EligibilityResult] = []
        for subject in subjects:
            if not subject.quiz_applicable:
                continue
            effective_dates = effective_by_subject.get(subject.id, [])
            results.append(await self._evaluate_subject(
                user_id, subject, effective_dates, cycle_model, events,
                quiz_cycle, semester_start,
            ))
        return results

    @staticmethod
    def _build_counts(raw_counts) -> Dict[str, Any]:
        """Aggregates raw (class_type, status) rows into the canonical L/T
        count shape consumed by the eligibility engine."""
        counts: Dict[str, Any] = {
            'L': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
            'T': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
        }
        for class_type_str, status in raw_counts:
            t = normalize_class_type(class_type_str.value)
            if t not in counts:
                continue

            counts[t]['tot'] += 1
            if status == AttendanceStatus.ATTENDED:
                counts[t]['att'] += 1
            elif status == AttendanceStatus.MISSED:
                counts[t]['miss'] += 1
            else:
                counts[t]['pending'] += 1
        return counts

    async def _evaluate_subject(
        self,
        user_id: UUID,
        subject_model,
        effective_dates,
        cycle_model,
        events,
        quiz_cycle: int,
        semester_start: date | None,
    ) -> EligibilityResult:
        """Shared per-subject eligibility evaluation (single canonical path for
        both the single-call endpoint and the dashboard batch). The subject has
        already passed the quiz_applicable check by its caller.

        `effective_dates` is the canonical (cycle_number, quiz_date) list from
        active QUIZ_DAY AcademicEvents (Phase 2); a cycle with no active event
        simply has no milestone, so the engine emits UNRESOLVED for it.
        """
        # Convert SQLAlchemy Subject to Domain Subject schema
        milestones = [
            Milestone(
                milestone_id=f"q{cycle_number}",
                date=quiz_date,
                type="QUIZ",
                metadata={"quizCycle": cycle_number}
            )
            for cycle_number, quiz_date in effective_dates
        ]

        domain_subject = SubjectSchema(
            code=subject_model.code,
            name=subject_model.name,
            category=subject_model.category,
            quiz_applicable=subject_model.quiz_applicable,
            attendance_applicable=subject_model.attendance_applicable,
            timeline=Timeline(commencement_date=semester_start or date.today(), milestones=milestones)
        )
        # Single source of truth from the calendar engine (JS getDay() indices:
        # 0=Sunday, 6=Saturday). Previously a local [5, 6] (Python weekday
        # indices) was passed here, which the engine interpreted as JS indices
        # and caused Friday to resolve non-working and Sunday working.
        default_weekends = DEFAULT_WEEKENDS
        
        # 4. Fetch Attendance — strictly bounded to the quiz's attendance windows
        #    (ADR 010 / reference engine: Quiz N counts from the previous quiz
        #    boundary through the day before the quiz; Q1 counts from commencement).
        #    Unresolved cycles (missing milestone, e.g. BCS-054 Q3) yield no counts
        #    and the engine emits the placeholder result below.
        #
        #    Two windows are evaluated (Phase 1 eligibility correction):
        #      - Criterion I  = cycle window (previous quiz -> day before quiz)
        #      - Criterion II = cumulative window (commencement -> day before quiz)
        #    Both use the same lecture/tutorial average formula.
        milestone = next((m for m in milestones if m.metadata.get('quizCycle') == quiz_cycle), None)
        raw_counts = []
        cumulative_raw_counts = []
        if milestone:
            window = get_attendance_window(domain_subject, milestone.milestone_id, events, default_weekends)
            raw_counts = await self.attendance_repo.get_subject_counts_between(
                user_id, subject_model.id, window['window_start'], window['window_end'],
                exclude_quiz_day=True,
            )
            cumulative_window = get_cumulative_attendance_window(domain_subject, milestone.milestone_id, events, default_weekends)
            cumulative_raw_counts = await self.attendance_repo.get_subject_counts_between(
                user_id, subject_model.id, cumulative_window['window_start'], cumulative_window['window_end'],
                exclude_quiz_day=True,
            )
        counts: Dict[str, Any] = self._build_counts(raw_counts)
        cumulative_counts: Dict[str, Any] = self._build_counts(cumulative_raw_counts)
        
        # 5. Evaluate (persisted policy thresholds are authoritative for both
        #    qualifying routes; the engine's hardcoded 70/75/75 is the fallback)
        result = evaluate_quiz_eligibility(
            domain_subject, quiz_cycle, counts, events, default_weekends,
            policy_thresholds={
                'lecture_threshold': cycle_model.policy.lecture_threshold,
                'combined_threshold': cycle_model.policy.combined_threshold or cycle_model.policy.lecture_threshold,
            },
            cumulative_counts=cumulative_counts,
        )
        
        # Enrich with subject identity + the confirmed quiz date (None when the
        # cycle is unresolved — the engine then emits the UNRESOLVED state).
        result.subject_name = subject_model.name
        result.category = subject_model.category.value
        result.quiz_date = milestone.date if milestone else None
        
        return result

    async def get_current_quiz_cycle(self, user_id: UUID) -> dict:
        """Canonical "currently relevant" quiz cycle for a student.

        Mirrors the dashboard quiz-snapshot pick semantics so the Quiz
        Eligibility page and the dashboard agree for the same user/cycle:
          - next active quiz date at/after today -> that cycle ("next_upcoming");
          - otherwise the highest-numbered resolved cycle ("latest_resolved");
          - otherwise the documented fallback Quiz I ("fallback",
            has_schedule=False, no invented date).
        Reads only active QUIZ_DAY AcademicEvents (the authoritative quiz-date
        source, Phase 2); never invents quiz dates and never mutates state.
        """
        subjects = await self.user_repo.get_enrolled_subjects(user_id)
        quiz_applicable = [s for s in subjects if s.quiz_applicable]

        effective_by_subject = await self.quiz_repo.get_effective_quiz_dates_for_subjects(
            [s.id for s in quiz_applicable]
        )
        resolved = [(cycle, quiz_date) for lst in effective_by_subject.values() for cycle, quiz_date in lst]
        future = [(cycle, quiz_date) for cycle, quiz_date in resolved if quiz_date >= date.today()]

        if future:
            cycle, quiz_date = min(future, key=lambda x: x[1])
            basis = "next_upcoming"
        elif resolved:
            cycle, quiz_date = max(resolved, key=lambda x: x[0])
            basis = "latest_resolved"
        else:
            return {
                "quiz_cycle": 1,
                "quiz_label": "Quiz I",
                "quiz_date": None,
                "has_schedule": False,
                "basis": "fallback",
            }

        cycle_model = await self.quiz_repo.get_quiz_cycle_with_policy(cycle)
        return {
            "quiz_cycle": cycle,
            "quiz_label": cycle_model.label if cycle_model else None,
            "quiz_date": quiz_date,
            "has_schedule": True,
            "basis": basis,
        }

