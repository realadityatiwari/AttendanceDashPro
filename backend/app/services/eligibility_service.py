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
        
    async def get_quiz_eligibility(self, user_id: UUID, subject_id: UUID, quiz_cycle: int) -> EligibilityResult:
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
                    type="quiz"
                ))
        
        domain_subject = SubjectSchema(
            code=subject_model.code,
            name=subject_model.name,
            category="theory",
            quiz_applicable=True,
            attendance_applicable=True,
            timeline=Timeline(commencement_date=date.today(), milestones=milestones)
        )
        
        # 2. Fetch Quiz Cycle Policy (if we needed to override the engine's hardcoded policy, we could, but we stick to the engine for now or pass it)
        # Actually, the user asked to: "Do not hardcode 70% or 75% in API routes. Use the persisted academic policy configuration."
        cycle_model = await self.quiz_repo.get_quiz_cycle_with_policy(quiz_cycle)
        if not cycle_model or not cycle_model.eligibility_policy:
            raise HTTPException(status_code=404, detail="Quiz cycle or policy not found")
        
        target_pct = cycle_model.eligibility_policy.lecture_threshold
        
        # 3. Fetch Attendance
        raw_counts = await self.attendance_repo.get_subject_counts_up_to_date(user_id, subject_id, date.today())
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
                
        # 4. Fetch Events
        events_models = await self.calendar_repo.get_all_events()
        # Mocking to dict for engine compatibility
        events = [{"date": e.start_date, "type": e.event_type.value} for e in events_models]
        default_weekends = [5, 6] # Saturday, Sunday
        
        # 5. Evaluate
        result = evaluate_quiz_eligibility(domain_subject, quiz_cycle, counts, events, default_weekends)
        
        # Override the engine's fallback target_pct with the DB one
        result.lecture_threshold = target_pct
        if result.combined_threshold is not None:
            result.combined_threshold = target_pct
            
        return result

