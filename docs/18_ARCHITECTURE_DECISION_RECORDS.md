# 18 — Architecture Decision Records (ADRs)

This document records the major architectural decisions made during the evolution of AttendanceDash Pro. It explains *why* the architecture looks the way it does, providing context for the constraints documented in [17_AI_HANDOFF.md](17_AI_HANDOFF.md).

---

## ADR 001: The Three-Engine Architecture

**Date**: Phase A2.3 / A2.4

**Problem**: Early versions of the application scattered attendance mathematics and date calculations across the UI, Quiz Engine, and core logic. Changing a threshold (e.g., 75%) or handling edge cases like public holidays required updates in multiple places, leading to inconsistent calculations.

**Alternatives Considered**:
1. Keep the fat Quiz Engine that handled both dates and attendance math.
2. Build a single monolithic "AcademicEngine".

**Final Decision**: Split the logic into three strictly layered engines:
1. **Calendar Engine**: Sole owner of temporal logic (dates, working days, event priority).
2. **Attendance Engine**: Sole owner of attendance math (counts, percentages, optimization).
3. **Quiz Engine**: Pure rules engine (evaluates eligibility based on the Attendance Engine's output).

**Why it was chosen**: Separation of concerns. Date math is complex (events, holidays). Attendance math is complex (exhaustive search optimization). Mixing them created untestable code. Layering them ensures deterministic, testable outputs.

**Trade-offs**: Requires passing large data structures (like `states` or `timetable`) down the chain. Slight performance overhead compared to an optimized monolithic loop.

**Future Implications**: Adding a new feature like "Surprise Quizzes" only requires changing the rules in the Quiz Engine and the event definitions in the Calendar Engine, leaving the Attendance math completely untouched.

---

## ADR 002: UI as a Pure Consumer

**Date**: Phase A2.4

**Problem**: The UI (`ui.js`) was orchestrating engine calls directly, fetching data from storage, transforming it, and sometimes performing its own minor calculations (like determining if a class was in the past). This made the UI impossible to test without a DOM.

**Alternatives Considered**:
1. Move to a framework like React or Vue to manage state and rendering.
2. Keep the existing structure but extract pure functions.

**Final Decision**: Enforce a strict unidirectional flow where the UI is a pure consumer. The UI reads `AppState`, passes it to the engines, receives computed models (e.g., `QuizDashboardModel`), and builds HTML strings. The UI **never** orchestrates engines or mutates state directly.

**Why it was chosen**: Avoids the overhead of a framework while maintaining predictable renders. The entire app state can be recalculated and re-rendered from scratch in milliseconds.

**Trade-offs**: Re-rendering the entire dashboard on every click (via `recalculateAndRender`) is computationally heavier than targeted DOM updates. However, for the current scale, it is imperceptibly fast.

**Future Implications**: If performance ever becomes an issue, we can optimize `recalculateAndRender` with Virtual DOM techniques or targeted DOM patching, but the pure-consumer rule will remain.

---

## ADR 003: Date-Indexed Storage for Academic Events

**Date**: Phase F1.2

**Problem**: We needed a way to store user-created academic events (extra classes, cancelled classes). Storing them as a flat array would require O(N) filtering on every calendar lookup (which happens hundreds of times during a single render).

**Alternatives Considered**:
1. Flat array `[AcademicEvent, AcademicEvent, ...]`.
2. Normalized relational store (events by ID, referenced by date).

**Final Decision**: Store events in a date-indexed dictionary:
```javascript
AppState.academicEvents = {
  "YYYY-MM-DD": [AcademicEvent, ...]
}
```

**Why it was chosen**: The Calendar Engine queries events by date (`getAcademicDay(dateString)`). Date-indexing provides O(1) lookups for the engine's most critical hot path.

**Trade-offs**: Updating an event's date requires removing it from one array and adding it to another, slightly complicating the controller logic.

**Future Implications**: Building a visual monthly calendar (Phase F2.1) will be extremely efficient because we can iterate days and immediately check for events.

---

## ADR 004: Soft-Delete Default Lifecycle

**Date**: Phase F1.3

**Problem**: Users need to delete academic events they created by mistake. However, deleting an event permanently alters historical attendance data, which could cause confusion if a user wants to audit their past eligibility.

**Alternatives Considered**:
1. Hard delete: Remove the event from `AppState.academicEvents`.
2. Audit log: Move deleted events to a separate `AppState.deletedEvents` collection.

**Final Decision**: Soft delete is the default lifecycle. Events have an `archived: true` flag. The Calendar Engine ignores archived events, but they remain in `AppState.academicEvents` and are visible in the "Archived" tab of the UI.

**Why it was chosen**: Protects against accidental data loss. Provides a built-in audit trail. Future-proofs the system for "restore" functionality.

**Trade-offs**: Storage size grows indefinitely. However, the data volume for a single student over a 4-year degree is negligible (a few KB).

**Future Implications**: Any future features involving user-created data (e.g., custom subjects, notes) should follow the same soft-delete pattern.

---

## ADR 005: Zero-Build Environment (No Frameworks/Bundlers)

**Date**: Phase A1

**Problem**: We needed to rapidly develop a PWA without the complexity of CI/CD pipelines, node_modules bloat, or compilation steps, while maintaining modularity.

**Alternatives Considered**:
1. Vite + React/TypeScript (industry standard).
2. Webpack + Babel.

**Final Decision**: Use pure Vanilla JS with ES Modules (`<script type="module">`). Load Firebase via compat CDN. Use CSS custom properties for styling. No build step.

**Why it was chosen**: Maximizes debuggability. The code running in the browser is exactly the code on disk. Deployment is as simple as serving static files.

**Trade-offs**: No TypeScript support (type safety is enforced via JSDoc and runtime validation). Cannot use the modern modular Firebase SDK (which requires a bundler). Requires strict discipline regarding code organization to avoid spaghetti code.

**Future Implications**: We are locked into the Firebase compat SDK. Any AI or developer joining the project must understand Vanilla JS DOM manipulation.

---

## ADR 006: Local-First Hydration Strategy

**Date**: Phase A1 (refined in S1)

**Problem**: A dashboard that relies heavily on cloud data takes seconds to load on a mobile network, creating a poor user experience. Furthermore, students often check attendance in low-connectivity areas (classrooms).

**Alternatives Considered**:
1. Firebase standard caching.
2. Full IndexedDB architecture.

**Final Decision**: Keep a complete, serialized copy of `AppState` in `localStorage`. On app launch, immediately hydrate from `localStorage` and render. Fetch cloud data in the background and silently update if differences exist.

**Why it was chosen**: Provides instant sub-50ms rendering on launch. `localStorage` is synchronous and simple to use for the small data footprint of this app.

**Trade-offs**: `localStorage` has a ~5MB limit (plenty for this app, but a hard ceiling). If cloud data differs significantly, the user might see a sudden UI jump (flicker) when the background sync completes.

**Future Implications**: The `AppState` must always remain serializable to JSON (no Sets, Maps, or class instances in state).

## ADR 010: Official Academic Data Reconciliation (S3.3)

**Context**: The application requires an authoritative baseline for Quiz applicability and attendance requirements. The official SRMCEM Attendance Criteria notice dated 14 July 2026 establishes cumulative but strict windows and varying target percentages per quiz cycle (Q1: 70%, Q2/Q3: 75%). Furthermore, specific boundaries dictate that Quiz II begins counting strictly from the Quiz I boundary, rather than from commencement.

**Final Decision**: 
1. Added `"policies"` configuration to `timetable.json` to centrally enforce varying quiz target percentages per cycle.
2. Updated `calendar-engine.js` (`getAttendanceWindow`) to properly resolve Quiz II/III windows starting from the previous quiz milestone rather than commencement.
3. Left BCS-054 explicitly unresolved for Q3 (marked as ACADEMIC VERIFICATION REQUIRED) pending physical proof of its subject-specific applicability, ensuring no unsupported academic assumptions are built into the data layer.

**Why it was chosen**: This preserves the data-driven architecture of the system. Instead of hardcoding cycle percentages in the `attendance-engine.js`, the policy was elevated to configuration (`timetable.json`). The window calculation fix ensures semantic alignment with the official university policy while remaining completely generic for any future branch or semester.

**Trade-offs**: None. This is a pure data-integrity fix conforming to official fact.

**Future Implications**: Future semesters will simply configure their `timetable.json` with the required dates and target percentages, and the engine will seamlessly resolve the logic.
 
 