from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import AnalyticsOverviewResponse

router = APIRouter()


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 8.1 analytics read model (authenticated, enrollment-scoped, read-only).

    Exposes the Phase 8.0-approved fields: overall current attendance (ERP,
    recorded-only), overall forecast attendance (pending-as-attended), pending
    count, a weekly read-model series, and per-subject analytics (current /
    forecast / practical % and the subject-level 75% must-attend / safe-skip
    optimization). Every value is derived from the canonical attendance engine
    and the canonical class_sessions + attendance_records pipeline; no analytics
    mathematics is computed here. AT-RISK and trend product semantics are NOT
    defined and are never emitted.
    """
    service = AnalyticsService(db)
    return await service.get_overview(current_user)
