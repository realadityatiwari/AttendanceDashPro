from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.services.calendar_service import CalendarService
from app.schemas.calendar import AcademicDayResponse, AcademicEventResponse, CalendarMonthResponse

router = APIRouter()

@router.get("", response_model=CalendarMonthResponse)
async def get_month_calendar(
    year: int = Query(..., ge=2000, le=2100, description="Calendar year to render (2000-2100)"),
    month: int = Query(..., ge=1, le=12, description="Calendar month to render (1-12)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Read-only month calendar read model for the authenticated student
    (Phase 6.2). The frontend renders the server-provided calendar state and
    must not recompute weekends, closures, events, semester bounds, or class
    session counts itself.

    The requested month is clamped to the student's real academic semester
    (same academic context as /student/me, Track and History); months outside
    the semester return a truthful empty result. Day resolution uses the
    canonical calendar engine (DEFAULT_WEEKENDS, closure events, active
    events); session counts are enrollment-scoped and include scheduled
    sessions only. No attendance percentages or quiz mathematics are computed.
    """
    service = CalendarService(db)
    return await service.get_month_view(current_user, year, month)

@router.get("/today", response_model=AcademicDayResponse)
async def get_today_calendar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the resolved academic day for today.
    """
    service = CalendarService(db)
    day = await service.get_day_schedule(date.today())
    return AcademicDayResponse(
        date=day.date,
        is_working_day=day.is_working_day,
        day_type=day.day_type,
        is_teaching_day=day.is_teaching_day,
        original_day_of_week=day.original_day_of_week,
        substitution_schedule_override=day.substitution_schedule_override,
        events=[AcademicEventResponse.model_validate(e) for e in day.events]
    )

@router.get("/{target_date}", response_model=AcademicDayResponse)
async def get_calendar_by_date(
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the resolved academic day for a specific date.
    """
    service = CalendarService(db)
    day = await service.get_day_schedule(target_date)
    return AcademicDayResponse(
        date=day.date,
        is_working_day=day.is_working_day,
        day_type=day.day_type,
        is_teaching_day=day.is_teaching_day,
        original_day_of_week=day.original_day_of_week,
        substitution_schedule_override=day.substitution_schedule_override,
        events=[AcademicEventResponse.model_validate(e) for e in day.events]
    )
