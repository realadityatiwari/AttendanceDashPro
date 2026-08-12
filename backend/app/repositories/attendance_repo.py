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
            AttendanceRecord.student_id == user_id,
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
            .outerjoin(AttendanceRecord, (AttendanceRecord.class_session_id == ClassSession.id) & (AttendanceRecord.student_id == user_id))\
            .filter(ClassSession.subject_id == subject_id, ClassSession.date <= end_date)
            
        result = await self.db.execute(stmt)
        return list(result.all())
