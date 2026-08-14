from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.engines.calendar_engine import get_academic_day, AcademicDay, DEFAULT_WEEKENDS
from app.repositories.calendar_repo import CalendarRepository
from app.repositories.user_repo import UserRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.models.user import User
from app.schemas.calendar import CalendarMonthResponse, CalendarDayItem, AcademicEventResponse

class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CalendarRepository(db)
        self.user_repo = UserRepository(db)
        self.attendance_repo = AttendanceRepository(db)

    async def get_day_schedule(self, target_date: date) -> AcademicDay:
        events = await self.repo.get_all_events()
        # Single source of truth from the calendar engine (JS getDay() indices:
        # 0=Sunday, 6=Saturday). Previously a local [5, 6] (Python weekday
        # indices) was passed here, which the engine interpreted as JS indices
        # and caused Friday to resolve non-working and Sunday working.
        return get_academic_day(target_date, events, DEFAULT_WEEKENDS)

    @staticmethod
    def _month_bounds(year: int, month: int) -> tuple:
        """First and last day of the requested month (server-computed)."""
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year, 12, 31)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)
        return month_start, month_end

    @staticmethod
    def _non_working_reason(day: AcademicDay) -> Optional[str]:
        """
        Render-only explanation for a non-working day, derived exclusively from
        the calendar engine's AcademicDay output (no reimplementation of
        weekday/closure logic): dominant active event title when an event is
        active on the day, otherwise 'Weekend'. None for working days.
        """
        if day.is_working_day:
            return None
        if day.events:
            return day.events[0].event_type.value.replace("_", " ").title()
        return "Weekend"

    async def get_month_view(self, user: User, year: int, month: int) -> CalendarMonthResponse:
        """
        Month-bounded calendar read model for the authenticated student.

        - Resolves the student's real academic semester bounds through the
          same academic-context repository /student/me, Track and History use
          (never hardcoded dates).
        - Clamps the requested month to the semester:
              effective_start = max(month_start, semester_start)
              effective_end   = min(month_end, semester_end)
          An empty intersection (month entirely outside the semester) yields an
          inverted effective range and an empty `days` list — no invented dates.
        - Day resolution (weekends via DEFAULT_WEEKENDS, academic closures,
          active-event effects) is delegated to the calendar engine; active
          events are fetched once for the effective range with the Phase 6.1
          /events semantics (active only, date-range overlap).
        - Session counts reuse the enrollment-scoped get_sessions_with_status
          (Phase 6.1) — one query for the whole range, grouped by date.
          No attendance/quiz mathematics are computed here.
        """
        context = await self.user_repo.get_academic_context(user)
        semester_start: Optional[date] = context.get("semester_start")
        semester_end: Optional[date] = context.get("semester_end")

        month_start, month_end = self._month_bounds(year, month)

        # No academic context (user without a section/semester): nothing to
        # render — return a truthful empty result with null bounds.
        if semester_start is None or semester_end is None:
            return CalendarMonthResponse(
                year=year,
                month=month,
                semester_start=None,
                semester_end=None,
                effective_start=None,
                effective_end=None,
                days=[],
            )

        effective_start = max(month_start, semester_start)
        effective_end = min(month_end, semester_end)

        # Month lies entirely outside the semester: truthful empty result.
        if effective_start > effective_end:
            return CalendarMonthResponse(
                year=year,
                month=month,
                semester_start=semester_start,
                semester_end=semester_end,
                effective_start=effective_start,
                effective_end=effective_end,
                days=[],
            )

        # Bounded reads: active events overlapping the effective range + the
        # student's scheduled sessions for the range (enrollment-scoped).
        events = await self.repo.get_all_events(
            active=True, date_from=effective_start, date_to=effective_end
        )
        session_rows = await self.attendance_repo.get_sessions_with_status(
            user.id, effective_start, effective_end
        )

        counts_by_date: Dict[date, int] = {}
        for row in session_rows:
            counts_by_date[row["date"]] = counts_by_date.get(row["date"], 0) + 1

        days: List[CalendarDayItem] = []
        current = effective_start
        while current <= effective_end:
            day = get_academic_day(current, events, DEFAULT_WEEKENDS)
            days.append(CalendarDayItem(
                date=day.date,
                is_working_day=day.is_working_day,
                day_type=day.day_type,
                is_teaching_day=day.is_teaching_day,
                original_day_of_week=day.original_day_of_week,
                substitution_schedule_override=day.substitution_schedule_override,
                non_working_reason=self._non_working_reason(day),
                events=[AcademicEventResponse.model_validate(e) for e in day.events],
                session_count=counts_by_date.get(current, 0),
            ))
            current += timedelta(days=1)

        return CalendarMonthResponse(
            year=year,
            month=month,
            semester_start=semester_start,
            semester_end=semester_end,
            effective_start=effective_start,
            effective_end=effective_end,
            days=days,
        )
