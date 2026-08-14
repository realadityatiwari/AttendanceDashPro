from uuid import UUID
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, or_, String
from datetime import date
from app.models.attendance import AttendanceRecord
from app.models.timetable import ClassSession, TimetableEntry
from app.models.enums import AttendanceStatus

class AttendanceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
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
        # This joins ClassSession and AttendanceRecord for a given student and subject
        stmt = select(ClassSession.class_type, AttendanceRecord.status)\
            .outerjoin(AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id))\
            .filter(ClassSession.subject_id == subject_id, ClassSession.date <= end_date)
            
        result = await self.db.execute(stmt)
        return list(result.all())

    async def get_subject_counts_between(self, user_id: UUID, subject_id: UUID, start_date: date, end_date: date) -> List[Tuple[str, AttendanceStatus]]:
        # Same as get_subject_counts_up_to_date but strictly bounded to a date range.
        # Used for quiz-window-bounded eligibility counts (ADR 010: Quiz N counts
        # attendance from the previous quiz boundary through the day before the quiz).
        stmt = select(ClassSession.class_type, AttendanceRecord.status)\
            .outerjoin(AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id))\
            .filter(
                ClassSession.subject_id == subject_id,
                ClassSession.date >= start_date,
                ClassSession.date <= end_date
            )
            
        result = await self.db.execute(stmt)
        return list(result.all())

    async def get_sessions_with_status(self, user_id: UUID, start_date: date, end_date: date) -> List[dict]:
        """
        Read-only dashboard aggregation source: every class session in the
        given date range joined with its subject and the user's attendance
        record status (None when the class has not been logged).

        Scoped to the authenticated student's enrolled subjects (StudentEnrollment
        join), mirroring get_daily_sessions and get_history.
        """
        from app.models.academic import Subject, StudentEnrollment

        stmt = select(
            ClassSession.id,
            ClassSession.date,
            ClassSession.class_type,
            ClassSession.is_extra,
            ClassSession.is_cancelled,
            Subject.code.label('subject_code'),
            Subject.name.label('subject_name'),
            AttendanceRecord.status,
        ).join(
            Subject, ClassSession.subject_id == Subject.id
        ).join(
            # Scope every read to the authenticated student's enrolled subjects
            StudentEnrollment,
            (StudentEnrollment.subject_id == Subject.id) & (StudentEnrollment.user_id == user_id)
        ).outerjoin(
            AttendanceRecord,
            (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id)
        ).filter(
            ClassSession.date >= start_date,
            ClassSession.date <= end_date,
        ).order_by(ClassSession.date, ClassSession.class_type)

        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    async def get_daily_sessions(self, user_id: UUID, target_date: date) -> List[dict]:
        from app.models.academic import Subject, StudentEnrollment

        stmt = select(
            ClassSession.id,
            ClassSession.date,
            ClassSession.class_type,
            ClassSession.is_extra,
            ClassSession.is_cancelled,
            Subject.code.label('subject_code'),
            Subject.name.label('subject_name'),
            AttendanceRecord.status,
            TimetableEntry.start_time,
            TimetableEntry.end_time,
        ).join(
            Subject, ClassSession.subject_id == Subject.id
        ).join(
            # Scope every read to the authenticated student's enrolled subjects
            StudentEnrollment,
            (StudentEnrollment.subject_id == Subject.id) & (StudentEnrollment.user_id == user_id)
        ).outerjoin(
            TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id
        ).outerjoin(
            AttendanceRecord,
            (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id)
        ).filter(
            ClassSession.date == target_date,
        ).order_by(TimetableEntry.start_time.nulls_last(), ClassSession.class_type)

        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

    def _history_conditions(
        self,
        user_id: UUID,
        subject_code: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        search: Optional[str] = None,
    ):
        """Shared WHERE clauses for the session-based history queries."""
        from app.models.academic import Subject

        conditions = []
        if date_from is not None:
            conditions.append(ClassSession.date >= date_from)
        if date_to is not None:
            conditions.append(ClassSession.date <= date_to)
        if subject_code:
            conditions.append(Subject.code == subject_code)
        if status == "Cancelled":
            conditions.append(ClassSession.is_cancelled.is_(True))
        elif status is not None:
            resolved = AttendanceStatus(status)
            if resolved == AttendanceStatus.PENDING:
                conditions.append(
                    AttendanceRecord.id.is_(None) & ClassSession.is_cancelled.is_(False)
                )
            else:
                conditions.append(AttendanceRecord.status == resolved)
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
        session of their enrolled subjects within [date_from, date_to],
        joined with the subject, timetable times, and their attendance record
        (None = Pending). Cancelled sessions are included as their own state.
        Mirrors the daily/Track read semantics; never creates rows.
        """
        from app.models.academic import Subject, StudentEnrollment

        conditions = self._history_conditions(
            user_id, subject_code, status, date_from, date_to, search
        )

        base_stmt = (
            select(
                ClassSession.id,
                ClassSession.date,
                ClassSession.class_type,
                ClassSession.is_extra,
                ClassSession.is_cancelled,
                Subject.code.label('subject_code'),
                Subject.name.label('subject_name'),
                AttendanceRecord.status,
                AttendanceRecord.updated_at.label('marked_at'),
                TimetableEntry.start_time,
                TimetableEntry.end_time,
            )
            .join(Subject, ClassSession.subject_id == Subject.id)
            .join(
                # Scope every read to the authenticated student's enrolled subjects
                StudentEnrollment,
                (StudentEnrollment.subject_id == Subject.id) & (StudentEnrollment.user_id == user_id)
            )
            .outerjoin(TimetableEntry, ClassSession.timetable_entry_id == TimetableEntry.id)
            .outerjoin(
                AttendanceRecord,
                (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id)
            )
            .filter(*conditions)
        )

        page_stmt = base_stmt.order_by(
            ClassSession.date.desc(),
            TimetableEntry.start_time.desc().nulls_last(),
            Subject.code.asc(),
        ).limit(limit).offset(offset)

        result = await self.db.execute(page_stmt)
        records = [dict(row._mapping) for row in result.all()]

        count_stmt = (
            select(func.count(ClassSession.id))
            .join(Subject, ClassSession.subject_id == Subject.id)
            .join(
                StudentEnrollment,
                (StudentEnrollment.subject_id == Subject.id) & (StudentEnrollment.user_id == user_id)
            )
            .outerjoin(
                AttendanceRecord,
                (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id)
            )
            .filter(*conditions)
        )
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar() or 0

        return records, total_count

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
        current page): cancelled is its own state; attended/missed/pending
        exclude cancelled sessions, mirroring the Track daily counts.
        """
        from app.models.academic import Subject, StudentEnrollment

        conditions = self._history_conditions(
            user_id, subject_code, status, date_from, date_to, search
        )

        stmt = (
            select(
                func.count(ClassSession.id).filter(ClassSession.is_cancelled.is_(True)).label('cancelled'),
                func.count(ClassSession.id).filter(
                    ClassSession.is_cancelled.is_(False) & (AttendanceRecord.status == AttendanceStatus.ATTENDED)
                ).label('attended'),
                func.count(ClassSession.id).filter(
                    ClassSession.is_cancelled.is_(False) & (AttendanceRecord.status == AttendanceStatus.MISSED)
                ).label('missed'),
                func.count(ClassSession.id).filter(
                    ClassSession.is_cancelled.is_(False) & AttendanceRecord.id.is_(None)
                ).label('pending'),
            )
            .join(Subject, ClassSession.subject_id == Subject.id)
            .join(
                StudentEnrollment,
                (StudentEnrollment.subject_id == Subject.id) & (StudentEnrollment.user_id == user_id)
            )
            .outerjoin(
                AttendanceRecord,
                (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id)
            )
            .filter(*conditions)
        )

        result = await self.db.execute(stmt)
        row = result.one()
        return {
            "cancelled": row.cancelled,
            "attended": row.attended,
            "missed": row.missed,
            "pending": row.pending,
        }
