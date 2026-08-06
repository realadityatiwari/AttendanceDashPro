You are an expert AI software architect refactoring code in AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture (Calendar → Attendance → Quiz/Lab).
3. Acknowledge that `ui.js` is a pure consumer and contains no business logic.
4. Verify you are not duplicating existing logic or violating dependency rules (`docs/19_DEPENDENCY_GRAPH.md`).

# INSTRUCTIONS

Execute the refactor with absolute preservation of existing behavior.

### 1. Identify Scope
Determine the exact boundaries of the refactor. Are you extracting a utility? Reorganizing an engine? Optimizing a loop? 

### 2. Preserve Public APIs
The public functions exposed by engines (e.g., `getAttendanceData`, `getAcademicDay`) must remain structurally identical unless the refactor explicitly calls for an API change (which requires an Implementation Plan and user approval).

### 3. Maintain Architecture
Do not blend engine responsibilities. If you extract logic from `attendance-engine.js` that deals with dates, it must be moved to `calendar-engine.js`, not left in a generic utility file.

### 4. Update Documentation
If the internal structure of an engine changes, update its corresponding documentation file (e.g., `docs/06_ATTENDANCE_ENGINE.md`). If dependencies change, update `docs/19_DEPENDENCY_GRAPH.md`.

### 5. Verify Tests
Run the Node.js test suite to ensure the refactored math or date logic matches the exact baseline output.
