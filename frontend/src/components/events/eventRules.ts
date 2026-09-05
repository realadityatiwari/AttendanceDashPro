"use client";

import { ClassType, ElectiveSlot, EventType } from "@/types/api";

/**
 * Frontend mirror of the backend event validation registry
 * (backend/app/services/event_registry.py) — used ONLY to decide which form
 * fields to show. The backend registry remains the authoritative validator.
 */
export interface EventTypeRule {
  eventType: EventType;
  requiresSubject: boolean;
  requiresClassType: boolean;
  allowedClassTypes: ClassType[];
  isClosure: boolean;
  isGlobal: boolean;
}

export const EVENT_TYPE_RULES: Record<EventType, EventTypeRule> = {
  [EventType.EXTRA_LECTURE]: {
    eventType: EventType.EXTRA_LECTURE, requiresSubject: true, requiresClassType: true,
    allowedClassTypes: [ClassType.LECTURE], isClosure: false, isGlobal: false,
  },
  [EventType.EXTRA_TUTORIAL]: {
    eventType: EventType.EXTRA_TUTORIAL, requiresSubject: true, requiresClassType: true,
    allowedClassTypes: [ClassType.TUTORIAL], isClosure: false, isGlobal: false,
  },
  [EventType.EXTRA_PRACTICAL]: {
    eventType: EventType.EXTRA_PRACTICAL, requiresSubject: true, requiresClassType: true,
    allowedClassTypes: [ClassType.PRACTICAL], isClosure: false, isGlobal: false,
  },
  [EventType.CLASS_CANCELLED]: {
    eventType: EventType.CLASS_CANCELLED, requiresSubject: true, requiresClassType: true,
    allowedClassTypes: [ClassType.LECTURE, ClassType.TUTORIAL],
    isClosure: false, isGlobal: false,
  },
  // Phase 9.1 laboratory events: subject-scoped PRACTICAL events resolved by
  // the canonical event synchronizer (no separate lab attendance system).
  [EventType.LAB_CANCELLED]: {
    eventType: EventType.LAB_CANCELLED, requiresSubject: true, requiresClassType: true,
    allowedClassTypes: [ClassType.PRACTICAL], isClosure: false, isGlobal: false,
  },
  [EventType.MID_SEM_PRACTICAL]: {
    eventType: EventType.MID_SEM_PRACTICAL, requiresSubject: true, requiresClassType: true,
    allowedClassTypes: [ClassType.PRACTICAL], isClosure: false, isGlobal: false,
  },
  [EventType.SURPRISE_QUIZ]: {
    eventType: EventType.SURPRISE_QUIZ, requiresSubject: true, requiresClassType: true,
    allowedClassTypes: [ClassType.LECTURE, ClassType.TUTORIAL], isClosure: false, isGlobal: false,
  },
  [EventType.QUIZ_DAY]: {
    eventType: EventType.QUIZ_DAY, requiresSubject: true, requiresClassType: false,
    allowedClassTypes: [], isClosure: false, isGlobal: false,
  },
  // Unified holiday: the consolidated closure flow (single day or range with
  // a reason/occasion note). The legacy holiday types remain supported for
  // backward compatibility.
  [EventType.HOLIDAY]: {
    eventType: EventType.HOLIDAY, requiresSubject: false, requiresClassType: false,
    allowedClassTypes: [], isClosure: true, isGlobal: true,
  },
  [EventType.PUBLIC_HOLIDAY]: {
    eventType: EventType.PUBLIC_HOLIDAY, requiresSubject: false, requiresClassType: false,
    allowedClassTypes: [], isClosure: true, isGlobal: true,
  },
  [EventType.INSTITUTE_HOLIDAY]: {
    eventType: EventType.INSTITUTE_HOLIDAY, requiresSubject: false, requiresClassType: false,
    allowedClassTypes: [], isClosure: true, isGlobal: true,
  },
  [EventType.FESTIVAL_HOLIDAY]: {
    eventType: EventType.FESTIVAL_HOLIDAY, requiresSubject: false, requiresClassType: false,
    allowedClassTypes: [], isClosure: true, isGlobal: true,
  },
  [EventType.EMERGENCY_CLOSURE]: {
    eventType: EventType.EMERGENCY_CLOSURE, requiresSubject: false, requiresClassType: false,
    allowedClassTypes: [], isClosure: true, isGlobal: true,
  },
  [EventType.SEMESTER_BREAK]: {
    eventType: EventType.SEMESTER_BREAK, requiresSubject: false, requiresClassType: false,
    allowedClassTypes: [], isClosure: true, isGlobal: true,
  },
  [EventType.MID_SEMESTER_BREAK]: {
    eventType: EventType.MID_SEMESTER_BREAK, requiresSubject: false, requiresClassType: false,
    allowedClassTypes: [], isClosure: true, isGlobal: true,
  },
  [EventType.WORKING_DAY_OVERRIDE]: {
    eventType: EventType.WORKING_DAY_OVERRIDE, requiresSubject: false, requiresClassType: false,
    allowedClassTypes: [], isClosure: false, isGlobal: true,
  },
  [EventType.WORKING_SATURDAY]: {
    eventType: EventType.WORKING_SATURDAY, requiresSubject: false, requiresClassType: false,
    allowedClassTypes: [], isClosure: false, isGlobal: true,
  },
  // Phase 23.7: subject-scoped modified occurrence. The scheduled class
  // happened but was modified (time/room/delivery). Not extra, not cancelled.
  [EventType.CLASS_MODIFIED]: {
    eventType: EventType.CLASS_MODIFIED, requiresSubject: true, requiresClassType: true,
    allowedClassTypes: [ClassType.LECTURE, ClassType.TUTORIAL, ClassType.PRACTICAL],
    isClosure: false, isGlobal: false,
  },
};

