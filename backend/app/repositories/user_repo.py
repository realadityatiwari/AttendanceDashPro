from uuid import UUID
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.user import User
from app.models.academic import StudentEnrollment, Subject

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_by_firebase_uid(self, firebase_uid: str) -> Optional[User]:
        stmt = select(User).options(
            selectinload(User.section)
        ).filter(User.firebase_uid == firebase_uid)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_enrolled_subjects(self, user_id: UUID) -> List[Subject]:
        stmt = select(Subject).join(StudentEnrollment).filter(StudentEnrollment.user_id == user_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
