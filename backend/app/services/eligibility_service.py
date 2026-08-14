from uuid import UUID
from typing import List, Dict, Any
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.repositories.quiz_repo import QuizRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.subject_repo import SubjectRepository
from app.repositories.calendar_repo import CalendarRepository
from app.schemas.attendance import EligibilityResult
from app.engines.eligibility_engine import evaluate_quiz_eligibility
from app.engines.calendar_engine import get_attendance_window, DEFAULT_WEEKENDS
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
        
    async def get_quiz_eligibility(self, user_id: UUID, subject_id: UUID, quiz_cycle: int, semester_start: date | None = None) -> EligibilityResult:
        # 1. Fetch Subject
        subject_model = await self.subject_repo.get_by_id(subject_id)
        if not subject_model:
            raise HTTPException(status_code=404, detail="Subject not found")
            
        # Convert SQLAlchemy Subject to Domain Subject schema
        milestones = []
        schedules = await self.quiz_repo.get_quiz_schedules_for_subject(subject_id)
        for sched in schedules:
            if sched.date:
                milestones.append(Milestone(
                    milestone_id=f"q{sched.quiz_cycle.cycle_number}",
                    date=sched.date,
                    type="QUIZ",
                    metadata={"quizCycle": sched.quiz_cycle.cycle_number}
                ))
        
        # Practicals/labs are strictly excluded from quiz eligibility
        # (S4 PRODUCT SPEC §5). The persisted subject flag is authoritative.
        if not subject_model.quiz_applicable:
            raise HTTPException(status_code=404, detail="Subject not found")
        
        domain_subject = SubjectSchema(
            code=subject_model.code,
            name=subject_model.name,
            category=subject_model.category,
            quiz_applicable=subject_model.quiz_applicable,
            attendance_applicable=subject_model.attendance_applicable,
            timeline=Timeline(commencement_date=semester_start or date.today(), milestones=milestones)
        )
        
        # 2. Fetch Quiz Cycle Policy (if we needed to override the engine's hardcoded policy, we could, but we stick to the engine for now or pass it)
        # Actually, the user asked to: "Do not hardcode 70% or 75% in API routes. Use the persisted academic policy configuration."
        cycle_model = await self.quiz_repo.get_quiz_cycle_with_policy(quiz_cycle)
        if not cycle_model or not cycle_model.policy:
            raise HTTPException(status_code=404, detail="Quiz cycle or policy not found")
        
        # 3. Fetch Events (needed to resolve the attendance window)
        events = await self.calendar_repo.get_all_events()
        # Single source of truth from the calendar engine (JS getDay() indices:
        # 0=Sunday, 6=Saturday). Previously a local [5, 6] (Python weekday
        # indices) was passed here, which the engine interpreted as JS indices
        # and caused Friday to resolve non-working and Sunday working.
        default_weekends = DEFAULT_WEEKENDS
        
        # 4. Fetch Attendance — strictly bounded to the quiz's attendance window
        #    (ADR 010 / reference engine: Quiz N counts from the previous quiz
        #    boundary through the day before the quiz; Q1 counts from commencement).
        #    Unresolved cycles (missing milestone, e.g. BCS-054 Q3) yield no counts
        #    and the engine emits the placeholder result below.
        milestone = next((m for m in milestones if m.metadata.get('quizCycle') == quiz_cycle), None)
        raw_counts = []
        if milestone:
            window = get_attendance_window(domain_subject, milestone.milestone_id, events, default_weekends)
            raw_counts = await self.attendance_repo.get_subject_counts_between(
                user_id, subject_id, window['window_start'], window['window_end']
            )
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
        
        # 5. Evaluate (persisted policy thresholds are authoritative for both
        #    qualifying routes; the engine's hardcoded 70/75/75 is the fallback)
        result = evaluate_quiz_eligibility(
            domain_subject, quiz_cycle, counts, events, default_weekends,
            policy_thresholds={
                'lecture_threshold': cycle_model.policy.lecture_threshold,
                'combined_threshold': cycle_model.policy.combined_threshold or cycle_model.policy.lecture_threshold,
            },
        )
        
        # Enrich with subject identity + the confirmed quiz date (None when the
        # cycle is unresolved — the engine then emits the UNRESOLVED state).
        result.subject_name = subject_model.name
        result.category = subject_model.category.value
        result.quiz_date = milestone.date if milestone else None
        
        return result

