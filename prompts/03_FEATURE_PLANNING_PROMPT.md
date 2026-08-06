You are an expert AI software architect planning a new feature for AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture (Calendar → Attendance → Quiz/Lab).
3. Acknowledge that `ui.js` is a pure consumer and contains no business logic.
4. Verify you are not duplicating existing logic or violating dependency rules (`docs/19_DEPENDENCY_GRAPH.md`).

# INSTRUCTIONS

Before writing any code, produce a detailed `implementation_plan.md` artifact for the user to review.

### 1. Requirements Gathering
If any part of the feature relies on university academic policy (e.g., how labs are graded, how leaves are calculated), STOP and ask the user for the official circular or documentation. Do not guess.

### 2. Architectural Design
Determine exactly which engines this feature will touch. 
- Are you adding date logic? It must go in `calendar-engine.js`.
- Are you adding math? It must go in `attendance-engine.js`.
- Are you adding rules? It must go in `quiz-engine.js` or `laboratory-engine.js`.
- Are you mutating state? It requires a controller.

### 3. Data Design
Does this feature require persisting new data? If so:
- Add it to `AppState` in `storage.js`.
- Update `firestore.rules`.
- Update `docs/20_DATA_DICTIONARY.md`.

### 4. Cross-Platform Considerations
Explicitly document how this feature will manifest on:
- Desktop
- Mobile Web (responsive breakpoints)
- Installed PWA (service worker caching)

### 5. Implementation Steps
Write a step-by-step checklist of files to modify and functions to create.

Set `request_feedback = true` on the artifact so the user can approve the plan before execution begins.
