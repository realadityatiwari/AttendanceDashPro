from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.services.calendar_service import CalendarService
from app.schemas.calendar import AcademicDayResponse

router = APIRouter()

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
        events=[] # The engine returns dictionaries in this setup, let's map it below.
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
        events=[]
    )
