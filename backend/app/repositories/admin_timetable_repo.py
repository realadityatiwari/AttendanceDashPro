"""
Phase 24.7-B — Admin Timetable Repository.

Bounded, scope-aware queries over the authoritative timetable domain
(``timetable_entries`` — the EXPECTED academic schedule, distinct from actual
``class_sessions`` occurrences).

Design rules:
  - Every read method accepts OPTIONAL academic-scope filters
    (``section_ids`` / ``subject_ids`` / ``subsection_ids``).  ``None`` means
    "no restriction" (used by HEAD_ADMIN); the SERVICE derives the filter sets
    from the acting user's DB-resolved scopes (Phase 23.11) — never from the
    client.  Phase 24.7-C wires the HTTP layer on top of these filters.
  - Conflict-candidate retrieval is intentionally bounded: only ACTIVE entries
    of the SAME section and SAME day are materialized (a section's weekly
    timetable is small); the deterministic conflict predicate lives in the
    service so the semantics are explicit and unit-testable.
  - No authorization decisions, no attendance/elective mathematics here.
"""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.timetable import TimetableEntry
from app.models.user import Section, Subsection
from app.models.academic import Subject


class AdminTimetableRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Timetable entries
    # ------------------------------------------------------------------

    async def list_entries(
        self,
        *,
        section_ids: Optional[List[UUID]] = None,
        subject_ids: Optional[List[UUID]] = None,
        day_of_week: Optional[int] = None,
        include_inactive: bool = False,
    ) -> List[TimetableEntry]:
        """Bounded scoped list.  ``section_ids`` / ``subject_ids`` are the
        server-derived scope filters (None = unrestricted).  Entries are
        deterministically ordered: day, then sort_order (NULLs last), then
        start_time, then id — the id tiebreak guarantees total order."""
        stmt = (
            select(TimetableEntry)
            .options(
                selectinload(TimetableEntry.subject),
                selectinload(TimetableEntry.section),
                selectinload(TimetableEntry.subsection),
            )
            .order_by(
                TimetableEntry.day_of_week,
                TimetableEntry.sort_order.nulls_last(),
                TimetableEntry.start_time,
                TimetableEntry.id,
            )
        )
        if section_ids is not None:
            stmt = stmt.where(TimetableEntry.section_id.in_(section_ids))
        if subject_ids is not None:
            stmt = stmt.where(TimetableEntry.subject_id.in_(subject_ids))
        if day_of_week is not None:
            stmt = stmt.where(TimetableEntry.day_of_week == day_of_week)
        if not include_inactive:
            stmt = stmt.where(TimetableEntry.is_active.is_(True))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_entry(self, entry_id: UUID) -> Optional[TimetableEntry]:
        result = await self.db.execute(
            select(TimetableEntry)
            .options(
                selectinload(TimetableEntry.subject),
                selectinload(TimetableEntry.section),
                selectinload(TimetableEntry.subsection),
            )
            .where(TimetableEntry.id == entry_id)
        )
        return result.scalars().first()

    async def list_active_conflict_candidates(
        self, section_id: UUID, day_of_week: int, exclude_id: Optional[UUID] = None
    ) -> List[TimetableEntry]:
        """All ACTIVE entries in the same section on the same day (bounded —
        a section's weekly timetable is small).  The service applies the
        deterministic conflict predicate (scope/elective/time semantics)."""
        stmt = (
            select(TimetableEntry)
            .options(selectinload(TimetableEntry.subject))
            .where(
                TimetableEntry.section_id == section_id,
                TimetableEntry.day_of_week == day_of_week,
                TimetableEntry.is_active.is_(True),
            )
        )
        if exclude_id is not None:
            stmt = stmt.where(TimetableEntry.id != exclude_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_entries_for_section(self, section_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(TimetableEntry).where(
                TimetableEntry.section_id == section_id
            )
        )
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Academic context lookups (validation support)
    # ------------------------------------------------------------------

    async def get_section(self, section_id: UUID) -> Optional[Section]:
        result = await self.db.execute(
            select(Section).where(Section.id == section_id)
        )
        return result.scalars().first()

    async def get_subsection(self, subsection_id: UUID) -> Optional[Subsection]:
        result = await self.db.execute(
            select(Subsection).where(Subsection.id == subsection_id)
        )
        return result.scalars().first()

    async def get_subject(self, subject_id: UUID) -> Optional[Subject]:
        result = await self.db.execute(
            select(Subject).where(Subject.id == subject_id)
        )
        return result.scalars().first()

    async def list_sections_by_ids(self, section_ids: List[UUID]) -> List[Section]:
        if not section_ids:
            return []
        result = await self.db.execute(
            select(Section).where(Section.id.in_(section_ids))
        )
        return list(result.scalars().all())

    async def list_subjects_by_ids(self, subject_ids: List[UUID]) -> List[Subject]:
        if not subject_ids:
            return []
        result = await self.db.execute(
            select(Subject).where(Subject.id.in_(subject_ids))
        )
        return list(result.scalars().all())
