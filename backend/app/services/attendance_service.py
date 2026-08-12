from datetime import date
from uuid import UUID
from typing import Optional, Dict, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.attendance_repo import AttendanceRepository
from app.models.attendance import AttendanceRecord
from app.models.enums import AttendanceStatus
from app.engines.attendance_engine import compute_subject_stats, normalize_class_type
from app.schemas.attendance import SubjectAttendanceSummary

class AttendanceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AttendanceRepository(db)
        
    async def get_summary(self, user_id: UUID, subject_id: UUID, subject_code: str, as_of_date: date) -> SubjectAttendanceSummary:
        raw_counts = await self.repo.get_subject_counts_up_to_date(user_id, subject_id, as_of_date)
        
        counts: Dict[str, Any] = {
            'L': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
            'T': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
            'P': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
        }
        
        for class_type_str, status in raw_counts:
            t = normalize_class_type(class_type_str.value)
            if t not in counts:
                continue
            
            counts[t]['tot'] += 1
            if status == AttendanceStatus.ATTENDED:
                counts[t]['att'] += 1
            elif status == AttendanceStatus.MISSED:
                counts[t]['miss'] += 1
            else:
                counts[t]['pending'] += 1
                
        attendance_data = {'counts': counts}
        return compute_subject_stats(subject_code, attendance_data)

    async def record_attendance(self, user_id: UUID, class_session_id: UUID, status: AttendanceStatus) -> AttendanceRecord:
        session = await self.repo.get_session_by_id(class_session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Class session not found")
            
        record = await self.repo.get_attendance_for_session(user_id, class_session_id)
        if record:
            record.status = status
        else:
            record = AttendanceRecord(
                student_id=user_id,
                class_session_id=class_session_id,
                status=status
            )
            await self.repo.save_attendance(record)
            
        await self.db.commit()
        return record
