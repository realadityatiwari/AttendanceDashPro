"""
Phase 24.11 — Admin & Scope Management service.

Exposes the authoritative `admin_scopes` configuration (Phase 23.11) to
HEAD_ADMIN.  All operations are HEAD_ADMIN-only (the endpoint enforces
`require_head_admin`; matrix FULL | NO | NO | NO).

Rules:
  - an admin user is: legacy `users.role == ADMIN` (HEAD_ADMIN) OR the holder
    of at least one active admin_scopes row;
  - assigning a scope validates the role-scope shape (mirrors the DB CHECK
    `ck_admin_scopes_role_scope`; the DB remains the backstop);
  - HEAD_ADMIN is never created as a scope row (HEAD authority comes from the
    legacy `users.role == ADMIN`);
  - duplicate ACTIVE scope for (user, role, target) -> 409;
  - revoke = `active=false` (canonical deprovisioning path); reactivate =
    `active=true`; never delete rows;
  - account creation / password bootstrap is a DECISION GATE (§25 gate 8)
    and is intentionally NOT exposed.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_scope import AdminScope
from app.models.enums import AdminRole, UserRole
from app.models.user import User
from app.repositories.admin_admin_repo import AdminAdminRepository
from app.schemas.admin_admins import (
    AdminScopeMutationResponse,
    AdminScopeRow,
    AdminUserDetail,
    AdminUserListResponse,
    AdminUserSummary,
    AssignScopeRequest,
)


class AdminAdminDomainError(Exception):
    def __init__(self, detail: str, http_status: int = 422):
        self.detail = detail
        self.http_status = http_status
        super().__init__(detail)


class AdminAdminNotFoundError(AdminAdminDomainError):
    def __init__(self, detail: str = "Not found"):
        super().__init__(detail, http_status=404)


class AdminAdminConflictError(AdminAdminDomainError):
    def __init__(self, detail: str):
        super().__init__(detail, http_status=409)


class AdminAdminService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AdminAdminRepository(db)

    # ------------------------------------------------------------------
    # Presentation composition
    # ------------------------------------------------------------------

    async def _scope_row(self, scope: AdminScope) -> AdminScopeRow:
        section_name = subsection_name = None
        subject_code = subject_name = None
        if scope.section_id is not None:
            section = await self.repo.get_section(scope.section_id)
            section_name = section.name if section else None
        if scope.subsection_id is not None:
            subsection = await self.repo.get_subsection(scope.subsection_id)
            subsection_name = subsection.name if subsection else None
        if scope.subject_id is not None:
            subject = await self.repo.get_subject(scope.subject_id)
            subject_code = subject.code if subject else None
            subject_name = subject.name if subject else None
        return AdminScopeRow(
            id=scope.id,
            role=scope.role,
            active=scope.active,
            section_id=scope.section_id,
            section_name=section_name,
            subsection_id=scope.subsection_id,
            subsection_name=subsection_name,
            subject_id=scope.subject_id,
            subject_code=subject_code,
            subject_name=subject_name,
        )

    def _effective_roles(self, user: User, scopes: List[AdminScope]) -> List[str]:
        roles = set()
        if user.role == UserRole.ADMIN:
            roles.add(AdminRole.HEAD_ADMIN.value)
        for s in scopes:
            roles.add(s.role.value)
        return sorted(roles)

    async def _summary(self, user: User, scopes: List[AdminScope]) -> AdminUserSummary:
        return AdminUserSummary(
            id=user.id,
            display_name=user.name,
            roll_number=user.roll_number,
            is_global=user.role == UserRole.ADMIN or any(
                s.role == AdminRole.HEAD_ADMIN and s.active for s in scopes
            ),
            roles=self._effective_roles(user, scopes),
            active_scope_count=sum(1 for s in scopes if s.active),
        )

    # ------------------------------------------------------------------
    # Reads (HEAD_ADMIN only — endpoint-enforced)
    # ------------------------------------------------------------------

    async def list_admins(self) -> AdminUserListResponse:
        users = await self.repo.list_admin_users()
        items = []
        for user in users:
            scopes = user.admin_scopes
            items.append(await self._summary(user, scopes))
        items.sort(key=lambda i: i.roll_number or "")
        return AdminUserListResponse(items=items, total=len(items))

    async def get_admin(self, user_id: UUID) -> AdminUserDetail:
        user = await self.repo.get_admin_user(user_id)
        if user is None:
            raise AdminAdminNotFoundError("Admin user not found")
        scopes = user.admin_scopes
        summary = await self._summary(user, scopes)
        rows = [await self._scope_row(s) for s in scopes]
        rows.sort(key=lambda r: (r.role.value, r.active is False))
        return AdminUserDetail(**summary.model_dump(), scopes=rows)

    # ------------------------------------------------------------------
    # Writes (HEAD_ADMIN only — endpoint-enforced)
    # ------------------------------------------------------------------

    async def assign_scope(self, user_id: UUID, request: AssignScopeRequest) -> AdminScopeMutationResponse:
        target_user = await self.repo.get_admin_user(user_id)
        if target_user is None:
            raise AdminAdminNotFoundError("Target user not found")

        role = request.role
        section_id = request.section_id
        subsection_id = request.subsection_id
        subject_id = request.subject_id

        # HEAD_ADMIN is never a scope row (legacy users.role == ADMIN).
        if role == AdminRole.HEAD_ADMIN:
            raise AdminAdminConflictError(
                "HEAD_ADMIN authority is granted via the legacy users.role; "
                "a HEAD_ADMIN scope row cannot be created"
            )
        # Role-scope shape must match the DB CHECK ck_admin_scopes_role_scope.
        if role == AdminRole.CLASS_ADMIN:
            if section_id is None or subsection_id is not None or subject_id is not None:
                raise AdminAdminDomainError("CLASS_ADMIN requires exactly section_id")
            section = await self.repo.get_section(section_id)
            if section is None:
                raise AdminAdminNotFoundError("Section not found")
        elif role == AdminRole.SUBSECTION_ADMIN:
            if subsection_id is None or section_id is not None or subject_id is not None:
                raise AdminAdminDomainError("SUBSECTION_ADMIN requires exactly subsection_id")
            subsection = await self.repo.get_subsection(subsection_id)
            if subsection is None:
                raise AdminAdminNotFoundError("Subsection not found")
        elif role == AdminRole.ELECTIVE_ADMIN:
            if subject_id is None or section_id is not None or subsection_id is not None:
                raise AdminAdminDomainError("ELECTIVE_ADMIN requires exactly subject_id")
            subject = await self.repo.get_subject(subject_id)
            if subject is None:
                raise AdminAdminNotFoundError("Subject not found")

        if await self.repo.scope_exists(
            user_id, role, section_id, subsection_id, subject_id
        ):
            raise AdminAdminConflictError(
                f"An active {role.value} scope for this target already exists"
            )

        scope = AdminScope(
            user_id=user_id,
            role=role,
            section_id=section_id,
            subsection_id=subsection_id,
            subject_id=subject_id,
            active=True,
        )
        self.db.add(scope)
        await self.db.commit()
        await self.db.refresh(scope)
        return AdminScopeMutationResponse(scope=await self._scope_row(scope))

    async def set_scope_active(self, scope_id: UUID, active: bool, user_id: Optional[UUID] = None) -> AdminScopeMutationResponse:
        scope = await self.repo.get_scope(scope_id)
        if scope is None:
            raise AdminAdminNotFoundError("Scope not found")
        if user_id is not None and str(scope.user_id) != str(user_id):
            raise AdminAdminNotFoundError("Scope not found for user")
        if scope.role == AdminRole.HEAD_ADMIN:
            raise AdminAdminConflictError("HEAD_ADMIN scope rows are not managed here")
        if scope.active != active:
            scope.active = active
            await self.db.commit()
            await self.db.refresh(scope)
        return AdminScopeMutationResponse(scope=await self._scope_row(scope))
