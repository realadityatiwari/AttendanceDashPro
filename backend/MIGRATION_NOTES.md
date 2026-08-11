# MIGRATION NOTES (Phase 1)

This document tracks the strategic decisions, conflicts, and resolutions made during the migration of AttendanceDash Pro from its legacy JS architecture to the Python/FastAPI backend.

## 1. JS → Python Mapping

| Legacy JS Module | New Python Module | Responsibility |
| :--- | :--- | :--- |
| `calendar-engine.js` | `app/engines/calendar_engine.py` | Core temporal logic, `AcademicDay` construction, and window calculations. |
| `attendance-engine.js` | `app/engines/attendance_engine.py` | Exhaustive optimization logic for lectures and tutorials, stats calculation. |
| `quiz-engine.js` | `app/engines/eligibility_engine.py` | Official quiz eligibility evaluation. |
| `utils.js` | `app/models/enums.py` | Standardized domain types (ClassType, EventType). |
| `storage.js` / Firebase | `app/services/*.py` (Future DB) | Abstraction over the database layer. |

## 2. Current Implementation Behavior vs. 3. Official Academic Rules

- **Current Behavior**: The legacy application embeds academic policy decisions either directly in the frontend UI layers, or within `attendance-engine.js`. Some dates, especially for quizzes, were tightly coupled to UI assumptions rather than a strict source of truth.
- **Official Rules**: The SRMCEM Attendance Criteria notice (14 July 2026) dictates specific quiz targets (Q1=70%, Q2=75%, Q3=75%) and specific attendance windows originating from the *previous* quiz, rather than semester commencement.

## 4. Current-vs-Official Conflicts

| Domain | Existing JS Behavior | Official Academic Rule | Conflict Resolution |
| :--- | :--- | :--- | :--- |
| **Quiz Eligibility** | Often evaluated entirely on the frontend or simplified to a flat 75%. | 70/75/75 percentage requirements dependent on cycle. | The new `eligibility_engine.py` explicitly models the cycle and threshold policy, rejecting the simplified 75% blanket rule. |
| **Timezone Logic** | Browsers rely on the user's local timezone (e.g. `new Date()`), causing shifts in calendar rendering. | "Class Days" are institutionally semantic and occur in IST (`Asia/Kolkata`). | Adopting the Timezone Strategy defined below. |

## 5. Timezone Strategy (Approved)

- **Academic Date**: Represented as naive `datetime.date`. An academic "class day" is a semantic calendar date tied to the institution, not a UTC instant.
- **Timestamp**: Represented as timezone-aware `datetime.datetime` **only** when an actual time-of-day is required (e.g., event logs, exact audit trails).
- **Institutional Timezone**: `Asia/Kolkata`.
- **Constraint**: Do NOT represent ordinary academic dates as naive datetimes. Do NOT perform unnecessary UTC conversions on academic dates.

## 6. BCS-054 Q3 Unresolved Status

- **Status**: The official academic sources do not provide a confirmed Q3 date for BCS-054.
- **Action**: We explicitly model this as "Schedule unavailable" / "Unresolved".
- **Constraint**: Do NOT invent a date, infer from other subjects, or copy the Bolt UI prototype. The backend will return `is_eligible=False` alongside a `policy_ambiguity_notes` entry stating the data is unavailable.

## 7. Eligibility Policy Architecture

The eligibility engine has been fundamentally restructured to support the complete official academic policy, not just a single percentage. The architecture now flows as:

1.  **Quiz Cycle**: Identify the targeted quiz.
2.  **Attendance Window**: Calculate the correct start/end date for the specific cycle.
3.  **Eligibility Policy**: Lookup the threshold (70/75/75).
4.  **Requirements**: Evaluate both lecture and tutorial thresholds explicitly as required by the policy.
5.  **Exclusion**: Explicitly exclude Practical/Lab attendance from quiz eligibility, maintaining a strict distinction between *general attendance* (which includes practicals) and *quiz eligibility* (which only includes lectures/tutorials per the official notice).
6.  **Result**: Yield an `EligibilityResult` encompassing all applied rules.

## 8. Future PostgreSQL Requirements

- A relational database (PostgreSQL) is required to strongly type and enforce referential integrity for `Subjects`, `TimetableEntries`, `AttendanceRecords`, and `AcademicEvents`.
- Alembic will be used for schema migrations.
- **Status**: Deferred. No schema or database interactions have been implemented in Phase 1.

## 9. Future Firebase Authentication Integration

- Firebase Auth will be retained.
- The FastAPI backend will validate Firebase ID tokens sent via the `Authorization: Bearer` header.
- A custom dependency in FastAPI (`get_current_user`) will decode the JWT using the Firebase Admin SDK and inject the user context into route handlers.
- **Status**: Deferred. The JS app continues to use the client-side Firebase Auth.

## 10. Deferred Migration Decisions

-   **PostgreSQL Schema**: Deferred to Phase 2.
-   **Data Migration**: Transferring existing Firestore data to PostgreSQL is deferred until the schema is stable.
-   **Frontend Migration**: The Next.js rebuild (using the Bolt prototype as visual reference) is deferred to a future phase.
-   **Laboratory Engine**: While practicals are supported in the core attendance stats, the specialized laboratory experiment tracking engine will be ported after the core theory engines are fully tested.
