"""Stage 3A — admin-assisted password recovery (single-use reset tokens).

Security invariants (mirrors ``refresh_token_service``):
- The raw reset secret is generated with ``secrets`` (CSPRNG) and is NEVER
  persisted; only its SHA-256 hex digest is stored.
- Lookup is always on the hash of the presented token.
- Single-use is enforced by a conditional UPDATE guarded on the token being
  unredeemed, unrevoked and unexpired; the loser of a concurrent redemption
  race observes ``rowcount == 0`` and is rejected. No raw tokens are logged.
- Issuance invalidates any previously outstanding token for the same student
  inside the same transaction, so at most one recovery path is live.

The service never sets or reads a plaintext password: it accepts an
already-validated new password from the endpoint and delegates hashing to
``hash_password``.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.services.refresh_token_service import RefreshTokenService

# 256 bits of entropy, url-safe — opaque, not a JWT.
_RESET_SECRET_BYTES = 32


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_expiry() -> datetime:
    return _now() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)


class PasswordResetError(Exception):
    """Domain error: reset token unknown/expired/redeemed/revoked."""


class PasswordResetService:
    """Issues and redeems admin-assisted password-reset tokens."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def issue(self, student: User, admin: User) -> tuple[str, PasswordResetToken]:
        """Mint a single-use reset token for ``student``, issued by ``admin``.

        Invalidates (revokes) any previously outstanding token for the same
        student first, so only one recovery path is ever live. Returns the raw
        secret (to be shown to the admin exactly once) and the persisted row.
        Does NOT commit — the caller owns the transaction.
        """
        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == student.id,
                PasswordResetToken.redeemed_at.is_(None),
                PasswordResetToken.is_revoked == False,  # noqa: E712
            )
            .values(is_revoked=True, updated_at=_now())
        )

        raw = secrets.token_urlsafe(_RESET_SECRET_BYTES)
        row = PasswordResetToken(
            user_id=student.id,
            issued_by_id=admin.id,
            token_hash=_hash_token(raw),
            expires_at=_new_expiry(),
        )
        self.db.add(row)
        await self.db.flush()
        return raw, row

    async def redeem(self, raw_token: str, new_password: str) -> User:
        """Consume ``raw_token`` and set the owner's new password.

        All state changes happen in the caller's transaction: the token is
        atomically marked redeemed, the target user's hash is replaced,
        competing outstanding tokens are revoked, and all of the user's
        refresh-token families are revoked. Raises ``PasswordResetError`` on
        any invalid/expired/used/revoked token (a single generic failure).

        Does NOT commit — the caller commits (or rolls back) atomically.
        """
        token_hash = _hash_token(raw_token)
        now = _now()

        row = (
            await self.db.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.token_hash == token_hash
                )
            )
        ).scalars().first()

        # Unknown token: never reveal whether anything exists.
        if row is None:
            raise PasswordResetError("Invalid or expired reset token")
        if row.is_revoked or row.redeemed_at is not None:
            raise PasswordResetError("Invalid or expired reset token")
        if row.expires_at <= now:
            raise PasswordResetError("Invalid or expired reset token")

        # Atomic single-use gate: only one concurrent caller can flip the row
        # from unredeemed -> redeemed; the loser gets rowcount 0.
        result = await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.id == row.id,
                PasswordResetToken.redeemed_at.is_(None),
                PasswordResetToken.is_revoked == False,  # noqa: E712
                PasswordResetToken.expires_at > now,
            )
            .values(redeemed_at=now, updated_at=now)
        )
        if (result.rowcount or 0) == 0:
            raise PasswordResetError("Invalid or expired reset token")

        user = (
            await self.db.execute(select(User).where(User.id == row.user_id))
        ).scalars().first()
        if user is None:
            raise PasswordResetError("Invalid or expired reset token")

        user.hashed_password = hash_password(new_password)

        # Invalidate any other outstanding token for this student.
        await self.db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.id != row.id,
                PasswordResetToken.redeemed_at.is_(None),
                PasswordResetToken.is_revoked == False,  # noqa: E712
            )
            .values(is_revoked=True, updated_at=now)
        )

        # Revoke every refresh-token family (participates in this transaction).
        await RefreshTokenService(self.db).revoke_all_for_user(user.id)
        return user