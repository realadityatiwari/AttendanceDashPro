"""
Phase 24.12 — Attendance admin & analytics repository (READ-ONLY).

Aggregate occurrence reads over the canonical class_sessions +
attendance_records pipeline for a scoped SET of users in ONE query each
(no N+1 per student). Elective resolution, occurrence-outcome application,
and practical-block collapse reuse the exact canonical helpers the student
pipeline uses; this layer only adds the user-set scoping and identity
columns (user_id / section_id / subject_id) needed for admin aggregation.
"""
from datetime import date
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.academic import Subject, StudentEnrollment, StudentElectiveChoice
from app.models.attendance import AttendanceRecord
from app.models.occurrence import OccurrenceOutcome
from app.models.timetable import ClassSession, TimetableEntry
from app.models.user import User, Section
from app.repositories.attendance_repo import AttendanceRepository


class AdminAttendanceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Scope identity
    # ------------------------------------------------------------------

    async def get_section_map(self, user_ids: List[UUID]) -> Dict[UUID, Optional[UUID]]:
        """user_id -> section_id for the given students (one query)."""
        if not user_ids:
            return {}
        result = await self.db.execute(
            select(User.id, User.section_id).where(User.id.in_(user_ids))
        )
        return {uid: sid for uid, sid in result.all()}

    async def list_sections(self) -> List[Section]:
        result = await self.db.execute(select(Section).order_by(Section.name))
        return list(result.scalars().all())

    async def list_subjects(self) -> List[Subject]:
        result = await self.db.execute(select(Subject).order_by(Subject.code))
        return list(result.scalars().all())

    async def get_subject(self, subject_id: UUID) -> Optional[Subject]:
        result = await self.db.execute(select(Subject).where(Subject.id == subject_id))
        return result.scalars().first()

    async def roster_size(self, subject_id: UUID) -> int:
        """Distinct STUDENT-role users enrolled in the subject (the legacy
        ADMIN account is enrolled but is not a student population — Phase
        24.13 truthfulness fix)."""
        result = await self.db.execute(
            select(func.count(func.distinct(StudentEnrollment.user_id)))
            .join(User, User.id == StudentEnrollment.user_id)
            .where(
                StudentEnrollment.subject_id == subject_id,
                User.role == "STUDENT",
            )
        )
        return int(result.scalar_one())

    # ------------------------------------------------------------------
    # Aggregate occurrence source (ONE query for a user set)
    # ------------------------------------------------------------------

    async def get_sessions_with_status_for_users(
        self,
        user_ids: List[UUID],
        start_date: date,
        end_date: date,
    ) -> List[dict]:
        """
        Every class session in [start_date, end_date] for the given users'
        enrolled subjects, resolved EXACTLY like the canonical per-student
        `AttendanceRepository.get_sessions_with_status` (elective slot ->
        resolved subject; Phase 23.6 occurrence-outcome join; practical
        collapse happens in the caller via `group_practical_occurrences`).

        Rows carry user_id / section_id / subject_id so the service can
        aggregate per section / per subject without extra queries. Scoped to
        the authenticated student set via StudentEnrollment; elective-choice
        and attendance-record joins are per-user (join on User.id).
        """
        if not user_ids:
            return []
        resolved_subject_id = func.coalesce(
            StudentElectiveChoice.subject_id, ClassSession.subject_id
        )
        stmt = (
            select(
                User.id.label("user_id"),
                ClassSession.id,
                ClassSession.date,
                ClassSession.class_type,
                ClassSession.is_extra,
                ClassSession.is_cancelled,
                ClassSession.designation,
                ClassSession.elective_slot,
                resolved_subject_id.label("subject_id"),
                Subject.code.label("subject_code"),
                AttendanceRecord.status,
                TimetableEntry.start_time,
                TimetableEntry.end_time,
                OccurrenceOutcome.outcome_type,
            )
            .select_from(ClassSession)
            # Cross the session set with the scoped user set (explicit join);
            # the enrollment join below narrows to the pairs that exist.
            .join(User, User.id.in_(user_ids))
            .outerjoin(TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id)
            .outerjoin(
                StudentElectiveChoice,
                (StudentElectiveChoice.user_id == User.id)
                & (
                    StudentElectiveChoice.elective_slot
                    == func.coalesce(TimetableEntry.elective_slot, ClassSession.elective_slot)
                ),
            )
            .outerjoin(
                OccurrenceOutcome,
                (OccurrenceOutcome.class_session_id == ClassSession.id)
                & (OccurrenceOutcome.subject_id == resolved_subject_id),
            )
            .join(Subject, Subject.id == resolved_subject_id)
            .join(
                StudentEnrollment,
                (StudentEnrollment.user_id == User.id)
                & (StudentEnrollment.subject_id == resolved_subject_id),
            )
            .outerjoin(
                AttendanceRecord,
                (AttendanceRecord.class_session_id == ClassSession.id)
                & (AttendanceRecord.user_id == User.id),
            )
            .where(
                ClassSession.date >= start_date,
                ClassSession.date <= end_date,
            )
            .order_by(
                User.id,
                ClassSession.date,
                TimetableEntry.start_time.asc().nulls_last(),
                ClassSession.id,
            )
        )
        result = await self.db.execute(stmt)
        # Phase 24.13 integration fix: apply the canonical occurrence-outcome
        # to each row (CANCELLED -> is_cancelled; EXTRA_*/SURPRISE_QUIZ ->
        # is_extra) exactly like the per-user pipeline, so subject-specific
        # outcomes are not silently miscounted in the admin aggregates.
        return [
            AttendanceRepository._apply_outcome_to_row(dict(row._mapping))
            for row in result.all()
        ]
