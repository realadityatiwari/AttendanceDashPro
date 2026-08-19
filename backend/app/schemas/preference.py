from pydantic import BaseModel
from datetime import datetime
from app.models.enums import WeekStartsOn


class PreferenceUpdate(BaseModel):
    """PUT payload for /api/v1/student/preferences (Phase 10D).

    Full-object replacement: all three fields are required, so a PUT always
    writes a complete preference object. user_id and timestamps are
    intentionally absent — the owner is always the authenticated user
    resolved from the JWT (get_current_user) and timestamps are
    server-controlled. Invalid week values (anything outside SUNDAY/MONDAY)
    fail Pydantic validation with the normal 422 response.
    """
    class_reminders: bool
    auto_mark_present: bool
    week_starts_on: WeekStartsOn


class PreferenceResponse(BaseModel):
    """GET/PUT response for /api/v1/student/preferences (Phase 10D).

    Always a complete preference object: the three stored values plus the
    server timestamps. user_id is not exposed — there is no user selector in
    this API, so the response never needs it.
    """
    class_reminders: bool
    auto_mark_present: bool
    week_starts_on: WeekStartsOn
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
