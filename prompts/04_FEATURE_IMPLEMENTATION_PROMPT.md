You are an expert AI software developer implementing a feature for AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture (Calendar → Attendance → Quiz/Lab).
3. Acknowledge that `ui.js` is a pure consumer and contains no business logic.
4. Verify you are not duplicating existing logic or violating dependency rules (`docs/19_DEPENDENCY_GRAPH.md`).

# INSTRUCTIONS

Implement the approved feature while adhering to the following strict constraints:

### 1. Cross-Platform Parity
Write UI code that works seamlessly on Desktop, Mobile Web, and Installed PWA. Do not write business logic that branches based on `window.innerWidth`. The underlying engines must calculate identically regardless of the viewport.

### 2. Adhere to Engine Boundaries
- If you are modifying dates, put it in `calendar-engine.js`.
- If you are calculating totals, put it in `attendance-engine.js`.
- If you are checking eligibility, put it in `quiz-engine.js`.
- If you are mutating state, route it through `events-controller.js` or `storage.js`.

### 3. Avoid Data Duplication
Do not fetch or calculate data in `ui.js` that has already been calculated in an engine. Pass the engine's result object (e.g., `OptimizationResult`) directly to the UI rendering function.

### 4. Zero Build Tools
Write pure Vanilla JS (ES Modules). Do not use JSX, TypeScript, Babel, or Webpack.

### 5. Regression Checklist
Before declaring the implementation complete, mentally or physically run through this checklist:
- [ ] Desktop layout preserved?
- [ ] Mobile responsive layout preserved?
- [ ] PWA service worker updated (if new files added)?
- [ ] Calendar Engine priority rules intact?
- [ ] Attendance optimizer output matches baseline?
- [ ] Quiz Engine eligibility matches policy?
- [ ] Laboratory Engine unaffected?
- [ ] UI pure consumer rule intact?
- [ ] Controllers handling all mutations?
- [ ] Documentation updated?
- [ ] Unit tests passing?
