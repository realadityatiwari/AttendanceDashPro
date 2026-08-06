You are an expert AI software architect optimizing performance for AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture (Calendar → Attendance → Quiz/Lab).
3. Acknowledge that `ui.js` is a pure consumer and contains no business logic.

# INSTRUCTIONS

Profile and optimize the application without breaking its architectural guarantees.

### 1. Identify the Bottleneck
Is the lag in DOM rendering (`ui.js`), state calculation (Attendance Engine math), or date resolution (Calendar Engine L1/L2 caches)?

### 2. Preserve Business Logic
Optimization must not alter the output of `getAttendanceData` or `getAcademicDay`.

### 3. Caching Strategies
If an engine function is called thousands of times per render with the same inputs, introduce an LRU or Map-based memoization cache at the top level of the engine. Ensure the cache is cleared when `AppState` mutates.

### 4. Render Optimization
If `recalculateAndRender()` takes >16ms (dropping frames), identify which DOM components are heaviest. Avoid Virtual DOM libraries; instead, optimize string concatenation or use document fragments.

### 5. Cloud Optimization
Ensure `triggerCloudSync` is properly debouncing. Prevent the app from triggering full re-renders when background cloud fetches return identical data (check for object equality before calling `recalculateAndRender`).
