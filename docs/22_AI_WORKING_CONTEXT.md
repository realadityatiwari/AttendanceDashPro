# 22 — AI Working Context

This document is the permanent "working mindset" for any AI agent continuing development on AttendanceDash Pro. It captures the engineering philosophy, workflow, and architectural constraints that have emerged during the project's evolution. 

**Read this before writing a single line of code.**

## 1. Project Philosophy
- **Architecture over quick fixes**: A temporary hack becomes permanent technical debt. We built the strict Three-Engine architecture to solve complex attendance and date math correctly. Do not compromise it for fast feature delivery.
- **Zero-build simplicity**: This project uses Vanilla JS, CSS, and ES Modules intentionally. Do not introduce bundlers (Webpack, Vite) or frameworks (React, Vue) without absolute necessity and explicit user approval.
- **Generic systems over feature-specific hacks**: When building a feature (e.g., "Surprise Quiz"), do not hardcode it as a special case. Build or extend a generic system (e.g., the Academic Event System) that supports it natively along with other similar features.
- **Configuration over hardcoding**: Rules, class types, event definitions, and lab grading rules live in configuration objects (`CLASS_TYPES`, `AcademicEventRegistry`, `LAB_RULES`, `timetable.json`). Engine logic must rely on these registries, not hardcoded conditionals.
- **Minimize technical debt**: Always fix the root cause. If the UI crashes due to a bad state, fix the state generation, don't just add a null check in the UI.

## 2. Development Workflow
Before writing code for any major feature, follow this workflow:
1. **Understand the requirement**: Never guess the intent.
2. **Ask for official references**: If the feature involves university rules (e.g., how labs are graded, how medical leaves work), ask the user for official circulars or documentation.
3. **Analyze the architecture**: Which engine owns this domain? Where does the data flow?
4. **Design the solution**: Formulate an implementation plan (`implementation_plan.md`).
5. **Wait for approval**: Stop and wait for the user to approve the architecture changes.
6. **Implement**: Write the code, strictly adhering to module boundaries.
7. **Verify Cross-Platform**: Ensure Desktop, Mobile Web, and PWA all function identically.
8. **Test**: Run Node-based engine unit tests (`node --experimental-vm-modules ...`) and AST syntax checks.
9. **Update Documentation**: Update the Project Bible, AI Handoff, and Changelog.

## 3. Engineering Principles
These are immutable architectural laws:
- **UI is a pure consumer**: `ui.js` contains zero business logic. It reads from engines and builds HTML strings. 
- **Calendar Engine owns time**: Only `calendar-engine.js` calculates working days, holidays, and attendance windows.
- **Attendance Engine owns math**: Only `attendance-engine.js` calculates percentages and optimizes attendance targets.
- **Quiz Engine evaluates rules**: `quiz-engine.js` checks if the Attendance Engine's optimization meets the Calendar Engine's policy. It does not calculate attendance independently.
- **Controllers own mutations**: `events-controller.js` manages academic event creation. The UI does not mutate `AppState` directly.
- **Preserve module boundaries**: Engines do not import from `ui.js` or `app.js`. Circular dependencies are strictly forbidden (see `19_DEPENDENCY_GRAPH.md`).
- **Never duplicate business logic**: If a calculation exists in an engine, call the engine. Do not rewrite it.

## 4. Project-Specific Expectations
AttendanceDash Pro is an academic tool for SRMCEM/AKTU students. Features must:
- **Match actual university workflows**: Features like "Cancelled Classes" or "Extra Tutorials" must reflect reality, affecting the total conducted classes precisely.
- **Be driven by official documents**: Use the university's academic calendar and attendance policies as the source of truth.
- **Integrate naturally**: New workflows should feel like they belong in the existing engine pipeline.
- **Preserve backward compatibility**: Data stored in `localStorage` from older versions must not break when the app updates (provide migration paths if necessary).

## 5. Cross-Platform Expectations
The app runs identically across three surfaces. You must design for all three simultaneously:
- **Desktop Website**: Wide viewport, full data tables, side-by-side components.
- **Mobile Website**: Bottom navigation, compact cards, accordion lists (`window.innerWidth <= 768`).
- **Installed PWA**: Standalone display mode, offline-first capabilities via Service Worker.

*Rule: Never write a feature that only works on desktop. Never write business logic that branches based on the viewport size. Viewport branches only belong in `ui.js` rendering logic.*

## 6. Coding Expectations
- **Vanilla ES Modules**: Use standard `import`/`export`. No CommonJS (`require`).
- **Clear boundaries**: Keep functions small and reusable. If an engine file grows too large, extract pure utility functions, but keep the domain logic intact.
- **No magic numbers**: Use constants. `75` shouldn't be hardcoded; it should come from `getQuizPolicy()`.
- **String dates**: Dates are passed between engines as `YYYY-MM-DD` strings. Only parse them into `Date` objects internally when arithmetic is required, and use `parseDateString()` to avoid timezone offset bugs.

## 7. Decision-Making Guidelines
When multiple solutions exist, choose the one that:
- **Scales via configuration**: Can this support a new institution by just changing a JSON file?
- **Fits the existing architecture**: Does it map cleanly to the Calendar -> Attendance -> Quiz pipeline?
- **Reduces duplication**: If you are writing a `for` loop to iterate days, check if `getTeachingDaysBetween()` in Calendar Engine already does it.

*Short-term convenience (e.g., "I'll just compute the date inside the UI render function to save an import") must never outweigh long-term architectural integrity.*

## 8. Working With Official Information
When future development depends on academic rules (e.g., "How does the university handle a medical leave?"):
- **Do not invent the policy.**
- Ask the user for the official circular, ERP behavior, or departmental rule.
- Never guess attendance rules or fabricate dates.
- This ensures the math remains rigorously correct for SRMCEM students.

## 9. Regression Mindset
Before declaring a feature complete, mentally or physically check:
- Did this break the Mobile view layout?
- Did this break the PWA offline cache? (If you added a new JS file, did you add it to `service-worker.js`?)
- Did this break the Calendar Engine's event priority resolution?
- Did this alter the optimizer's output for standard L/T classes unexpectedly?
- **Are all unit tests still passing?**
- Are cloud sync payloads still schema-compliant with `firestore.rules`?

## 10. Documentation Policy
Documentation is a core part of the feature, not an afterthought.
- **Architecture changes**: Update `04_ARCHITECTURE.md`, `18_ARCHITECTURE_DECISION_RECORDS.md`, and `19_DEPENDENCY_GRAPH.md`.
- **New State**: Update `20_DATA_DICTIONARY.md`.
- **Bugs Fixed**: Update `15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md`.
- **Major Feature Finished**: Update `21_CHANGELOG.md` and `17_AI_HANDOFF.md`.

## 11. Things Future AI Should Never Forget
1. **Think before coding**: Write an implementation plan for architectural changes.
2. **Understand before modifying**: Trace the data flow from `storage.js` -> `ui.js` -> `engines` before touching a function.
3. **Preserve architecture**: The strictly-layered engine split is non-negotiable.
4. **Don't sacrifice maintainability for speed**: Write clean, testable, dependency-free vanilla JS.
5. **Ask, don't assume**: If you don't know the university's rule, ask the user.
6. **Respect existing decisions**: ADRs exist for a reason. Read them before proposing a "better" way.
