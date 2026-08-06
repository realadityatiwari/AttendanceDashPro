# 04 — Complete Architecture

## Architectural Philosophy

The architecture is a **strict layered engine architecture** with clear data ownership, unidirectional data flow, and a single unified render pipeline. Every design decision enforces one principle: **no duplicated business logic anywhere in the codebase**.

---

## Layer Diagram

```mermaid
graph TD
    subgraph "Data Sources"
        TT[timetable.json]
        LS[localStorage]
        FS[Firestore]
    end

    subgraph "Bootstrap Layer"
        BOOT[app.js bootstrap]
    end

    subgraph "State Layer"
        AS[AppState]
        DC[dateContext]
    end

    subgraph "Engine Layer"
        CE[Calendar Engine]
        AE[Attendance Engine]
        QE[Quiz Engine]
        LE[Laboratory Engine]
    end

    subgraph "Controller Layer"
        EC[EventsController]
        LC[logAttendance in ui.js]
    end

    subgraph "Rendering Layer"
        UI[ui.js - recalculateAndRender]
    end

    TT --> BOOT
    BOOT --> CE
    BOOT --> AS
    LS --> AS
    FS --> AS
    AS --> CE
    AS --> DC
    CE --> AE
    AE --> QE
    AE --> LE
    DC --> UI
    AE --> UI
    QE --> UI
    LE --> UI
    EC --> AS
    EC --> CE
    EC --> UI
    LC --> DC
    LC --> UI
```

---

## Unidirectional Data Flow

```mermaid
sequenceDiagram
    actor User
    User->>Controller: Action (e.g. toggle class, create event)
    Controller->>State: Mutate State (AppState or dateContext)
    State-->>Persistence: persistLocalState + triggerCloudSync
    Controller->>UI: recalculateAndRender()
    UI->>Engines: Execute Pipeline (CE → AE → QE → LE)
    Engines-->>UI: Return Computed Models
    UI->>DOM: Update DOM
```

This flow is **always** followed. No exceptions. The UI never mutates state directly or calls engine functions independently.

---

## Engine Architecture

### Dependency Order

```
timetable.json (raw data)
    ↓
utils.js (CLASS_TYPES, getMergedDaySchedule)
    ↓
calendar-engine.js (AcademicDay, windows, event deltas)
    ↓
attendance-engine.js (counts, optimization)
    ↓
quiz-engine.js (eligibility from Attendance Engine results)
    ↓
laboratory-engine.js (independent, uses only utils.js)
```

Each engine only imports from layers below it. No circular imports.

### Engine Data Ownership

| Engine | Owns | Does NOT Own |
|---|---|---|
| Calendar Engine | Working days, holidays, quiz windows, attendance windows, event resolution, event priority | Attendance counts, optimization, eligibility |
| Attendance Engine | All attendance math: current %, forecast %, optimization, must-attend counts, safe skips | Dates, quiz dates, eligibility rules |
| Quiz Engine | Eligibility determination per subject per quiz cycle | Attendance calculation (delegates to Attendance Engine) |
| Laboratory Engine | Lab experiment tracking, milestone evaluation | Regular attendance, quiz eligibility |

---

## Module Boundaries

### Strict Rules (Never Violate)

1. **`ui.js` imports from engines — engines do NOT import from `ui.js`** (except `events-controller.js` which must call `recalculateAndRender` after mutations — this is the single allowed reverse reference and is intentional).
2. **`calendar-engine.js` has no imports** (aside from no external dependencies). It is a pure, self-contained temporal authority.
3. **`attendance-engine.js` does not import `quiz-engine.js`** or any UI layer.
4. **`app.js` is the only file that imports from all other modules**.
5. **`storage.js` does not import engine modules**. It owns the data layer only.

---

## State Architecture

### `AppState` (in `storage.js`)

The single global state object. Not a reactive store — it is a plain JavaScript object.

```javascript
export const AppState = {
  profile: {},           // { name, rollNumber, createdAt }
  attendance: {},        // { "YYYY-MM-DD:CODE:TYPE": "Attended|Missed" }
  laboratory: {},        // { "CODE": LabExperiment[] }
  history: [],           // Reserved — not actively used
  settings: { theme: 'dark', simulationMode: false },
  academicEvents: {},    // { "YYYY-MM-DD": AcademicEvent[] }
  isDirty: false
};
```

**Rules**:
- `attendance` is keyed by class IDs: `"YYYY-MM-DD:SUBJ_CODE:TYPE"`.
- `academicEvents` is date-indexed (not flat array) for O(1) lookups by date.
- No module mutates `AppState` directly in a one-off manner — all mutations go through dedicated functions.

### `dateContext` (in `dateContext.js`)

A secondary state object governing which date is being viewed and whether the app is in live or simulation mode.

