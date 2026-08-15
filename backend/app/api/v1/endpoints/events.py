from datetime import date
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.repositories.calendar_repo import CalendarRepository
from app.schemas.calendar import (
    AcademicEventResponse,
    AcademicEventCreate,
    AcademicEventUpdate,
)
from app.services.event_service import EventService, EventForbidden
from app.services.event_registry import EventValidationError
from app.repositories.event_repo import EventNotFound, EventConflict

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


@router.post("", response_model=AcademicEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: AcademicEventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Event creation (Phase 6.5 + attendance-spec alignment). Authenticated
    users may create the flexible subject-scoped event types (extra classes,
    class cancellations, surprise quizzes) for their own enrolled subjects;
    global/closure/quiz-schedule events remain admin-only. Authorization and
    business validation happen in the EventService / validation registry;
    business conflicts return 409.
    """
    service = EventService(db)
    try:
        event = await service.create_event(current_user, payload)
    except EventForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except EventValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except EventConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return event


@router.patch("/{event_id}", response_model=AcademicEventResponse)
async def update_event(
    event_id: UUID,
    payload: AcademicEventUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Partial event update (Phase 6.5 + attendance-spec alignment). Students
    may update flexible subject-scoped events for their enrolled subjects;
    global/closure events stay admin-only. Absent fields are unchanged.
    """
    service = EventService(db)
    try:
        event = await service.update_event(current_user, event_id, payload)
    except EventForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except EventNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except EventValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except EventConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return event


@router.delete("/{event_id}", response_model=AcademicEventResponse)
async def delete_event(
    event_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Event deactivation (Phase 6.5 + attendance-spec alignment). Students may
    remove flexible subject-scoped events for their enrolled subjects;
    global/closure events stay admin-only. Deletion is safe deactivation:
    `active` is the lifecycle flag (legacy soft-delete semantics), so the row
    is preserved and the calendar engine / read APIs stop considering it.
    Re-enable via PATCH {"active": true}.
    """
    service = EventService(db)
    try:
        event = await service.deactivate_event(current_user, event_id)
    except EventForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except EventNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return event
