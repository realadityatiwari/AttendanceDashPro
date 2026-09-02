from uuid import UUID
from typing import List, Dict, Any, Optional
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.core.timezone import institution_today
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
from app.engines.practical_occurrence import collapse_count_rows
from app.schemas.academic import Subject as SubjectSchema, Milestone, Timeline
from app.services.elective_resolver import ElectiveResolver

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
        # (Phase 2 + Phase 22.4): positional cycles over the subject's
        # effective quiz dates. A Departmental Elective subject the student
        # selected resolves the shared slot's quiz dates.
        elective_scope = await ElectiveResolver(self.db).chosen_elective_map(user_id)
        effective_dates = await self.quiz_repo.get_effective_quiz_dates_for_subject(
            subject_id, elective_scope=elective_scope
        )

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
        *,
        # Phase 25.4 (optimization #1): optional pre-fetched data. When None
        # (default) the method fetches them as before — zero behavior change
        # for existing callers. The dashboard summary passes pre-fetched
        # values so these queries happen once per request instead of twice.
        cycle_model=None,
        events=None,
        elective_scope=None,
        effective_by_subject=None,
    ) -> List[EligibilityResult]:
        """
        Batched quiz eligibility for many subjects (dashboard quiz-snapshot
        N+1 fix). Fetches the cycle policy, events, and every subject's
        effective quiz dates (from active QUIZ_DAY AcademicEvents) ONCE, then
        evaluates each subject through the exact same canonical engine path as
        get_quiz_eligibility (via _evaluate_subject). Non-quiz-applicable
        subjects are skipped (mirroring the single-call 404; callers filter
        first). No eligibility mathematics is duplicated.

        Phase 26.3 (optimization #3): the per-subject quiz-window attendance
        scans (2N total) are replaced by ONE date-bounded scan over the union
        of all subjects' windows, bucketed per (subject, window) in memory.
        """
        if cycle_model is None:
            cycle_model = await self.quiz_repo.get_quiz_cycle_with_policy(quiz_cycle)
        if not cycle_model or not cycle_model.policy:
            raise HTTPException(status_code=404, detail="Quiz cycle or policy not found")
        if events is None:
            events = await self.calendar_repo.get_all_events()
        if elective_scope is None:
            elective_scope = await ElectiveResolver(self.db).chosen_elective_map(user_id)
        if effective_by_subject is None:
            effective_by_subject = await self.quiz_repo.get_effective_quiz_dates_for_subjects(
                [s.id for s in subjects], elective_scope=elective_scope
            )

        # Phase 26.3: ONE scoped scan -> per-(subject, window) count buckets.
        window_counts = await self._quiz_window_counts_by_subject(
            user_id, subjects, quiz_cycle, events, semester_start, effective_by_subject,
        )

        results: List[EligibilityResult] = []
        for subject in subjects:
            if not subject.quiz_applicable:
                continue
            effective_dates = effective_by_subject.get(subject.id, [])
            counts = window_counts.get(subject.id, {})
            results.append(await self._evaluate_subject(
                user_id, subject, effective_dates, cycle_model, events,
                quiz_cycle, semester_start,
                raw_counts=counts.get("raw_counts"),
                cumulative_raw_counts=counts.get("cumulative_raw_counts"),
            ))
        return results

    @staticmethod
    def _build_domain_subject(subject_model, effective_dates, semester_start: date | None):
        """Canonical domain Subject + milestone timeline construction shared by
        the single-subject and batched evaluation paths (single source of
        truth; the engine consumes this exact shape)."""
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
            timeline=Timeline(commencement_date=semester_start or institution_today(), milestones=milestones)
        )
        return milestones, domain_subject

    async def _quiz_window_counts_by_subject(
        self,
        user_id: UUID,
        subjects,
        quiz_cycle: int,
        events,
        semester_start: date | None,
        effective_by_subject,
    ) -> Dict[UUID, Dict[str, Any]]:
        """
        Phase 26.3: per-(subject, window) attendance counts from ONE scan.

        For every quiz-applicable subject with a resolved milestone for the
        requested cycle, computes both attendance windows (Criterion I =
        cycle window; Criterion II = cumulative) with the SAME canonical
        calendar-engine calls `_evaluate_subject` uses, then loads every
        matching session for all such subjects in a single date-bounded scan
        (`get_subject_counts_between_for_subjects`) covering the union of all
        windows. Each subject's window rows are then filtered and practical-
        collapsed in memory via the same `collapse_count_rows` the per-subject
        repo path used — byte-identical engine input, without the 2N scans.

        Returns {subject.id: {"raw_counts": [...], "cumulative_raw_counts": [...]}}
        where each value is a list of (class_type, status) count tuples exactly
        like `get_subject_counts_between` produced. Subjects without a
        resolved milestone are absent (their evaluation takes the UNRESOLVED
        empty-count path, identical to before).
        """
        windowed: List[tuple] = []
        global_start: Optional[date] = None
        global_end: Optional[date] = None

        for subject in subjects:
            if not subject.quiz_applicable:
                continue
            effective_dates = effective_by_subject.get(subject.id, [])
            milestones, domain_subject = self._build_domain_subject(
                subject, effective_dates, semester_start
            )
            milestone = next(
                (m for m in milestones if m.metadata.get("quizCycle") == quiz_cycle),
                None,
            )
            if milestone is None:
                # UNRESOLVED cycle — no window, no scan, empty counts (the
                # engine emits the placeholder result as before).
                continue
            window_i = get_attendance_window(
                domain_subject, milestone.milestone_id, events, DEFAULT_WEEKENDS
            )
            window_ii = get_cumulative_attendance_window(
                domain_subject, milestone.milestone_id, events, DEFAULT_WEEKENDS
            )
            windowed.append((subject, window_i, window_ii))
            for w in (window_i, window_ii):
                if global_start is None or w["window_start"] < global_start:
                    global_start = w["window_start"]
                if global_end is None or w["window_end"] > global_end:
                    global_end = w["window_end"]

        if not windowed or global_start is None or global_end is None:
            return {}

        rows = await self.attendance_repo.get_subject_counts_between_for_subjects(
            user_id,
            [s.id for s, _, _ in windowed],
            global_start,
            global_end,
            exclude_quiz_day=True,
        )

        return {
            subject.id: {
                "raw_counts": self._bucket_window_counts(rows, subject.id, window_i),
                "cumulative_raw_counts": self._bucket_window_counts(rows, subject.id, window_ii),
            }
            for subject, window_i, window_ii in windowed
        }

    @staticmethod
    def _bucket_window_counts(rows: List[dict], subject_id: UUID, window: Dict[str, Any]):
        """
        In-memory (subject, window) bucketing: select the scan rows that belong
        to `subject_id` (same `_resolved_subject_match` attribution: the
        session's own subject OR an elective slot the student selected this
        subject for) and fall within the window's inclusive date bounds, then
        run the SAME practical-block collapse + cancellation exclusion
        (`collapse_count_rows`) the per-subject repo query applied. Row order
        is preserved (the scan is ordered by date, start_time, id), so the
        collapse is byte-identical to the per-subject path.
        """
        ws, we = window["window_start"], window["window_end"]
        selected = [
            r
            for r in rows
            if ws <= r["date"] <= we
            and (
                r["session_subject_id"] == subject_id
                or (r["slot"] is not None and r["choice_subject_id"] == subject_id)
            )
        ]
        return collapse_count_rows(selected)

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
        *,
        # Phase 26.3 (optimization #3): optional precomputed window counts from
        # the batch path (`_quiz_window_counts_by_subject`). When provided,
        # the two per-subject DB scans are skipped and the exact same count
        # tuples feed the engine. When None (single-subject path) the method
        # fetches them as before — zero behavior change.
        raw_counts=None,
        cumulative_raw_counts=None,
    ) -> EligibilityResult:
        """Shared per-subject eligibility evaluation (single canonical path for
        both the single-call endpoint and the dashboard batch). The subject has
        already passed the quiz_applicable check by its caller.

        `effective_dates` is the canonical (cycle_number, quiz_date) list from
        active QUIZ_DAY AcademicEvents (Phase 2); a cycle with no active event
        simply has no milestone, so the engine emits UNRESOLVED for it.
        """
        # Convert SQLAlchemy Subject to Domain Subject schema
        milestones, domain_subject = self._build_domain_subject(
            subject_model, effective_dates, semester_start
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
        if milestone:
            if raw_counts is None:
                window = get_attendance_window(domain_subject, milestone.milestone_id, events, default_weekends)
                raw_counts = await self.attendance_repo.get_subject_counts_between(
                    user_id, subject_model.id, window['window_start'], window['window_end'],
                    exclude_quiz_day=True,
                )
            if cumulative_raw_counts is None:
                cumulative_window = get_cumulative_attendance_window(domain_subject, milestone.milestone_id, events, default_weekends)
                cumulative_raw_counts = await self.attendance_repo.get_subject_counts_between(
                    user_id, subject_model.id, cumulative_window['window_start'], cumulative_window['window_end'],
                    exclude_quiz_day=True,
                )
        if raw_counts is None:
            raw_counts = []
        if cumulative_raw_counts is None:
            cumulative_raw_counts = []
        counts: Dict[str, Any] = self._build_counts(raw_counts)
        cumulative_counts: Dict[str, Any] = self._build_counts(cumulative_raw_counts)
        
        # 5. Evaluate (persisted policy thresholds are authoritative for both
        #    qualifying routes; the engine's hardcoded 70/75/75 is the fallback)
        result = evaluate_quiz_eligibility(
            domain_subject, quiz_cycle, counts, events, default_weekends,
            policy_thresholds={
                'lecture_threshold': cycle_model.policy.lecture_threshold,
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

        # Phase 22.4: elective subjects the student selected resolve the shared
        # slot's quiz dates.
        elective_scope = await ElectiveResolver(self.db).chosen_elective_map(user_id)
        effective_by_subject = await self.quiz_repo.get_effective_quiz_dates_for_subjects(
            [s.id for s in quiz_applicable], elective_scope=elective_scope
        )
        resolved = [(cycle, quiz_date) for lst in effective_by_subject.values() for cycle, quiz_date in lst]
        future = [(cycle, quiz_date) for cycle, quiz_date in resolved if quiz_date >= institution_today()]

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

