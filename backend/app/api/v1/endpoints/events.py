from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.repositories.calendar_repo import CalendarRepository
from app.schemas.calendar import AcademicEventResponse

router = APIRouter()

@router.get("", response_model=List[AcademicEventResponse])
async def get_all_events(
    active: Optional[bool] = Query(
        True,
        description="Restrict to active events (default true). Pass false for inactive events only.",
    ),
    date_from: Optional[date] = Query(
        None,
        description="Inclusive lower bound (YYYY-MM-DD): include events whose date range overlaps on or after this date.",
    ),
    date_to: Optional[date] = Query(
        None,
        description="Inclusive upper bound (YYYY-MM-DD): include events whose date range overlaps on or before this date.",
    ),
    upcoming: Optional[bool] = Query(
        False,
        description="Restrict to events whose end_date is today or later (current/upcoming events).",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Read-only academic events list.

    Contract (Phase 6.1):
      - Default: only ACTIVE events are returned (inactive events are excluded
        unless `active=false` is passed explicitly).
      - `date_from` / `date_to` filter by range overlap on the event's
        [start_date, end_date].
      - `upcoming=true` restricts to events whose end_date is today or later,
        giving a predictable "current/upcoming" read without client-side
        filtering.

    Mutation is explicitly out of scope for students.
    """
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")

    repo = CalendarRepository(db)
    events = await repo.get_all_events(
        active=active,
        date_from=date_from,
        date_to=date_to,
        upcoming=upcoming,
    )
    return events
