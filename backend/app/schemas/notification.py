from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import date
from app.models.enums import NotificationKind

# Phase 11A notification read model — additive, read-only aggregation contract.
# Every item is a projection of existing engine/service outputs composed by
# NotificationService; notifications never compute attendance themselves. There
# is no persistence in 11A: the contract is generated on-read (notification
# storage/dedup is Phase 11B).

class NotificationItem(BaseModel):
    # Deterministic natural key (kind + canonical reference) the client uses to
    # key and deduplicate items; stable across the 11A -> 11B persistence step.
    id: str
    kind: NotificationKind
    date: date
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    message: str
    # Canonical reference fields (for future 11B persistence/dedup and client
    # deep-linking); None when the kind has no such reference.
    session_id: Optional[UUID] = None  # CLASS_REMINDER
    quiz_cycle: Optional[int] = None   # QUIZ_APPROACHING
    event_id: Optional[UUID] = None    # ACADEMIC_EVENT

class NotificationsResponse(BaseModel):
    items: List[NotificationItem] = []
    # Institution-local current date (server-generated; never the client clock).
    as_of: date