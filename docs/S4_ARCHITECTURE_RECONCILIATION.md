# S4.1 Architecture Reconciliation

## 1. Current Architecture Overview
The S3 foundation established a modular separation of concerns on the backend (Engines vs. State vs. Persistence), but the frontend UI currently conflates several responsibilities.
- **State & Persistence:** Clean. Uses `AppState`, flushes to `localStorage`, and merges to Firestore via debounce.
- **Engines:** Clean. `attendance-engine.js`, `calendar-engine.js`, `quiz-engine.js`, `laboratory-engine.js`, and `events-controller.js` mathematically separate temporal logic from attendance rules.
- **UI:** Conflated. `ui.js` mixes Quiz Eligibility metrics directly into Overall Attendance cards, and blurs Current vs. Forecast statuses.

## 2. Authoritative Data Owners
- **Temporal/Schedule Data:** `calendar-engine.js` (deriving from `timetable.json` and `events-controller.js`).
- **Attendance Math:** `attendance-engine.js`.
- **Persistent State:** `storage.js` (`AppState`).
- **Eligibility Rules:** `quiz-engine.js`.

## 3. Data Flow Map
1. **Init:** `storage.js` hydrates local/Firestore data → `AppState`.
2. **Context:** `dateContext.js` sets the active viewing date.
3. **Event Layer:** `events-controller.js` parses stored events and injects them into the calendar timeline.
4. **Calendar:** `calendar-engine.js` computes the daily schedule and applicable teaching days.
5. **Attendance:** `attendance-engine.js` correlates the calendar against `AppState.attendance` to compute Current and Forecast.
6. **Quiz:** `quiz-engine.js` layers over attendance data to determine eligibility.
7. **Render:** `ui.js` paints the DOM (currently merging multiple layers incorrectly).

## 4. Attendance Calculation Flow
- **Current Attendance:** Strictly calculates based on schedule boundaries up to the *selected date* (excluding future classes).
- **Forecast Attendance:** Uses the same engine but projects the schedule to the *end of the semester or quiz boundary*, assuming all future classes are attended (or skipped, based on scenario).

## 5. Event Flow
- `AcademicEvent` (e.g., EXTRA_LECTURE) is created → persisted in `AppState.academicEvents`.
- On render, `events-controller.js` provides deltas (+1, -1) to the Calendar Engine.
- The Attendance Engine transparently reads the modified Calendar array, affecting all downstream stats (Current/Forecast).

## 6. Current vs Forecast Contamination (Gap Found)
- **Problem:** The UI (`ui.js`) derives the global `getSubjectStatus` ("SAFE", "WARNING", "CRITICAL") exclusively from `forecastAvgPct`. This forces the user to view their overall standing through a future lens rather than understanding their *actual* current standing.
- **Resolution:** The UI must display Current status independently of Forecast status.

## 7. Quiz Eligibility Flow (Gap Found)
- **Problem:** `ui.js` injects `Must Attend` and `Safe Skips Left` (which are fundamentally Quiz Criterion metrics) directly into the generic Subject Cards and the Dashboard Hero. Practical subjects, which have no quiz eligibility, get confused by this rendering.
- **Resolution:** Quiz Eligibility must be fully extracted from the Dashboard/Overall Attendance into a dedicated tab or view.

## 8. Persistence Flow
- The `isDirty` flag pattern successfully protects against offline data loss.
- Null or undefined values are sanitized before Cloud Sync, preventing Firestore rejection.
- Separation is verified.

## 9. UI Ownership
- `ui.js` is currently a monolithic renderer. As the Product Spec splits responsibilities, `ui.js` should delegate rendering to specific sub-modules (e.g., `renderDashboard()`, `renderDailyAttendance()`, `renderQuizEligibility()`).

## 10. Contradictions & Gaps Found
| File | Issue | Severity | Target Phase |
|---|---|---|---|
| `ui.js` | Quiz logic (Must Attend/Skips) leaked into Dashboard Hero. | P1 | S4.5 (Quiz Eligibility) & S4.6 (Overall) |
| `ui.js` | Subject Cards merge Quiz Target metrics with generic stats. | P1 | S4.6 (Overall Attendance) |
| `ui.js` | Subject status explicitly ignores Current Attendance in favor of Forecast. | P2 | S4.6 (Overall Attendance) |
| `events-controller.js` | UI lacks the actual forms/buttons to input exact-date schedule mutations. | P1 | S4.3 / S4.9 |
| `ui.js` | Mobile views are heavily derived from Desktop styles, lacking bespoke intent. | P2 | S4.12 (Responsive) |

## 11. Risks
- **Data Contamination during UI Refactor:** Separating Quiz Eligibility from Overall Attendance requires careful decoupling in `ui.js` without breaking `attendance-engine.js` arrays.
- **Event Scope:** Adding UI for Academic Events might require complex date-picker logic.

## 12. Recommended Implementation Order
1. **S4.0** Product Specification Freeze *(Complete)*
2. **S4.1** Architecture Reconciliation *(Complete)*
3. **S4.2** Attendance Calculation Integrity (ensure Current/Forecast separation at engine boundary)
4. **S4.3** Academic Events Engine (validate event-to-schedule pipeline)
5. **S4.4** Daily Attendance Experience (implement distinct daily marking view)
6. **S4.5** Quiz Eligibility (extract target/must-attend logic into distinct view)
7. **S4.6** Overall Attendance (clean subject cards without quiz logic)
8. **S4.7** Dashboard (Hero rework)
9. **S4.8** History
10. **S4.9** Academic Events UI
11. **S4.10** Profile / Settings
12. **S4.11** Design System
13. **S4.12** Responsive Architecture
14. **S4.13** Visual QA
15. **S4.14** Functional Regression
16. **S4.15** Production Release Candidate

## 13. Explicitly Deferred Work
- Cross-semester (multi-year) architecture.
- Real-time multiplayer synchronization.
- Complex profile customization (beyond basic theme).
- URL-based hash routing (internal deep linking).
