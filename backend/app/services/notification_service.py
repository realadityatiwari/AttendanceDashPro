from datetime import date, timedelta
import time
from typing import List, Optional, Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.user_repo import UserRepository
from app.repositories.calendar_repo import CalendarRepository
from app.repositories.preference_repo import PreferenceRepository
from app.services.attendance_service import AttendanceService, institution_today
from app.services.eligibility_service import EligibilityService
from app.services.elective_resolver import ElectiveResolver
from app.engines.attendance_engine import classify_attendance_status
from app.engines.practical_occurrence import occurrence_is_cancelled
from app.schemas.notification import NotificationItem, NotificationsResponse
from app.models.enums import NotificationKind, ElectiveSlot
from app.models.user import User
from app.models.notification import Notification
from app.models.academic import Subject
from app.repositories.notification_repo import NotificationRepository
from app.core.logging import get_logger

logger = get_logger("app.notification")

# Human-readable class-type labels for notification messages (presentation only).
_CLASS_TYPE_LABELS = {"L": "Lecture", "T": "Tutorial", "P": "Practical"}

# Phase B (2026-08-31): short-lived, per-user, in-process TTL cache for the
# notification inbox response.
_NOTIFICATION_CACHE_TTL_SECONDS = 60.0
_notification_cache: dict[UUID, tuple[float, NotificationsResponse]] = {}

# Phase 11C-P4: deep-link URLs for each notification kind.
_KIND_DEEP_LINKS: dict[NotificationKind, str] = {
    NotificationKind.CLASS_REMINDER: "/dashboard",
    NotificationKind.QUIZ_APPROACHING: "/tools/quiz-schedule",
    NotificationKind.ATTENDANCE_THRESHOLD: "/history",
    NotificationKind.MUST_ATTEND: "/history",
    NotificationKind.SAFE_SKIP: "/history",
    NotificationKind.ACADEMIC_EVENT: "/tools/events",
}


