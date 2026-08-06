# 16 — Product Roadmap

## Current Status: Phase F1.3 — Academic Event Management System (In Progress)

Phase F1.3 implementation is code-complete. The backend (registry, controller, storage, engine integration) is fully implemented. The UI (event form, event cards, Academic Tools workspace) is implemented and integrated. Browser-level validation of the complete flow is the immediate next step.

---

## Immediate Priorities (Before Any New Feature Work)

### 1. Fix BUG-001 — Firestore Rules

Update `firestore.rules` to allow `laboratory` and `academicEvents` fields.

**Effort**: 30 minutes  
**Impact**: Critical — without this, lab data and events are never cloud-synced.

### 2. Fix BUG-002 — Service Worker Cache

Add `events-controller.js` to the service worker static asset allowlist. Bump `APP_VERSION`.

**Effort**: 15 minutes  
**Impact**: High — Events feature broken offline.

### 3. Complete Phase F1.3 Browser Validation

Open the application in a browser, test the full Academic Event CRUD flow:
- Create an Extra Lecture event → verify attendance percentage increases.
- Create a Class Cancelled event → verify attendance count decreases.
- Disable an event → verify percentages revert.
- Archive an event → verify it moves to archived tab.

**Effort**: 1–2 hours  
**Impact**: Close Phase F1.3.

### 4. Fix DEBT-002 — Lab Attendance Key Bug

Fix `getExperimentAttendanceStatus` to use `:P1` instead of `:P`.

**Effort**: 5 minutes  
**Impact**: Lab attendance status will correctly show Attended/Missed.

---

## Near-Term Feature Work

### Phase F2.1 — Holiday Calendar (UI)

**Goal**: Allow students to browse and add institutional holidays from a visual calendar interface.

**Scope**:
- New Calendar view accessible from Academic Tools workspace.
- Monthly calendar grid rendered from `getAcademicDay()` for each day.
- Holiday indicators shown inline.
- Click to add `PUBLIC_HOLIDAY`, `INSTITUTE_HOLIDAY`, or `FESTIVAL_HOLIDAY` events.
- No new engine work needed — builds entirely on the existing Academic Event System.

**Effort estimate**: 2–3 development days.

### Phase F2.2 — Quiz Schedule Manager (UI)

**Goal**: Allow students to adjust quiz dates per subject, reflecting the actual quiz schedule issued by the university.

**Scope**:
- Per-subject quiz date editing UI in Academic Tools workspace.
- Changes saved to `timetable.json` overrides (a runtime override layer, not file mutation).
- Calendar Engine reads subject timeline milestones to compute windows — editing a quiz milestone date updates the window boundary automatically.

**Effort estimate**: 1–2 development days for UI. Requires a milestone override architecture in the Calendar Engine.

### Phase F2.3 — Surprise Quiz Attendance Tracking

**Goal**: When a professor announces a surprise quiz, the student marks it as a `SURPRISE_QUIZ` academic event. The Quiz Engine evaluates surprise quiz eligibility separately.

**Scope**:
- The event type already exists in `AcademicEventRegistry`.
- Requires Quiz Engine extension to evaluate surprise quiz attendance windows.
- Requires UI addition to the Quiz Dashboard section to show surprise quiz eligibility separately.

**Effort estimate**: 1 development day for engine extension + 1 day for UI.

### Phase F3.1 — Extra Class Tracking

**Goal**: When a professor schedules a makeup class on a normally non-scheduled day, log it as an `EXTRA_LECTURE` or `EXTRA_PRACTICAL` event. Attendance for that class can be marked normally.

**Scope**:
- Backend: Already implemented via `EXTRA_LECTURE`, `EXTRA_TUTORIAL`, `EXTRA_PRACTICAL` event types.
- The `getSubjectEventDeltas()` function in Calendar Engine already returns +1 for extra classes.
- Requires validation that the extra class is correctly counted in `getAttendanceData()`.
- UI: Create Event form already supports these types.

**Effort estimate**: Validation only — may already be fully functional.

---

## Medium-Term Feature Work

### Phase F4.1 — ERP Integration

**Goal**: Auto-import attendance from SRMCEM's ERP portal to eliminate manual logging.

**Approach Options**:
1. **Screenshot OCR**: User uploads a screenshot of the ERP attendance page. App parses it.
2. **Browser extension**: Extension scrapes the ERP page while user is logged in.
3. **Bulk import**: User exports a CSV from ERP; app imports it.

**Blockers**: University ERP API is not publicly documented. Option 3 (CSV) is most realistic.

**Effort estimate**: High — 1–2 weeks depending on approach.

### Phase F4.2 — Multiple Batch/Section Support

**Goal**: Support students from different sections or batches, each with their own timetable.

**Approach**: Configuration-driven — user selects their batch/section at signup, app loads the corresponding `timetable.json` variant.

**Required changes**:
- Multiple timetable JSON files or a timetable registry.
- Batch/section stored in `AppState.profile`.
- `initTimetable()` modified to fetch the correct file.

**Effort estimate**: 3–5 days.

### Phase F4.3 — Lab Grading and Viva

**Goal**: Track marks and viva for lab experiments.

**Scope**:
- Add marks input to lab experiment card UI.
- `LAB_RULES.default.grading.enabled = true`.
- Marks stored in `AppState.laboratory[code][expIdx].marks`.
- Lab summary shows total marks earned.

**Effort estimate**: 1–2 days.

---

## Long-Term Vision

### Phase F5 — Institutional Multi-Tenancy

Support multiple universities, each with their own academic calendar, holiday schedule, and eligibility policy. The engine architecture already supports this via the `calendarId` field and separate `initCalendarEngine` configurations.

### Phase F6 — Faculty Dashboard

A separate admin interface for faculty to:
- View class-wide attendance statistics.
- Mark attendance bulk by subject.
- Set quiz dates, extra classes, and holiday events that push to all students.

This requires a Firestore security model redesign (faculty role, class-wide documents).

### Phase F7 — Notifications

Push notifications (via Web Push API) when:
- Attendance falls below threshold.
- Quiz date is approaching.
- An extra class is scheduled.

Requires a notification service and permission handling.

---

## Architectural Constraints on Future Work

> The following decisions are **locked**. Any feature work must operate within them.

1. **No engine rewrites.** The three-engine architecture is stable. Build features on top.
2. **No fifth bottom navigation tab.** All management tools go in the Academic Tools workspace (Profile → Academic Tools).
3. **No duplicate attendance calculations.** All math stays in the Attendance Engine.
4. **No duplicate temporal logic.** All date math stays in the Calendar Engine.
5. **UI never orchestrates engines.** Feature flags, complex conditionals, and multi-engine coordination go in controllers or `app.js`.
6. **No build tools without explicit approval.** The zero-build approach is intentional.
7. **Soft delete is the default.** Academic Events are archived, not deleted.
