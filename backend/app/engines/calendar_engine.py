from datetime import date, timedelta
from typing import List, Dict, Optional, Any
from app.models.enums import EventType, ClassType
from app.schemas.academic import AcademicEvent, TimetableEntry, Subject

# State (in a real app, this would be injected or read from the DB)
# For the engine pure functions, we pass these as arguments instead of mutating globals.

DAY_NAMES = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY']

def get_event_priority(event_type: EventType) -> int:
    priorities = {
        EventType.EMERGENCY_CLOSURE: 100,
        EventType.WORKING_DAY_OVERRIDE: 90,
        EventType.WORKING_SATURDAY: 80,
        EventType.PUBLIC_HOLIDAY: 70,
        EventType.SEMESTER_BREAK: 60,
        EventType.MID_SEMESTER_BREAK: 60,
        EventType.INSTITUTE_HOLIDAY: 50,
        EventType.FESTIVAL_HOLIDAY: 40,
        EventType.CLASS_CANCELLED: 30,
        EventType.EXTRA_LECTURE: 30,
        EventType.EXTRA_TUTORIAL: 30,
        EventType.EXTRA_PRACTICAL: 30,
        EventType.SURPRISE_QUIZ: 30,
        EventType.QUIZ_DAY: 30,
    }
    return priorities.get(event_type, 10)

class AcademicDay:
    def __init__(
        self, 
        d: date, 
        is_working_day: bool, 
        day_type: str, 
        events: List[AcademicEvent], 
        is_teaching_day: bool,
        original_day_of_week: str,
        substitution_schedule_override: Optional[str] = None
    ):
        self.date = d
        self.is_working_day = is_working_day
        self.day_type = day_type
        self.events = events
        self.is_teaching_day = is_teaching_day
        self.original_day_of_week = original_day_of_week
        self.substitution_schedule_override = substitution_schedule_override

def get_academic_day(
    target_date: date, 
    events: List[AcademicEvent], 
    default_weekends: List[int] # 0 = Monday, 6 = Sunday in Python, whereas JS was 0=Sun. JS: [0, 6] meaning Sun/Sat. In Python, Monday is 0, Sunday is 6.
) -> AcademicDay:
    # Python weekday(): 0=Mon, 1=Tue, ..., 5=Sat, 6=Sun
    # JS getDay(): 0=Sun, 1=Mon, ..., 6=Sat
    # The default_weekends from JSON are [0, 6] meaning Sun/Sat.
    # So we map python weekday to JS getDay to check default_weekends
    js_dow = (target_date.weekday() + 1) % 7
    
    is_working_day = js_dow not in default_weekends
    original_day_of_week = DAY_NAMES[target_date.weekday()]
    substitution_schedule_override = None
    
    # Filter events for this date and active
    active_events = [e for e in events if e.start_date <= target_date <= e.end_date and e.active]
    sorted_events = sorted(active_events, key=lambda e: get_event_priority(e.event_type), reverse=True)
    
    if sorted_events:
        dominant_event = sorted_events[0]
        is_closure = dominant_event.event_type in [
            EventType.PUBLIC_HOLIDAY, EventType.INSTITUTE_HOLIDAY, EventType.FESTIVAL_HOLIDAY, 
            EventType.EMERGENCY_CLOSURE, EventType.SEMESTER_BREAK
        ]
        
        if dominant_event.is_working_day is not None or is_closure:
            is_working_day = False if is_closure else dominant_event.is_working_day
            
        if dominant_event.substitution_schedule_override:
            substitution_schedule_override = dominant_event.substitution_schedule_override
            
    day_type = 'WORKING_DAY' if is_working_day else 'NON_WORKING_DAY'
    
    return AcademicDay(
        d=target_date,
        is_working_day=is_working_day,
        day_type=day_type,
        events=sorted_events,
        is_teaching_day=is_working_day,
        original_day_of_week=original_day_of_week,
        substitution_schedule_override=substitution_schedule_override
    )

def get_teaching_days_between(
    start_date: date, 
    end_date: date, 
    events: List[AcademicEvent], 
    default_weekends: List[int]
) -> List[date]:
    if start_date > end_date:
        return []
    
    teaching_days = []
    current = start_date
    while current <= end_date:
        day = get_academic_day(current, events, default_weekends)
        if day.is_teaching_day:
            teaching_days.append(current)
        current += timedelta(days=1)
    return teaching_days

def get_attendance_window(
    subject: Subject, 
    milestone_id: str,
    events: List[AcademicEvent],
    default_weekends: List[int]
) -> Dict[str, Any]:
    if not subject.timeline:
        raise ValueError(f"Subject {subject.code} has no timeline")
        
    milestone = next((m for m in subject.timeline.milestones if m.milestone_id == milestone_id), None)
    if not milestone:
        raise ValueError(f"Unknown milestone {milestone_id}")
        
    window_start = subject.timeline.commencement_date
    
    quiz_cycle = milestone.metadata.get('quizCycle')
    if quiz_cycle and quiz_cycle > 1:
        prev_quiz = next((m for m in subject.timeline.milestones if m.type == 'QUIZ' and m.metadata.get('quizCycle') == quiz_cycle - 1), None)
        if prev_quiz:
            window_start = prev_quiz.date
            
    window_end = milestone.date - timedelta(days=1)
    
    if window_start > window_end:
        raise ValueError("Window end before window start")
        
    teaching_dates = get_teaching_days_between(window_start, window_end, events, default_weekends)
    
    return {
        "subject_code": subject.code,
        "window_start": window_start,
        "window_end": window_end,
        "teaching_days": len(teaching_dates),
        "effective_teaching_dates": teaching_dates
    }
