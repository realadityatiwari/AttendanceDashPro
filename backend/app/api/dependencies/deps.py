import jwt
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.enums import UserRole
from app.services.authorization_service import AuthorizationService
from app.core.config import settings
import uuid

security = HTTPBearer()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Decodes the JWT access token and returns the authenticated user.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        if user_id_str is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID format in token")

    result = await db.execute(
        select(User).options(selectinload(User.section)).filter_by(id=user_id)
    )
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        
    return user

async def require_admin(current_user: User = Depends(get_current_user)):
    """
    Authorization boundary for admin-only mutations (Phase 6.5).

    The role is resolved from the database for every request (never from the
    token, request body, query parameters, or frontend state) so a role change
    takes effect immediately and the backend remains authoritative.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


async def require_head_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Phase 23.11: global administrative authority.

    Authorized for the legacy ``users.role == ADMIN`` account (resolved as
    HEAD_ADMIN) and for any user with an ACTIVE ``admin_scopes`` row of role
    HEAD_ADMIN. Role/scope are resolved from the DB on every request — never
    from the JWT, body, query, or frontend.
    """
    authz = AuthorizationService(db)
    if not await authz.is_head_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_class_scope(section_id):
    """Phase 23.11 dependency factory: HEAD_ADMIN or an active CLASS_ADMIN
    scope for the exact section_id. Denies other roles and out-of-scope
    sections server-side."""
    async def _dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        authz = AuthorizationService(db)
        if not await authz.can_access_section(current_user, section_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this section",
            )
        return current_user
    return _dependency


def require_subsection_scope(subsection_id):
    """Phase 23.11 dependency factory: HEAD_ADMIN or an active SUBSECTION_ADMIN
    scope for the exact subsection_id.

    NOTE: structurally inert today — no authoritative subsection data exists,
    so no resource can be proven inside a subsection scope. The check remains
    conservative (denies non-HEAD_ADMIN) until a subsection scheduling schema
    decision lands.
    """
    async def _dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        authz = AuthorizationService(db)
        if not await authz.can_access_subsection(current_user, subsection_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this subsection",
            )
        return current_user
    return _dependency


def require_elective_subject_scope(subject_id):
    """Phase 23.11 dependency factory: HEAD_ADMIN or an active ELECTIVE_ADMIN
    scope for the exact concrete subject_id. One subject per scope row — never
    a collapsed elective scope. Denies other subjects server-side."""
    async def _dependency(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        authz = AuthorizationService(db)
        if not await authz.can_access_subject(current_user, subject_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this subject",
            )
        return current_user
    return _dependency

