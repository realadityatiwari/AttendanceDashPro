"""
Phase 24.11 — Admin & Scope Management repository.

Bounded queries over the authoritative `admin_scopes` (Phase 23.11) and the
users who hold administrative authority (legacy `users.role == ADMIN` OR any
active `admin_scopes` row). Resolves presentation names for scope targets.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, Section, Subsection
from app.models.academic import Subject
from app.models.admin_scope import AdminScope
from app.models.enums import AdminRole, UserRole


class AdminAdminRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Admin users (legacy ADMIN OR active scope)
    # ------------------------------------------------------------------

    async def list_admin_users(self) -> List[User]:
        """Users holding administrative authority, with their scope rows
        eager-loaded.  An admin user is: legacy `users.role == ADMIN`
        (HEAD_ADMIN) OR the holder of at least one admin_scopes row."""
        stmt = (
            select(User)
            .options(selectinload(User.admin_scopes))
            .where(
                or_(
                    User.role == UserRole.ADMIN,
                    User.id.in_(
                        select(AdminScope.user_id).where(AdminScope.active.is_(True))
                    ),
                )
            )
            .order_by(User.roll_number, User.name)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_admin_user(self, user_id: UUID) -> Optional[User]:
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.admin_scopes))
            .where(User.id == user_id)
        )
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Scope rows
    # ------------------------------------------------------------------

    async def list_scopes_for_user(self, user_id: UUID) -> List[AdminScope]:
        result = await self.db.execute(
            select(AdminScope)
            .where(AdminScope.user_id == user_id)
            .order_by(AdminScope.role, AdminScope.created_at)
        )
        return list(result.scalars().all())

    async def get_scope(self, scope_id: UUID) -> Optional[AdminScope]:
        result = await self.db.execute(
            select(AdminScope).where(AdminScope.id == scope_id)
        )
        return result.scalars().first()

    async def scope_exists(
        self,
        user_id: UUID,
        role: AdminRole,
        section_id: Optional[UUID],
        subsection_id: Optional[UUID],
        subject_id: Optional[UUID],
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """Duplicate-scope guard: one ACTIVE scope per (user, role, target)."""
        stmt = select(func.count()).select_from(AdminScope).where(
            AdminScope.user_id == user_id,
            AdminScope.role == role,
            AdminScope.active.is_(True),
            AdminScope.section_id == section_id,
            AdminScope.subsection_id == subsection_id,
            AdminScope.subject_id == subject_id,
        )
        if exclude_id is not None:
            stmt = stmt.where(AdminScope.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    async def count_admin_scopes(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(AdminScope))
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Presentation-name lookups
    # ------------------------------------------------------------------

    async def get_section(self, section_id: UUID) -> Optional[Section]:
        result = await self.db.execute(select(Section).where(Section.id == section_id))
        return result.scalars().first()

    async def get_subsection(self, subsection_id: UUID) -> Optional[Subsection]:
        result = await self.db.execute(select(Subsection).where(Subsection.id == subsection_id))
        return result.scalars().first()

    async def get_subject(self, subject_id: UUID) -> Optional[Subject]:
        result = await self.db.execute(select(Subject).where(Subject.id == subject_id))
        return result.scalars().first()
