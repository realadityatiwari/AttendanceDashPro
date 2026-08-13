from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, get_current_user
from app.models.user import User
from app.services.dashboard_service import DashboardService
from app.schemas.dashboard import DashboardSummaryResponse

router = APIRouter()

@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Read-only Home dashboard aggregation.

    Composes today's attendance, overall attendance, weekly summary, quiz
    snapshot, attention-required subjects, and upcoming events from the
    existing attendance/eligibility/calendar services and engines. This is a
    dashboard read model only — it performs no mutations and owns no business
    rules.
    """
    service = DashboardService(db)
    return await service.get_summary(current_user)