"""
Centralized academic-event validation registry (Phase 6.5).

The single location for event-type-specific rules, ported from the legacy
`AcademicEventRegistry` + `validateAcademicEvent` (js/calendar-engine.js,
docs/09_ACADEMIC_EVENT_SYSTEM.md) and extended to the full 14-value Python
`EventType` enum. No event-type logic lives in endpoints, schemas, or the
service — endpoints only translate registry failures into HTTP responses.

Layering (per the Phase 6.5 spec):
    structural validation  -> Pydantic schemas
    business validation    -> EventService + this registry
    persistence            -> EventRepository

Rules are derived from repository evidence, never invented:
- requires_subject / requires_class_type / allowed_class_types come from the
  legacy registry (docs/09 §AcademicEventRegistry).
- Closure semantics come from the frozen calendar engine's closure list
  (calendar_engine.get_academic_day) — mirrored here so creation can sanity-
  check day-affecting state, but the engine remains the day-resolution
  authority.
- `substitution_schedule_override` is a day-name string from the engine's
  DAY_NAMES (the representation used by the engine and expand_baseline.py).
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from app.models.enums import ClassType, EventType, SubjectCategory
from app.engines.calendar_engine import DAY_NAMES


class EventValidationError(ValueError):
    """Business-level validation failure (mapped to 422 by the endpoint)."""


@dataclass(frozen=True)
class EventTypeRule:
    event_type: EventType
    display_name: str
    requires_subject: bool
    requires_class_type: bool
    allowed_class_types: List[ClassType] = field(default_factory=list)
    # Mirrors the engine's closure semantics (engine remains authoritative
    # for day resolution; this is metadata for creation-time guidance).
    is_closure: bool = False
    is_global: bool = False


def _rule(
    event_type: EventType,
    display_name: str,
    requires_subject: bool = False,
    requires_class_type: bool = False,
    allowed_class_types: Optional[List[ClassType]] = None,
    is_closure: bool = False,
    is_global: bool = False,
) -> EventTypeRule:
    return EventTypeRule(
        event_type=event_type,
        display_name=display_name,
        requires_subject=requires_subject,
        requires_class_type=requires_class_type,
        allowed_class_types=allowed_class_types or [],
        is_closure=is_closure,
        is_global=is_global,
    )


# Single source of truth for event-type rules. Derived from the legacy
# registry (EXTRA_*/CLASS_CANCELLED/SURPRISE_QUIZ/QUIZ_DAY/PUBLIC_HOLIDAY/
# INSTITUTE_HOLIDAY/WORKING_DAY_OVERRIDE/EMERGENCY_CLOSURE) plus the Python
# additions (WORKING_SATURDAY, FESTIVAL_HOLIDAY, SEMESTER_BREAK,
# MID_SEMESTER_BREAK), whose global/no-class-type semantics follow the
# documented break/holiday family.
EVENT_TYPE_RULES: dict[EventType, EventTypeRule] = {
    EventType.EXTRA_LECTURE: _rule(
        EventType.EXTRA_LECTURE, "Extra Lecture",
        requires_subject=True, requires_class_type=True,
        allowed_class_types=[ClassType.LECTURE],
    ),
    EventType.EXTRA_TUTORIAL: _rule(
        EventType.EXTRA_TUTORIAL, "Extra Tutorial",
        requires_subject=True, requires_class_type=True,
        allowed_class_types=[ClassType.TUTORIAL],
    ),
    EventType.EXTRA_PRACTICAL: _rule(
        EventType.EXTRA_PRACTICAL, "Extra Practical",
        requires_subject=True, requires_class_type=True,
        allowed_class_types=[ClassType.PRACTICAL],
    ),
    EventType.CLASS_CANCELLED: _rule(
        EventType.CLASS_CANCELLED, "Class Cancelled",
        requires_subject=True, requires_class_type=True,
        allowed_class_types=[
            ClassType.LECTURE, ClassType.TUTORIAL,
        ],
    ),
    # Phase 9.1 laboratory events. Both are subject-scoped PRACTICAL events
    # the synchronizer resolves into canonical ClassSession state: LAB_CANCELLED
    # cancels the matching practical occurrence (same session semantics as
    # CLASS_CANCELLED, restricted to practical subjects); MID_SEM_PRACTICAL
    # resolves/designates the practical occurrence as the mid-semester
    # practical. Neither is a closure, override, or quiz-schedule event.
    EventType.LAB_CANCELLED: _rule(
        EventType.LAB_CANCELLED, "Lab Cancelled",
        requires_subject=True, requires_class_type=True,
        allowed_class_types=[ClassType.PRACTICAL],
    ),
    EventType.MID_SEM_PRACTICAL: _rule(
        EventType.MID_SEM_PRACTICAL, "Mid-Sem Practical",
        requires_subject=True, requires_class_type=True,
        allowed_class_types=[ClassType.PRACTICAL],
    ),
    EventType.SURPRISE_QUIZ: _rule(
        EventType.SURPRISE_QUIZ, "Surprise Quiz",
        requires_subject=True, requires_class_type=True,
        allowed_class_types=[ClassType.LECTURE, ClassType.TUTORIAL],
    ),
    EventType.QUIZ_DAY: _rule(
        EventType.QUIZ_DAY, "Quiz Day",
        requires_subject=True, requires_class_type=False,
    ),
    # Unified holiday: the consolidated user-facing holiday type. Same
    # closure semantics as the legacy holiday family (PUBLIC_HOLIDAY /
    # INSTITUTE_HOLIDAY / FESTIVAL_HOLIDAY remain supported and readable);
    # the reason/occasion travels in the optional `note` field.
    EventType.HOLIDAY: _rule(
        EventType.HOLIDAY, "Holiday",
        is_closure=True, is_global=True,
    ),
    EventType.PUBLIC_HOLIDAY: _rule(
        EventType.PUBLIC_HOLIDAY, "Public Holiday",
        is_closure=True, is_global=True,
    ),
    EventType.INSTITUTE_HOLIDAY: _rule(
        EventType.INSTITUTE_HOLIDAY, "Institute Holiday",
        is_closure=True, is_global=True,
    ),
    EventType.FESTIVAL_HOLIDAY: _rule(
        EventType.FESTIVAL_HOLIDAY, "Festival Holiday",
        is_closure=True, is_global=True,
    ),
    EventType.EMERGENCY_CLOSURE: _rule(
        EventType.EMERGENCY_CLOSURE, "Emergency Closure",
        is_closure=True, is_global=True,
    ),
    EventType.SEMESTER_BREAK: _rule(
        EventType.SEMESTER_BREAK, "Semester Break",
        is_closure=True, is_global=True,
    ),
    EventType.MID_SEMESTER_BREAK: _rule(
        EventType.MID_SEMESTER_BREAK, "Mid Semester Break",
        is_closure=True, is_global=True,
    ),
    EventType.WORKING_DAY_OVERRIDE: _rule(
        EventType.WORKING_DAY_OVERRIDE, "Working Day Override",
        is_global=True,
    ),
    EventType.WORKING_SATURDAY: _rule(
        EventType.WORKING_SATURDAY, "Working Saturday",
        is_global=True,
    ),
}

# Valid values for substitution_schedule_override: the engine's canonical
# day-name representation (DAY_NAMES in calendar_engine.py).
VALID_SUBSTITUTION_DAYS = list(DAY_NAMES)

# Quiz events are scoped to quiz-bearing subjects. The canonical marker for a
# practical/lab subject is `SubjectCategory.LAB` (Phase 9.1 canonical
# metadata); quiz attendance only exists for theory subjects (eligibility
# treats lab subjects as 404 / strictly excluded).
QUIZ_BEARING_EVENT_TYPES = {
    EventType.SURPRISE_QUIZ,
    EventType.QUIZ_DAY,
}


def get_rule(event_type: EventType) -> EventTypeRule:
    rule = EVENT_TYPE_RULES.get(event_type)
    if rule is None:
        raise EventValidationError(f"Unknown event type: {event_type}")
    return rule


def validate_event(
    *,
    event_type: EventType,
    start_date: date,
    end_date: date,
    subject_id: Optional[object] = None,
    class_type: Optional[ClassType] = None,
    subject_category: Optional[SubjectCategory] = None,
    substitution_schedule_override: Optional[str] = None,
    is_working_day: Optional[bool] = None,
) -> None:
    """
    Validates an academic event against the registry (business rules).

    Structural shape (types, presence) is already enforced by the Pydantic
    schemas; this checks the registry rules that depend on actual values.
    Raises EventValidationError with a concrete message on failure.
    """
    rule = get_rule(event_type)

    if start_date > end_date:
        raise EventValidationError("start_date must not be after end_date")

    if rule.requires_subject and subject_id is None:
        raise EventValidationError(f"{rule.display_name} requires a subject")
    if not rule.requires_subject and subject_id is not None:
        raise EventValidationError(f"{rule.display_name} must not have a subject")

    if rule.requires_class_type and class_type is None:
        raise EventValidationError(f"{rule.display_name} requires a class type")
    if not rule.requires_class_type and class_type is not None:
        raise EventValidationError(f"{rule.display_name} must not have a class type")
    if (
        rule.requires_class_type
        and class_type is not None
        and class_type not in rule.allowed_class_types
    ):
        allowed = ", ".join(c.value for c in rule.allowed_class_types)
        raise EventValidationError(
            f"{rule.display_name} does not support class type {class_type.value} "
            f"(allowed: {allowed})"
        )

    if substitution_schedule_override is not None:
        if substitution_schedule_override not in VALID_SUBSTITUTION_DAYS:
            raise EventValidationError(
                "substitution_schedule_override must be a valid day name "
                f"(one of: {', '.join(VALID_SUBSTITUTION_DAYS)})"
            )

    # Quiz events (surprise quiz / quiz day) are theory-subject events: a lab
    # subject can never carry quiz attendance (eligibility strictly excludes
    # labs). The service resolves the subject's canonical category before
    # validation.
    if (
        event_type in QUIZ_BEARING_EVENT_TYPES
        and subject_category == SubjectCategory.LAB
    ):
        raise EventValidationError(
            f"{rule.display_name} is only valid for theory subjects "
            "(practical/lab subjects cannot host quizzes)"
        )

    # Working-day state is an explicit per-event override for the dominant
    # event (engine honors it when set). The engine treats closure types as
    # non-working regardless; no policy is invented beyond that.
    if is_working_day is not None and rule.is_closure:
        raise EventValidationError(
            f"{rule.display_name} is a closure; is_working_day cannot be set "
            "(the calendar engine treats closure days as non-working)"
        )

    # A Working Saturday is by definition a working day on Saturdays — an
    # explicit non-working override is contradictory and is rejected instead
    # of being silently ignored.
    if event_type == EventType.WORKING_SATURDAY and is_working_day is False:
        raise EventValidationError(
            "Working Saturday is always a working day on Saturdays; "
            "is_working_day=false is contradictory"
        )