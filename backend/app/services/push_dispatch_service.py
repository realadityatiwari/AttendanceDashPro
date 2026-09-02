from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, List, Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.repositories.push_subscription_repo import PushSubscriptionRepository

logger = get_logger("app.push_dispatch")

# Web Push TTL for delivered payloads (seconds). 0 = no storage (drop if
# offline); a bounded TTL lets the push service hold the message briefly.
_DEFAULT_TTL_SECONDS = 3600
# HTTP timeout for the push-service request (network boundary).
_SEND_TIMEOUT_SECONDS = 10.0

# Provider status codes that mean the subscription is permanently gone.
# Per the Web Push protocol these are 404 (endpoint not found) and 410 (gone).
_PERMANENTLY_GONE_STATUS_CODES = (404, 410)


class PushResult(str, Enum):
    """Outcome classification for a single Web Push delivery attempt.

    - SUCCESS: the push service accepted the delivery.
    - INVALID_SUBSCRIPTION: the provider reports the subscription is
      permanently gone (404/410) — the row is removed.
    - TEMPORARY_FAILURE: transient (network error, timeout, 5xx, 429, other
      provider rejection) — the row is KEPT for a later retry.
    - CONFIGURATION_ERROR: VAPID is not configured; nothing was attempted.
    - UNEXPECTED_ERROR: an internal failure outside the delivery call.
    """
    SUCCESS = "SUCCESS"
    INVALID_SUBSCRIPTION = "INVALID_SUBSCRIPTION"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"


@dataclass
class DeliveryResult:
    """Outcome of dispatching one push payload to one subscription."""
    subscription_id: UUID
    result: PushResult
    error: Optional[str] = None


@dataclass
class PushPayload:
    """The JSON payload sent to the P1 service worker.

    Shape is exactly the P1 service-worker contract:
    ``{ title, body, icon, badge, tag, url }`` (all optional there, bounded,
    same-origin validated). ``notification_id`` and ``kind`` are ADDITIVE
    optional structured data (the service worker ignores unknown fields; P4 may
    consume them). Never contains tokens, JWTs, keys, or sensitive internals.

    ``url`` is restricted to same-origin relative application paths (must start
    with "/" and not "//") so a payload can never navigate the browser to an
    external origin — mirroring the service worker's own resolvePushUrl().
    """

    title: str
    body: str
    icon: str = "/brand/icon-192.png"
    badge: str = "/brand/icon-192.png"
    tag: str = ""
    url: str = "/dashboard"
    notification_id: Optional[str] = None
    kind: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.url, str) or not self.url.startswith("/") or self.url.startswith("//"):
            raise ValueError("Push payload url must be a same-origin relative path")

    def to_json(self) -> str:
        """Serialize to the exact JSON the P1 service worker parses."""
        payload: dict[str, Any] = {
            "title": self.title,
            "body": self.body,
            "icon": self.icon,
            "badge": self.badge,
            "tag": self.tag,
            "url": self.url,
        }
        if self.notification_id is not None:
            payload["notification_id"] = self.notification_id
        if self.kind is not None:
            payload["kind"] = self.kind
        return json.dumps(payload, ensure_ascii=False)


SendFunction = Callable[..., Awaitable[Any]]


