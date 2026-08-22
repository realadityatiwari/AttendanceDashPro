from datetime import date, timedelta
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.user_repo import UserRepository
from app.repositories.quiz_repo import QuizRepository
from app.repositories.calendar_repo import CalendarRepository
from app.services.attendance_service import AttendanceService
from app.services.eligibility_service import EligibilityService
from app.services.calendar_service import CalendarService
from app.engines.attendance_engine import (
    ATTENDANCE_TARGET_PCT,
    WATCH_BAND_PCT,
    SAFE_BAND_PCT,
    classify_attendance_status,
)
from app.engines.practical_occurrence import occurrence_is_cancelled
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    TodaySection,
    DashboardClassItem,
    OverallSection,
    WeeklySection,
    WeekDayItem,
    SubjectBrief,
    QuizSnapshotSection,
    AttentionItem,
    UpcomingEventItem,
)
from app.models.academic import Semester, Subject
from app.models.user import Section
from app.models.enums import AttendanceStatus

# DAY_LABELS + banding constants/functions now live in the canonical
# attendance engine (single definition; dashboard + analytics + subject
# summaries all consume it).
DAY_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

class DashboardService:
    """
    Read-only aggregation for the Home dashboard.

    This service is a consumer of the existing attendance/eligibility/calendar
    systems. It does not re-implement attendance mathematics: per-subject
    percentages come from AttendanceService (attendance_engine), quiz
    eligibility comes from EligibilityService (eligibility_engine), and the
    day/event context comes from CalendarService (calendar_engine).
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.attendance_repo = AttendanceRepository(db)
        self.user_repo = UserRepository(db)
        self.quiz_repo = QuizRepository(db)
        self.calendar_repo = CalendarRepository(db)
        self.attendance_service = AttendanceService(db)
        self.eligibility_service = EligibilityService(db)
        self.calendar_service = CalendarService(db)

    async def get_summary(self, user) -> DashboardSummaryResponse:
        today = date.today()
        subjects = await self.user_repo.get_enrolled_subjects(user.id)

        semester_start = None
        if user.section_id is not None:
            section = await self.db.get(Section, user.section_id)
            if section is not None and section.semester_id is not None:
                semester = await self.db.get(Semester, section.semester_id)
                if semester is not None:
                    semester_start = semester.start_date

        # Phase 8.1 N+1 fix: ONE enrollment-scoped range scan feeds the Today /
        # Overall / Weekly sections (previously up to four overlapping scans).
        # The scan starts at the earliest bound any section needs (semester
        # start, or the previous week when the semester bound is unknown) and
        # each builder slices its own date window from the shared rows.
        prev_week_start = today - timedelta(days=today.weekday() + 7)
        # Earliest bound any section needs: the semester start (overall) and
        # the previous week (weekly delta). The strict min covers both; each
        # builder re-applies its own bound.
        scan_start = min(semester_start, prev_week_start) if semester_start is not None else prev_week_start
        rows = await self.attendance_repo.get_sessions_with_status(user.id, scan_start, today)

        summaries = await self._subject_summaries(user.id, subjects, today)

        return DashboardSummaryResponse(
            generated_at=today,
            today=await self._build_today(user.id, today, rows),
            overall=self._build_overall(rows, today, semester_start),
            weekly=self._build_weekly(rows, today, summaries),
            quiz_snapshot=await self._build_quiz_snapshot(user, subjects, semester_start),
            attention_required=self._build_attention_required(subjects, summaries),
            upcoming_events=await self._build_upcoming_events(subjects),
        )

    async def _subject_summaries(self, user_id, subjects: List[Subject], as_of_date: date):
        """Per-subject statistics via the existing AttendanceService (engine-owned).
        Phase 8.1 N+1 fix: one grouped count query replaces one query per subject;
        each summary is built by the identical canonical engine path."""
        applicable = [s for s in subjects if s.attendance_applicable]
        summaries_map = await self.attendance_service.get_subject_summaries(
            user_id=user_id,
            subjects=applicable,
            as_of_date=as_of_date,
        )
        return [(s, summaries_map[s.id]) for s in applicable]

    async def _build_today(self, user_id, today: date, rows) -> TodaySection:
        day = await self.calendar_service.get_day_schedule(today)

        classes: List[DashboardClassItem] = []
        attended = 0
        total = 0
        for r in rows:
            if r["date"] != today:
                continue
            if r["is_cancelled"]:
                status = "CANCELLED"
            elif r["status"] is not None:
                status = r["status"].value.upper()
            else:
                status = "PENDING"

            classes.append(DashboardClassItem(
                session_id=r["id"],
                subject_code=r["subject_code"],
                subject_name=r["subject_name"],
                class_type=r["class_type"],
                status=status,
                is_extra=r["is_extra"],
            ))
            if status == "ATTENDED":
                attended += 1
            if status != "CANCELLED":
                total += 1

        day_note = None
        if day.events:
            day_note = day.events[0].event_type.value.replace('_', ' ').title()

        return TodaySection(
            date=today,
            is_working_day=day.is_working_day,
            is_teaching_day=day.is_teaching_day,
            day_note=day_note,
            classes=classes,
            attended=attended,
            total=total,
        )

    def _build_overall(self, rows, today: date, semester_start: Optional[date]) -> OverallSection:
        start = semester_start if semester_start is not None else today
        # Preserve the per-section date bound (semester start, or today when
        # the semester bound is unknown) exactly as the pre-batch query did:
        # every aggregate in this section counts only rows >= start.
        section_rows = [r for r in rows if r["date"] >= start]

        attended = 0
        missed = 0
        pending = 0
        for r in section_rows:
            # Cancelled sessions are their own state — never pending
            # (Phase 6.6 event->session integration).
            if r["is_cancelled"]:
                continue
            if r["status"] == AttendanceStatus.ATTENDED:
                attended += 1
            elif r["status"] == AttendanceStatus.MISSED:
                missed += 1
            else:
                pending += 1

        recorded = attended + missed
        overall_pct = (attended / recorded * 100.0) if recorded > 0 else None

        week_start = today - timedelta(days=today.weekday())
        this_week = self._aggregate_range(section_rows, week_start, today)
        prev_week = self._aggregate_range(section_rows, week_start - timedelta(days=7), week_start - timedelta(days=1))

        weekly_delta = None
        if this_week is not None and prev_week is not None:
            weekly_delta = this_week - prev_week

        return OverallSection(
            semester_start=semester_start,
            overall_pct=overall_pct,
            attended=attended,
            recorded=recorded,
            pending=pending,
            status=classify_attendance_status(overall_pct),
            weekly_delta_pct=weekly_delta,
        )

    @staticmethod
    def _aggregate_range(rows: List[dict], start: date, end: date) -> Optional[float]:
        """
        ERP-style weekly percentage (attended / conducted) over a date range.
        Returns None when nothing has been recorded in the range. Cancelled
        occurrences are never conducted classes: the canonical
        occurrence_is_cancelled rule excludes them (a cancelled theory class
        is never an absence even with a stale mark; a recorded lab block keeps
        its frozen record-wins rule).
        """
        attended = 0
        recorded = 0
        for r in rows:
            if not (start <= r["date"] <= end):
                continue
            if occurrence_is_cancelled(r):
                continue
            if r["status"] == AttendanceStatus.ATTENDED:
                attended += 1
                recorded += 1
            elif r["status"] == AttendanceStatus.MISSED:
                recorded += 1
        if recorded == 0:
            return None
        return attended / recorded * 100.0

    def _build_weekly(self, rows, today: date, summaries) -> WeeklySection:
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        prev_start = week_start - timedelta(days=7)
        prev_end = week_start - timedelta(days=1)

        # Slice the shared scan instead of issuing per-section queries.
        week_rows = [r for r in rows if week_start <= r["date"] <= week_end]
        prev_rows = [r for r in rows if prev_start <= r["date"] <= prev_end]

        days: List[WeekDayItem] = []
        for i in range(5):
            d = week_start + timedelta(days=i)
            day_classes = 0
            day_attended = 0
            day_recorded = 0
            for r in week_rows:
                if r["date"] != d:
                    continue
                # Cancelled sessions are not classes (matches Today's total).
                if r["is_cancelled"]:
                    continue
                day_classes += 1
                if r["status"] == AttendanceStatus.ATTENDED:
                    day_attended += 1
                    day_recorded += 1
                elif r["status"] == AttendanceStatus.MISSED:
                    day_recorded += 1
            days.append(WeekDayItem(
                date=d,
                day_label=DAY_LABELS[i],
                is_today=(d == today),
                is_future=(d > today),
                classes=day_classes,
                attended=day_attended,
                recorded=day_recorded,
            ))

        weekly_pct = self._aggregate_range(week_rows, week_start, week_end)
        previous_week_pct = self._aggregate_range(prev_rows, prev_start, prev_end)

        delta_pct = None
        if weekly_pct is not None and previous_week_pct is not None:
            delta_pct = weekly_pct - previous_week_pct

        best_subject = None
        needs_attention_subject = None
        for subject, summary in summaries:
            pct = summary.current_avg_pct
            if pct is None:
                continue
            if best_subject is None or pct > best_subject.pct:
                best_subject = SubjectBrief(subject_code=subject.code, subject_name=subject.name, pct=pct)
            if pct < ATTENDANCE_TARGET_PCT and (
                needs_attention_subject is None or pct < needs_attention_subject.pct
            ):
                needs_attention_subject = SubjectBrief(subject_code=subject.code, subject_name=subject.name, pct=pct)

        return WeeklySection(
            week_start=week_start,
            week_end=week_end,
            days=days,
            weekly_pct=weekly_pct,
            recorded=sum(d.recorded for d in days),
            previous_week_pct=previous_week_pct,
            delta_pct=delta_pct,
            best_subject=best_subject,
            needs_attention_subject=needs_attention_subject,
        )

    async def _build_quiz_snapshot(self, user, subjects: List[Subject], semester_start: Optional[date]) -> QuizSnapshotSection:
        quiz_applicable = [s for s in subjects if s.quiz_applicable]
        empty = QuizSnapshotSection()
        if not quiz_applicable:
            return empty

        # Phase 8.1 N+1 fix: one grouped effective-quiz-dates query + one
        # batched eligibility evaluation (single canonical engine path),
        # replacing the previous per-subject schedule + eligibility loops.
        # Quiz dates are authoritative from active QUIZ_DAY AcademicEvents
        # (Phase 2), with positional cycle ranks.
        effective_by_subject = await self.quiz_repo.get_effective_quiz_dates_for_subjects(
            [s.id for s in quiz_applicable]
        )
        resolved = [(cyc, d) for lst in effective_by_subject.values() for cyc, d in lst]
        future = [(cyc, d) for cyc, d in resolved if d >= date.today()]
        pick = min(future, key=lambda x: x[1]) if future else (max(resolved, key=lambda x: x[0]) if resolved else None)
        if pick is None:
            return empty

        cycle_number, quiz_date = pick
        cycle_model = await self.quiz_repo.get_quiz_cycle_with_policy(cycle_number)
        threshold = cycle_model.policy.lecture_threshold if cycle_model and cycle_model.policy else None

        results = await self.eligibility_service.get_quiz_eligibility_for_subjects(
            user_id=user.id,
            subjects=quiz_applicable,
            quiz_cycle=cycle_number,
            semester_start=semester_start,
        )
        eligible = 0
        attention = 0
        not_eligible = 0
        for result in results:
            if result.is_eligible:
                eligible += 1
            elif result.optimization is not None and result.optimization.is_reachable:
                attention += 1
            else:
                not_eligible += 1

        return QuizSnapshotSection(
            quiz_cycle=cycle_number,
            quiz_label=cycle_model.label if cycle_model else None,
            quiz_date=quiz_date,
            threshold=threshold,
            eligible=eligible,
            attention=attention,
            not_eligible=not_eligible,
            total_theory=len(quiz_applicable),
            has_snapshot=True,
        )

    def _build_attention_required(self, subjects: List[Subject], summaries) -> List[AttentionItem]:
        items: List[AttentionItem] = []
        for subject, summary in summaries:
            status = classify_attendance_status(summary.current_avg_pct)
            if status not in ("WATCH", "CRITICAL"):
                continue
            items.append(AttentionItem(
                subject_code=subject.code,
                subject_name=subject.name,
                current_pct=summary.current_avg_pct,
                forecast_pct=summary.forecast_avg_pct,
                status=status,
            ))
        items.sort(key=lambda x: (x.status == "CRITICAL", -(x.current_pct if x.current_pct is not None else 0)), reverse=True)
        return items

    async def _build_upcoming_events(self, subjects: List[Subject]) -> List[UpcomingEventItem]:
        today = date.today()
        enrolled_ids = {s.id for s in subjects}
        subject_by_id = {s.id: s for s in subjects}

        events = await self.calendar_repo.get_all_events()
        upcoming: List[UpcomingEventItem] = []
        for e in events:
            if not e.active or e.end_date < today:
                continue
            if e.subject_id is not None and e.subject_id not in enrolled_ids:
                continue
            subject = subject_by_id.get(e.subject_id) if e.subject_id else None
            upcoming.append(UpcomingEventItem(
                id=e.id,
                event_type=e.event_type,
                start_date=e.start_date,
                end_date=e.end_date,
                subject_code=subject.code if subject else None,
                subject_name=subject.name if subject else None,
                class_type=e.class_type,
            ))

        upcoming.sort(key=lambda x: (x.start_date, x.event_type.value))
        return upcoming[:4]