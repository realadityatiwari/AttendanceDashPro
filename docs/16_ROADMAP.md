# 16 — Product Roadmap

## Current Status: Audit Series Complete — Baseline Frozen (S3.10)

The S3.x audit series is complete. S3.4 closed the core engine/rule/SW gaps, S3.5–S3.9 audited UI/UX, persistence/sync, mobile/PWA, full regression, and production readiness, and **S3.10 froze the current-semester baseline** in `docs/S3.10_CURRENT_SEMESTER_BASELINE.md`. The previously flagged blockers (BUG-001 Firestore rules, BUG-002 service worker cache, DEBT-002 lab attendance key) are all **resolved in the current code**. Any new feature work must start from the frozen baseline document.

> ✅ **Resolved (do not re-open)**: BUG-001 — `firestore.rules` now whitelists all five root fields incl. `laboratory`/`academicEvents` (`firestore.rules:58-65`). BUG-002 — `events-controller.js` is in `STATIC_ASSETS` (`service-worker.js:25`). DEBT-002 — lab attendance lookup matches normalized `P` (`laboratory-engine.js:109-134`).

---

## Immediate Priorities (Before Any New Feature Work)

### 1. Confirm Phase F1.3 Browser Validation

The Academic Event CRUD flow (create Extra Lecture / Class Cancelled, disable, archive) was browser-validated as part of the S3.x audit series (S3.5–S3.6 verified event creation, rendering, and cross-device round-trip). Confirm the recorded results remain valid against the current baseline before starting new feature work.

**Effort**: 30 minutes  
**Impact**: Closes the last open F1.3 validation item.

### 2. Reset Remaining Technical Debt

Debt not yet resolved is tracked in `docs/15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md` (e.g. DEBT-001 dual-write divergence risk in `events-controller.js`). Re-scan this register against the S3.10 baseline before planning new features.

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