class PushDispatchService:
    """Phase 11C-P3: Web Push DELIVERY infrastructure.

    Responsibility is ONLY delivery: given a user/subscription and a
    PushPayload, attempt Web Push via VAPID + pywebpush and report the outcome.
    It does NOT decide which notification should exist, whether one should be
    generated, or when it is due — those decisions belong to P4 (triggers).

    The canonical in-app notification system is never touched: a push failure
    never deletes, alters, or invalidates canonical notifications.

    Failure isolation: one subscription's failure never affects other
    subscriptions of the same user or other users. Permanently invalid
    subscriptions (provider 404/410) are removed via the existing P2 repository
    (owner-scoped, repo-owned commit — the established session convention);
    transient failures keep the row. Credentials (endpoint/p256dh/auth) are
    never logged — only the subscription UUID and the outcome classification.
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        send_function: Optional[SendFunction] = None,
    ):
        self.db = db
        self.repo = PushSubscriptionRepository(db)
        # The external delivery boundary. Injectable for verification; defaults
        # to pywebpush.webpush_async (async-native, matches the app stack).
        self._send = send_function or self._default_send

    # ── configuration ────────────────────────────────────────────────────────

    @staticmethod
    def is_configured() -> bool:
        """True only when the full VAPID triple is present. Public + private
        keys and subject are all required for authenticated delivery."""
        return bool(
            settings.VAPID_PUBLIC_KEY
            and settings.VAPID_PRIVATE_KEY
            and settings.VAPID_SUBJECT
        )

    # ── external delivery boundary ───────────────────────────────────────────

    async def _default_send(self, subscription_info: dict, data: str) -> Any:
        """Send via pywebpush's async entry point (aiohttp). Raises
        WebPushException on any non-success, whose ``status_code`` classifies
        the outcome; network/timeout errors surface as raw exceptions."""
        from pywebpush import webpush_async

        return await webpush_async(
            subscription_info=subscription_info,
            data=data,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
            ttl=_DEFAULT_TTL_SECONDS,
            timeout=_SEND_TIMEOUT_SECONDS,
        )

    @staticmethod
    def _subscription_info(sub: PushSubscription) -> dict:
        return {
            "endpoint": sub.endpoint,
            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
        }

    # ── delivery ─────────────────────────────────────────────────────────────

    async def _attempt(self, sub: PushSubscription, data: str) -> PushResult:
        """One delivery attempt; classifies the outcome without side effects."""
        if not self.is_configured():
            logger.warning(
                "Push delivery skipped: VAPID not configured (subscription=%s)",
                sub.id,
            )
            return PushResult.CONFIGURATION_ERROR
        try:
            await self._send(self._subscription_info(sub), data)
            return PushResult.SUCCESS
        except Exception as exc:  # noqa: BLE001 — classification boundary
            # pywebpush raises WebPushException with a ``status_code`` property
            # (None when no HTTP response, e.g. a network error). aiohttp
            # network/timeout errors carry no status either.
            status_code = getattr(exc, "status_code", None)
            if status_code in _PERMANENTLY_GONE_STATUS_CODES:
                return PushResult.INVALID_SUBSCRIPTION
            return PushResult.TEMPORARY_FAILURE

    async def dispatch_to_subscription(
        self,
        sub: PushSubscription,
        payload: PushPayload,
    ) -> DeliveryResult:
        """Deliver ``payload`` to one persisted subscription.

        On a permanently-invalid subscription the row is removed (owner-scoped
        via the existing P2 repository). Never raises for delivery failures —
        the outcome is returned.
        """
        data = payload.to_json()
        result = await self._attempt(sub, data)
        if result is PushResult.INVALID_SUBSCRIPTION:
            logger.warning(
                "Push subscription permanently invalid; removing (subscription=%s)",
                sub.id,
            )
            try:
                await self.repo.delete(sub.user_id, sub.id)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to remove invalid push subscription=%s: %s",
                    sub.id,
                    exc,
                )
                return DeliveryResult(
                    subscription_id=sub.id,
                    result=PushResult.UNEXPECTED_ERROR,
                    error="Failed to remove invalid subscription",
                )
            return DeliveryResult(
                subscription_id=sub.id,
                result=PushResult.INVALID_SUBSCRIPTION,
                error="Subscription permanently invalid; removed",
            )
        if result is PushResult.SUCCESS:
            logger.debug("Push delivered (subscription=%s)", sub.id)
        elif result is PushResult.TEMPORARY_FAILURE:
            logger.warning("Push delivery transient failure (subscription=%s)", sub.id)
        return DeliveryResult(subscription_id=sub.id, result=result)

    async def dispatch_to_user(
        self,
        user: Union[User, UUID],
        payload: PushPayload,
    ) -> List[DeliveryResult]:
        """Deliver ``payload`` to every subscription belonging to the user.

        Each subscription is attempted independently — one failure never stops
        the others. Returns one DeliveryResult per subscription (empty list when
        the user has no subscriptions). Accepts a User OR a raw user UUID.
        """
        user_id = user.id if isinstance(user, User) else user
        subs = await self.repo.get_by_user(user_id)
        results: List[DeliveryResult] = []
        for sub in subs:
            try:
                results.append(await self.dispatch_to_subscription(sub, payload))
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Unexpected push dispatch error (subscription=%s): %s",
                    sub.id,
                    exc,
                )
                results.append(
                    DeliveryResult(
                        subscription_id=sub.id,
                        result=PushResult.UNEXPECTED_ERROR,
                        error="Unexpected dispatch error",
                    )
                )
        return results
