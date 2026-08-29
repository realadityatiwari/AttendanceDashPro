from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class AdminScopeDescriptor(BaseModel):
    """Presentation-only descriptor of ONE active admin_scopes row
    (Phase 24.1). Resolved names are read-only context for the Admin Portal
    shell; authorization itself always remains server-side
    (AuthorizationService). HEAD_ADMIN rows carry no scope target (global)."""
    role: str
    section_name: Optional[str] = None
    subsection_name: Optional[str] = None
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None


class AdminIdentity(BaseModel):
    """Read-only administrative identity for GET /api/v1/admin/me
    (Phase 24.1).

    ``roles`` is the DB-resolved union of the legacy ``users.role == ADMIN``
    (HEAD_ADMIN) and the ACTIVE admin_scopes roles. ``is_global`` is True only
    when HEAD_ADMIN is effective. This contract is PRESENTATION data: the
    frontend may render it but is never an authorization boundary — every
    admin endpoint re-resolves authority server-side per request.
    """
    id: UUID
    display_name: str
    roll_number: Optional[str] = None
    roles: list[str]
    is_global: bool
    scopes: list[AdminScopeDescriptor]
