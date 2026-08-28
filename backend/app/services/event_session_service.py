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
  deleted, and they are never cancelled by day-wide schedule mutations
  (closures, working-Saturday replays) or by LAB_CANCELLED (Phase 9.1). The
  ONE exception is an explicit CLASS_CANCELLED occurrence: the class-reality
  event must propagate to its matching session even when a stale mark exists
  (e.g. Absent recorded before the cancellation was known). Consumers treat
  such a session as Cancelled (never absent) and exclude it from every
  attendance count; deactivating the event restores the session exactly.
  Cancelled sessions never receive new attendance (record_attendance already
  rejects them with 409), so the "cancelled != absent" rule is preserved end
  to end.
- Quiz-day attendance (product decision — Option A): QUIZ_DAY is NOT
  calendar-only — an active QUIZ_DAY event materializes exactly one
  attendance-bearing quiz-day session for its subject/date (bucket in
  _reconcile_date; shape mirrors the quiz-schedule materialization script),
  INDEPENDENT of any normal timetable class on the same date. A covered
  subject/date therefore has its regular occurrence(s) AND the quiz-day
  occurrence, each markable and each counted once in subject attendance/ERP.
  The bucket is shape-count based and idempotent (never duplicates the
  script's sessions or itself), and deletes only unattended quiz-day
  sessions.
- Sessions are only *created* inside the canonical baseline span
  ([min, max] date of scheduled sessions). Events outside that span still
  affect the calendar engine and reads, but never extend the session pipeline.
- Deterministic ordering: same-priority events are processed by event id, so
  repeated syncs always converge on the same result.

No session deletions for scheduled (non-extra) classes: closures and
cancellations are represented with `is_cancelled` (ADR 004 / audit Q12), never
by removing rows. Quiz-day sessions (non-extra, no timetable binding) are the
exception — like extras, they are reversible projections of an event, and an
unattended one is removed when the event no longer implies it.
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.engines.calendar_engine import (
    get_academic_day,
    DAY_NAMES,
    DEFAULT_WEEKENDS,
    get_event_priority,
)
from app.models.event import AcademicEvent
from app.models.enums import EventType, ClassType, SessionDesignation, ElectiveSlot, OccurrenceOutcomeType
from app.models.timetable import ClassSession, TimetableEntry
from app.models.occurrence import OccurrenceOutcome
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
# non-working); they never reach the per-occurrence logic. HOLIDAY is the
# unified closure type (same semantics as the legacy holiday family, which
# remains fully supported).
CLOSURE_TYPES = {
    EventType.HOLIDAY,
    EventType.PUBLIC_HOLIDAY,
    EventType.INSTITUTE_HOLIDAY,
    EventType.FESTIVAL_HOLIDAY,
    EventType.EMERGENCY_CLOSURE,
    EventType.SEMESTER_BREAK,
    EventType.MID_SEMESTER_BREAK,
}

# Event types that have no session-level effect (calendar/read semantics only).
# QUIZ_DAY is NOT in this set: product decision — a quiz day is one
# attendance-bearing occurrence for its subject (see the quiz-day bucket in
# _reconcile_date).
NO_SESSION_EFFECT_TYPES = {
    EventType.WORKING_DAY_OVERRIDE,
    EventType.WORKING_SATURDAY,
}

# Phase 9.1 laboratory events. LAB_CANCELLED is session-identical to
# CLASS_CANCELLED (removes one matching practical occurrence); the registry
# restricts it to PRACTICAL class type. MID_SEM_PRACTICAL is NOT an extra:
# it resolves the existing practical occurrence for the subject/date (or
# materializes exactly one extra when no timetable practical exists that day)
# and marks that session with ClassSession.designation = MID_SEM_PRACTICAL.
# Neither event creates a duplicate attendance opportunity for the same
# practical turn, and neither touches attendance records.
CANCELLATION_TYPES = {
    EventType.CLASS_CANCELLED,
    EventType.LAB_CANCELLED,
}

# Phase 23.6: event type -> occurrence outcome type for subject-specific
# elective events. Unused event types are intentionally absent (no mapping).
EVENT_TO_OUTCOME_TYPE: dict[EventType, OccurrenceOutcomeType] = {
    EventType.EXTRA_LECTURE: OccurrenceOutcomeType.EXTRA_LECTURE,
    EventType.EXTRA_TUTORIAL: OccurrenceOutcomeType.EXTRA_TUTORIAL,
    EventType.EXTRA_PRACTICAL: OccurrenceOutcomeType.EXTRA_PRACTICAL,
    EventType.SURPRISE_QUIZ: OccurrenceOutcomeType.SURPRISE_QUIZ,
    EventType.CLASS_MODIFIED: OccurrenceOutcomeType.MODIFIED,
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

        # Phase 23.6: which subjects are Departmental Elective catalog subjects
        # (subject.elective_slot IS NOT NULL). Subject-specific events targeting
        # one of these subjects produce occurrence OUTCOMES (per-subject
        # overrides of a shared slot session) instead of separate sessions.
        from app.models.academic import Subject as SubjectModel
        result = await self.db.execute(
            select(SubjectModel.id, SubjectModel.elective_slot).where(
                SubjectModel.elective_slot.isnot(None)
            )
        )
        subject_elective_slots: Dict[object, ElectiveSlot] = {
            row[0]: row[1] for row in result.all()
        }

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

        # Phase 9.1: mid-sem designations are managed ONLY when the triggering
        # event is itself MID_SEM_PRACTICAL (create/update/deactivate). Other
        # event syncs never touch ClassSession.designation, so the Phase 8.2
        # admin endpoint's designation survives unrelated event reconciliation.
        manage_mid_sem = event.event_type == EventType.MID_SEM_PRACTICAL
        mid_sem_subject = event.subject_id if manage_mid_sem else None

        current = start
        while current <= end:
            desired_scheduled, desired_extras, extras_slots, mid_sem_active, desired_quiz_days, quiz_day_slots, cancellation_removed, desired_outcomes = (
                self._desired_schedule(
                    current, all_active_events, entries_by_dow,
                    by_date.get(current, []), attended_ids,
                    subject_elective_slots,
                )
            )
            await self._reconcile_date(
                current,
                desired_scheduled,
                desired_extras,
                extras_slots,
                mid_sem_active,
                desired_quiz_days,
                quiz_day_slots,
                cancellation_removed,
                desired_outcomes,
                manage_mid_sem,
                mid_sem_subject,
                by_date.get(current, []),
                attended_ids,
                subject_elective_slots,
            )
            current += timedelta(days=1)

    # -- desired-schedule computation (port of legacy getEffectiveDaySchedule) --

    @staticmethod
    def _cancellation_match(
        scheduled: Dict[object, object],
        subject_id: object,
        class_type: ClassType,
        existing: List[ClassSession],
        attended_ids: set,
    ) -> object:
        """
        The timetable occurrence a CLASS_CANCELLED / LAB_CANCELLED event
        removes. Unattended occurrences are preferred when several matching
        entries exist on one date; when every matching occurrence is attended
        (or none is marked yet) the first matching entry is returned.
        """
        candidates = [
            entry
            for entry in scheduled.values()
            if entry.subject_id == subject_id and entry.class_type == class_type
        ]
        if not candidates:
            return None
        if existing:
            unattended_entry_ids = {
                s.timetable_entry_id
                for s in existing
                if s.timetable_entry_id is not None and s.id not in attended_ids
            }
            for entry in candidates:
                if entry.id in unattended_entry_ids:
                    return entry
        return candidates[0]

    def _desired_schedule(
        self,
        target: date,
        events: List[AcademicEvent],
        entries_by_dow: Dict[int, list],
        existing: List[ClassSession],
        attended_ids: set,
        subject_elective_slots: Dict[object, ElectiveSlot],
    ) -> Tuple[Dict[object, object], Dict[Tuple[object, object], int], Dict[Tuple[object, object], Optional[ElectiveSlot]], set, set, Dict[object, Optional[ElectiveSlot]], set, Dict[object, OccurrenceOutcomeType]]:
        """
        Returns:
          desired_scheduled: {timetable_entry_id: TimetableEntry} for the
                             classes the engine says should exist on the date.
          desired_extras:    {(subject_id, class_type): count} of extra
                             occurrences to materialize.
          extras_slots:      {(subject_id, class_type): ElectiveSlot | None} —
                             the logical elective slot of each extra occurrence
                             (Phase 22.4). None for regular extras.
          mid_sem_active:    subject_ids whose practical occurrence on this
                             date is the mid-semester practical (Phase 9.1).
                             A subject is EXCLUDED when a practical
                             cancellation (CLASS_CANCELLED / LAB_CANCELLED)
                             is also active on this date — cancellation wins.
          desired_quiz_days: subject_ids with an active QUIZ_DAY event on this
                             date — each is one attendance-bearing quiz-day
                             occurrence (see _reconcile_date).
          quiz_day_slots:    {subject_id: ElectiveSlot | None} — the logical
                             elective slot of each quiz-day occurrence (Phase
                             22.4). None for regular quiz days.
          cancellation_removed: timetable_entry_ids explicitly removed from
                             the desired schedule by an active CLASS_CANCELLED
                             event on this date. This is the canonical marker
                             that a specific scheduled occurrence is cancelled
                             by class-reality (not by a day-wide closure), and
                             the only case in which reconciliation cancels a
                             session that already holds an attendance record
                             (bugfix: an active cancellation must propagate to
                             the matching session even when a stale mark —
                             e.g. Absent entered before the cancellation was
                             recorded — exists; consumers treat the session as
                             cancelled and exclude it from attendance math).
                             LAB_CANCELLED is deliberately excluded: Phase 9.1
                             froze "attended lab sessions are never cancelled".
          desired_outcomes:  {subject_id: OccurrenceOutcomeType} — Phase 23.6:
                             subject-specific elective events (elective_slot
                             NULL targeting a catalog elective subject) whose
                             slot HAS a timetable session on this date. These
                             produce per-subject occurrence OUTCOMES overriding
                             the shared anchor session (e.g. only Student A's
                             BCS-058 becomes a Surprise Quiz while Student B's
                             BCS-055 stays a normal lecture). When the slot has
                             NO timetable session on the date, the event falls
                             back to the regular extra path (a subject-scoped
                             session) and never appears here.
        """
        day = get_academic_day(target, events, DEFAULT_WEEKENDS)
        if not day.is_working_day:
            return {}, {}, {}, set(), set(), {}, set(), {}

        schedule_day = day.substitution_schedule_override or day.original_day_of_week
        target_dow = DAY_NAMES.index(schedule_day)
        scheduled = {entry.id: entry for entry in entries_by_dow.get(target_dow, [])}
        # Snapshot BEFORE cancellation removal: the mid-sem reuse rule must
        # see the ORIGINAL timetable so a cancelled occurrence is never
        # replaced by a freshly created extra (which would create two
        # attendance opportunities for one practical turn).
        original_scheduled = dict(scheduled)

        # Deterministic order: priority desc, then event id (no timestamps on
        # the model; uuid ordering is stable across runs).
        ordered = sorted(
            day.events,
            key=lambda e: (get_event_priority(e.event_type), str(e.id)),
            reverse=True,
        )

        extras: Dict[Tuple[object, object], int] = {}
        extras_slots: Dict[Tuple[object, object], Optional[ElectiveSlot]] = {}
        cancelled_practical_subjects: set = set()
        cancellation_removed: set = set()
        # Phase 23.6: per-subject occurrence outcomes for subject-specific
        # elective events (subject_id -> outcome type). Cancellation wins when
        # multiple subject-specific events collide on one subject/date; else
        # the highest-priority extra type (deterministic event ordering).
        desired_outcomes: Dict[object, OccurrenceOutcomeType] = {}
        for event in ordered:
            if event.event_type in CLOSURE_TYPES:
                # Unreachable on a working day (closure => non-working), kept
                # as the legacy guard.
                continue
            # Phase 23.7: subject-scoped MODIFIED event. The scheduled
            # occurrence for this concrete subject was modified (time/room/
            # delivery) — an occurrence OUTCOME, NOT an extra/cancellation.
            # Subject-scoped only (the registry rejects elective_slot). When
            # the subject has a timetable session on this date (as an elective
            # slot member or as a regular subject), the shared anchor session
            # gets a MODIFIED outcome for that subject; otherwise no-op
            # (nothing exists to modify).
            if event.event_type == EventType.CLASS_MODIFIED:
                if event.subject_id is not None:
                    if event.subject_id in subject_elective_slots:
                        subject_slot = subject_elective_slots[event.subject_id]
                        slot_has_timetable = any(
                            entry.elective_slot == subject_slot
                            for entry in scheduled.values()
                        )
                    else:
                        slot_has_timetable = any(
                            entry.subject_id == event.subject_id
                            for entry in scheduled.values()
                        )
                    if slot_has_timetable:
                        desired_outcomes[event.subject_id] = OccurrenceOutcomeType.MODIFIED
                continue
            # Phase 23.6: subject-specific ELECTIVE event (no slot marker, but
            # the concrete subject is a catalog elective subject). When the
            # subject's slot has a timetable session on this date, the event
            # OVERRIDES that shared anchor session for the subject (outcome).
            # When the slot has no session here, extras fall back to the
            # regular subject-scoped extra path below (a session only that
            # subject's students see) and cancellations become no-ops.
            if (
                event.elective_slot is None
                and event.subject_id is not None
                and event.subject_id in subject_elective_slots
            ):
                subject_slot = subject_elective_slots[event.subject_id]
                slot_has_timetable = any(
                    entry.elective_slot == subject_slot
                    for entry in scheduled.values()
                )
                if slot_has_timetable:
                    if event.event_type in CANCELLATION_TYPES:
                        desired_outcomes[event.subject_id] = OccurrenceOutcomeType.CANCELLED
                    elif event.event_type in EXTRA_OCCURRENCE_TYPES:
                        desired_outcomes[event.subject_id] = EVENT_TO_OUTCOME_TYPE.get(
                            event.event_type, OccurrenceOutcomeType.SURPRISE_QUIZ
                        )
                    continue
                if event.event_type in CANCELLATION_TYPES:
                    # No session to cancel on this date (nothing matches) —
                    # a no-op, matching the pre-23.6 behavior.
                    continue
            if event.event_type in CANCELLATION_TYPES:
                # Remove ONE matching occurrence (legacy splice semantics).
                if event.class_type == ClassType.PRACTICAL:
                    cancelled_practical_subjects.add(event.subject_id)
                match = self._cancellation_match(
                    scheduled, event.subject_id, event.class_type, existing, attended_ids
                )
                if match is not None:
                    del scheduled[match.id]
                    if event.event_type == EventType.CLASS_CANCELLED:
                        cancellation_removed.add(match.id)
            elif event.event_type in EXTRA_OCCURRENCE_TYPES:
                key = (event.subject_id, event.class_type)
                extras[key] = extras.get(key, 0) + 1
                # Phase 22.4: an extra materialized from an elective-slot event
                # carries the logical slot so per-student resolution works on
                # the resulting session (it has no timetable link).
                if event.elective_slot is not None:
                    extras_slots[key] = event.elective_slot

        # Phase 9.1 mid-sem plan (state-based, idempotent):
        #   - cancellation wins (the occurrence is cancelled, never markable,
        #     so it is not the mid-sem);
        #   - a timetable practical for the subject/date is REUSED (never
        #     duplicated — the same session becomes the mid-sem);
        #   - when no timetable practical exists, exactly ONE extra practical
        #     occurrence is materialized so attendance can be marked.
        mid_sem_active: set = set()
        for event in ordered:
            if event.event_type != EventType.MID_SEM_PRACTICAL:
                continue
            subject_id = event.subject_id
            if subject_id is None or subject_id in cancelled_practical_subjects:
                continue
            mid_sem_active.add(subject_id)
            has_timetable_practical = any(
                entry.subject_id == subject_id
                and entry.class_type == ClassType.PRACTICAL
                for entry in original_scheduled.values()
            )
            if not has_timetable_practical:
                key = (subject_id, ClassType.PRACTICAL)
                extras[key] = extras.get(key, 0) + 1

        # Quiz-day subjects: every active QUIZ_DAY event on this date implies
        # one attendance-bearing occurrence for its subject (product decision;
        # mirrored by the quiz-schedule materialization script for the seeded
        # quiz dates — the bucket below never duplicates those).
        quiz_day_subjects: set = {
            event.subject_id
            for event in ordered
            if event.event_type == EventType.QUIZ_DAY
            and event.subject_id is not None
        }
        # Phase 22.4: track the elective slot (if any) for each quiz-day
        # occurrence so the resulting session carries the slot marker.
        quiz_day_slots: Dict[object, Optional[ElectiveSlot]] = {
            event.subject_id: event.elective_slot
            for event in ordered
            if event.event_type == EventType.QUIZ_DAY
            and event.subject_id is not None
            and event.elective_slot is not None
        }

        return scheduled, extras, extras_slots, mid_sem_active, quiz_day_subjects, quiz_day_slots, cancellation_removed, desired_outcomes

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
        extras_slots: Dict[Tuple[object, object], Optional[ElectiveSlot]],
        mid_sem_active: set,
        desired_quiz_days: set,
        quiz_day_slots: Dict[object, Optional[ElectiveSlot]],
        cancellation_removed: set,
        desired_outcomes: Dict[object, OccurrenceOutcomeType],
        manage_mid_sem: bool,
        mid_sem_subject: object,
        existing: List[ClassSession],
        attended_ids: set,
        subject_elective_slots: Dict[object, ElectiveSlot],
    ) -> None:
        desired_scheduled_ids = set(desired_scheduled.keys())

        scheduled = [s for s in existing if not s.is_extra]
        extras = [s for s in existing if s.is_extra]

        # Sessions created / deleted by this pass (tracked so the quiz-day
        # bucket below sees the post-reconcile state and never counts a
        # deleted session as covering its subject).
        created: List[ClassSession] = []
        removed_ids: set = set()

        # Scheduled (non-extra) sessions: cancel those no longer desired,
        # restore those desired again, create missing ones.
        #
        # Attendance safety (frozen contracts): sessions with attendance
        # records are never deleted and are never cancelled by day-wide
        # schedule mutations (closures / working-Saturday replays — Phase 6.6
        # checks 5/31; LAB_CANCELLED — Phase 9.1 check 18). The ONE exception
        # is an explicit CLASS_CANCELLED occurrence: the canonical class-
        # reality event must propagate to its matching session even when a
        # stale mark exists (e.g. Absent recorded before the cancellation was
        # known) — Track then presents the session as Cancelled and every
        # consumer excludes it from attendance math (cancelled != absent).
        # Restoration is always allowed: un-cancelling returns a session to
        # its pre-event state (deactivation reversal), which is safe for
        # attended sessions too — their records simply count again.
        for session in scheduled:
            if session.timetable_entry_id is None:
                # Quiz-day session (attendance-spec alignment): authoritative
                # from the quiz schedule, not from any timetable/event. Event
                # reconciliation never cancels or deletes it — quiz-day
                # attendance must stay recordable and counted.
                continue
            if session.timetable_entry_id in desired_scheduled_ids:
                if session.is_cancelled:
                    session.is_cancelled = False
                continue
            if session.is_cancelled:
                continue
            if self._is_weekend_artifact(target, session):
                if session.id in attended_ids:
                    # Baseline expansion never created sessions on default
                    # weekends; attended projections are historical truth and
                    # are never deleted.
                    continue
                # Baseline expansion never created sessions on default
                # weekends (expand_baseline skips non-teaching days), so any
                # scheduled session there was materialized by a
                # working-Saturday/substitution event. It is a reversible
                # projection: remove it when the event no longer implies it,
                # instead of leaving an unbounded cancelled residue.
                await self.session_repo.delete_session(session)
                removed_ids.add(session.id)
                continue
            override = (
                session.id in attended_ids
                and session.timetable_entry_id not in cancellation_removed
            )
            if override:
                continue
            session.is_cancelled = True

        existing_scheduled_ids = {
            s.timetable_entry_id for s in scheduled if s.timetable_entry_id is not None
        }
        for entry_id in desired_scheduled_ids - existing_scheduled_ids:
            entry = desired_scheduled[entry_id]
            created.append(
                self.session_repo.add_session(
                    subject_id=entry.subject_id,
                    date=target,
                    class_type=entry.class_type,
                    is_extra=False,
                    timetable_entry_id=entry.id,
                )
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
                created.append(
                    self.session_repo.add_session(
                        subject_id=key[0],
                        date=target,
                        class_type=key[1],
                        is_extra=True,
                        timetable_entry_id=None,
                        elective_slot=extras_slots.get(key),
                    )
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
                removed_ids.add(session.id)
                removed += 1

        # Quiz-day attendance bucket (product decision): an active QUIZ_DAY
        # event is ONE attendance-bearing occurrence for its subject —
        # exactly one quiz-day session per (subject, date), shaped like the
        # quiz-schedule materialization script (LECTURE, is_extra=false,
        # timetable_entry_id=null). State-based and idempotent:
        #   - created only when the subject has NO non-cancelled session on
        #     the date (timetable, extra, or an existing quiz-day session all
        #     cover the occurrence — never duplicates the script's sessions
        #     on the seeded quiz dates);
        #   - removed ONLY when no QUIZ_DAY event implies them anymore
        #     (deactivated/moved) — a covered-by-another-session occurrence
        #     is never deleted by unrelated event reconciliation (frozen
        #     contract: quiz-day sessions are never cancelled/deleted by
        #     other events; quiz-day attendance must stay recordable);
        #   - attended quiz-day sessions are historical truth and are never
        #     deleted (attendance safety, same as extras).
        # Quiz-day attendance bucket (product decision — Option A): an active
        # QUIZ_DAY event is ONE attendance-bearing occurrence for its subject,
        # INDEPENDENT of any normal timetable class on the same date — a
        # covered subject/date now has its regular occurrence(s) AND the
        # quiz-day occurrence (each markable, each counted once in subject
        # attendance and ERP). Creation is shape-count based and idempotent:
        # exactly one quiz-day-shaped session (LECTURE, is_extra=false,
        # timetable_entry_id=null) per subject in desired_quiz_days; multiple
        # active QUIZ_DAY events for the same subject/date collapse to one
        # (desired_quiz_days is a set). A normal timetable lecture NEVER
        # suppresses quiz-day creation.
        quiz_day_sessions = [
            s for s in existing
            if s.timetable_entry_id is None
            and not s.is_extra
            and s.class_type == ClassType.LECTURE
        ]
        existing_quiz_day_subjects = {
            s.subject_id for s in quiz_day_sessions if s.subject_id in desired_quiz_days
        }
        for subject_id in desired_quiz_days - existing_quiz_day_subjects:
            created.append(
                self.session_repo.add_session(
                    subject_id=subject_id,
                    date=target,
                    class_type=ClassType.LECTURE,
                    is_extra=False,
                    timetable_entry_id=None,
                    elective_slot=quiz_day_slots.get(subject_id),
                )
            )

        for session in sorted(quiz_day_sessions, key=lambda s: str(s.id)):
            if session.id in attended_ids:
                continue
            if session.subject_id not in desired_quiz_days:
                await self.session_repo.delete_session(session)
                removed_ids.add(session.id)

        # Phase 9.1: mid-sem designation step. Runs only when the triggering
        # event is itself MID_SEM_PRACTICAL (the event's create/update/
        # deactivate lifecycle defines the designation). Designation is
        # context (never attendance): clearing it never touches records.
        if manage_mid_sem and mid_sem_subject is not None:
            if mid_sem_subject in mid_sem_active:
                await self._designate_mid_sem(target, mid_sem_subject)
            else:
                await self._clear_mid_sem(target, mid_sem_subject)

        # Phase 23.6: subject-specific elective-event outcomes. After the main
        # session reconciliation, create/update occurrence_outcomes for the
        # desired subjects and remove stale ones no longer implied by events
        # (state-based, idempotent — runs even when desired_outcomes is empty
        # so a deactivated event's outcomes are always removed).
        await self._reconcile_outcomes(
            target, desired_scheduled, desired_outcomes,
            existing, subject_elective_slots,
        )

    # -- Phase 23.6 occurrence outcomes -----------------------------------------

    async def _reconcile_outcomes(
        self,
        target: date,
        desired_scheduled: Dict[object, object],
        desired_outcomes: Dict[object, OccurrenceOutcomeType],
        existing: List[ClassSession],
        subject_elective_slots: Dict[object, ElectiveSlot],
    ) -> None:
        """
        State-based reconciliation of per-subject occurrence outcomes
        (Phase 23.6). A subject-specific elective event whose slot has a
        timetable session on this date overrides that shared anchor session
        for the subject (e.g. only BCS-058 students see a Surprise Quiz while
        BCS-055 stays a normal lecture).

        The anchor session is the timetable-bound session for the subject's
        slot (deterministic: first by timetable start time, then session id).
        For non-elective subjects the anchor session is the timetable-bound
        session whose subject matches the event's subject_id.
        Creating/updating an outcome NEVER modifies the session row or any
        attendance record. Stale outcomes (subject no longer implied by an
        active event on this date) are removed; outcomes never hold attendance
        and are safe to delete.
        """
        # Build anchor entry lookups: by slot (elective) and by subject
        # (non-elective). An entry may appear in both maps (elective slot
        # entries also have a subject_id — the anchor subject).
        anchor_entry_by_slot: Dict[ElectiveSlot, object] = {}
        anchor_entry_by_subject: Dict[object, object] = {}
        for entry in desired_scheduled.values():
            if entry.elective_slot is not None:
                anchor_entry_by_slot.setdefault(entry.elective_slot, entry)
            if entry.subject_id is not None:
                anchor_entry_by_subject.setdefault(entry.subject_id, entry)

        # Anchor sessions already materialized for the date, keyed by their
        # timetable_entry_id.
        session_by_entry_id: Dict[object, ClassSession] = {}
        for session in existing:
            if session.timetable_entry_id is not None:
                # Deterministic: keep the earliest by id (stable ordering).
                session_by_entry_id.setdefault(session.timetable_entry_id, session)

        # Build the desired (session, subject) -> outcome_type set.
        desired_rows: Dict[Tuple[object, object], OccurrenceOutcomeType] = {}
        for subject_id, outcome_type in desired_outcomes.items():
            slot = subject_elective_slots.get(subject_id)
            if slot is not None and slot in anchor_entry_by_slot:
                # Elective subject: anchor session is the slot's timetable session.
                entry = anchor_entry_by_slot[slot]
            elif slot is None and subject_id in anchor_entry_by_subject:
                # Non-elective subject: anchor session is the subject's timetable session.
                entry = anchor_entry_by_subject[subject_id]
            else:
                # No anchor entry for this subject on this date — nothing to override.
                continue
            session = session_by_entry_id.get(entry.id)
            if session is None:
                continue
            desired_rows[(session.id, subject_id)] = outcome_type

        # Collect all anchor sessions that are outcome targets.
        target_session_ids = set(k[0] for k in desired_rows)
        # Also include sessions whose timetable_entry_id is in any anchor entry
        # (so stale outcomes on those sessions are cleaned up).
        all_anchor_entry_ids = set(anchor_entry_by_slot[s].id for s in anchor_entry_by_slot) | set(
            anchor_entry_by_subject[s].id for s in anchor_entry_by_subject
        )
        for entry_id, session in session_by_entry_id.items():
            if entry_id in all_anchor_entry_ids:
                target_session_ids.add(session.id)

        session_ids = list(target_session_ids)
        existing_outcomes = await self._load_outcomes_for_sessions(session_ids)
        existing_key_to_row = {
            (o.class_session_id, o.subject_id): o for o in existing_outcomes
        }

        # Create / update the desired rows.
        for key, outcome_type in desired_rows.items():
            row = existing_key_to_row.get(key)
            if row is None:
                self.session_repo.add_outcome(
                    class_session_id=key[0],
                    subject_id=key[1],
                    outcome_type=outcome_type,
                )
            elif row.outcome_type != outcome_type:
                row.outcome_type = outcome_type

        # Remove stale outcomes (subject no longer implied on this date).
        for key, row in existing_key_to_row.items():
            if key not in desired_rows:
                await self.session_repo.delete_outcome(row)

    async def _load_outcomes_for_sessions(self, session_ids: List[object]) -> List[OccurrenceOutcome]:
        if not session_ids:
            return []
        result = await self.db.execute(
            select(OccurrenceOutcome).where(
                OccurrenceOutcome.class_session_id.in_(session_ids)
            )
        )
        return list(result.scalars().all())

    # -- Phase 9.1 mid-sem designation ------------------------------------------

    async def _designate_mid_sem(self, target: date, subject_id: object) -> None:
        """
        Designates the deterministic practical occurrence for (subject, date)
        as the mid-semester practical. The occurrence is the FIRST practical
        session ordered by timetable start time (then id) — the canonical
        period resolution when a lab day has two P slots; a mid-sem extra is
        the only candidate when the event materialized one. One mid-sem per
        subject: any other designated session for the subject is cleared
        (mirrors the Phase 8.2 admin service's replace semantics). Attendance
        records are never touched.
        """
        stmt = (
            select(ClassSession)
            .outerjoin(TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id)
            .where(
                ClassSession.subject_id == subject_id,
                ClassSession.date == target,
                ClassSession.class_type == ClassType.PRACTICAL,
            )
            .order_by(
                TimetableEntry.start_time.asc().nulls_last(),
                ClassSession.id.asc(),
            )
        )
        candidates = (await self.db.execute(stmt)).scalars().all()
        if not candidates:
            # No occurrence exists (e.g. non-working day with no materialized
            # session) — nothing to designate.
            return
        target_session = candidates[0]
        others = await self.db.execute(
            select(ClassSession).where(
                ClassSession.subject_id == subject_id,
                ClassSession.designation == SessionDesignation.MID_SEM_PRACTICAL,
                ClassSession.id != target_session.id,
            )
        )
        for session in others.scalars().all():
            session.designation = None
        target_session.designation = SessionDesignation.MID_SEM_PRACTICAL

    async def _clear_mid_sem(self, target: date, subject_id: object) -> None:
        """
        Clears the mid-sem designation on (subject, date) practical sessions.
        Used when a MID_SEM_PRACTICAL event is deactivated or moved away from
        this date. Attendance records on the session are untouched.
        """
        stmt = select(ClassSession).where(
            ClassSession.subject_id == subject_id,
            ClassSession.date == target,
            ClassSession.class_type == ClassType.PRACTICAL,
            ClassSession.designation == SessionDesignation.MID_SEM_PRACTICAL,
        )
        for session in (await self.db.execute(stmt)).scalars().all():
            session.designation = None