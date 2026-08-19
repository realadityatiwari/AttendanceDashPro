from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.preference import UserPreference
from app.repositories.preference_repo import PreferenceRepository
from app.schemas.preference import PreferenceUpdate


class PreferenceService:
    """User preferences (Phase 10D) — STORAGE/PREFERENCE DATA ONLY.

    Nothing here sends reminders, marks attendance, or alters calendar /
    analytics / attendance calculations. The values are simply persisted per
    authenticated user; Phase 11 consumes them later.

    Lazy-default semantics (Phase 10A decision): a user with no preference
    row receives the documented server defaults (false / false / MONDAY),
    materialized on first GET. No backfill migration is run for existing
    users. The lazy create is idempotent and transaction-safe: a concurrent
    GET race that both try to insert the same PK rolls back and re-reads.

    Endpoint -> Service -> Repository -> SQLAlchemy; no business logic lives
    in the endpoint. Ownership is always current_user.id — never accepted
    from query params or the request body.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = PreferenceRepository(db)

    async def get_or_create(self, user: User) -> UserPreference:
        pref = await self.repo.get(user.id)
        if pref is not None:
            return pref
        pref = await self.repo.create_default(user.id)
        try:
            await self.db.commit()
        except IntegrityError:
            # A concurrent request materialized the row between our read and
            # insert; roll back and re-read the winner's row.
            await self.db.rollback()
            pref = await self.repo.get(user.id)
            if pref is None:
                raise
        await self.db.refresh(pref)
        return pref

    async def replace(self, user: User, payload: PreferenceUpdate) -> UserPreference:
        # PUT is full-object replacement: the row is lazily materialized if
        # missing, then every field is overwritten with the submitted value.
        # Omitted fields are impossible (all three are required), so a PUT can
        # never produce accidental NULLs.
        await self.get_or_create(user)
        pref = await self.repo.replace(
            user.id,
            class_reminders=payload.class_reminders,
            auto_mark_present=payload.auto_mark_present,
            week_starts_on=payload.week_starts_on,
        )
        await self.db.commit()
        await self.db.refresh(pref)
        return pref