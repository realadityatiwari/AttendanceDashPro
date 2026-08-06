You are an expert AI QA engineer running regression tests for AttendanceDash Pro.

# PREREQUISITES
Before executing this prompt, you MUST:
1. Read `docs/17_AI_HANDOFF.md` and `docs/22_AI_WORKING_CONTEXT.md`.
2. Understand the strict Three-Engine Architecture (Calendar → Attendance → Quiz/Lab).

# INSTRUCTIONS

Execute a full regression pass to ensure recent changes have not broken existing functionality.

### 1. Engine Baselines
Verify that the Attendance Engine produces the exact same optimization arrays and percentage calculations for a standard student profile.

### 2. Calendar Resolution
Verify that `calendar-engine.js` correctly prioritizes holidays over working days, and extra classes over holidays.

### 3. UI Rendering (Desktop & Mobile)
Simulate or manually instruct the user to verify that the UI renders the Dashboard, Subject detail tabs, and Laboratory views correctly on both wide and narrow viewports.

### 4. PWA and Storage
Verify that `localStorage` serialization is intact. Ensure the Service Worker (`service-worker.js`) cache version (`APP_VERSION`) was bumped if JS/CSS files changed.

Report any deviations immediately as bugs requiring root cause analysis.
