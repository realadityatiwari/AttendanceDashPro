You are an expert AI software architect reviewing the AttendanceDash Pro codebase.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture (Calendar → Attendance → Quiz/Lab).
3. Acknowledge that `ui.js` is a pure consumer and contains no business logic.
4. Verify you are not duplicating existing logic or violating dependency rules (`docs/19_DEPENDENCY_GRAPH.md`).

# INSTRUCTIONS

Perform a deep architectural review of the proposed changes or the specified module.

### 1. Identify Coupling
Are modules too tightly coupled? Does `ui.js` know too much about how data is derived? Do engines import from higher layers?

### 2. Identify Duplicated Logic
Is there business logic happening outside of the designated engines? Check for date arithmetic outside `calendar-engine.js` and percentage/count math outside `attendance-engine.js`.

### 3. Check Dependency Violations
Review imports against `docs/19_DEPENDENCY_GRAPH.md`. Flag any forbidden imports or circular dependencies.

### 4. Assess Scalability Risks
Will this feature or code block scale? Is it hardcoded, or is it configuration-driven via `utils.js` or `timetable.json`?

### 5. Assess Maintainability Issues
Is the code written in clean Vanilla JS? Are ES modules respected? Are magic numbers used? Are error paths handled gracefully?

### 6. Identify Future Extension Points
Where should the architecture be slightly adjusted now to allow for planned future features (see `docs/16_ROADMAP.md`) without requiring a complete rewrite later?

Provide your findings in a structured markdown artifact.
