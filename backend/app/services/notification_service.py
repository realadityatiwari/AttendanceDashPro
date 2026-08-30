from datetime import date, timedelta
import time
from typing import List, Optional
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
from app.models.enums import NotificationKind
from app.repositories.notification_repo import NotificationRepository

# Human-readable class-type labels for notification messages (presentation only).
_CLASS_TYPE_LABELS = {"L": "Lecture", "T": "Tutorial", "P": "Practical"}

# Phase B (2026-08-31): short-lived, per-user, in-process TTL cache for the
# notification inbox response.
#
# Why: every GET /api/v1/notifications previously regenerated ALL notification
# projections (class reminders, quiz approaching, attendance items, academic
# events) and upserted each into the database — even for a routine shell-mount
# read of the unread badge. On Render free-tier cold starts and on every PWA
# background/foreground focus this meant expensive engine work for a single
# badge read.
#
# Design:
# - Cache key is the authenticated user's UUID — strictly per-user, so one
#   user can never receive another user's notifications or unread count.
# - TTL is short (60s) and deterministic (monotonic clock). After expiry the
#   next read regenerates + upserts exactly once; repeated reads within the
#   window are served from the cache (no regeneration, no writes).
# - Invalidation: a read/dismiss PATCH (update_state) removes the user's entry
#   so the very next GET reflects the new state (badge stays correct).
# - The cached value is the final NotificationsResponse (items + as_of +
#   unread_count); FastAPI re-serializes it without mutating the model.
#
# Limitations (documented): in-process only. A single uvicorn worker (the
# project's deployment) gets full benefit; N workers would run N independent
# caches (still per-user keyed — never a leak — just duplicated regeneration
# at most once per TTL per worker). No Redis or new infrastructure is used.
_NOTIFICATION_CACHE_TTL_SECONDS = 60.0
_notification_cache: dict[UUID, tuple[float, NotificationsResponse]] = {}


