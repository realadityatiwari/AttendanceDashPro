"""Refresh-token session infrastructure (rotation + reuse detection).

Security invariants:
- The raw refresh secret is generated with `secrets` (CSPRNG) and is NEVER
  persisted; only its SHA-256 hex digest is stored.
- Lookup is always on the hash of the presented token.
- Rotation preserves the token family; reuse of a used/revoked/expired token
  revokes the entire family (theft indicator) and never yields a session.
- Concurrency: rotation state transitions happen inside a single
  serialization-safe transaction (SELECT ... FOR UPDATE on the token row);
  two simultaneous refreshes cannot both succeed — the loser observes a used
  token and triggers family revocation.
- No raw tokens are ever logged.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.logging import get_logger
from app.models.refresh_token import RefreshToken
from app.models.user import User

logger = get_logger(__name__)

# 256 bits of entropy, url-safe — opaque, not a JWT.
_REFRESH_SECRET_BYTES = 32


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _new_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


class RefreshTokenError(Exception):
    """Domain error: refresh token invalid/expired/revoked/reused."""

    def __init__(self, message: str, *, reuse_detected: bool = False):
        super().__init__(message)
        self.reuse_detected = reuse_detected


async def _revoke_family(db: AsyncSession, family_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.family_id == family_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
        .values(is_revoked=True, updated_at=datetime.now(timezone.utc))
    )


class RefreshTokenService:
    """Issues, rotates and revokes opaque DB-backed refresh tokens."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def issue(self, user: User) -> tuple[str, RefreshToken]:
        """Mint a new token family for a freshly authenticated user.

        Returns the raw secret (to be set as an HttpOnly cookie) and the
        persisted row. The raw secret never touches the database or logs.
        """
        raw = secrets.token_urlsafe(_REFRESH_SECRET_BYTES)
        row = RefreshToken(
            user_id=user.id,
            token_hash=_hash_token(raw),
            family_id=uuid.uuid4(),
            expires_at=_new_expiry(),
        )
        self.db.add(row)
        await self.db.flush()
        return raw, row

    async def rotate(self, raw_token: str) -> tuple[User, str, RefreshToken]:
        """Validate + rotate a presented refresh token.

        Returns (user, new_raw_secret, new_row). Raises RefreshTokenError on
        any failure path; reuse of a consumed/revoked token revokes the whole
        family before raising.
        """
        token_hash = _hash_token(raw_token)

        # Single-row lock: two simultaneous refreshes serialize here; the
        # loser observes is_used=True and takes the reuse path.
        row = (
            await self.db.execute(
                select(RefreshToken)
                .where(RefreshToken.token_hash == token_hash)
                .with_for_update()
            )
        ).scalars().first()

        if row is None:
            # Unknown token: never reveal whether anything exists.
            raise RefreshTokenError("Invalid refresh token")

        family_id = row.family_id
        user_id = row.user_id

        if row.is_used or row.is_revoked:
            # Reuse of an already-rotated/revoked token is a theft indicator:
            # revoke the entire family, never silently re-issue a session.
            await _revoke_family(self.db, family_id)
            await self.db.commit()
            logger.warning(
                "Refresh-token reuse detected: family revoked for user %s", user_id
            )
            raise RefreshTokenError("Invalid refresh token", reuse_detected=True)

        if row.expires_at <= datetime.now(timezone.utc):
            # Natural expiry: reject without family revocation (not theft).
            raise RefreshTokenError("Invalid refresh token")

        user = (
            await self.db.execute(select(User).where(User.id == user_id))
        ).scalars().first()

        if user is None or not getattr(user, "is_active", True):
            # The user vanished or was deactivated between issue and refresh:
            # revoke the family, never mint a session for an invalid user.
            await _revoke_family(self.db, family_id)
            await self.db.commit()
            raise RefreshTokenError("Invalid refresh token")

        raw_new = secrets.token_urlsafe(_REFRESH_SECRET_BYTES)
        new_row = RefreshToken(
            user_id=user_id,
            token_hash=_hash_token(raw_new),
            family_id=family_id,
            expires_at=_new_expiry(),
        )
        self.db.add(new_row)
        await self.db.flush()

        # Mark the old token used and link its replacement.
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.id == row.id)
            .values(is_used=True, replaced_by=new_row.id, updated_at=datetime.now(timezone.utc))
        )
        await self.db.commit()
        return user, raw_new, new_row

    async def revoke_by_token(self, raw_token: str) -> None:
        """Logout: revoke the presented token's family. Idempotent — an
        unknown/expired/already-revoked token is silently accepted."""
        token_hash = _hash_token(raw_token)
        row = (
            await self.db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).scalars().first()
        if row is None:
            return
        await _revoke_family(self.db, row.family_id)
        await self.db.commit()
