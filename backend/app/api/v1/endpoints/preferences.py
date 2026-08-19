from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.preference import PreferenceUpdate, PreferenceResponse
from app.services.preference_service import PreferenceService

router = APIRouter()


@router.get("/preferences", response_model=PreferenceResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    GET /api/v1/student/preferences (Phase 10D).

    Returns the authenticated user's preferences. Lazy-create: a user with no
    preference row receives the documented server defaults materialized for
    them (class_reminders=false, auto_mark_present=false,
    week_starts_on=MONDAY), so the response is always a complete preference
    object. user_id is always the authenticated user — no query-parameter or
    body selector exists. Preferences are personal settings for both STUDENT
    and ADMIN users.
    """
    return await PreferenceService(db).get_or_create(current_user)


@router.put("/preferences", response_model=PreferenceResponse)
async def update_preferences(
    payload: PreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    PUT /api/v1/student/preferences (Phase 10D).

    Full-object replacement of the authenticated user's preference row. All
    three fields are required, so omitted fields are impossible (a PUT never
    produces accidental NULLs — the documented server defaults apply only when
    no row exists yet). Invalid week values fail with the normal 422.
    """
    return await PreferenceService(db).replace(current_user, payload)