class NotificationService:
    """Notification projection + persistence (Phase 11A + 11B + 11C-P4).

    Phase 11C-P4 architectural change:
    - GET /api/v1/notifications is now READ-ONLY: it reads the persisted inbox
      from the database (or the TTL cache) and never generates or writes
      notification rows. Generation is removed from the read path.
    - Notification rows are created by MUTATION TRIGGERS (attendance marking,
      event creation/update/deactivation, quiz schedule changes) and by the
      explicit callable sweep (regenerate_user_notifications, NOT scheduled).
    - NotificationService.emit() is the single canonical emission boundary:
      it creates a new notification row (race-free via PostgreSQL ON CONFLICT
      DO NOTHING) and, only when the row was genuinely new, dispatches a best-
      effort Web Push side-channel via PushDispatchService.
    - The in-app notification inbox remains the source of truth. Push is a
      delivery side-channel only — never the source of truth.
    """

    def __init__(self, db: AsyncSession, *, push_dispatch=None):
        self.db = db
        self.attendance_repo = AttendanceRepository(db)
        self.user_repo = UserRepository(db)
        self.calendar_repo = CalendarRepository(db)
        self.preference_repo = PreferenceRepository(db)
        self.attendance_service = AttendanceService(db)
        self.eligibility_service = EligibilityService(db)
        self.notification_repo = NotificationRepository(db)
        # Phase 11C-P4: best-effort push dispatch callable. Injected by the
        # verifier; defaults to the real PushDispatchService (lazy-imported).
        self._push_dispatch = push_dispatch

    # ── Cache ────────────────────────────────────────────────────────────────

    @classmethod
    def _cache_get(cls, user_id: UUID) -> Optional[NotificationsResponse]:
        entry = _notification_cache.get(user_id)
        if entry is None:
            return None
        stored_at, response = entry
        if time.monotonic() - stored_at >= _NOTIFICATION_CACHE_TTL_SECONDS:
            _notification_cache.pop(user_id, None)
            return None
        return response

    @classmethod
    def _cache_put(cls, user_id: UUID, response: NotificationsResponse) -> None:
        _notification_cache[user_id] = (time.monotonic(), response)

    @classmethod
    def _cache_invalidate(cls, user_id: UUID) -> None:
        _notification_cache.pop(user_id, None)

    # ── Read-only inbox (Phase 11C-P4: no generation, no writes) ────────────

    async def get_notifications(self, user) -> NotificationsResponse:
        """Read-only: serve the persisted inbox from the cache or the database.
        Never generates or writes notification rows."""
        cached = self._cache_get(user.id)
        if cached is not None:
            return cached

        as_of = institution_today()
        rows = await self.notification_repo.get_inbox(user.id)
        unread_count = await self.notification_repo.count_unread(user.id)
        response = NotificationsResponse(
            items=[self._to_item(r) for r in rows],
            as_of=as_of,
            unread_count=unread_count,
        )
        self._cache_put(user.id, response)
        return response

    # ── Emission boundary (Phase 11C-P4) ────────────────────────────────────

    async def emit(
        self,
        user: Union[User, UUID],
        kind: NotificationKind,
        occurrence_key: str,
        date: date,
        message: str,
        subject_code: Optional[str] = None,
        subject_name: Optional[str] = None,
        session_id: Optional[UUID] = None,
        quiz_cycle: Optional[int] = None,
        event_id: Optional[UUID] = None,
    ) -> Notification:
        """Canonical notification emission boundary (Phase 11C-P4).

        Creates a new notification row (race-free PostgreSQL ON CONFLICT DO
        NOTHING) or, when the idempotency key (user_id, kind, occurrence_key)
        already exists, refreshes the mutable fields in place.

        After a successful INSERT the best-effort Web Push side-channel is
        dispatched (via PushDispatchService or the injected callable).
        Existing rows are refreshed WITHOUT re-pushing, so re-running a
        trigger/sweep for the same notification fact never sends a duplicate
        push. Push failures are logged and never propagate.
        """
        user_id = user.id if isinstance(user, User) else user
        row = await self.notification_repo.try_create(
            user_id=user_id,
            kind=kind,
            occurrence_key=occurrence_key,
            date=date,
            message=message,
            subject_code=subject_code,
            subject_name=subject_name,
            session_id=session_id,
            quiz_cycle=quiz_cycle,
            event_id=event_id,
        )
        if row is not None:
            # Newly inserted — push is warranted exactly once.
            self._cache_invalidate(user_id)
            await self._notify_push(user_id, kind, row)
            return row

        # Row already exists — refresh in place without pushing.
        existing = await self.notification_repo.get_by_occurrence_key(
            user_id, kind, occurrence_key
        )
        if existing is not None:
            existing.message = message
            existing.subject_code = subject_code
            existing.subject_name = subject_name
            await self.db.commit()
            self._cache_invalidate(user_id)
            return existing

        # Race: try_create reported None (conflict) but the row disappeared
        # between try_create and the lookup. Fall back to upsert (idempotent).
        # This is exceptionally rare (concurrent delete).
        row_id = await self.notification_repo.upsert(
            user_id=user_id,
            kind=kind,
            occurrence_key=occurrence_key,
            date=date,
            message=message,
            subject_code=subject_code,
            subject_name=subject_name,
            session_id=session_id,
            quiz_cycle=quiz_cycle,
            event_id=event_id,
        )
        new_row = await self.notification_repo.get_by_id(user_id, row_id)
        self._cache_invalidate(user_id)
        return new_row

    # ── Push dispatch (best-effort side-channel) ────────────────────────────

    async def _notify_push(
        self, user_id: UUID, kind: NotificationKind, row: Notification
    ) -> None:
        """Best-effort Web Push delivery for a newly created notification.
        Never raises — failures are logged with safe metadata only. Runs
        synchronously (awaited) inside the caller's request/session lifecycle."""
        try:
            from app.services.push_dispatch_service import PushDispatchService, PushPayload

            url = _KIND_DEEP_LINKS.get(kind, "/dashboard")
            payload = PushPayload(
                title="AttendanceDash Pro",
                body=(row.message or "")[:400],
                url=url,
                notification_id=str(row.id),
                kind=kind.value,
            )
            if self._push_dispatch is not None:
                await self._push_dispatch(user_id, payload)
            else:
                await PushDispatchService(self.db).dispatch_to_user(user_id, payload)
        except Exception as exc:
            logger.warning(
                "Push dispatch failed for notification %s (kind=%s): %s",
                row.id, kind.value, exc,
            )

    # ── Mutation-trigger helpers (fully isolated — never raise) ─────────────

    async def after_attendance_mutation(
        self, user_id: UUID, subject_code: str, as_of_date: Optional[date] = None,
    ) -> None:
        """Post-commit attendance trigger: re-evaluate the attendance kinds
        (ATTENTION_THRESHOLD, MUST_ATTEND, SAFE_SKIP) for the affected subject
        and emit any new/changed notifications. Fully isolated — never raises."""
        try:
            if as_of_date is None:
                as_of_date = institution_today()
            subjects = await self.user_repo.get_enrolled_subjects(user_id)
            target = [s for s in subjects if s.code == subject_code]
            if not target:
                return
            items = await self._attendance_items(user_id, as_of_date, subjects)
            for item in items:
                if item.subject_code == subject_code:
                    await self.emit(
                        user=user_id,
                        kind=item.kind,
                        occurrence_key=item.subject_code,
                        date=item.date,
                        message=item.message,
                        subject_code=item.subject_code,
                        subject_name=item.subject_name,
                        session_id=item.session_id,
                        quiz_cycle=item.quiz_cycle,
                        event_id=item.event_id,
                    )
        except Exception as exc:
            logger.warning(
                "Attendance notification trigger failed for user %s subject %s: %s",
                user_id, subject_code, exc,
            )

    async def after_event_mutation(self, event) -> None:
        """Post-commit event trigger: emit ACADEMIC_EVENT notifications for the
        users affected by a created/updated event. Fully isolated — never raises.

        Recipient resolution mirrors the canonical read projection
        (``_academic_events``):
        - subject-scoped event  -> users enrolled in that concrete subject
          (elective isolation: a BCS-058 event never reaches a BCS-055 student
          because enrollments are concrete-subject rows);
        - elective-slot event   -> users who chose a subject in that slot
          (their concrete choice), plus users enrolled in the slot's shared
          anchor (no-choice fallback);
        - global event          -> all users (ADMIN-only, broadcast).
        Past/inactive events are skipped (no notification fact).
        """
        try:
            as_of = institution_today()
            if not event.active or event.end_date < as_of:
                return

            notified: set[UUID] = set()
            if event.elective_slot is not None:
                choices = await self.user_repo.get_elective_choices_for_slot(event.elective_slot)
                notified.update(c.user_id for c in choices)
                # No-choice fallback: users enrolled in the shared anchor.
                if event.subject_id is not None:
                    notified.update(
                        await self.user_repo.get_enrolled_user_ids(event.subject_id)
                    )
            elif event.subject_id is not None:
                notified.update(await self.user_repo.get_enrolled_user_ids(event.subject_id))
            else:
                # Global event (no subject, no slot) — ADMIN-only broadcast.
                all_ids = await self.user_repo.get_all_user_ids()
                notified.update(all_ids)

            label = event.event_type.value.replace("_", " ").title()
            if event.start_date == event.end_date:
                date_text = event.start_date.strftime("%d %b %Y")
            else:
                date_text = f"{event.start_date.strftime('%d %b')} - {event.end_date.strftime('%d %b %Y')}"
            message = f"{label} on {date_text}"

            for uid in notified:
                await self.emit(
                    user=uid,
                    kind=NotificationKind.ACADEMIC_EVENT,
                    occurrence_key=str(event.id),
                    date=event.start_date,
                    message=message,
                    event_id=event.id,
                )
        except Exception as exc:
            logger.warning(
                "Event notification trigger failed for event %s: %s",
                getattr(event, "id", None), exc,
            )

    async def after_quiz_mutation(self, user_id: UUID) -> None:
        """Post-commit quiz schedule trigger: re-evaluate the QUIZ_APPROACHING
        notification for the user. Fully isolated — never raises."""
        try:
            as_of = institution_today()
            subjects = await self.user_repo.get_enrolled_subjects(user_id)
            items = await self._quiz_approaching(user_id, as_of, subjects)
            for item in items:
                await self.emit(
                    user=user_id,
                    kind=item.kind,
                    occurrence_key=str(item.quiz_cycle),
                    date=item.date,
                    message=item.message,
                    quiz_cycle=item.quiz_cycle,
                )
        except Exception as exc:
            logger.warning(
                "Quiz notification trigger failed for user %s: %s",
                user_id, exc,
            )

    # ── Sweep (callable, NOT scheduled — Phase 11C-P4) ───────────────────────

    async def regenerate_user_notifications(self, user) -> None:
        """Regenerate ALL canonical notification projections for a user.

        This is a callable sweep function — it is NOT scheduled in P4, but
        provides the capability for P5 or ops to invoke it. Each projection
        is emitted via the canonical emit() boundary (new rows → push, existing
        rows → refresh in place without re-push).
        """
        as_of = institution_today()
        subjects = await self.user_repo.get_enrolled_subjects(user.id)
        items: List[NotificationItem] = []
        items += await self._class_reminders(user, as_of, subjects)
        items += await self._quiz_approaching(user.id, as_of, subjects)
        items += await self._attendance_items(user.id, as_of, subjects)
        items += await self._academic_events(user, as_of, subjects)
        for item in items:
            await self.emit(
                user=user.id,
                kind=item.kind,
                occurrence_key=self._occurrence_key(item),
                date=item.date,
                message=item.message,
                subject_code=item.subject_code,
                subject_name=item.subject_name,
                session_id=item.session_id,
                quiz_cycle=item.quiz_cycle,
                event_id=item.event_id,
            )

    # ── State mutation (unchanged from Phase 11B) ───────────────────────────

    async def update_state(
        self,
        user,
        notification_id,
        is_read: Optional[bool] = None,
        is_dismissed: Optional[bool] = None,
    ) -> Optional[NotificationItem]:
        row = await self.notification_repo.update_state(
            user_id=user.id,
            notification_id=notification_id,
            is_read=is_read,
            is_dismissed=is_dismissed,
        )
        self._cache_invalidate(user.id)
        return self._to_item(row) if row is not None else None

    # ── Projection builders (private, shared by sweep + mutation triggers) ──

    @staticmethod
    def _occurrence_key(item: NotificationItem) -> str:
        if item.kind in (NotificationKind.ATTENDANCE_THRESHOLD,
                         NotificationKind.MUST_ATTEND,
                         NotificationKind.SAFE_SKIP):
            return item.subject_code
        if item.kind == NotificationKind.QUIZ_APPROACHING:
            return str(item.quiz_cycle)
        if item.kind == NotificationKind.ACADEMIC_EVENT:
            return str(item.event_id)
        return str(item.session_id)

    @staticmethod
    def _to_item(row) -> NotificationItem:
        return NotificationItem(
            id=f"{row.kind.value}:{row.occurrence_key}",
            notification_id=row.id,
            kind=row.kind,
            date=row.date,
            subject_code=row.subject_code,
            subject_name=row.subject_name,
            message=row.message,
            session_id=row.session_id,
            quiz_cycle=row.quiz_cycle,
            event_id=row.event_id,
            is_read=row.is_read,
        )

    async def _class_reminders(self, user, as_of: date, subjects) -> List[NotificationItem]:
        pref = await self.preference_repo.get(user.id)
        if pref is None or not pref.class_reminders:
            return []
        week_start = as_of - timedelta(days=as_of.weekday())
        week_end = week_start + timedelta(days=6)
        rows = await self.attendance_repo.get_sessions_with_status(user.id, as_of, week_end)
        items: List[NotificationItem] = []
        for r in rows:
            if occurrence_is_cancelled(r) or r["status"] is not None:
                continue
            if r["date"] == as_of:
                when = "today"
            else:
                when = r["date"].strftime("%A, %d %b")
            time_suffix = f" at {r['start_time']}" if r.get("start_time") else ""
            type_label = _CLASS_TYPE_LABELS.get(r["class_type"].value, r["class_type"].value)
            items.append(NotificationItem(
                id=f"{NotificationKind.CLASS_REMINDER.value}:{r['id']}",
                kind=NotificationKind.CLASS_REMINDER,
                date=r["date"],
                subject_code=r["subject_code"],
                subject_name=r["subject_name"],
                message=f"{r['subject_code']} {type_label} {when}{time_suffix}",
                session_id=r["id"],
            ))
        return items

    async def _quiz_approaching(self, user_id: UUID, as_of: date, subjects) -> List[NotificationItem]:
        if not [s for s in subjects if s.quiz_applicable]:
            return []
        cycle = await self.eligibility_service.get_current_quiz_cycle(user_id)
        if cycle["basis"] != "next_upcoming" or cycle["quiz_date"] is None:
            return []
        label = cycle["quiz_label"] or f"Quiz {cycle['quiz_cycle']}"
        return [NotificationItem(
            id=f"{NotificationKind.QUIZ_APPROACHING.value}:{cycle['quiz_cycle']}",
            kind=NotificationKind.QUIZ_APPROACHING,
            date=cycle["quiz_date"],
            message=f"{label} approaching on {cycle['quiz_date'].strftime('%d %b %Y')}",
            quiz_cycle=cycle["quiz_cycle"],
        )]

    async def _attendance_items(self, user_id: UUID, as_of: date, subjects) -> List[NotificationItem]:
        applicable = [s for s in subjects if s.attendance_applicable]
        if not applicable:
            return []
        summaries_map = await self.attendance_service.get_subject_summaries(
            user_id=user_id,
            subjects=applicable,
            as_of_date=as_of,
        )
        items: List[NotificationItem] = []
        for subject in applicable:
            summary = summaries_map.get(subject.id)
            if summary is None:
                continue
            status = classify_attendance_status(summary.current_avg_pct)
            if status in ("WATCH", "CRITICAL"):
                pct_text = f"{summary.current_avg_pct:.1f}%" if summary.current_avg_pct is not None else "no recorded attendance"
                items.append(NotificationItem(
                    id=f"{NotificationKind.ATTENDANCE_THRESHOLD.value}:{subject.code}",
                    kind=NotificationKind.ATTENDANCE_THRESHOLD,
                    date=as_of,
                    subject_code=subject.code,
                    subject_name=subject.name,
                    message=f"{subject.code} attendance is {status.lower()} ({pct_text})",
                ))
            opt = summary.optimization
            if opt is not None and opt.is_reachable:
                if (opt.lecture_deficit or 0) + (opt.tutorial_deficit or 0) > 0:
                    parts = self._count_parts(opt.lecture_deficit, opt.tutorial_deficit)
                    items.append(NotificationItem(
                        id=f"{NotificationKind.MUST_ATTEND.value}:{subject.code}",
                        kind=NotificationKind.MUST_ATTEND,
                        date=as_of,
                        subject_code=subject.code,
                        subject_name=subject.name,
                        message=f"{subject.code}: attend {' + '.join(parts)} to reach {summary.required_pct:.0f}%",
                    ))
                if (opt.safe_skip_lecture or 0) + (opt.safe_skip_tutorial or 0) > 0:
                    parts = self._count_parts(opt.safe_skip_lecture, opt.safe_skip_tutorial)
                    items.append(NotificationItem(
                        id=f"{NotificationKind.SAFE_SKIP.value}:{subject.code}",
                        kind=NotificationKind.SAFE_SKIP,
                        date=as_of,
                        subject_code=subject.code,
                        subject_name=subject.name,
                        message=f"{subject.code}: safe to skip {' + '.join(parts)}",
                    ))
        return items

    @staticmethod
    def _count_parts(lectures: int, tutorials: int) -> List[str]:
        parts = []
        if lectures:
            parts.append(f"{lectures} lecture{'s' if lectures != 1 else ''}")
        if tutorials:
            parts.append(f"{tutorials} tutorial{'s' if tutorials != 1 else ''}")
        return parts

    async def _academic_events(self, user, as_of: date, subjects) -> List[NotificationItem]:
        enrolled_ids = {s.id for s in subjects}
        subject_by_id = {s.id: s for s in subjects}
        resolver = ElectiveResolver(self.db)
        choices = await resolver.load_choices(user.id)
        anchor_subjects = await resolver.anchor_subjects()
        events = await self.calendar_repo.get_all_events()
        upcoming = []
        for e in events:
            if not e.active or e.end_date < as_of:
                continue
            if e.elective_slot is not None:
                choice = choices.get(e.elective_slot)
                subject = choice.subject if choice is not None else anchor_subjects.get(e.elective_slot)
                if subject is None or subject.id not in enrolled_ids:
                    continue
                effective = subject
            else:
                if e.subject_id is not None and e.subject_id not in enrolled_ids:
                    continue
                effective = subject_by_id.get(e.subject_id) if e.subject_id else None
            upcoming.append((e, effective))
        upcoming.sort(key=lambda x: (x[0].start_date, x[0].event_type.value))
        return [
            NotificationItem(
                id=f"{NotificationKind.ACADEMIC_EVENT.value}:{e.id}",
                kind=NotificationKind.ACADEMIC_EVENT,
                date=e.start_date,
                subject_code=effective.code if effective else None,
                subject_name=effective.name if effective else None,
                message=self._event_message(e, effective),
                event_id=e.id,
            )
            for e, effective in upcoming[:4]
        ]

    @staticmethod
    def _event_message(e, subject) -> str:
        label = e.event_type.value.replace("_", " ").title()
        if e.start_date == e.end_date:
            date_text = e.start_date.strftime("%d %b %Y")
        else:
            date_text = f"{e.start_date.strftime('%d %b')} - {e.end_date.strftime('%d %b %Y')}"
        prefix = f"{subject.code} " if subject else ""
        return f"{prefix}{label} on {date_text}"