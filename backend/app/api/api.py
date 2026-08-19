from fastapi import APIRouter
from app.api.v1.endpoints import auth, student, subjects, timetable, attendance, quiz, calendar, events, laboratory, dashboard, analytics, feedback, preferences, notifications

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(student.router, prefix="/student", tags=["student"])
api_router.include_router(preferences.router, prefix="/student", tags=["student"])
api_router.include_router(subjects.router, prefix="/subjects", tags=["subjects"])
api_router.include_router(timetable.router, prefix="/timetable", tags=["timetable"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(quiz.router, prefix="/quiz-eligibility", tags=["quiz-eligibility"])
api_router.include_router(calendar.router, prefix="/calendar", tags=["calendar"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(laboratory.router, prefix="/laboratory", tags=["laboratory"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