```javascript
export const dateContext = {
  selectedDate: getTodayString(), // YYYY-MM-DD string
  mode: MODE.LIVE,                // 'LIVE' or 'SIMULATION'
  simulationAttendance: {}        // Temporary overlay, never persisted
};
```

**Rules**:
- `selectedDate` is always a `YYYY-MM-DD` **string** (never a `Date` object).
- Mode is derived automatically from `selectedDate` vs. today. Never set manually.
- Simulation attendance is always discarded when returning to LIVE mode.

---

## Rendering Pipeline

### `recalculateAndRender()` in `ui.js`

This is the **single master refresh function**. Every state change triggers this function. It:

1. Reads `getEffectiveStates()` from `dateContext` (live or simulation attendance).
2. Reads `getTimetable()` from `utils.js`.
3. For each quiz tab:
   - Calls `getAttendanceData(quizDate, states)` from `attendance-engine.js`.
   - Calls `computeSubjectStats()` for each subject.
   - Calls `computeOverallStats()` for the dashboard summary.
   - Calls `computeQuizDashboard()` from `quiz-engine.js`.
   - Calls `computeLaboratoryDashboard()` from `laboratory-engine.js`.
4. Builds the full HTML via component builder functions.
5. Injects into the correct DOM containers.
6. Calls `renderTodayClasses()` for today's class log.
7. Calls `renderAcademicEvents()` for the events view.

---

## Storage Pipeline

```mermaid
sequenceDiagram
    actor User
    User->>UI: logAttendance()
    UI->>DateContext: logClassState()
    alt if LIVE mode
        DateContext->>Storage: saveStates()
        Storage->>Storage: AppState.attendance updated
        Storage->>Storage: persistLocalState(uid)
        Storage->>Firestore: triggerCloudSync() (1000ms debounce, merge: true)
    end
```

---

## Calendar Pipeline

```mermaid
sequenceDiagram
    participant Boot as Bootstrap (app.js)
    participant CE as Calendar Engine
    participant AE as Attendance Engine
    
    Boot->>CE: initCalendarEngine(calendarData)
    Note over CE: L1 static cache frozen
    Boot->>CE: syncRuntimeEvents(AppState.academicEvents)
    Note over CE: runtime events loaded
    
    AE->>CE: getAcademicDay(dateString)
    Note over CE: resolves events for date<br/>applies priority conflict resolution
    CE-->>AE: immutable AcademicDay (cached in L2)
    
    AE->>CE: getQuizWindow(subjectCode, quizCycle)
    Note over CE: finds quiz milestone<br/>computes effective teaching dates
    CE-->>AE: AttendanceWindow
```

---

## Academic Event Pipeline

```mermaid
sequenceDiagram
    actor User
    participant App as app.js
    participant Ctrl as EventsController
    participant CE as Calendar Engine
    participant Storage as AppState/Storage
    participant UI as ui.js
    
    User->>App: handleEventFormSubmit()
    App->>Ctrl: createAcademicEvent()
    Ctrl->>CE: validateAcademicEvent()
    Ctrl->>Storage: Uniqueness check (AppState.academicEvents)
    Ctrl->>CE: addAcademicEvent(newEventData)
    Note over CE: L2 cache cleared
    Ctrl->>Storage: AppState.academicEvents[date].push(event)
    Ctrl->>Storage: persistLocalState() + triggerCloudSync()
    Ctrl->>UI: recalculateAndRender()
    UI-->>User: Event appears in UI
```

---

## Bootstrap Sequence

```mermaid
sequenceDiagram
    participant DOM as DOM
    participant App as app.js
    participant Auth as auth.js
    participant UI as ui.js
    participant Store as storage.js
    
    DOM->>App: DOMContentLoaded
    App->>App: initDOMBindings()
    App->>App: bootstrap()
    Note over App: initTimetable, initCalendarEngine,<br/>syncRuntimeEvents, apply theme
    App->>Auth: onAuthStateChanged() listener registered
    
    Note over Auth: On User Login
    Auth->>Store: initLocalState(uid) (Hydrate from LocalStorage)
    Auth->>UI: applyTheme(), updateProfileUI(), recalculateAndRender()
    Auth->>Store: fetchCloudStates() (Background sync)
    
    alt if cloud state changed
        Store->>UI: applyTheme(), updateProfileUI(), recalculateAndRender()
    end
    
    Auth->>Auth: checkProfileRecovery(), checkMigration()
```

---

## Desktop vs Mobile Rendering

`recalculateAndRender()` uses `window.innerWidth <= 768` to detect mobile viewport and branches:

- **Desktop**: Renders hero card + quiz table + lab section + full statistics table per tab.
- **Mobile**: Renders compact attendance cards for the dashboard panel; subject accordion cards are injected into `#subjectsViewContent` separately.

The underlying engine calculations are **identical** regardless of viewport. Only the HTML template functions differ.