class NotificationService:
    """Notification projection + persistence (Phase 11A + 11B).

    Architectural rule: notifications CONSUME engine/service outputs; they do
    not independently calculate attendance. Every value emitted here is the
    existing canonical output of attendance_engine / eligibility_engine /
    calendar_engine (via their services and repositories) — this service only
    selects, labels and sorts them.

    11A: the read model is generated on-read.
    11B: generation snapshots each projection into a persisted notification row
    via NotificationRepository.upsert, which keys on UNIQUE(user_id, kind,
    occurrence_key) — the deterministic identity derived from the projection's
    canonical reference (session id / quiz cycle / event id / subject code).
    Regeneration of the same occurrence refreshes the row in place (message +
    subject references) and PRESERVES date, is_read, is_dismissed and
    created_at, so read/dismissed notifications never reappear or reset while
    their source condition still holds (audit §8-3/5). The inbox served to the
    client is the persisted inbox, newest first, with the unread count; a
    previously generated notification stays in the inbox (until dismissed) even
    after its source condition passes.

    Phase B (2026-08-31): the expensive regeneration is throttled by a
    per-user in-process TTL cache (see module docstring) so shell-mount reads
    and PWA foreground transitions serve a cached response instead of
    regenerating projections on every request. Generation still runs — at most
    once per TTL per user — so new class/quiz/attendance/event notifications
    are eventually reflected. Read/dismiss PATCH invalidates the user's entry.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.attendance_repo = AttendanceRepository(db)
        self.user_repo = UserRepository(db)
        self.calendar_repo = CalendarRepository(db)
        self.preference_repo = PreferenceRepository(db)
        self.attendance_service = AttendanceService(db)
        self.eligibility_service = EligibilityService(db)
        self.notification_repo = NotificationRepository(db)

    @classmethod
    def _cache_get(cls, user_id: UUID) -> Optional[NotificationsResponse]:
        """Return the user's cached inbox response if fresh, else None."""
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
        """Store the user's inbox response with the current monotonic time."""
        _notification_cache[user_id] = (time.monotonic(), response)

    @classmethod
    def _cache_invalidate(cls, user_id: UUID) -> None:
        """Remove the user's cache entry (read/dismiss PATCH)."""
        _notification_cache.pop(user_id, None)

    async def get_notifications(self, user) -> NotificationsResponse:
        # Phase B: serve a fresh cached response without regenerating. The
        # cache is keyed by user UUID — never cross-user.
        cached = self._cache_get(user.id)
        if cached is not None:
            return cached

        as_of = institution_today()
        subjects = await self.user_repo.get_enrolled_subjects(user.id)

        items: List[NotificationItem] = []
        items += await self._class_reminders(user, as_of, subjects)
        items += await self._quiz_approaching(user, as_of, subjects)
        items += await self._attendance_items(user, as_of, subjects)
        items += await self._academic_events(user, as_of, subjects)

        # Phase 11B: snapshot the generated projections into persisted rows.
        # Idempotent by construction — the same occurrence upserts, never
        # duplicates. The inbox is then the persisted rows, newest first.
        for item in items:
            await self.notification_repo.upsert(
                user_id=user.id,
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

        rows = await self.notification_repo.get_inbox(user.id)
        unread_count = await self.notification_repo.count_unread(user.id)
        response = NotificationsResponse(
            items=[self._to_item(r) for r in rows],
            as_of=as_of,
            unread_count=unread_count,
        )
        # Phase B: cache the fresh response for subsequent cheap reads.
        self._cache_put(user.id, response)
        return response

    async def update_state(
        self,
        user,
        notification_id,
        is_read: Optional[bool] = None,
        is_dismissed: Optional[bool] = None,
    ) -> Optional[NotificationItem]:
        """Phase 11B PATCH: apply read/dismiss state to one persisted row.
        Owner-scoped (a non-owned id yields None -> 404). Idempotent: repeating
        the same transition is a no-op success."""
        row = await self.notification_repo.update_state(
            user_id=user.id,
            notification_id=notification_id,
            is_read=is_read,
            is_dismissed=is_dismissed,
        )
        # Phase B: a state change must be visible on the next GET (badge
        # correctness) — drop the user's cached response.
        self._cache_invalidate(user.id)
        return self._to_item(row) if row is not None else None

    @staticmethod
    def _occurrence_key(item: NotificationItem) -> str:
        """Deterministic natural-key reference of the projection, mirroring the
        11A item `id` suffix (kind:reference). This is the DB idempotency
        component: CLASS_REMINDER -> session id, QUIZ_APPROACHING -> quiz
        cycle, ACADEMIC_EVENT -> event id, attendance kinds -> subject code."""
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
        """Upcoming (unmarked, non-cancelled) classes within the current
        institutional week — the same repository-defined weekly scope the
        dashboard Weekly section uses (Monday..Sunday). Gated by the user's
        `class_reminders` preference (a missing row means the documented
        default: off)."""
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

    async def _quiz_approaching(self, user, as_of: date, subjects) -> List[NotificationItem]:
        """The next upcoming quiz at/after today — the canonical "currently
        relevant quiz cycle" (get_current_quiz_cycle, basis "next_upcoming").
        A quiz with a confirmed date that has not happened yet IS
        "approaching"; no invented lookahead horizon."""
        if not [s for s in subjects if s.quiz_applicable]:
            return []
        cycle = await self.eligibility_service.get_current_quiz_cycle(user.id)
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

    async def _attendance_items(self, user, as_of: date, subjects) -> List[NotificationItem]:
        """Per-subject attention / must-attend / safe-skip notifications — pure
        projections of the canonical AttendanceService subject summaries (the
        engine's own banding and optimizer); no re-computation."""
        applicable = [s for s in subjects if s.attendance_applicable]
        if not applicable:
            return []
        summaries_map = await self.attendance_service.get_subject_summaries(
            user_id=user.id,
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
                if summary.current_avg_pct is not None:
                    pct_text = f"{summary.current_avg_pct:.1f}%"
                else:
                    pct_text = "no recorded attendance"
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
        """Upcoming academic events — the identical canonical selection the
        dashboard upcoming-events section uses (active, end_date >= today,
        enrolled-scoped, sorted by (start_date, event_type), capped at 4).
        Phase 22.4: elective-slot events resolve to the student's selected
        subject (shared anchor when no selection exists)."""
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
        label = e.event_type.value.replace('_', ' ').title()
        if e.start_date == e.end_date:
            date_text = e.start_date.strftime("%d %b %Y")
        else:
            date_text = f"{e.start_date.strftime('%d %b')} - {e.end_date.strftime('%d %b %Y')}"
        prefix = f"{subject.code} " if subject else ""
        return f"{prefix}{label} on {date_text}"