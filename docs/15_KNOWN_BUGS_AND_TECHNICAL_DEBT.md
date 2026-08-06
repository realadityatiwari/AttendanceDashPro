# 15 — Known Bugs and Technical Debt

This document is a living record of known issues, confirmed bugs, and acknowledged technical debt. Every item was either confirmed during development or explicitly called out in an architectural review.

---

## 🔴 Critical Bugs

### BUG-001: Firestore Rules Block `laboratory` and `academicEvents`

**File**: `firestore.rules`  
**Line**: 48  
**Severity**: Critical — data loss in production

**Description**: The `isValidStudentDoc()` function restricts root-level fields to `['attendance', 'settings', 'profile']`. The `laboratory` and `academicEvents` fields are written to Firestore by `triggerCloudSync()` but the server-side validation rejects them. This causes a Firestore "permission denied" error silently.

**Impact**: Laboratory data and Academic Events are **not synced to the cloud**. They are only in `localStorage`. Data is lost when localStorage is cleared or a new device is used.

**Fix**: Update `isValidStudentDoc()` to also allow `laboratory` and `academicEvents`:
```javascript
return docData.keys().hasOnly(['attendance', 'settings', 'profile', 'laboratory', 'academicEvents'])
```

Also add validation functions for `laboratory` and `academicEvents`.

---

### BUG-002: `events-controller.js` Not in Service Worker Cache

**File**: `service-worker.js`  
**Line**: 5–30 (STATIC_ASSETS array)  
**Severity**: High — Academic Events feature fails offline

**Description**: `js/events-controller.js` is not included in `STATIC_ASSETS`. When the service worker is active and the user is offline, importing `events-controller.js` fails, breaking Academic Event creation/management.

**Fix**: Add `/js/events-controller.js` to `STATIC_ASSETS` in `service-worker.js`. Then increment `APP_VERSION` in `utils.js` to invalidate old caches.

---

## 🟡 Known Design Issues

### DEBT-001: Dual-Write Between `AppState.academicEvents` and `runtimeEvents`

**Files**: `events-controller.js`, `calendar-engine.js`  
**Severity**: Medium — potential inconsistency

**Description**: When an academic event is created/updated/archived, the controller:
1. Calls `addAcademicEvent()` in Calendar Engine → updates `runtimeEvents` in-memory.
2. Also writes to `AppState.academicEvents` directly.

On app restart, `syncRuntimeEvents(AppState.academicEvents)` reloads `runtimeEvents` from `AppState`. But within a single session, if either write fails, they can diverge.

**Risk**: Calendar Engine computes event deltas from `runtimeEvents`. AppState is what persists. If they diverge, the displayed percentages may differ from what's stored.

**Fix**: Consider making `AppState.academicEvents` the source of truth always, and having the Calendar Engine read directly from it (or have a single sync point).

---

### DEBT-002: Lab Attendance Lookup Uses Wrong Key Format

**File**: `laboratory-engine.js`  
**Line**: 112  
**Severity**: Medium — lab attendance status always null

**Description**: `getExperimentAttendanceStatus` looks up:
```javascript
const classId = `${dateConducted}:${subjectCode}:P`;
```

But attendance is logged as `"DATE:CODE:P1"` (the raw timetable slot type). The lookup key `":P"` never matches anything — `attendanceStatus` will always be `null`.

**Fix**: Look up `P1` instead:
```javascript
const classId = `${dateConducted}:${subjectCode}:P1`;
```

Or use both and take the first truthy result.

---

### DEBT-003: `computeSubjectStats` References Non-Existent `totP`, `attP_done` in Lab

**File**: `laboratory-engine.js`  
**Lines**: 143–147  
**Severity**: Medium — lab attendance percentage always 0

**Description**: The lab engine tries to read `stats.totP`, `stats.attP_done`, `stats.pendingP` from `subjectStatsArray`. But `computeSubjectStats()` returns `totL`, `totT`, `totComb` etc. — not `totP`.

**Fix**: Either:
1. Pass raw `rawData[code]` to the lab engine instead of composed stats.
2. Add `totP`, `attP_done`, `pendingP` extraction to `computeSubjectStats`.

---

### DEBT-004: `semesterEnd` is Hardcoded in `app.js`

**File**: `app.js`  
**Line**: 270  
**Severity**: Low — will break in 2030

**Description**:
```javascript
semesterEnd: '2030-12-31', // Mock end for now
```

This should come from `timetable.json`.

**Fix**: Add a `end_date` field to `timetable.json` and read it in `bootstrap()`.

---

### DEBT-005: `getAcademicDay` Uses `new Date(dateString)` Instead of `parseDateString`

**File**: `calendar-engine.js`  
**Line**: ~463  
**Severity**: Low — may cause off-by-one date errors in certain timezones

**Description**: `new Date('YYYY-MM-DD')` parses as UTC midnight. In timezone-negative offsets (e.g., UTC-5), this resolves to the previous day in local time.

**Fix**: Replace with `parseDateString()` from `utils.js` which creates a local noon date.

---

### DEBT-006: `addDays` Uses `toISOString()` Which Is UTC-Based

**File**: `calendar-engine.js`  
**Line**: ~addDays function  
**Severity**: Low — same timezone risk as DEBT-005

**Fix**: Replace `date.toISOString().split('T')[0]` with `getLocalDateString(date)` from `utils.js`.

---

### DEBT-007: `currentQuiz` Is a Mutable Module-Level Variable in `ui.js`

**File**: `ui.js`  
**Severity**: Low — minor design smell

**Description**: Tab state is stored as a module-level variable. This works but breaks the single-state pattern. It can't be serialized or debugged from outside `ui.js`.

**Fix**: Move into `AppState` or a dedicated `uiState` object for consistency.

---

### DEBT-008: `AppState.history` Is Never Populated

**File**: `storage.js`, `ui.js`  
**Severity**: Low — dead code

**Description**: `AppState.history = []` exists but nothing writes to it. The History view is generated from `AppState.attendance` keys. The `history` field confuses readers of the code.

**Fix**: Either remove the field from `AppState` or implement it properly as a timestamped log of user actions.

---

### DEBT-009: No Error Toast for Failed Event Operations

**File**: `app.js` (event form submission handler)  
**Severity**: Low — poor UX

**Description**: If `createAcademicEvent()` returns `{ success: false, error }`, the error is logged to console but not shown to the user.

**Fix**: Show a toast notification (using the existing feedback toast system) when event operations fail.

---

### DEBT-010: `optimizeLive` in Attendance Engine Uses Hardcoded `75` in Dashboard Tab

**File**: `attendance-engine.js`  
**Line**: 458  
**Severity**: Low — inconsistency with policy system

**Description**: `computeSubjectStats()` calls `optimizeLive()` with `75` hardcoded. It should use `getQuizPolicy(currentQuizCycle).targetPercentage` to match the active tab's policy.

---

## 🟢 Resolved Issues (Historical Reference)

### RESOLVED: Phase S1.10 — `ui.js` Syntax Error Caused Complete Login Failure

**Resolution**: Removed duplicate `const labSectionHTML` declaration, fixed malformed template literal injection in `recalculateAndRender()`. See `regression_report.md` for full details.

### RESOLVED: Hydration Crash — `formatTodayHeader` Called with String Instead of Date

**Resolution**: Patched `formatTodayHeader()` in `utils.js` to handle both string and Date inputs safely using `parseDateString()`.

### RESOLVED: Mobile Subjects Tab Was Empty

**Resolution**: Modified `recalculateAndRender()` to explicitly inject `mobileCardsHTML` into `#subjectsViewContent`, separate from the dashboard `#panels` injection.
