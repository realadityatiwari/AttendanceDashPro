# 05 — Calendar Engine

**File**: `js/calendar-engine.js`  
**Lines**: 736  
**Status**: ✅ Complete, production-stable

---

## Purpose

The Calendar Engine is the **single temporal authority** for the entire application. It answers every date-related question: Is a given day a working day? What events occur on a date? What is the attendance window for a subject before its quiz? What is the effective teaching day schedule on a working Saturday?

No other module is allowed to reason about dates, holidays, working days, or quiz windows independently.

---

## Why It Exists

Early versions of the codebase had duplicated temporal logic scattered across the Attendance Engine, Quiz Engine, and UI layer. Each maintained its own notion of "quiz window" and "working day." This created subtle inconsistencies when edge cases arose (e.g., holidays exactly on or adjacent to a quiz date).

The Calendar Engine was introduced during Phase A2.3 to consolidate all temporal logic into one stateless, pure functional module with a verified, deterministic API.

---

## Internal State

The engine maintains two internal cache levels:

```javascript
let l1StaticData = null;        // Frozen AcademicCalendar (loaded once at bootstrap)
let l2MemoryCache = new Map();  // AcademicDay result cache (keyed by YYYY-MM-DD)
let runtimeEvents = {};         // Date-indexed: YYYY-MM-DD -> AcademicEvent[]
```

- **L1** is loaded exactly once via `initCalendarEngine()`. It is `Object.freeze()`d for immutability.
- **L2** is a performance cache for `getAcademicDay()`. It is cleared whenever runtime events are added or removed.
- **runtimeEvents** is the in-memory store for user-created academic events (extra lectures, holidays, etc.).

---

## Initialization

```javascript
initCalendarEngine(calendarData)
```

`calendarData` is the `AcademicCalendar` aggregate root. In `app.js`, it is constructed from `timetable.json` and additional configuration:

```javascript
{
  calendarId: 'default',
  semesterId: 'current',
  semesterStart: timetable.start_date,        // e.g. '2026-07-15'
  semesterEnd: '2030-12-31',                   // Currently mocked
  defaultWeekends: [0, 6],                     // Sunday=0, Saturday=6
  events: [],                                  // Static L1 events (holidays, etc.)
  subjectTimelines: [ ... ],                   // Per-subject academic timelines
  policies: {
    quiz: {
      quiz1: { targetPercentage: 70 },
      quiz2: { targetPercentage: 75 },
      quiz3: { targetPercentage: 75 },
      default: { targetPercentage: 70 }
    }
  }
}
```

The validator inside `initCalendarEngine()` throws on invalid data — missing fields, invalid dates, out-of-order milestones, duplicate IDs, quiz milestones before `FIRST_LECTURE`.

---

## Domain Models

### `AcademicCalendar` (input to `initCalendarEngine`)

| Field | Type | Description |
|---|---|---|
| `calendarId` | string | Unique identifier for this calendar configuration |
| `semesterId` | string | Semester identifier |
| `semesterStart` | YYYY-MM-DD | First day of the semester |
| `semesterEnd` | YYYY-MM-DD | Last day of the semester |
| `defaultWeekends` | number[] | Day-of-week indices treated as weekends (0=Sun, 6=Sat) |
| `events` | StaticCalendarEvent[] | Pre-declared institutional events (holidays, working Saturdays) |
| `subjectTimelines` | SubjectTimeline[] | Per-subject academic timeline with milestones |
| `policies` | Object | Policy configuration (quiz thresholds, etc.) |

### `AcademicDay` (output of `getAcademicDay`)

| Field | Type | Description |
|---|---|---|
| `date` | YYYY-MM-DD | The date this object represents |
| `dayOfWeek` | 0–6 | JavaScript day of week |
| `isWorkingDay` | boolean | Whether this date has scheduled classes |
| `workingStatus` | `'FULL_DAY'|'CANCELLED'` | Working status after event resolution |
| `dayType` | `'WORKING_DAY'|'NON_WORKING_DAY'` | Classification |
| `isOverride` | boolean | Whether the default working status was overridden by an event |
| `events` | array | All events active on this date, sorted by priority descending |
| `metadata.isTeachingDay` | boolean | True if classes should be held |
| `metadata.originalDayOfWeek` | string | Day name (e.g. `'MONDAY'`) |
| `metadata.substitutionScheduleOverride` | string|null | Day name override for working Saturdays (e.g. `'TUESDAY'`) |

### `AttendanceWindow` (output of `getAttendanceWindow`)

| Field | Type | Description |
|---|---|---|
| `subjectCode` | string | Subject this window belongs to |
| `windowStart` | YYYY-MM-DD | Commencement date of the subject |
| `windowEnd` | YYYY-MM-DD | One day before the quiz milestone |
| `teachingDays` | number | Count of effective teaching days in window |
| `effectiveTeachingDates` | string[] | All YYYY-MM-DD strings that are teaching days |
| `holidayCount` | number | Non-working days with events in the window |
| `weekendCount` | number | Non-working days without events (weekends) |
| `activeMilestones` | Milestone[] | Milestones that fall within the window |

---

## Public API

### Initialization
- `initCalendarEngine(calendarData)` — Initialize. Must be called at bootstrap.
- `syncRuntimeEvents(eventsMap)` — Load/replace runtime event map. Clears L2 cache.

### Policy API
- `getPolicy(policyDomain)` — Returns policy object for a domain (e.g. `'quiz'`).
- `getQuizPolicy(quizCycle)` — Returns `{ targetPercentage }` for the specified quiz cycle.

### Day Resolution
- `getAcademicDay(dateString)` — Core function. Returns frozen `AcademicDay`. Cached.

