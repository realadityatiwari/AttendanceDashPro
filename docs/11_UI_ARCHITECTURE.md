# 11 — UI Architecture

**File**: `js/ui.js`  
**Lines**: 1468  
**Status**: ✅ Core rendering complete. Academic Events UI implemented, awaiting validation.

---

## Purpose

`ui.js` is the **rendering layer only**. It consumes data from engines and renders HTML. It contains no business logic, no attendance calculations, no eligibility rules, and no date math.

The single entry point for all re-renders is `recalculateAndRender()`.

---

## Core Principle

> The UI never orchestrates engines. The UI never mutates `AppState` directly. The UI reads from engines and writes through controllers.

The one exception: `logAttendance()` and `logExperiment()` live in `ui.js` because they are tightly coupled to user interaction, but they route all mutations through `dateContext.logClassState()` and `saveLaboratoryStates()` respectively — never bypassing the controller/storage layer.

---

## recalculateAndRender()

The master render function. Called after every state change (attendance log, quiz tab switch, date change, event mutation):

```
1. getTimetable() — get academic model
2. getEffectiveStates() — get current or simulation attendance
3. For each quiz tab (one per quiz_dates entry + "All Dates"):
   a. getAttendanceData(quizDate, states)
   b. computeSubjectStats() for each subject → subjectStats[]
   c. computeOverallStats(subjectStats)
   d. computeCurrentOverallAttendance(rawData, subjects)
   e. computeForecastOverallAttendance(rawData, subjects)
   f. computeQuizDashboard(states, quizCycle, timetable)
   g. computeLaboratoryDashboard(...)
   h. renderPanel(...)
4. renderTabs(tabs) — inject tab buttons into #quizTabs
5. renderTodayClasses(selectedDate, quizLiveData)
6. renderAcademicEvents() — populate #eventsList
7. updateModeBadge()
8. updateViewingLabel()
9. updateMobileDateLabel()
```

---

## Quiz Tab System

The dashboard is organized around quiz cycles. Each quiz cycle gets its own tab:

```
Tab 0: "All Dates" — covers all teaching dates from semester start to now
Tab 1: "1st Quiz" — covers commencement to day before Quiz 1
Tab 2: "2nd Quiz" — covers commencement to day before Quiz 2
Tab 3: "3rd Quiz" — covers commencement to day before Quiz 3
```

The active tab index is stored in `currentQuiz` (exported module-level variable). Switching tabs calls `recalculateAndRender()`.

---

## Key Rendering Functions

### Dashboard Section Builders (Desktop)

- `buildHeroCard(overallStats, erpStats, forecastStats, label, quizDate)` — Top summary card with overall/forecast ERP percentages, classes attended today, safe skips, and must-attend counts.
- `buildQuizDashboardSection(quizModel)` — Quiz eligibility cards per subject.
- `buildLaboratoryDashboardSection(labModel)` — Lab experiment progress cards.
- `buildSubjectCard(row)` — Individual subject percentage card.
- `buildTableRow(row)` — Full attendance data table row.
- `buildStatsRow(overallStats)` — Summary statistics footer row.

### Dashboard Section Builders (Mobile)

- `buildMobileAttendanceCard(row)` — Compact attendance card for mobile dashboard.
- Mobile subjects are rendered into `#subjectsViewContent` (Subjects tab), not `#panels`.

### Today's Classes Section

- `renderTodayClasses(targetDateStr, quizLiveData)` — Renders the class log for the selected date. Shows each scheduled class with attendance toggle buttons (Attended/Missed/Pending). Integrates with `getAcademicDay()` for schedule substitution. Shows "No classes" for non-working days.

### Academic Events Section

- `renderAcademicEvents()` — Reads `AppState.academicEvents`, filters by the active tab (`data-filter` attribute), builds event cards, injects into `#eventsList`.

### History Section

