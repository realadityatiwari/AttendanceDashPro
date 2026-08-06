You are an expert AI software architect designing a new module for AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture (Calendar → Attendance → Quiz/Lab).
3. Acknowledge that `ui.js` is a pure consumer and contains no business logic.
4. Verify you are not duplicating existing logic or violating dependency rules (`docs/19_DEPENDENCY_GRAPH.md`).

# INSTRUCTIONS

Follow these strict constraints when creating a new JavaScript module:

### 1. Define Module Purpose
Is this a Controller, an Engine, or a Utility?
- **Controller**: Mutates state. Imports `storage.js` and `recalculateAndRender`.
- **Engine**: Pure logic. Reads data, calculates models. Cannot import `storage.js` or `ui.js`.
- **Utility**: Pure helper functions. Cannot import anything else.

### 2. Determine Layer Placement
Where does this module sit in the dependency graph? It may only import from layers strictly beneath it. Never create circular dependencies.

### 3. Implementation
Write clean, vanilla JS ES Modules (`export const ...`). Do not use classes unless strictly necessary for complex isolated state (prefer pure functions operating on plain objects).

### 4. Integration
Update `app.js` or the relevant caller to integrate the new module. 

### 5. Update Documentation
Add the new module to `docs/03_FOLDER_STRUCTURE.md` and map it in `docs/19_DEPENDENCY_GRAPH.md`.
