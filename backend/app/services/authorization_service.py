"""
Authoritative backend authorization service (Phase 23.11 — API Scope &
Authorization).

Every administrative decision resolves the user's effective role and academic
scope from PostgreSQL state on every request. NEVER from the JWT, request
body, query parameters, or frontend state.

Effective administrative authority is the union of:
  - the legacy ``users.role == ADMIN`` (resolved as HEAD_ADMIN — global), and
  - the ACTIVE rows in ``admin_scopes``.

Role semantics (see ``AdminRole``):
  - HEAD_ADMIN:      global authority.
  - CLASS_ADMIN:     only the assigned section(s) — a subject is within scope
                     when it belongs to the assigned section's semester.
  - SUBSECTION_ADMIN: only the assigned subsection(s) — INERT today: no
                     authoritative subsection data exists (subsections table
                     empty, users.subsection_id NULL), so no resource can be
                     proven inside a subsection scope and the check denies.
  - ELECTIVE_ADMIN:  only the assigned concrete elective subject(s) — never a
                     collapsed "all electives" scope.

Scope checks are composable and reusable by the API dependency layer and by
services (e.g. the event mutation gate). No duplicate academic resolver is
introduced: subject/section/semester relationships are read directly from the
authoritative tables (subjects.semester_id, sections.semester_id).
"""

from typing import List, Optional, Set
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, Section
from app.models.admin_scope import AdminScope
from app.models.academic import Subject
from app.models.enums import AdminRole, UserRole


class AuthorizationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Scope loading
    # ------------------------------------------------------------------
    async def get_active_scopes(self, user_id: UUID) -> List[AdminScope]:
        """Active (non-revoked) admin_scopes rows for a user. One query."""
        if user_id is None:
            return []
        result = await self.db.execute(
            select(AdminScope).where(
                AdminScope.user_id == user_id,
                AdminScope.active.is_(True),
            )
        )
        return list(result.scalars().all())

    @staticmethod
    def _legacy_role(user: User) -> Set[AdminRole]:
        """Legacy users.role == ADMIN resolves as HEAD_ADMIN (global)."""
        if user is not None and user.role == UserRole.ADMIN:
            return {AdminRole.HEAD_ADMIN}
        return set()

    async def effective_admin_roles(self, user: User) -> Set[AdminRole]:
        """The set of effective administrative roles (legacy + active scopes)."""
        roles: Set[AdminRole] = set(self._legacy_role(user))
        if user is not None and user.id is not None:
            scopes = await self.get_active_scopes(user.id)
            roles.update(s.role for s in scopes)
        return roles

    async def is_head_admin(self, user: User) -> bool:
        return AdminRole.HEAD_ADMIN in await self.effective_admin_roles(user)

    # ------------------------------------------------------------------
    # Scope checks
    # ------------------------------------------------------------------
    async def can_access_section(self, user: User, section_id: Optional[UUID]) -> bool:
        """HEAD_ADMIN: anything. CLASS_ADMIN: an active scope for that section.
        SUBSECTION_ADMIN / ELECTIVE_ADMIN: NOT automatically granted section
        authority (an explicit scope row is required)."""
        if await self.is_head_admin(user):
            return True
        scopes = await self.get_active_scopes(user.id)
        return any(
            s.role == AdminRole.CLASS_ADMIN
            and s.section_id is not None
            and s.section_id == section_id
            for s in scopes
        )

    async def can_access_subsection(self, user: User, subsection_id: Optional[UUID]) -> bool:
        """HEAD_ADMIN: anything. SUBSECTION_ADMIN: an active scope for that
        subsection. Others: NOT automatically granted.

        NOTE (structural limitation): no authoritative subsection data exists,
        so no student/session/timetable resource can be proven to belong to a
        subsection; this check is therefore conservative (denies) until a
        subsection-scoped scheduling schema decision lands."""
        if await self.is_head_admin(user):
            return True
        scopes = await self.get_active_scopes(user.id)
        return any(
            s.role == AdminRole.SUBSECTION_ADMIN
            and s.subsection_id is not None
            and s.subsection_id == subsection_id
            for s in scopes
        )

    async def can_access_subject(self, user: User, subject_id: Optional[UUID]) -> bool:
        """HEAD_ADMIN: anything. ELECTIVE_ADMIN: an active scope for that
        concrete subject. CLASS_ADMIN: a subject that belongs to the assigned
        section's semester (sections.semester_id == subjects.semester_id).
        SUBSECTION_ADMIN: NOT automatically granted subject authority."""
        if await self.is_head_admin(user):
            return True
        if subject_id is None:
            return False
        scopes = await self.get_active_scopes(user.id)
        elective_ok = any(
            s.role == AdminRole.ELECTIVE_ADMIN
            and s.subject_id is not None
            and s.subject_id == subject_id
            for s in scopes
        )
        if elective_ok:
            return True
        class_scopes = [s for s in scopes if s.role == AdminRole.CLASS_ADMIN and s.section_id is not None]
        if class_scopes:
            # Resolve the subject's semester once; a CLASS_ADMIN covers the
            # subjects of their section's semester.
            subject = (await self.db.execute(
                select(Subject).where(Subject.id == subject_id)
            )).scalars().first()
            if subject is None:
                return False
            result = await self.db.execute(
                select(Section.id).where(
                    Section.id.in_([s.section_id for s in class_scopes]),
                    Section.semester_id == subject.semester_id,
                )
            )
            return result.scalars().first() is not None
        return False

    # ------------------------------------------------------------------
    # Event-mutation authorization (used by EventService — Phase 23.11)
    # ------------------------------------------------------------------
    async def can_mutate_event(
        self,
        user: User,
        *,
        subject_id: Optional[UUID],
        elective_slot_is_set: bool,
        student_creatable: bool,
    ) -> str:
        """Authorization decision for an event mutation.

        Returns "authorized" (admin scope satisfied), "student" (fall through
        to the existing enrollment check), or raises no exception here — the
        caller raises the appropriate EventForbidden.

        Rules:
          - elective-slot events and global/closure/quiz-schedule events:
            HEAD_ADMIN only.
          - subject-scoped events: an effective admin is authorized only when
            the concrete subject is inside their scope (ELECTIVE_ADMIN subject
            match / CLASS_ADMIN section-semester match / HEAD_ADMIN anything).
          - non-admin: "student" -> the caller applies the enrollment rule.
        """
        roles = await self.effective_admin_roles(user)
        is_admin = bool(roles)

        if elective_slot_is_set or subject_id is None:
            # Slot-wide / global events require global authority.
            return "authorized" if AdminRole.HEAD_ADMIN in roles else "denied"

        if is_admin:
            if await self.can_access_subject(user, subject_id):
                return "authorized"
            return "denied"

        if student_creatable:
            return "student"
        return "denied"