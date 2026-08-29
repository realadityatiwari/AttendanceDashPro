from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies.deps import get_db, require_any_admin
from app.models.user import User
from app.schemas.admin import AdminIdentity, AdminScopeDescriptor
from app.services.authorization_service import AuthorizationService

router = APIRouter()


@router.get("/me", response_model=AdminIdentity)
async def get_admin_identity(
    current_user: User = Depends(require_any_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Phase 24.1: DB-authoritative administrative identity for the Admin Portal
    shell. Read-only — no write behavior, no academic data beyond the scope
    descriptors the shell needs.

    Authorization: ``require_any_admin`` (Phase 23.11 AuthorizationService,
    DB-resolved per request) — unauthenticated → 401, STUDENT with no
    effective admin role → 403. The returned roles/scopes are PRESENTATION
    data for the shell/navigation only; the frontend is never an
    authorization boundary and every admin endpoint stays server-gated.
    """
    identity = await AuthorizationService(db).get_admin_identity(current_user)
    return AdminIdentity(
        id=current_user.id,
        display_name=current_user.name,
        roll_number=current_user.roll_number,
        roles=identity["roles"],
        is_global=identity["is_global"],
        scopes=[AdminScopeDescriptor(**s) for s in identity["scopes"]],
    )
