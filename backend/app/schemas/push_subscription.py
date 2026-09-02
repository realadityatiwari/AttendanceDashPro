from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID
from datetime import datetime
from urllib.parse import urlparse

# Phase 11C-P2 push-subscription contract.
#
# POST /api/v1/push-subscriptions accepts ONLY the browser subscription data
# needed for future push delivery: the endpoint URL and the browser-generated
# p256dh/auth keys. user_id is intentionally absent — the owner is always the
# authenticated user resolved from the JWT (get_current_user), and the client
# can never specify an arbitrary owner.

# Endpoint URLs can be long (FCM/Mozilla/APNs endpoints); cap generously.
ENDPOINT_MAX_LENGTH = 2048
# Browser push keys are URL-safe base64 strings. p256dh (P-256 uncompressed) is
# ~87 chars and auth is ~24 chars; a generous cap rejects junk without assuming
# a specific browser vendor.
KEY_MAX_LENGTH = 1024


class PushSubscriptionKeys(BaseModel):
    """The browser-generated keys of a PushSubscription (keys.p256dh/auth)."""
    p256dh: str
    auth: str

    @field_validator("p256dh", "auth")
    @classmethod
    def _validate_key_length(cls, value: str) -> str:
        if len(value) > KEY_MAX_LENGTH:
            raise ValueError("Key value exceeds maximum length")
        return value


class PushSubscriptionCreate(BaseModel):
    """POST payload for /api/v1/push-subscriptions.

    Matches the browser PushSubscription.toJSON() shape (endpoint + keys) so
    the frontend sends exactly the data the Web Push contract provides. No
    user_id, no tokens, no browser metadata.

    extra="forbid": unknown fields (including a client-supplied ``user_id``)
    are rejected outright — the owner can never be influenced by the request
    body; it is always the authenticated JWT principal.
    """
    model_config = ConfigDict(extra="forbid")

    endpoint: str
    keys: PushSubscriptionKeys

    @field_validator("endpoint")
    @classmethod
    def _validate_endpoint(cls, value: str) -> str:
        if len(value) > ENDPOINT_MAX_LENGTH:
            raise ValueError("Endpoint exceeds maximum length")
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("Endpoint must be a valid HTTPS URL")
        return value


class PushSubscriptionResponse(BaseModel):
    """Response for the push-subscription endpoints.

    Exposes only the persisted row identity the client needs for unsubscribe
    (id + endpoint). p256dh/auth are server-side delivery data and are never
    returned to the client.
    """
    id: UUID
    endpoint: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
