from typing import List, Optional
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.event import AcademicEvent

class CalendarRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_events(
        self,
        active: Optional[bool] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        upcoming: bool = False,
    ) -> List[AcademicEvent]:
        """
        Returns academic events, optionally filtered.

        - active: when not None, restrict to events whose `active` flag equals
          this value. Existing internal callers (dashboard/eligibility) rely on
          the default (None = no filter) and apply their own semantics.
        - date_from/date_to: inclusive range-overlap filters. An event is
          included when its [start_date, end_date] range overlaps the requested
          [date_from, date_to] range (event.start_date <= date_to AND
          event.end_date >= date_from).
        - upcoming: restrict to events whose end_date is today or later.
        """
        stmt = select(AcademicEvent).order_by(AcademicEvent.start_date)
        if active is not None:
            stmt = stmt.where(AcademicEvent.active.is_(active))
        if date_from is not None:
            stmt = stmt.where(AcademicEvent.end_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(AcademicEvent.start_date <= date_to)
        if upcoming:
            stmt = stmt.where(AcademicEvent.end_date >= date.today())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
