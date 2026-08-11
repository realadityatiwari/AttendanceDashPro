from typing import List
from app.schemas.academic import Subject
from app.schemas.attendance import EligibilityResult
from app.engines.eligibility_engine import evaluate_quiz_eligibility

class EligibilityService:
    def __init__(self):
        pass
        
    async def get_quiz_eligibility(self, student_id: str, subject_code: str, quiz_cycle: int) -> EligibilityResult:
        """
        Coordinates data retrieval for timetable, events, and attendance, 
        then uses the pure eligibility_engine to evaluate the official rules.
        """
        # Placeholder for DB query
        # subject = await db.query(Subject).filter(...)
        # attendance = await attendance_service.get_raw(...)
        # events = await calendar_service.get_events(...)
        
        subject = Subject(code=subject_code, name="Placeholder", category="theory", quiz_applicable=True, attendance_applicable=True)
        attendance: dict = {}
        events: list = []
        default_weekends = [0, 6]
        
        return evaluate_quiz_eligibility(subject, quiz_cycle, attendance, events, default_weekends)
