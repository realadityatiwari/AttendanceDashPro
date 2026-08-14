"""
Event -> engine session synchronizer (Phase 6.6).

The legacy invariant (docs/S4.3, docs/09, js/calendar-engine.js
getEffectiveDaySchedule) is: **ACADEMIC EVENT = EXACT-DATE SCHEDULE
MUTATION**. The legacy attendance engine iterated the *effective* daily
schedule — extras natively added, cancellations removed, closures emptied the
day, substitution swapped the timetable day — so totals always reflected
events.

The Python canonical pipeline materializes the effective schedule in
`class_sessions` (expand_baseline.py) and every consumer (Track, History,
Dashboard, calendar, quiz eligibility) reads that table. This synchronizer
reconciles `class_sessions` to the engine's effective schedule for the dates an
event touches, so the canonical pipeline reacts to events exactly as the
legacy engine did — without touching any engine mathematics.

Design rules:
- Day semantics (working/non-working, substitution, dominance) come from the
  frozen calendar engine (`get_academic_day`) — never reimplemented here.
- Desired-schedule computation is the direct port of legacy
  `getEffectiveDaySchedule` + expand_baseline's substitution handling:
      base    = timetable entries for the day the engine says the date
                follows (substitution override or original weekday)
      minus   = one matching occurrence per CLASS_CANCELLED
      plus    = one is_extra occurrence per EXTRA_* / SURPRISE_QUIZ
  On a non-working day (closure/weekend) the desired schedule is empty.
- Reconciliation is state-based, so it is inherently idempotent: running it
  twice converges on the same state with no duplicates.
- Attendance safety: sessions that already have attendance records are never
  cancelled, un-cancelled, or deleted. Cancelled sessions never receive
  attendance (record_attendance already rejects them with 409), so the
  "cancelled != absent" rule is preserved end to end.
- Sessions are only *created* inside the canonical baseline span
  ([min, max] date of scheduled sessions). Events outside that span still
  affect the calendar engine and reads, but never extend the session pipeline.
- Deterministic ordering: same-priority events are processed by event id, so
  repeated syncs always converge on the same result.

No session deletions for scheduled (non-extra) classes: closures and
cancellations are represented with `is_cancelled` (ADR 004 / audit Q12), never
by removing rows.
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.calendar_engine import (
    get_academic_day,
    DAY_NAMES,
    DEFAULT_WEEKENDS,
    get_event_priority,
)
from app.models.event import AcademicEvent
from app.models.enums import EventType
from app.models.timetable import ClassSession
from app.repositories.calendar_repo import CalendarRepository
from app.repositories.session_repo import SessionRepository

# Event types that inject one extra class occurrence (legacy delta +1:
# docs/09 "How Events Affect Attendance Calculations"; registry + legacy
# getEffectiveDaySchedule inject occurrences for all four).
EXTRA_OCCURRENCE_TYPES = {
    EventType.EXTRA_LECTURE,
    EventType.EXTRA_TUTORIAL,
    EventType.EXTRA_PRACTICAL,
    EventType.SURPRISE_QUIZ,
}

# Closure types are handled entirely by the calendar engine (day becomes
# non-working); they never reach the per-occurrence logic.
CLOSURE_TYPES = {
    EventType.PUBLIC_HOLIDAY,
    EventType.INSTITUTE_HOLIDAY,
    EventType.FESTIVAL_HOLIDAY,
    EventType.EMERGENCY_CLOSURE,
    EventType.SEMESTER_BREAK,
    EventType.MID_SEMESTER_BREAK,
}

# Event types that have no session-level effect (calendar/read semantics only).
NO_SESSION_EFFECT_TYPES = {
    EventType.QUIZ_DAY,
    EventType.WORKING_DAY_OVERRIDE,
    EventType.WORKING_SATURDAY,
}


class EventSessionSynchronizer:
    """
    Reconciles class_sessions with the engine's effective schedule for every
    date an event touches. Runs inside the event mutation transaction (the
    caller commits), so an event and its session effect are atomic.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = SessionRepository(db)
        self.calendar_repo = CalendarRepository(db)

    async def sync_event(
        self,
        event: AcademicEvent,
        span_override: Optional[Tuple[date, date]] = None,
    ) -> None:
        """
        Reconcile sessions for the event's date range (or an explicit span
        override, e.g. the union of an event's old and new ranges after an
        update). Reconciliation is date-scoped, not event-scoped: the desired
        schedule for each date is computed from ALL active events, so
        deactivating or moving an event automatically restores everything its
        dates no longer imply.
        """
        span = await self.session_repo.get_session_date_span()
        if span is None:
            return
        span_start, span_end = span

        all_active_events = await self.calendar_repo.get_all_events(active=True)
        entries = await self.session_repo.get_timetable_entries()
        entries_by_dow: Dict[int, list] = {}
        for entry in entries:
            entries_by_dow.setdefault(entry.day_of_week, []).append(entry)

        if span_override is not None:
            event_start, event_end = span_override
        else:
            event_start, event_end = event.start_date, event.end_date

        start = max(event_start, span_start)
        end = min(event_end, span_end)
        if start > end:
            return

        existing = await self.session_repo.get_sessions_in_range(start, end)
        by_date: Dict[date, List[ClassSession]] = {}
        for session in existing:
            by_date.setdefault(session.date, []).append(session)

        attended_ids = await self.session_repo.get_session_ids_with_attendance(
            [s.id for s in existing]
        )

        current = start
        while current <= end:
            desired_scheduled, desired_extras = self._desired_schedule(
                current, all_active_events, entries_by_dow
            )
            await self._reconcile_date(
                current,
                desired_scheduled,
                desired_extras,
                by_date.get(current, []),
                attended_ids,
            )
            current += timedelta(days=1)

    # -- desired-schedule computation (port of legacy getEffectiveDaySchedule) --

    def _desired_schedule(
        self,
        target: date,
        events: List[AcademicEvent],
        entries_by_dow: Dict[int, list],
    ) -> Tuple[Dict[object, object], Dict[Tuple[object, object], int]]:
        """
        Returns:
          desired_scheduled: {timetable_entry_id: TimetableEntry} for the
                             classes the engine says should exist on the date.
          desired_extras:    {(subject_id, class_type): count} of extra
                             occurrences to materialize.
        """
        day = get_academic_day(target, events, DEFAULT_WEEKENDS)
        if not day.is_working_day:
            return {}, {}

        schedule_day = day.substitution_schedule_override or day.original_day_of_week
        target_dow = DAY_NAMES.index(schedule_day)
        scheduled = {entry.id: entry for entry in entries_by_dow.get(target_dow, [])}

        # Deterministic order: priority desc, then event id (no timestamps on
        # the model; uuid ordering is stable across runs).
        ordered = sorted(
            day.events,
            key=lambda e: (get_event_priority(e.event_type), str(e.id)),
            reverse=True,
        )

        extras: Dict[Tuple[object, object], int] = {}
        for event in ordered:
            if event.event_type in CLOSURE_TYPES:
                # Unreachable on a working day (closure => non-working), kept
                # as the legacy guard.
                continue
            if event.event_type == EventType.CLASS_CANCELLED:
                # Remove ONE matching occurrence (legacy splice semantics).
                match = next(
                    (
                        entry
                        for entry in scheduled.values()
                        if entry.subject_id == event.subject_id
                        and entry.class_type == event.class_type
                    ),
                    None,
                )
                if match is not None:
                    del scheduled[match.id]
            elif event.event_type in EXTRA_OCCURRENCE_TYPES:
                key = (event.subject_id, event.class_type)
                extras[key] = extras.get(key, 0) + 1

        return scheduled, extras

    @staticmethod
    def _is_weekend_artifact(target: date, session: ClassSession) -> bool:
        """
        True when a scheduled session sits on a default weekend date — the
        baseline never expanded weekends, so the row must be a sync-created
        projection (working Saturday / substitution replay).
        Python weekday(): 5=Saturday, 6=Sunday.
        """
        return target.weekday() >= 5

    # -- reconciliation (state-based => idempotent, attendance-safe) --

    async def _reconcile_date(
        self,
        target: date,
        desired_scheduled: Dict[object, object],
        desired_extras: Dict[Tuple[object, object], int],
        existing: List[ClassSession],
        attended_ids: set,
    ) -> None:
        desired_scheduled_ids = set(desired_scheduled.keys())

        scheduled = [s for s in existing if not s.is_extra]
        extras = [s for s in existing if s.is_extra]

        # Scheduled (non-extra) sessions: cancel those no longer desired,
        # restore those desired again, create missing ones. Never touch
        # sessions with attendance records.
        for session in scheduled:
            if session.id in attended_ids:
                continue
            if session.timetable_entry_id in desired_scheduled_ids:
                if session.is_cancelled:
                    session.is_cancelled = False
            elif not session.is_cancelled:
                if self._is_weekend_artifact(target, session):
                    # Baseline expansion never created sessions on default
                    # weekends (expand_baseline skips non-teaching days), so
                    # any scheduled session there was materialized by a
                    # working-Saturday/substitution event. It is a reversible
                    # projection: remove it when the event no longer implies
                    # it, instead of leaving an unbounded cancelled residue.
                    await self.session_repo.delete_session(session)
                else:
                    session.is_cancelled = True

        existing_scheduled_ids = {
            s.timetable_entry_id for s in scheduled if s.timetable_entry_id is not None
        }
        for entry_id in desired_scheduled_ids - existing_scheduled_ids:
            entry = desired_scheduled[entry_id]
            self.session_repo.add_session(
                subject_id=entry.subject_id,
                date=target,
                class_type=entry.class_type,
                is_extra=False,
                timetable_entry_id=entry.id,
            )

        # Extra sessions: matched by (subject_id, class_type) count. They are
        # indistinguishable in their real fields (the model has no event
        # linkage), so count reconciliation is deterministic and correct.
        existing_extra_counts: Dict[Tuple[object, object], int] = {}
        for session in extras:
            key = (session.subject_id, session.class_type)
            existing_extra_counts[key] = existing_extra_counts.get(key, 0) + 1

        for key, desired_count in desired_extras.items():
            missing = desired_count - existing_extra_counts.get(key, 0)
            for _ in range(missing):
                self.session_repo.add_session(
                    subject_id=key[0],
                    date=target,
                    class_type=key[1],
                    is_extra=True,
                    timetable_entry_id=None,
                )

        for key, existing_count in existing_extra_counts.items():
            excess = existing_count - desired_extras.get(key, 0)
            if excess <= 0:
                continue
            # Delete the excess extras that have no attendance records
            # (deterministic by id); extras with attendance are kept — the
            # class happened and was logged, which is historical truth.
            candidates = sorted(
                (s for s in extras if (s.subject_id, s.class_type) == key),
                key=lambda s: str(s.id),
            )
            removed = 0
            for session in candidates:
                if removed >= excess:
                    break
                if session.id in attended_ids:
                    continue
                await self.session_repo.delete_session(session)
                removed += 1