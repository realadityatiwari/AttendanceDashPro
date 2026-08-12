from fastapi import APIRouter
from app.api.v1.endpoints import student, subjects, timetable, attendance, quiz, calendar, events, laboratory

api_router = APIRouter()
api_router.include_router(student.router, prefix="/student", tags=["student"])
api_router.include_router(subjects.router, prefix="/subjects", tags=["subjects"])
api_router.include_router(timetable.router, prefix="/timetable", tags=["timetable"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(quiz.router, prefix="/quiz-eligibility", tags=["quiz-eligibility"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(laboratory.router, prefix="/laboratory", tags=["laboratory"])
