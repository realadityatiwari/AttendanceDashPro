# 01 — Project Overview

## Purpose

AttendanceDash Pro tracks lecture, tutorial, and practical attendance for a fixed cohort of subjects, and applies a mathematically optimal algorithm to compute exactly how many remaining classes a student needs to attend — or can skip — to remain eligible for each upcoming quiz.

---

## Target Platform

The application is a **single HTML file, multi-module vanilla JavaScript** web application deployed as a Progressive Web App (PWA). It runs identically across three surfaces:

### Desktop Browser (Wide Viewport)
- Shows the full-width dashboard with an attendance statistics table.
- Hero card with overall/forecast ERP-style attendance percentages.
- Quiz dashboard sections embedded in-line.
- Laboratory dashboard embedded in-line.
- Full subject card grid with per-subject percentage bars.

### Mobile Web (≤768px Viewport)
- Bottom navigation bar: **Dashboard / Subjects / History / Profile**.
- Dashboard shows today's class log cards, mobile hero card, and attendance cards in list format.
- Subjects tab shows accordion-style subject detail cards.
- History tab shows the full attendance log sorted by date.
- Profile tab exposes theme toggle, academic tools workspace, feedback form, logout, and app install.

### Installed PWA (Android / Chrome)
- Runs in `standalone` display mode — no browser chrome.
- Uses service worker for offline-capable operation.
- Full feature parity with the mobile web experience.
- Install prompt is shown in the Profile tab.

---

## Design Philosophy

1. **Local-first, Cloud-backed**: State is always hydrated from `localStorage` first. Cloud sync happens in the background. This prevents blank screens on reconnect and ensures the app is usable offline.

2. **Engine architecture with strict data ownership**: The application is divided into specialized engines. No engine performs work outside its domain boundary:
   - **Calendar Engine** owns all temporal logic.
   - **Attendance Engine** owns all attendance mathematics.
   - **Quiz Engine** evaluates eligibility only — never calculates attendance.
   - **Laboratory Engine** manages practical session state independently.

3. **UI is a pure consumer**: The UI layer (`ui.js`) reads from engines and renders. It never orchestrates engines, never directly mutates `AppState`, and never contains business logic. All mutations go through dedicated controllers.

4. **Configuration over hardcoding**: Class types, quiz policies, subject timelines, event types, and lab rules are all driven by data structures, not hardcoded conditionals. Changing behavior means changing configuration, not engine logic.

5. **Desktop and mobile share identical business logic**: There is exactly one set of engines, one set of calculations, and one set of controllers. Only rendering differs by viewport.

---

## Scalability Goals

- **New institution support**: Adding a new institution should require only a new `timetable.json` file and a new `AcademicCalendar` configuration object. Zero engine changes.
- **New subject types**: Adding new class types (e.g., seminars) should require only additions to the `CLASS_TYPES` registry in `utils.js`. Zero engine rewrites.
- **New academic event types**: Adding new event categories (e.g., field trips) should require only additions to `AcademicEventRegistry` in `calendar-engine.js`. Zero controller rewrites.
- **New quiz policies**: Changing eligibility thresholds per quiz cycle should require only changes to the `policies` object passed to `initCalendarEngine()`.
