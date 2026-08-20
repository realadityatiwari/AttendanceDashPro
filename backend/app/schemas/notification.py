from pydantic import BaseModel, model_validator
from typing import List, Optional
from uuid import UUID
from datetime import date
from app.models.enums import NotificationKind

# Phase 11A/11B notification contract.
#
# 11A: read-only aggregation contract — every item is a projection of existing
# engine/service outputs composed by NotificationService; notifications never
# compute attendance themselves.
#
# 11B (additive): the same item shape, extended with the persisted-row
# identifier (notification_id) and the read state (is_read); the response
# additionally carries the unread count. Persistence is DB-enforced idempotent
# (UNIQUE(user_id, kind, occurrence_key)); generation snapshots projections
# into rows and regeneration refreshes in place.

class NotificationItem(BaseModel):
    # Deterministic natural key (kind + canonical reference) the client uses to
    # key and deduplicate items; stable across the 11A -> 11B persistence step.
    id: str
    kind: NotificationKind
    date: date
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    message: str
    # Canonical reference fields (for persistence/dedup and client
    # deep-linking); None when the kind has no such reference.
    session_id: Optional[UUID] = None  # CLASS_REMINDER
    quiz_cycle: Optional[int] = None   # QUIZ_APPROACHING
    event_id: Optional[UUID] = None    # ACADEMIC_EVENT
    # Phase 11B: the persisted row id (the PATCH mutation target). Null in the
    # pre-11B read model; always present once the inbox is persisted.
    notification_id: Optional[UUID] = None
    # Phase 11B: read state. False when unread (default for new rows).
    is_read: bool = False

class NotificationsResponse(BaseModel):
    items: List[NotificationItem] = []
    # Institution-local current date (server-generated; never the client clock).
    as_of: date
    # Phase 11B: number of unread, non-dismissed notifications (the badge).
    unread_count: int = 0

class NotificationUpdate(BaseModel):
    """Phase 11B PATCH body: state transitions for one persisted notification.

    Read/dismiss are separate booleans; exactly the semantics of the audit
    (PATCH read/dismiss). At least one field must be present — an empty body is
    a 422, never a silent no-op success. is_dismissed is a persisted flag (not
    a physical delete) so a regenerated occurrence cannot resurrect a
    dismissed row (audit §8-3/5 spam mitigation).
    """
    is_read: Optional[bool] = None
    is_dismissed: Optional[bool] = None

    @model_validator(mode="after")
    def _at_least_one_field(self):
        if self.is_read is None and self.is_dismissed is None:
            raise ValueError(
                "Provide at least one of is_read or is_dismissed"
            )
        return self