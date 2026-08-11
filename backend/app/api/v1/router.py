from fastapi import APIRouter

api_router = APIRouter()

# Placeholder routers for future implementation
attendance_router = APIRouter(prefix="/attendance", tags=["attendance"])
calendar_router = APIRouter(prefix="/calendar", tags=["calendar"])
subjects_router = APIRouter(prefix="/subjects", tags=["subjects"])
timetable_router = APIRouter(prefix="/timetable", tags=["timetable"])
assessments_router = APIRouter(prefix="/assessments", tags=["assessments"])
eligibility_router = APIRouter(prefix="/eligibility", tags=["eligibility"])
events_router = APIRouter(prefix="/events", tags=["events"])
student_router = APIRouter(prefix="/student", tags=["student"])

api_router.include_router(attendance_router)
api_router.include_router(calendar_router)
api_router.include_router(subjects_router)
api_router.include_router(timetable_router)
api_router.include_router(assessments_router)
api_router.include_router(eligibility_router)
api_router.include_router(events_router)
api_router.include_router(student_router)
