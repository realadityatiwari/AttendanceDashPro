"""Institutional timezone helpers.

Single authoritative clock for "today" across the application. Extracted from
``app.services.attendance_service`` so that any layer (repositories, services,
endpoints) can resolve the institution-local current date without importing a
service module (avoids repository -> service layering inversion and circular
import risk). Semantics are unchanged: the institutional timezone
(settings.INSTITUTION_TIMEZONE, Asia/Kolkata) is the canonical local clock.

    from app.core.timezone import institution_today
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings

# Institutional timezone (settings.INSTITUTION_TIMEZONE, Asia/Kolkata) is the
# canonical local clock for "today". Attendance mutation is rejected for any
# session dated after this local date — future dates are view-only (Track
# renders them, but Present/Absent cannot be recorded before the date).
INSTITUTION_TZ = ZoneInfo(settings.INSTITUTION_TIMEZONE)


def institution_today() -> date:
    """The canonical institution-local current date (single source of truth)."""
    return datetime.now(INSTITUTION_TZ).date()
