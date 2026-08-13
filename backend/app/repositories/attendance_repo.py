from uuid import UUID
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
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
        """
        from app.models.academic import Subject

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
        from app.models.academic import Subject

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

    async def get_history(self, user_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[dict], int]:
        from app.models.academic import Subject
        
        # Base statement for records
        stmt = select(
            AttendanceRecord.id,
            ClassSession.date,
            Subject.code.label('subject_code'),
            ClassSession.class_type,
            AttendanceRecord.status,
            AttendanceRecord.updated_at.label('marked_at')
        ).join(
            ClassSession, AttendanceRecord.class_session_id == ClassSession.id
        ).join(
            Subject, ClassSession.subject_id == Subject.id
        ).filter(
            AttendanceRecord.user_id == user_id
        ).order_by(
            AttendanceRecord.updated_at.desc()
        ).limit(limit).offset(offset)
        
        result = await self.db.execute(stmt)
        records = [dict(row._mapping) for row in result.all()]
        
        # Count statement
        count_stmt = select(func.count(AttendanceRecord.id)).filter(AttendanceRecord.user_id == user_id)
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar() or 0
        
        return records, total_count
