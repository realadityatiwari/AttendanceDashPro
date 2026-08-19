from uuid import UUID
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.preference import UserPreference
from app.models.enums import WeekStartsOn


class PreferenceRepository:
    """Persistence for the user-preferences row (Phase 10D). Exactly one row
    per user (user_id is the primary key); the owner is always derived from
    the authenticated user — no client-controlled identity. Repositories do
    not commit — the service owns the transaction boundary."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, user_id: UUID) -> Optional[UserPreference]:
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create_default(self, user_id: UUID) -> UserPreference:
        """Materialize the documented server defaults: false / false / MONDAY."""
        pref = UserPreference(user_id=user_id)
        self.db.add(pref)
        return pref

    async def replace(
        self,
        user_id: UUID,
        class_reminders: bool,
        auto_mark_present: bool,
        week_starts_on: WeekStartsOn,
    ) -> UserPreference:
        """Full-object replacement of the user's preference row. The caller
        guarantees the row exists (lazy-create), so this is an update in
        place; the PK uniqueness keeps it to exactly one row."""
        pref = await self.get(user_id)
        pref.class_reminders = class_reminders
        pref.auto_mark_present = auto_mark_present
        pref.week_starts_on = week_starts_on
        return pref
