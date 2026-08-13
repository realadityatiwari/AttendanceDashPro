from uuid import UUID
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from datetime import date
from app.models.attendance import AttendanceRecord
from app.models.timetable import ClassSession
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

    async def save_attendance(self, record: AttendanceRecord):
        self.db.add(record)
        
    async def get_subject_counts_up_to_date(self, user_id: UUID, subject_id: UUID, end_date: date) -> List[Tuple[str, AttendanceStatus]]:
        # This joins ClassSession and AttendanceRecord for a given student and subject
        stmt = select(ClassSession.class_type, AttendanceRecord.status)\
            .outerjoin(AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.user_id == user_id))\
            .filter(ClassSession.subject_id == subject_id, ClassSession.date <= end_date)
            
        result = await self.db.execute(stmt)
        return list(result.all())

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
