from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Enum, Boolean, CheckConstraint
from app.db.base_class import Base
from app.models.enums import AdminRole
import uuid
from sqlalchemy.dialects.postgresql import UUID


class AdminScope(Base):
    """Authoritative assignment of a scoped administrative role (Phase 23.11).

    One row per (user, role, scope-target). A user may hold multiple scopes
    (e.g. CLASS_ADMIN for section A + CLASS_ADMIN for section B, or
    ELECTIVE_ADMIN for BCS-054 + BCS-058). Legacy ``users.role == ADMIN``
    is resolved as HEAD_ADMIN (global) and does NOT require an ``admin_scopes``
    row.

    Role-scope consistency (enforced by CHECK constraint below):
      - HEAD_ADMIN:        section_id, subsection_id, subject_id must ALL be NULL.
      - CLASS_ADMIN:       section_id must be set (subsection_id, subject_id NULL).
      - SUBSECTION_ADMIN:  subsection_id must be set (section_id, subject_id NULL).
      - ELECTIVE_ADMIN:    subject_id must be set (section_id, subsection_id NULL).

    ``active`` is a DB-level toggle: an inactive scope is treated as
    nonexistent by every authorization gate. Deactivation is the canonical
    deprovisioning path (never delete rows outright).
    """

    __tablename__ = "admin_scopes"
    __table_args__ = (
        CheckConstraint(
            "CASE role "
            "  WHEN 'HEAD_ADMIN' THEN "
            "    section_id IS NULL AND subsection_id IS NULL AND subject_id IS NULL "
            "  WHEN 'CLASS_ADMIN' THEN "
            "    section_id IS NOT NULL AND subsection_id IS NULL AND subject_id IS NULL "
            "  WHEN 'SUBSECTION_ADMIN' THEN "
            "    subsection_id IS NOT NULL AND section_id IS NULL AND subject_id IS NULL "
            "  WHEN 'ELECTIVE_ADMIN' THEN "
            "    subject_id IS NOT NULL AND section_id IS NULL AND subsection_id IS NULL "
            "END",
            name="ck_admin_scopes_role_scope",
        ),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    role: Mapped[AdminRole] = mapped_column(Enum(AdminRole))
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sections.id"), nullable=True
    )
    subsection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subsections.id"), nullable=True
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # Relationship back to the user (the admin who holds this scope).
    user: Mapped["User"] = relationship(back_populates="admin_scopes")