// Event types students may create/update/deactivate for their OWN enrolled
// subjects (attendance spec: events are student-adjustable; mirrors the
// backend STUDENT_CREATABLE_EVENT_TYPES). Used only to decide which types the
// form exposes and which rows offer edit/deactivate to non-admins — the
// backend remains authoritative.
export const STUDENT_CREATABLE_EVENT_TYPES: EventType[] = [
  EventType.EXTRA_LECTURE,
  EventType.EXTRA_TUTORIAL,
  EventType.EXTRA_PRACTICAL,
  EventType.CLASS_CANCELLED,
  EventType.SURPRISE_QUIZ,
  // Phase 9.1: students may record laboratory reality (mid-sem practical /
  // cancelled lab) for their own enrolled practical subjects.
  EventType.MID_SEM_PRACTICAL,
  EventType.LAB_CANCELLED,
  // Phase 23.7: students may report a scheduled class was modified
  // (subject-scoped, enrollment-checked by the backend).
  EventType.CLASS_MODIFIED,
];

export function canStudentMutateEventType(eventType: EventType): boolean {
  return STUDENT_CREATABLE_EVENT_TYPES.includes(eventType);
}

// Humanizes any event type string — including types unknown to the current
// enum — so an unknown/future type renders a readable label instead of
// crashing. Canonical copy (Phase 6, UI-021): previously duplicated in
// EventRow and DayDetail.
export function humanizeEventType(type: string): string {
  return type.toLowerCase().replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

// Null for class types without a display label (unknown/legacy). Note: the
// dashboard's status.ts has its own classTypeLabel with a DIFFERENT contract
// (string return, "Practical" default) — intentionally not unified.
export function classTypeLabel(type: ClassType | null): string | null {
  if (type === ClassType.LECTURE) return "Lecture";
  if (type === ClassType.TUTORIAL) return "Tutorial";
  if (type === ClassType.PRACTICAL || type === ClassType.PRACTICAL2) return "Practical";
  return null;
}

export type DurationMode = "single" | "range";

// Default duration mode for a newly created event (UX preference only). The
// backend has no duration concept — every event is start_date/end_date and a
// single-day event is simply start_date == end_date. Used to seed the Add
// Event form and when the user switches event type without having deliberately
// changed the duration control.
export const DEFAULT_DURATION_MODE: Record<EventType, DurationMode> = {
  // Naturally single-day: extras, cancellations, quizzes, and the Phase 9.1
  // laboratory events (each resolves one practical occurrence for the date).
  [EventType.EXTRA_LECTURE]: "single",
  [EventType.EXTRA_TUTORIAL]: "single",
  [EventType.EXTRA_PRACTICAL]: "single",
  [EventType.CLASS_CANCELLED]: "single",
  [EventType.SURPRISE_QUIZ]: "single",
  [EventType.QUIZ_DAY]: "single",
  [EventType.MID_SEM_PRACTICAL]: "single",
  [EventType.LAB_CANCELLED]: "single",
  [EventType.CLASS_MODIFIED]: "single",
  // Naturally multi-day: breaks and the holiday/closure/working-day family
  // (still able to represent a single day by collapsing to one date).
  [EventType.HOLIDAY]: "range",
  [EventType.PUBLIC_HOLIDAY]: "range",
  [EventType.INSTITUTE_HOLIDAY]: "range",
  [EventType.FESTIVAL_HOLIDAY]: "range",
  [EventType.EMERGENCY_CLOSURE]: "range",
  [EventType.SEMESTER_BREAK]: "range",
  [EventType.MID_SEMESTER_BREAK]: "range",
  [EventType.WORKING_DAY_OVERRIDE]: "range",
  [EventType.WORKING_SATURDAY]: "range",
};

export function defaultDurationMode(eventType: EventType): DurationMode {
  return DEFAULT_DURATION_MODE[eventType] ?? "range";
}

// Engine day-name representation (backend DAY_NAMES in calendar_engine.py).
export const SUBSTITUTION_DAYS = [
  "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY",
];

export const CLASS_TYPE_LABELS: Record<ClassType, string> = {
  [ClassType.LECTURE]: "Lecture",
  [ClassType.TUTORIAL]: "Tutorial",
  [ClassType.PRACTICAL]: "Practical",
  [ClassType.PRACTICAL2]: "Practical", // legacy alias, never returned by the backend
};

// Phase 22.4: the ADMIN-facing "subject" options for Departmental Elective
// logical slots. ADMIN creates ONE shared event scoped to the slot; each
// student sees it resolved to their own selected subject. These are not
// concrete subjects — the backend rejects them for non-ADMIN users and for
// practical/lab event types.
export const ELECTIVE_SLOT_LABELS: Record<ElectiveSlot, string> = {
  [ElectiveSlot.ELECTIVE_I]: "Departmental Elective-I",
  [ElectiveSlot.ELECTIVE_II]: "Departmental Elective-II",
};

// Option values used by the event form's subject selector to represent the
// logical slots (prefixed so they can never collide with subject UUIDs).
export const SLOT_OPTION_PREFIX = "slot:";

export function slotOptionValue(slot: ElectiveSlot): string {
  return `${SLOT_OPTION_PREFIX}${slot}`;
}

export function parseSlotOption(value: string): ElectiveSlot | null {
  if (!value.startsWith(SLOT_OPTION_PREFIX)) return null;
  const slot = value.slice(SLOT_OPTION_PREFIX.length);
  return (Object.values(ElectiveSlot) as string[]).includes(slot)
    ? (slot as ElectiveSlot)
    : null;
}

export function getRule(eventType: EventType): EventTypeRule {
  return EVENT_TYPE_RULES[eventType] ?? {
    eventType, requiresSubject: false, requiresClassType: false,
    allowedClassTypes: [], isClosure: false, isGlobal: true,
  };
}