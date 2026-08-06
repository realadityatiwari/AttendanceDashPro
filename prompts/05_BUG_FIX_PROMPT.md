You are an expert AI software developer diagnosing and fixing a bug in AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture (Calendar → Attendance → Quiz/Lab).
3. Acknowledge that `ui.js` is a pure consumer and contains no business logic.
4. Verify you are not duplicating existing logic or violating dependency rules (`docs/19_DEPENDENCY_GRAPH.md`).

# INSTRUCTIONS

Follow this strict protocol to resolve the bug:

### 1. Root Cause Analysis
Do not apply a symptom-only fix (e.g., adding a null check in the UI when the engine is returning bad data). Trace the data flow backward from the UI, through the engines, to the state, and finally to the user input or cloud sync. Identify the exact line where the invariant was broken.

### 2. Architectural Impact Assessment
Before writing the fix, determine if your proposed solution violates engine boundaries. If fixing the bug requires the Attendance Engine to know about the UI, your fix is wrong. Find a solution that respects the unidirectional data flow.

### 3. Implement the Fix
Write the fix in clean, vanilla JS. Ensure no other modules are negatively impacted.

### 4. Regression Testing
Test the fix. Does it break the baseline for standard users? Verify across Desktop, Mobile Web, and PWA.

### 5. Documentation Updates
If this bug revealed a flaw in the documented architecture or data models:
- Update `docs/15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md` (move it to resolved).
- Update the Changelog (`docs/21_CHANGELOG.md`).
- If data models changed, update `docs/20_DATA_DICTIONARY.md`.
