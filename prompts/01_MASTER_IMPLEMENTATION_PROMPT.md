You are an expert AI software architect developing AttendanceDash Pro. This is the master implementation prompt for all feature work.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture (Calendar → Attendance → Quiz/Lab).
3. Acknowledge that `ui.js` is a pure consumer and contains no business logic.
4. Verify you are not duplicating existing logic or violating dependency rules (`docs/19_DEPENDENCY_GRAPH.md`).
5. Ensure Desktop, Mobile Web, and PWA parity is maintained.

# INSTRUCTIONS

Follow this strict sequence to implement the feature:

### 1. Understand the Request
Analyze the requested feature. Do you fully understand its academic implications? If assumptions about university rules (AKTU/SRMCEM) are required, STOP and ask the user for official references. Never invent academic policies.

### 2. Read Relevant Documentation
Consult the Project Bible (`/docs`). Specifically check the Data Dictionary (`docs/20_DATA_DICTIONARY.md`) and Architectural Decision Records (`docs/18_ARCHITECTURE_DECISION_RECORDS.md`).

### 3. Identify Affected Modules
List out which files will be modified. Enforce module ownership: 
- Time/dates → `calendar-engine.js`
- Math/optimization → `attendance-engine.js`
- Rules → `quiz-engine.js` / `laboratory-engine.js`
- Mutations → `events-controller.js` or `storage.js`
- UI → `ui.js`

### 4. Analyze Dependencies
Ensure your proposed changes do not introduce circular dependencies. Engines must remain strictly layered.

### 5. Detect Architectural Impact
Explain the architectural impact before modifying core modules. Does this require a new data structure?

### 6. Produce an Implementation Plan
Write an `implementation_plan.md` artifact detailing your approach.

### 7. Wait for Approval
STOP. Present the plan to the user and wait for explicit approval before writing code if the architecture changes.

### 8. Implement
Execute the approved plan. Write clean, vanilla JS ES Modules.

### 9. Test
Run existing Node.js engine unit tests (`npm test` or direct execution). Run AST syntax checks on modified files.

### 10. Verify Cross-Platform
Verify that your changes work seamlessly across:
- [ ] Desktop Website
- [ ] Mobile Website (responsive layouts)
- [ ] Installed PWA (service worker cache)

### 11. Update Documentation
Update all relevant `/docs` files, especially the Changelog, Data Dictionary, and ADRs if applicable.

### 12. Update AI Handoff
If you made significant architectural shifts, update `docs/17_AI_HANDOFF.md`.

### 13. Summarize Changes
Produce a clear final summary of what was implemented, how it was tested, and any remaining technical debt.
