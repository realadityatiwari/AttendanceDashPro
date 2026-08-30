"""
Phase 24.11 — Admin & Scope Management schemas.

Exposes the authoritative `admin_scopes` configuration (Phase 23.11) to
HEAD_ADMIN: an admin user's effective roles and scope rows, plus scope
assign/deactivate/reactivate.

The matrix is FULL | NO | NO | NO for every admin-management operation; the
endpoint layer enforces `require_head_admin`. Account creation / password
bootstrap is a DECISION GATE (§25 gate 8) and is intentionally NOT exposed.
"""
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import AdminRole


class AdminScopeRow(BaseModel):
    """One `admin_scopes` row with resolved presentation names."""
    id: UUID
    role: AdminRole
    active: bool
    section_id: Optional[UUID] = None
    section_name: Optional[str] = None
    subsection_id: Optional[UUID] = None
    subsection_name: Optional[str] = None
    subject_id: Optional[UUID] = None
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None

    model_config = {"from_attributes": True}


class AdminUserSummary(BaseModel):
    """A user holding administrative authority (legacy ADMIN or active scope)."""
    id: UUID
    display_name: str
    roll_number: Optional[str] = None
    is_global: bool
    roles: List[str] = Field(default_factory=list)
    active_scope_count: int = 0


class AdminUserListResponse(BaseModel):
    items: List[AdminUserSummary] = Field(default_factory=list)
    total: int = 0


class AdminUserDetail(AdminUserSummary):
    """Full admin user: effective roles + ALL scope rows (active + inactive)."""
    scopes: List[AdminScopeRow] = Field(default_factory=list)


class AssignScopeRequest(BaseModel):
    """Assign a scope to a user.

    Exactly one target column must be set per role (mirrors the DB CHECK
    `ck_admin_scopes_role_scope`):
      - HEAD_ADMIN:       section_id, subsection_id, subject_id ALL null;
      - CLASS_ADMIN:      section_id set (others null);
      - SUBSECTION_ADMIN: subsection_id set (others null);
      - ELECTIVE_ADMIN:   subject_id set (others null).
    HEAD_ADMIN scope rows are never created here — HEAD authority comes from
    the legacy `users.role == ADMIN`. Assigning HEAD_ADMIN as a scope row is
    rejected.
    """
    role: AdminRole
    section_id: Optional[UUID] = None
    subsection_id: Optional[UUID] = None
    subject_id: Optional[UUID] = None


class AdminScopeMutationResponse(BaseModel):
    scope: AdminScopeRow


class UpdateScopeActiveRequest(BaseModel):
    """Deactivate (revoke) or reactivate a scope: ``active`` toggle only."""
    active: bool