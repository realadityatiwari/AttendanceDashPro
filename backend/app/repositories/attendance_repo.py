from uuid import UUID
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, or_, and_, String
from datetime import date
from app.models.attendance import AttendanceRecord
from app.models.timetable import ClassSession, TimetableEntry
from app.models.academic import StudentElectiveChoice
from app.models.occurrence import OccurrenceOutcome
from app.models.enums import AttendanceStatus, ClassType, OccurrenceOutcomeType
from app.engines.practical_occurrence import (
    collapse_count_rows,
    group_practical_occurrences,
    occurrence_is_cancelled,
)

class AttendanceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _outcome_join_on(resolved_subject_id):
        """ON clause for the Phase 23.6 occurrence-outcome LEFT JOIN.

        Matches a class session to a per-subject occurrence outcome for the
        student's RESOLVED subject (their elective choice for the slot, else
        the session's own subject). A student whose subject has no outcome row
        gets NULL -> the anchor session state (unchanged behavior).
        """
        return and_(
            OccurrenceOutcome.class_session_id == ClassSession.id,
            OccurrenceOutcome.subject_id == resolved_subject_id,
        )

    @staticmethod
    def _apply_outcome_to_row(row: dict) -> dict:
        """Phase 23.6: apply a per-subject occurrence outcome to a read row.

        CANCELLED -> effective is_cancelled = True (cancelled != absent,
        excluded from attendance math like any cancelled occurrence);
        EXTRA_LECTURE/EXTRA_TUTORIAL/EXTRA_PRACTICAL/SURPRISE_QUIZ ->
        effective is_extra = True. Absence (outcome_type None) leaves the
        anchor session's own flags untouched. The row dict is returned for
        chaining.
        """
        outcome_type = row.get("outcome_type")
        if outcome_type is None:
            return row
        if outcome_type == OccurrenceOutcomeType.CANCELLED:
            row["is_cancelled"] = True
        else:
            row["is_extra"] = True
        return row

    @staticmethod
    def _elective_choice_on(user_id: UUID):
        """ON-clause for the per-user elective choice join: matches a
        timetable entry's elective slot (or, for event-created sessions with
        no timetable link, the session's own elective slot marker — Phase
        22.4) to the student's selected subject for that slot. Non-elective
        sessions (elective_slot NULL everywhere) never match, so regular
        sessions resolve through ClassSession.subject_id as before."""
        return and_(
            StudentElectiveChoice.user_id == user_id,
            StudentElectiveChoice.elective_slot == func.coalesce(
                TimetableEntry.elective_slot, ClassSession.elective_slot
            ),
        )

    @staticmethod
    def _resolved_subject_match(subject_id: UUID):
        """WHERE predicate: a session belongs to `subject_id` when its
        concrete subject is the subject (regular sessions, and the student who
        selected the slot anchor subject), OR when the session belongs to a
        Department Elective slot (via its timetable entry or its own marker)
        and the student selected `subject_id` for that slot."""
        resolved_slot = func.coalesce(
            TimetableEntry.elective_slot, ClassSession.elective_slot
        )
        return or_(
            ClassSession.subject_id == subject_id,
            and_(
                resolved_slot.isnot(None),
                StudentElectiveChoice.subject_id == subject_id,
            ),
        )

    async def get_attendance_for_session(self, user_id: UUID, class_session_id: UUID) -> Optional[AttendanceRecord]:
        stmt = select(AttendanceRecord).filter(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.class_session_id == class_session_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
        
    async def get_session_by_id(self, class_session_id: UUID) -> Optional[ClassSession]:
        stmt = select(ClassSession).filter(ClassSession.id == class_session_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def is_enrolled(self, user_id: UUID, subject_id: UUID) -> bool:
        from app.models.academic import StudentEnrollment
        stmt = select(StudentEnrollment).filter(
            StudentEnrollment.user_id == user_id,
            StudentEnrollment.subject_id == subject_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    async def save_attendance(self, record: AttendanceRecord):
        self.db.add(record)
        
    async def get_subject_counts_up_to_date(self, user_id: UUID, subject_id: UUID, end_date: date) -> List[Tuple[str, AttendanceStatus]]:
        # This joins ClassSession and AttendanceRecord for a given student and subject.
        # Cancelled sessions are excluded: a cancelled class is not a pending,
        # absent, or attended class (Phase 6.6 event->session integration; the
        # legacy engine applied the same rule via the effective schedule).
        #
        # Track lab correction: contiguous two-period PRACTICAL blocks are
        # collapsed into ONE logical occurrence (one lab = one attendance
        # decision), so a 2-hour lab is never counted twice in any denominator.
        # The collapse (app.engines.practical_occurrence) is the single source
        # of occurrence semantics shared by every consumer.
        stmt = select(
            ClassSession.class_type,
            AttendanceRecord.status,
            ClassSession.date,
            ClassSession.is_cancelled,
            TimetableEntry.start_time,
            TimetableEntry.end_time,
            OccurrenceOutcome.outcome_type,
        ).outerjoin(
            AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id)
        ).outerjoin(
            TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id
        ).outerjoin(
            StudentElectiveChoice, self._elective_choice_on(user_id)
        ).outerjoin(
            # Phase 23.6: per-subject occurrence outcome (student-scoped).
            OccurrenceOutcome, self._outcome_join_on(
                func.coalesce(StudentElectiveChoice.subject_id, ClassSession.subject_id)
            )
        ).filter(
            self._resolved_subject_match(subject_id),
            ClassSession.date <= end_date,
        ).order_by(
            ClassSession.date,
            TimetableEntry.start_time.asc().nulls_last(),
            ClassSession.id,
        )

        result = await self.db.execute(stmt)
        rows = [
            self._apply_outcome_to_row(
                {
                    "class_type": row[0],
                    "status": row[1],
                    "date": row[2],
                    "is_cancelled": row[3],
                    "start_time": row[4],
                    "end_time": row[5],
                    "outcome_type": row[6],
                }
            )
            for row in result.all()
        ]
        return collapse_count_rows(rows)

    async def get_subject_counts_for_user(self, user_id: UUID, end_date: date) -> List[Tuple[UUID, str, AttendanceStatus]]:
        """
        All enrolled-subject counts for a user up to end_date in ONE query
        (dashboard/analytics N+1 fix). Mirrors get_subject_counts_up_to_date
        semantics exactly: cancelled sessions excluded (practical blocks
        collapsed to one occurrence); a missing record row is Pending (outer
        join); scoped to the authenticated student's enrollments
        (StudentEnrollment join). Returns (subject_id, class_type, status).
        """
        from app.models.academic import StudentEnrollment

        # Phase 22.3: the effective subject of an elective slot session is the
        # student's selection for that slot; enrollment scoping and the
        # grouped subject_id both use the resolved subject.
        resolved_subject_id = func.coalesce(
            StudentElectiveChoice.subject_id, ClassSession.subject_id
        )
        stmt = select(
            resolved_subject_id.label('subject_id'),
            ClassSession.class_type,
            AttendanceRecord.status,
            ClassSession.date,
            ClassSession.is_cancelled,
            TimetableEntry.start_time,
            TimetableEntry.end_time,
            OccurrenceOutcome.outcome_type,
        ).outerjoin(
            TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id
        ).outerjoin(
            StudentElectiveChoice, self._elective_choice_on(user_id)
        ).outerjoin(
            # Phase 23.6: per-subject occurrence outcome (student-scoped).
            OccurrenceOutcome, self._outcome_join_on(resolved_subject_id)
        ).join(
            StudentEnrollment,
            (StudentEnrollment.user_id == user_id)
            & (StudentEnrollment.subject_id == resolved_subject_id)
        ).outerjoin(AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id)
                    & (AttendanceRecord.user_id == user_id))\
            .filter(
                ClassSession.date <= end_date,
            ).order_by(
                ClassSession.date,
                TimetableEntry.start_time.asc().nulls_last(),
                ClassSession.id,
            )

        result = await self.db.execute(stmt)
        rows = [
            self._apply_outcome_to_row(
                {
                    "subject_id": row[0],
                    "class_type": row[1],
                    "status": row[2],
                    "date": row[3],
                    "is_cancelled": row[4],
                    "start_time": row[5],
                    "end_time": row[6],
                    "outcome_type": row[7],
                }
            )
            for row in result.all()
        ]
        return collapse_count_rows(rows, include_subject=True)

    async def get_mid_sem_sessions(self, subject_ids) -> dict:
        """
        Phase 8.2: the designated mid-semester practical sessions for the given
        subject ids, keyed by subject_id -> (session_id, date). A designation
        is an ADMIN-controlled session-level fact (ClassSession.designation ==
        MID_SEM_PRACTICAL); it is never inferred from experiment counts or a
        computed date. Returns an empty mapping when nothing is designated.
        """
        from app.models.enums import SessionDesignation
        if not subject_ids:
            return {}
        stmt = select(
            ClassSession.subject_id,
            ClassSession.id,
            ClassSession.date,
        ).where(
            ClassSession.subject_id.in_(list(subject_ids)),
            ClassSession.designation == SessionDesignation.MID_SEM_PRACTICAL,
        )
        result = await self.db.execute(stmt)
        return {subject_id: (str(session_id), session_date)
                for subject_id, session_id, session_date in result.all()}

    async def get_subject_counts_between(
        self,
        user_id: UUID,
        subject_id: UUID,
        start_date: date,
        end_date: date,
        exclude_quiz_day: bool = False,
    ) -> List[Tuple[str, AttendanceStatus]]:
        # Same as get_subject_counts_up_to_date but strictly bounded to a date range.
        # Used for quiz-window-bounded eligibility counts (ADR 010: Quiz N counts
        # attendance from the previous quiz boundary through the day before the quiz).
        # Cancelled sessions are excluded for the same reason as above (practical
        # blocks collapsed to one occurrence).
        #
        # exclude_quiz_day (product decision — Option A): Quiz-Day sessions are
        # attendance occurrences for SUBJECT ATTENDANCE / ERP, but they must
        # NOT become additional LECTURE/TUTORIAL opportunities inside the
        # eligibility L/T calculation (the eligibility window starts inclusive
        # on the previous quiz date, so a quiz-day session on that date would
        # otherwise enter the next window). The canonical quiz-day shape is
        # LECTURE + is_extra=false + timetable_entry_id IS NULL — normal
        # lectures (timetable-bound) remain fully included.
        stmt = select(
            ClassSession.class_type,
            AttendanceRecord.status,
            ClassSession.date,
            ClassSession.is_cancelled,
            TimetableEntry.start_time,
            TimetableEntry.end_time,
            OccurrenceOutcome.outcome_type,
        ).outerjoin(
            AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id)
        ).outerjoin(
            TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id
        ).outerjoin(
            StudentElectiveChoice, self._elective_choice_on(user_id)
        ).outerjoin(
            # Phase 23.6: per-subject occurrence outcome (student-scoped).
            OccurrenceOutcome, self._outcome_join_on(
                func.coalesce(StudentElectiveChoice.subject_id, ClassSession.subject_id)
            )
        ).filter(
            self._resolved_subject_match(subject_id),
            ClassSession.date >= start_date,
            ClassSession.date <= end_date,
        )
        if exclude_quiz_day:
            stmt = stmt.filter(
                ~(ClassSession.timetable_entry_id.is_(None)
                  & ~ClassSession.is_extra
                  & (ClassSession.class_type == ClassType.LECTURE))
            )
        stmt = stmt.order_by(
            ClassSession.date,
            TimetableEntry.start_time.asc().nulls_last(),
            ClassSession.id,
        )

        result = await self.db.execute(stmt)
        rows = [
            self._apply_outcome_to_row(
                {
                    "class_type": row[0],
                    "status": row[1],
                    "date": row[2],
                    "is_cancelled": row[3],
                    "start_time": row[4],
                    "end_time": row[5],
                    "outcome_type": row[6],
                }
            )
            for row in result.all()
        ]
        return collapse_count_rows(rows)

    async def get_sessions_with_status(self, user_id: UUID, start_date: date, end_date: date) -> List[dict]:
        """
        Read-only dashboard aggregation source: every class session in the
        given date range joined with its subject and the user's attendance
        record status (None when the class has not been logged).

        Scoped to the authenticated student's enrolled subjects (StudentEnrollment
        join), mirroring get_daily_sessions and get_history.
        """
        from app.models.academic import Subject, StudentEnrollment

        # Phase 22.3: elective slot sessions display the student's selected
        # subject (not the shared slot anchor). Effective subject =
        # COALESCE(choice.subject_id, ClassSession.subject_id); enrollment
        # scope and the Subject join both use that resolved subject.
        resolved_subject_id = func.coalesce(
            StudentElectiveChoice.subject_id, ClassSession.subject_id
        )
        stmt = select(
            ClassSession.id,
            ClassSession.date,
            ClassSession.class_type,
            ClassSession.is_extra,
            ClassSession.is_cancelled,
            ClassSession.designation,
            Subject.id.label('subject_id'),
            Subject.code.label('subject_code'),
            Subject.name.label('subject_name'),
            AttendanceRecord.status,
            TimetableEntry.start_time,
            TimetableEntry.end_time,
            OccurrenceOutcome.outcome_type,
        ).outerjoin(
            TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id
        ).outerjoin(
            StudentElectiveChoice, self._elective_choice_on(user_id)
        ).outerjoin(
            # Phase 23.6: per-subject occurrence outcome (student-scoped).
            OccurrenceOutcome, self._outcome_join_on(resolved_subject_id)
        ).join(
            Subject, Subject.id == resolved_subject_id
        ).join(
            # Scope every read to the authenticated student's enrolled subjects
            StudentEnrollment,
            (StudentEnrollment.user_id == user_id)
            & (StudentEnrollment.subject_id == resolved_subject_id)
        ).outerjoin(
            AttendanceRecord,
            (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id)
        ).filter(
            ClassSession.date >= start_date,
            ClassSession.date <= end_date,
        ).order_by(
            ClassSession.date,
            TimetableEntry.start_time.asc().nulls_last(),
            ClassSession.id,
        )

        result = await self.db.execute(stmt)
        rows = [
            self._apply_outcome_to_row(dict(row._mapping))
            for row in result.all()
        ]
        # Track lab correction: contiguous two-period PRACTICAL blocks are one
        # logical occurrence for dashboard/analytics/calendar consumers (a lab
        # counts once in weekly analytics and calendar session counts).
        return group_practical_occurrences(rows)

    async def get_daily_sessions(self, user_id: UUID, target_date: date) -> List[dict]:
        from app.models.academic import Subject, StudentEnrollment

        resolved_subject_id = func.coalesce(
            StudentElectiveChoice.subject_id, ClassSession.subject_id
        )
        stmt = select(
            ClassSession.id,
            ClassSession.date,
            ClassSession.class_type,
            ClassSession.is_extra,
            ClassSession.is_cancelled,
            ClassSession.designation,
            Subject.code.label('subject_code'),
            Subject.name.label('subject_name'),
            AttendanceRecord.status,
            TimetableEntry.start_time,
            TimetableEntry.end_time,
            OccurrenceOutcome.outcome_type,
        ).outerjoin(
            TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id
        ).outerjoin(
            StudentElectiveChoice, self._elective_choice_on(user_id)
        ).outerjoin(
            # Phase 23.6: per-subject occurrence outcome (student-scoped).
            OccurrenceOutcome, self._outcome_join_on(resolved_subject_id)
        ).join(
            Subject, Subject.id == resolved_subject_id
        ).join(
            # Scope every read to the authenticated student's enrolled subjects
            StudentEnrollment,
            (StudentEnrollment.user_id == user_id)
            & (StudentEnrollment.subject_id == resolved_subject_id)
        ).outerjoin(
            AttendanceRecord,
            (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id)
        ).filter(
            ClassSession.date == target_date,
        ).order_by(TimetableEntry.start_time.asc().nulls_last(), ClassSession.id)

        result = await self.db.execute(stmt)
        rows = [
            self._apply_outcome_to_row(dict(row._mapping))
            for row in result.all()
        ]
        # Track lab correction: a two-hour laboratory block (two contiguous
        # timetable PRACTICAL periods) is ONE attendance occurrence. The daily
        # read model collapses the block into a single card with the block
        # status and the 01:00 PM – 03:00 PM span; attendance mutation against
        # it records exactly ONE AttendanceRecord on the representative
        # session. Non-practical sessions pass through unchanged.
        return group_practical_occurrences(rows)

    def _history_base_conditions(
        self,
        subject_code: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search: Optional[str] = None,
    ):
        """Shared non-status WHERE clauses for the session-based history queries.
        The attendance status filter is applied at OCCURRENCE level after the
        practical-block collapse (a lab block is one history row)."""
        from app.models.academic import Subject

        conditions = []
        if date_from is not None:
            conditions.append(ClassSession.date >= date_from)
        if date_to is not None:
            conditions.append(ClassSession.date <= date_to)
        if subject_code:
            conditions.append(Subject.code == subject_code)
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    Subject.code.ilike(pattern),
                    Subject.name.ilike(pattern),
                    ClassSession.class_type.cast(String).ilike(pattern),
                    ClassSession.date.cast(String).ilike(pattern),
                )
            )
        return conditions

    async def _fetch_history_occurrences(
        self,
        user_id: UUID,
        conditions,
    ) -> List[dict]:
        """Every class-session row for the base history conditions, collapsed
        into logical occurrences (contiguous two-period labs = one row)."""
        from app.models.academic import Subject, StudentEnrollment

        resolved_subject_id = func.coalesce(
            StudentElectiveChoice.subject_id, ClassSession.subject_id
        )
        stmt = (
            select(
                ClassSession.id,
                ClassSession.date,
                ClassSession.class_type,
                ClassSession.is_extra,
                ClassSession.is_cancelled,
                ClassSession.designation,
                Subject.code.label('subject_code'),
                Subject.name.label('subject_name'),
                AttendanceRecord.status,
                AttendanceRecord.updated_at.label('marked_at'),
                TimetableEntry.start_time,
                TimetableEntry.end_time,
                OccurrenceOutcome.outcome_type,
            )
            .outerjoin(TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id)
            .outerjoin(StudentElectiveChoice, self._elective_choice_on(user_id))
            .outerjoin(
                # Phase 23.6: per-subject occurrence outcome (student-scoped).
                OccurrenceOutcome, self._outcome_join_on(resolved_subject_id)
            )
            .join(Subject, Subject.id == resolved_subject_id)
            .join(
                # Scope every read to the authenticated student's enrolled subjects
                StudentEnrollment,
                (StudentEnrollment.user_id == user_id)
                & (StudentEnrollment.subject_id == resolved_subject_id)
            )
            .outerjoin(
                AttendanceRecord,
                (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id)
            )
            .filter(*conditions)
            .order_by(
                ClassSession.date,
                TimetableEntry.start_time.asc().nulls_last(),
                ClassSession.id,
            )
        )
        result = await self.db.execute(stmt)
        rows = [
            self._apply_outcome_to_row(dict(row._mapping))
            for row in result.all()
        ]
        return group_practical_occurrences(rows)

    @staticmethod
    def _history_status_match(occ: dict, status: Optional[str]) -> bool:
        """Occurrence-level status matching for history filters (a lab block
        is one row: any member record resolves the block status). A cancelled
        theory occurrence is Cancelled — never Attended/Missed/Pending, even
        when a stale mark predates the cancellation (occurrence_is_cancelled);
        a recorded lab block stays counted by its record (frozen lab rule)."""
        if status == "Cancelled":
            return bool(occ.get("is_cancelled"))
        if status is None:
            return True
        if occurrence_is_cancelled(occ):
            return False
        resolved = AttendanceStatus(status)
        if resolved == AttendanceStatus.PENDING:
            return occ.get("status") is None
        return occ.get("status") == resolved

    async def get_history(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        subject_code: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[dict], int]:
        """
        Semester-scoped history for the authenticated student: every class
        session occurrence of their enrolled subjects within [date_from,
        date_to], joined with the subject, timetable times, and their
        attendance record (None = Pending). A two-hour laboratory block is ONE
        history row. Cancelled occurrences are included as their own state.
        Mirrors the daily/Track read semantics; never creates rows.
        """
        conditions = self._history_base_conditions(
            subject_code, date_from, date_to, search
        )
        occurrences = await self._fetch_history_occurrences(user_id, conditions)
        filtered = [
            o for o in occurrences if self._history_status_match(o, status)
        ]
        total_count = len(filtered)

        def sort_key(o: dict):
            st = o.get("start_time")
            st_secs = (st.hour * 3600 + st.minute * 60 + st.second) if st else 0
            return (-o["date"].toordinal(), -st_secs, o.get("subject_code") or "")

        filtered.sort(key=sort_key)
        page = filtered[offset:offset + limit]
        return page, total_count

    async def get_history_summary(
        self,
        user_id: UUID,
        subject_code: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search: Optional[str] = None,
    ) -> dict:
        """
        Aggregate counts over the full filtered history result set (not the
        current page), at OCCURRENCE level: a two-hour lab counts once.
        Cancelled is its own state; attended/missed/pending exclude cancelled
        occurrences, mirroring the Track daily counts. A cancelled theory
        occurrence never counts as attended/missed even when a stale mark
        predates the cancellation (occurrence_is_cancelled); a recorded lab
        block keeps its frozen record-wins rule.
        """
        conditions = self._history_base_conditions(
            subject_code, date_from, date_to, search
        )
        occurrences = await self._fetch_history_occurrences(user_id, conditions)
        filtered = [
            o for o in occurrences if self._history_status_match(o, status)
        ]
        cancelled = sum(1 for o in filtered if o.get("is_cancelled"))
        attended = sum(
            1 for o in filtered
            if o.get("status") == AttendanceStatus.ATTENDED
            and not occurrence_is_cancelled(o)
        )
        missed = sum(
            1 for o in filtered
            if o.get("status") == AttendanceStatus.MISSED
            and not occurrence_is_cancelled(o)
        )
        pending = sum(
            1 for o in filtered
            if o.get("status") is None and not o.get("is_cancelled")
        )
        return {
            "cancelled": cancelled,
            "attended": attended,
            "missed": missed,
            "pending": pending,
        }
