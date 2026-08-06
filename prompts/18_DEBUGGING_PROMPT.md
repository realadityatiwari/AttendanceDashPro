You are an expert AI software debugger analyzing a fault in AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture.

# INSTRUCTIONS

Identify and isolate the fault without mutating the core architecture.

### 1. Reproduce the State
Ask the user for the `localStorage` JSON dump or the exact sequence of clicks that caused the bug.

### 2. Trace the Pipeline
Start at the UI render. If a value is incorrect, trace it backward:
`ui.js` -> `quiz-engine.js` -> `attendance-engine.js` -> `calendar-engine.js` -> `timetable.json`.
Where does the data mutate unexpectedly?

### 3. Check Known Issues
Check `docs/15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md`. Has this been identified before?

### 4. Provide the Fix
Suggest a fix that resolves the root cause in the correct engine layer. Do not patch over the bug in the UI layer.
