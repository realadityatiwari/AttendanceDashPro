from datetime import date, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.user_repo import UserRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.services.attendance_service import AttendanceService
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    OverallAnalytics,
    WeeklyAnalyticsItem,
    AnalyticsSubjectItem,
)
from app.models.user import User
from app.models.enums import AttendanceStatus
from app.engines.attendance_engine import classify_attendance_status
from app.engines.practical_occurrence import occurrence_is_cancelled

# Monday-start week bucketing for the weekly read model. A structure, not a
# product "trend" definition (Phase 8.0 contract §I/§J/§15).
WEEKDAY_MONDAY = 0


class AnalyticsService:
    """
    Phase 8.1 analytics read model (Phase 8.0 contract §L).

    This service is a PURE CONSUMER: overall/forecast/weekly sums come from one
    enrollment-scoped range scan of the canonical class_sessions +
    attendance_records rows (the same source the dashboard service uses), and
    per-subject analytics come from AttendanceService.get_subject_summaries
    (the canonical attendance engine). No attendance mathematics is reproduced
    here; the ERP overall and forecast formulas are exactly the frozen
    semantics (Phase 8.0 contract §7/§8).
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.attendance_repo = AttendanceRepository(db)
        self.attendance_service = AttendanceService(db)

    async def get_overview(self, user: User) -> AnalyticsOverviewResponse:
        today = date.today()
        context = await self.user_repo.get_academic_context(user)
        semester_start: Optional[date] = context.get("semester_start")
        semester_end: Optional[date] = context.get("semester_end")

        start = semester_start if semester_start is not None else today

        # ONE enrollment-scoped range scan feeds overall + forecast + weekly.
        rows = await self.attendance_repo.get_sessions_with_status(user.id, start, today)

        overall = self._overall(rows)
        weekly = self._weekly_series(rows, start, today)
        subjects = await self.user_repo.get_enrolled_subjects(user.id)
        summaries = await self.attendance_service.get_subject_summaries(user.id, subjects, today)

        subject_items: List[AnalyticsSubjectItem] = []
        for subject in subjects:
            if not subject.attendance_applicable:
                continue
            summary = summaries[subject.id]
            item = AnalyticsSubjectItem(
                **summary.model_dump(),
                subject_name=subject.name,
            )
            subject_items.append(item)

        return AnalyticsOverviewResponse(
            as_of=today,
            semester_start=semester_start,
            semester_end=semester_end,
            overall=overall,
            weekly=weekly,
            subjects=subject_items,
        )

    def _overall(self, rows: List[dict]) -> OverallAnalytics:
        """
        ERP overall (Phase 8.0 contract §7/§8):

          current_pct  = Σ attended / Σ recorded × 100   (recorded-only)
          forecast_pct = Σ (attended + pending) / Σ total × 100

        Cancelled sessions are their own state (excluded). Pending is never
        converted to absent. Not an average of subject percentages.
        """
        attended = 0
        missed = 0
        pending = 0
        cancelled = 0
        for r in rows:
            if occurrence_is_cancelled(r):
                cancelled += 1
                continue
            if r["status"] == AttendanceStatus.ATTENDED:
                attended += 1
            elif r["status"] == AttendanceStatus.MISSED:
                missed += 1
            else:
                pending += 1

        recorded = attended + missed
        total = attended + missed + pending

        current_pct = (attended / recorded * 100.0) if recorded > 0 else None
        forecast_pct = ((attended + pending) / total * 100.0) if total > 0 else None

        return OverallAnalytics(
            current_pct=current_pct,
            forecast_pct=forecast_pct,
            attended=attended,
            recorded=recorded,
            pending=pending,
            cancelled=cancelled,
            status=classify_attendance_status(current_pct),
        )

    def _weekly_series(self, rows: List[dict], start: date, today: date) -> List[WeeklyAnalyticsItem]:
        """
        Weekly read-model series (Phase 8.0 contract §I/§L-1): Monday-start weeks
        from the week of `start` through the week of `today`, bucketed with the
        same recorded-only ERP semantics. Weeks with no recorded classes are
        gaps (current_pct None). No trend/rolling/AT-RISK semantics.
        """
        week_start = start - timedelta(days=start.weekday())
        weeks: List[WeeklyAnalyticsItem] = []
        while week_start <= today:
            week_end = week_start + timedelta(days=6)
            attended = 0
            missed = 0
            pending = 0
            for r in rows:
                if not (week_start <= r["date"] <= week_end):
                    continue
                if occurrence_is_cancelled(r):
                    continue
                if r["status"] == AttendanceStatus.ATTENDED:
                    attended += 1
                elif r["status"] == AttendanceStatus.MISSED:
                    missed += 1
                else:
                    pending += 1
            recorded = attended + missed
            weeks.append(WeeklyAnalyticsItem(
                week_start=week_start,
                current_pct=(attended / recorded * 100.0) if recorded > 0 else None,
                attended=attended,
                recorded=recorded,
                pending=pending,
            ))
            week_start += timedelta(days=7)
        return weeks
