"""
Scoped, read-only student queries for the Admin Portal (Phase 24.3).

Every method is a bounded SELECT over the authoritative tables — no row
materialization for counting, no N+1 (the list joins Section/Subsection once
and applies LIMIT/OFFSET). Nothing here mutates state and nothing re-implements
attendance, eligibility, or elective mathematics: placement and enrollment
composition come from the canonical tables, and the detail read delegates to
``StudentContextService`` (the single context authority).

Scope filtering is applied here as data, but the AUTHORIZATION decision
(which section_ids / subject_ids the caller may see) is made by
``AdminStudentService`` from ``AuthorizationService`` active scopes — never
from client input.
"""

from typing import Optional, Set, List
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import StudentElectiveChoice
from app.models.user import User, Section, Subsection
from app.models.enums import UserRole


class StudentScopeFilter:
    """Resolved admin scope for student reads (Phase 24.3).

    ``is_global`` (HEAD_ADMIN) bypasses all filters. Otherwise the visible
    students are the UNION of:
      - students whose section_id is in ``section_ids`` (CLASS_ADMIN scopes), and
      - students holding a StudentElectiveChoice for a subject_id in
        ``subject_ids`` (ELECTIVE_ADMIN scopes).
    A SUBSECTION_ADMIN-only caller resolves to empty sets -> conservative
    empty result (no authoritative subsection data exists). Never client-trusted.
    """

    __slots__ = ("is_global", "section_ids", "subject_ids")

    def __init__(
        self,
        is_global: bool = False,
        section_ids: Optional[Set[UUID]] = None,
        subject_ids: Optional[Set[UUID]] = None,
    ):
        self.is_global = is_global
        self.section_ids = section_ids or set()
        self.subject_ids = subject_ids or set()

    @property
    def is_restricted(self) -> bool:
        return not self.is_global


class AdminStudentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # List / search (bounded, scope-filtered)
    # ------------------------------------------------------------------
    async def count_students(
        self,
        scope: StudentScopeFilter,
        q: Optional[str] = None,
    ) -> int:
        stmt = select(func.count(func.distinct(User.id))).select_from(User)
        stmt = self._apply_scope_filter(stmt, scope)
        stmt = self._apply_search(stmt, q)
        result = await self.db.execute(stmt)
        return int(result.scalar_one())

    async def search_students(
        self,
        scope: StudentScopeFilter,
        q: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[dict]:
        """Bounded list of student summaries (roll, name, placement names).
        One query with outer joins to Section/Subsection and the elective-
        roster EXISTS; no N+1."""
        stmt = (
            select(
                User.id,
                User.roll_number,
                User.name,
                Section.name.label("section_name"),
                Section.program,
                Subsection.name.label("subsection_name"),
            )
            .select_from(User)
            .outerjoin(Section, Section.id == User.section_id)
            .outerjoin(Subsection, Subsection.id == User.subsection_id)
            .where(User.role == UserRole.STUDENT)
        )
        stmt = self._apply_scope_filter(stmt, scope)
        stmt = self._apply_search(stmt, q)
        stmt = stmt.order_by(User.roll_number).limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        rows = []
        for row in result.all():
            rows.append({
                "id": row.id,
                "roll_number": row.roll_number,
                "name": row.name,
                "section_name": row.section_name,
                "program": row.program,
                "subsection_name": row.subsection_name,
                "is_placed": row.section_name is not None,
            })
        return rows

    def _apply_scope_filter(self, stmt, scope: StudentScopeFilter):
        if scope.is_global:
            return stmt
        predicates = []
        if scope.section_ids:
            predicates.append(User.section_id.in_(scope.section_ids))
        if scope.subject_ids:
            predicates.append(
                User.id.in_(
                    select(StudentElectiveChoice.user_id).where(
                        StudentElectiveChoice.subject_id.in_(scope.subject_ids)
                    )
                )
            )
        if not predicates:
            # Restricted scope with nothing to match (e.g. SUBSECTION_ADMIN-only
            # or an admin whose scopes are all inactive) -> conservative empty.
            return stmt.where(False)
        return stmt.where(or_(*predicates))

    def _apply_search(self, stmt, q: Optional[str]):
        if q is None or not q.strip():
            return stmt
        term = f"%{q.strip()}%"
        return stmt.where(
            or_(
                User.roll_number.ilike(term),
                User.name.ilike(term),
            )
        )

    # ------------------------------------------------------------------
    # Detail support
    # ------------------------------------------------------------------
    async def get_student(self, student_id: UUID) -> Optional[User]:
        """The target student row (STUDENT role) if it exists."""
        result = await self.db.execute(
            select(User).where(User.id == student_id, User.role == UserRole.STUDENT)
        )
        return result.scalars().first()

    async def student_is_in_elective_roster(
        self, student_id: UUID, subject_ids: Set[UUID]
    ) -> bool:
        """True when the student holds a StudentElectiveChoice for any of the
        given concrete subjects (the ELECTIVE_ADMIN roster membership rule —
        one choice per slot; never slot-collapsed)."""
        if not subject_ids:
            return False
        result = await self.db.execute(
            select(func.count()).select_from(StudentElectiveChoice).where(
                StudentElectiveChoice.user_id == student_id,
                StudentElectiveChoice.subject_id.in_(subject_ids),
            )
        )
        return int(result.scalar_one()) > 0