### Event Queries
- `getCalendarEventsByType(eventType)` — Filter L1 static events by type.
- `getSubjectEventDeltas(dateString, subjectCode, classType)` — Returns integer delta (+1, -1, 0) representing extra or cancelled classes.
- `addAcademicEvent(raw)` — Create/update a runtime event. Clears L2 cache.
- `archiveAcademicEvent(eventId, dateString)` — Mark a runtime event as archived.

### Date Math
- `addDays(dateString, days)` — Add/subtract days. Returns YYYY-MM-DD.
- `getTodayString()` — Returns today as YYYY-MM-DD in local time.
- `getPreviousWorkingDay(dateString)` — Walk backwards until a teaching day.
- `getNextWorkingDay(dateString)` — Walk forwards until a teaching day.
- `getTeachingDaysBetween(start, end)` — Array of all teaching days in range.
- `getWorkingDaysUntil(dateString)` — Count working days from semester start.

### Subject Timeline API
- `getSubjectTimeline(subjectCode)` — Returns timeline for a subject.
- `getSubjectMilestones(subjectCode)` — Returns milestones for a subject.
- `getPreviousMilestone(subjectCode, milestoneId)` — Immediately preceding milestone.
- `getNextMilestone(subjectCode, milestoneId)` — Immediately following milestone.

### Attendance Window API
- `getAttendanceWindow(subjectCode, milestoneId)` — Full `AttendanceWindow` for a milestone.
- `getQuizWindow(subjectCode, quizCycle)` — Convenience: window for a specific quiz cycle.
- `getWindowTeachingDays(window)` — Extract teaching dates from a window.
- `getRemainingTeachingDays(window)` — Count remaining teaching days until window end.

### Validation
- `validateAcademicEvent(raw)` — Validate against registry. Throws on failure.

---

## Event Priority System

Events are resolved using a priority system. Higher number = higher precedence:

| Event Type | Priority |
|---|---|
| `EMERGENCY_CLOSURE` | 100 |
| `WORKING_DAY_OVERRIDE` | 90 |
| `WORKING_SATURDAY` | 80 |
| `PUBLIC_HOLIDAY` | 70 |
| `SEMESTER_BREAK` / `MID_SEMESTER_BREAK` | 60 |
| `INSTITUTE_HOLIDAY` | 50 |
| `FESTIVAL_HOLIDAY` | 40 |
| `CLASS_CANCELLED` / `EXTRA_LECTURE` / `SURPRISE_QUIZ` / etc. | 30 |
| (default) | 10 |

The dominant event (highest priority) determines `isWorkingDay` and `substitutionScheduleOverride`. This means an `EMERGENCY_CLOSURE` always overrides a `WORKING_SATURDAY`, regardless of order.

---

## AcademicEventRegistry

The registry is exported from `calendar-engine.js` and is the **single source of truth for all academic event type metadata**:

```javascript
export const AcademicEventRegistry = {
  EXTRA_LECTURE:       { displayName, icon, color, requiresSubject: true,  requiresClassType: true,  allowedClassTypes: ['L'] },
  EXTRA_TUTORIAL:      { displayName, icon, color, requiresSubject: true,  requiresClassType: true,  allowedClassTypes: ['T'] },
  EXTRA_PRACTICAL:     { displayName, icon, color, requiresSubject: true,  requiresClassType: true,  allowedClassTypes: ['P1','P2'] },
  CLASS_CANCELLED:     { displayName, icon, color, requiresSubject: true,  requiresClassType: true,  allowedClassTypes: ['L','T','P1','P2'] },
  SURPRISE_QUIZ:       { displayName, icon, color, requiresSubject: true,  requiresClassType: true,  allowedClassTypes: ['L','T'] },
  QUIZ_DAY:            { displayName, icon, color, requiresSubject: true,  requiresClassType: false, allowedClassTypes: [] },
  PUBLIC_HOLIDAY:      { displayName, icon, color, requiresSubject: false, requiresClassType: false, allowedClassTypes: [] },
  INSTITUTE_HOLIDAY:   { displayName, icon, color, requiresSubject: false, requiresClassType: false, allowedClassTypes: [] },
  WORKING_DAY_OVERRIDE:{ displayName, icon, color, requiresSubject: false, requiresClassType: false, allowedClassTypes: [] },
  EMERGENCY_CLOSURE:   { displayName, icon, color, requiresSubject: false, requiresClassType: false, allowedClassTypes: [] }
};
```

The UI reads this registry to dynamically build forms and cards. The validation function uses it to enforce rules. Never hardcode event type behavior in any other module.

---

## Known Limitations

1. **`semesterEnd` is currently hardcoded to `'2030-12-31'`** in `app.js`. This should be driven by timetable configuration.
2. **Static L1 events array is empty** (`events: []` in `app.js`). All holiday configuration currently happens via runtime `AcademicEvent` objects. Institutional holidays should eventually be pre-declared as L1 events.
3. **`getAcademicDay` uses `new Date(dateString)`** for parsing in line 463. This can behave unexpectedly for strings in certain locales. Should use the local-safe `parseDateString()` from `utils.js` instead.
4. **`addDays` uses `toISOString()`** which returns UTC. For dates around midnight in certain timezones, this can shift the date by one day. Should use `getLocalDateString()` from `utils.js` for consistency.

---

## Extension Points

To add a new event type:
1. Add an entry to `AcademicEventRegistry` in `calendar-engine.js`.
2. Add priority handling in `getEventPriority()`.
3. If it affects working day status, ensure `isWorkingDay` is set in the static event.
4. If it creates class count deltas, add handling in `getSubjectEventDeltas()`.
