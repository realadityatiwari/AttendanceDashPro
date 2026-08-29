"""
Phase 24.5 — Admin Structure Repository.

Bounded, read-only (for reads) and transactional (for mutations) queries
over the academic hierarchy tables:
  AcademicSession -> Semester -> Section -> Subsection

All queries use the async SQLAlchemy session passed from the service.
No authorization decisions are made here — that is the service/endpoint layer.
No attendance / enrollment / elective mathematics are re-implemented.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import AcademicSession, Semester
from app.models.user import Section, Subsection, User


class AdminStructureRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # AcademicSession
    # ------------------------------------------------------------------

    async def list_sessions(self) -> List[AcademicSession]:
        """All sessions ordered by start_date descending (newest first)."""
        result = await self.db.execute(
            select(AcademicSession).order_by(AcademicSession.start_date.desc())
        )
        return list(result.scalars().all())

    async def get_session(self, session_id: UUID) -> Optional[AcademicSession]:
        result = await self.db.execute(
            select(AcademicSession).where(AcademicSession.id == session_id)
        )
        return result.scalars().first()

    async def get_active_session(self) -> Optional[AcademicSession]:
        result = await self.db.execute(
            select(AcademicSession).where(AcademicSession.is_active.is_(True))
        )
        return result.scalars().first()

    async def count_semesters_for_session(self, session_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Semester).where(Semester.session_id == session_id)
        )
        return result.scalar_one()

    async def session_name_exists(self, name: str, exclude_id: Optional[UUID] = None) -> bool:
        stmt = select(func.count()).select_from(AcademicSession).where(
            AcademicSession.name == name
        )
        if exclude_id is not None:
            stmt = stmt.where(AcademicSession.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    # ------------------------------------------------------------------
    # Semester
    # ------------------------------------------------------------------

    async def list_semesters(self, session_id: UUID) -> List[Semester]:
        result = await self.db.execute(
            select(Semester).where(Semester.session_id == session_id)
            .order_by(Semester.start_date)
        )
        return list(result.scalars().all())

    async def get_semester(self, semester_id: UUID) -> Optional[Semester]:
        result = await self.db.execute(
            select(Semester).where(Semester.id == semester_id)
        )
        return result.scalars().first()

    async def count_sections_for_semester(self, semester_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Section).where(Section.semester_id == semester_id)
        )
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Section
    # ------------------------------------------------------------------

    async def list_sections(self, semester_id: UUID) -> List[Section]:
        result = await self.db.execute(
            select(Section).where(Section.semester_id == semester_id)
            .order_by(Section.name)
        )
        return list(result.scalars().all())

    async def get_section(self, section_id: UUID) -> Optional[Section]:
        result = await self.db.execute(
            select(Section).where(Section.id == section_id)
        )
        return result.scalars().first()

    async def section_name_exists(
        self, semester_id: UUID, name: str, exclude_id: Optional[UUID] = None
    ) -> bool:
        stmt = select(func.count()).select_from(Section).where(
            Section.semester_id == semester_id,
            Section.name == name,
        )
        if exclude_id is not None:
            stmt = stmt.where(Section.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    async def count_subsections_for_section(self, section_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Subsection).where(Subsection.section_id == section_id)
        )
        return result.scalar_one()

    async def count_students_for_section(self, section_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(User.section_id == section_id)
        )
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Subsection
    # ------------------------------------------------------------------

    async def list_subsections(self, section_id: UUID) -> List[Subsection]:
        result = await self.db.execute(
            select(Subsection).where(Subsection.section_id == section_id)
            .order_by(Subsection.name)
        )
        return list(result.scalars().all())

    async def get_subsection(self, subsection_id: UUID) -> Optional[Subsection]:
        result = await self.db.execute(
            select(Subsection).where(Subsection.id == subsection_id)
        )
        return result.scalars().first()

    async def subsection_name_exists(
        self, section_id: UUID, name: str, exclude_id: Optional[UUID] = None
    ) -> bool:
        stmt = select(func.count()).select_from(Subsection).where(
            Subsection.section_id == section_id,
            Subsection.name == name,
        )
        if exclude_id is not None:
            stmt = stmt.where(Subsection.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.scalar_one() > 0

    async def count_students_for_subsection(self, subsection_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(User.subsection_id == subsection_id)
        )
        return result.scalar_one()