- History is rendered from the `states` map (attendance keys) extracted into a flat list sorted by date. No separate history data structure.

---

## Date Navigator

Rendered by `renderDateNavigator()` (for desktop) and `renderBottomSheetDateNav()` (for mobile bottom sheet).

Shows:
- Yesterday
- Today
- Tomorrow
- The last 7 past dates with attendance data
- A "Pick a date" fallback date input

Date changes call `selectDateByString(dateStr)` from `dateContext.js`, then `recalculateAndRender()`.

---

## Status Color System

All status coloring is driven by three threshold-aware helpers:

```javascript
pctColor(pct, targetPercentage = 75)
  → pct >= 75: 'var(--green)'
  → pct >= 60: 'var(--amber)'
  → else:      'var(--red)'

getSubjectStatus(forecastAvgPct, targetPercentage = 75)
  → pct >= 80: { text: 'SAFE',     cls: 'status-safe' }
  → pct >= 75: { text: 'WARNING',  cls: 'status-warning' }
  → else:      { text: 'CRITICAL', cls: 'status-critical' }
```

Status is **always** based on forecast percentage, never current percentage. This is intentional — pending classes are included in the forecast, giving an optimistic "best case" view.

---

## Attendance Logging

```javascript
export function logAttendance(dateStr, subjectCode, type, newState)
```

Called from the global click handler in `app.js` when a user taps a class button.

Flow:
1. Validates via `isScheduledClass()`.
2. Routes through `logClassState()` from `dateContext.js` (handles LIVE vs. SIMULATION).
3. Calls `recalculateAndRender()`.

**The click handler in `app.js`** uses event delegation on `document.body`:

```javascript
document.body.addEventListener('click', (e) => {
  // Attendance log buttons
  if (t.dataset.dateStr && t.dataset.code && t.dataset.type) {
    logAttendance(t.dataset.dateStr, t.dataset.code, t.dataset.type, t.dataset.state);
  }
  // Academic event actions
  if (t.id === 'btnNewEvent') openEventForm();
  if (t.dataset.action === 'toggle-event') toggleAcademicEvent(...);
  if (t.dataset.action === 'archive-event') archiveAcademicEventController(...);
  // etc.
});
```

---

## Imports

`ui.js` imports from:
- `storage.js` — `loadStates`, `clearStates`, `AppState`, `saveLaboratoryStates`
- `utils.js` — `getTimetable`, formatters, `CLASS_TYPES`, schedule helpers
- `attendance-engine.js` — all computation functions
- `laboratory-engine.js` — `computeLaboratoryDashboard`
- `quiz-engine.js` — `computeQuizDashboard`
- `dateContext.js` — `dateContext`, `MODE`, navigation functions
- `calendar-engine.js` — `addDays`, `getTodayString`, `getAcademicDay`, `AcademicEventRegistry`

`ui.js` does **not** import from `events-controller.js` (the controller imports from `ui.js` for `recalculateAndRender`, not the reverse).

---

## Known Issues / Technical Debt

1. **`logExperiment()` in `ui.js`**: Lab experiment logging should be in a dedicated `LabController`, not in the rendering module.
2. **`currentQuiz` is a module-level mutable variable**: This is a design smell. Tab state should ideally be in a proper state object.
3. **Template literal HTML generation**: Building HTML via string concatenation in template literals is the current approach for component rendering. This works but is not scalable for complex interactive components. No framework migration is planned — just be aware that complex nested interactivity is harder to implement with this pattern.
4. **`history` tab implementation**: The History view reads from `AppState.attendance` keys at render time by filtering dates from the full state map. This is O(n) on every render where n = total logged classes. Should be cached or pre-indexed for large datasets.
5. **Mobile/Desktop rendering branch**: The `window.innerWidth <= 768` check inside `recalculateAndRender()` is evaluated on every render. This is not reactive — window resizing mid-session doesn't automatically re-render. Intended for initial load detection.
