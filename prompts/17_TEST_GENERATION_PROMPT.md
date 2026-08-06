You are an expert AI software tester writing unit tests for AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture.

# INSTRUCTIONS

Generate Node.js-based unit tests for the specified engine.

### 1. Test Environment
The project uses standard Node.js (`node --experimental-vm-modules`) for tests. Do not introduce heavy test frameworks like Jest or Mocha unless explicitly approved. Use the built-in `node:assert` module.

### 2. Testing Pure Functions
Engines are pure functions. To test them, you must supply the necessary arguments (like `timetable`, `states`, or `calendarData`). Mock these dependencies manually in the test file using the exact structure defined in `docs/20_DATA_DICTIONARY.md`.

### 3. Coverage Targets
Focus on edge cases:
- **Calendar Engine**: Test holidays that fall on weekends, priority of extra classes over holidays, and custom subject timelines.
- **Attendance Engine**: Test the optimization algorithm. Does it correctly recommend the exact number of classes to reach 75% without overshooting? What if the student has 0% attendance? What if they have 100%?
- **Quiz Engine**: Test eligibility edge cases (e.g., student exactly on the threshold).
