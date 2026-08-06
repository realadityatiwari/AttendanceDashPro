# 03 — Folder Structure

## Root Directory

```
AttendanceDashPro/
├── index.html                  # Application shell — ALL static layout lives here
├── offline.html                # Offline fallback page (served by service worker)
├── manifest.json               # PWA manifest (name, icons, display mode)
├── service-worker.js           # PWA service worker (cache-first, version-based)
├── firebase.json               # Firebase project config (hosting + Firestore)
├── firestore.rules             # Firestore security rules (server-side schema validation)
├── firestore.indexes.json      # Firestore composite index declarations
├── timetable.json              # ACADEMIC DATA MODEL — subject schedule, quiz dates, timeslots
├── package.json                # Dev dependencies (acorn, jsdom, puppeteer, express)
├── package-lock.json           # Lock file
├── README.md                   # Basic project README
├── screenshot.png              # PWA screenshot (used by manifest or marketing)
│
├── js/                         # All application JavaScript (ES modules)
├── css/                        # All application styles
├── assets/                     # Static assets (icons, images)
├── docs/                       # THIS DIRECTORY — project documentation
│
└── [scratch files]             # See below
```

---

## `js/` Directory — JavaScript Modules

Every file in `js/` is an ES module. Import/export are used throughout. No CommonJS.

```
js/
├── app.js                  # ENTRY POINT — bootstraps engines, auth, DOM bindings
├── utils.js                # CLASS_TYPES registry, timetable loader, date helpers
├── firebase.js             # Firebase initialization, auth/db singleton exports
├── auth.js                 # loginUser, signupUser, logoutUser
├── validation.js           # Roll number and password validators
├── storage.js              # AppState singleton, localStorage, Firestore cloud sync
├── dateContext.js          # Date selection system, LIVE/SIMULATION mode
├── calendar-engine.js      # TEMPORAL AUTHORITY — AcademicDay, windows, events
├── attendance-engine.js    # ATTENDANCE MATH — optimizer, computeSubjectStats
├── quiz-engine.js          # QUIZ RULES ENGINE — eligibility, QuizDashboardModel
├── laboratory-engine.js    # LAB ENGINE — LabExperiment, LaboratoryDashboardModel
├── events-controller.js    # CRUD controller for AcademicEvents
├── ui.js                   # ALL rendering — recalculateAndRender, component builders
├── feedback.js             # Feedback form, Firestore write, cooldown timer
├── pwa.js                  # Service worker registration, install prompt
│
├── test-calendar-engine.js     # Unit tests — calendar engine
├── test-attendance-engine.js   # Unit tests — attendance engine
└── test-calendar-window.js     # Integration tests — attendance windows
```

### File Responsibilities

| File | Owns | Imports From |
|---|---|---|
| `app.js` | Bootstrap, auth listener, DOM bindings, view switching | All modules |
| `utils.js` | `CLASS_TYPES`, timetable data, date helpers, `APP_VERSION` | None (leaf module) |
| `firebase.js` | Firebase `auth` and `db` singleton | None (depends on CDN globals) |
| `auth.js` | Authentication actions | `firebase.js`, `storage.js` |
| `validation.js` | Form validation rules | None |
| `storage.js` | `AppState`, persistence, cloud sync | `firebase.js` |
| `dateContext.js` | Date navigation state, simulation mode | `utils.js`, `storage.js`, `calendar-engine.js` |
| `calendar-engine.js` | All temporal authority | None (leaf — pure logic) |
| `attendance-engine.js` | All attendance math | `utils.js`, `calendar-engine.js` |
| `quiz-engine.js` | Quiz eligibility evaluation | `calendar-engine.js`, `attendance-engine.js` |
| `laboratory-engine.js` | Lab session tracking | `utils.js` |
| `events-controller.js` | Academic event mutations | `storage.js`, `calendar-engine.js`, `ui.js`, `firebase.js` |
| `ui.js` | All DOM rendering | `storage.js`, `utils.js`, `attendance-engine.js`, `laboratory-engine.js`, `quiz-engine.js`, `dateContext.js`, `calendar-engine.js` |
| `feedback.js` | Feedback form submission | `firebase.js`, `storage.js`, `utils.js` |
| `pwa.js` | Service worker, install | `utils.js` |

---

## `css/` Directory

```
css/
├── styles.css          # Primary design system (64 KB) — all tokens, components, layout
└── responsive.css      # Responsive breakpoints and mobile-specific overrides (8.7 KB)
```

`styles.css` contains:
- CSS custom properties (color tokens: `--text`, `--surface`, `--accent`, `--green`, `--red`, `--amber`, etc.)
- Dark and light theme definitions (toggled via `data-theme` attribute on `<html>`)
- All component styles: header, bottom nav, cards, tables, hero, quiz section, lab section, modals, toasts, form bottom sheet, date navigator
- Animation and transition definitions

`responsive.css` contains:
- Mobile-specific layout overrides for viewports ≤768px
- Desktop-specific layout corrections for viewports >768px
- PWA standalone display-mode overrides

---

## `assets/` Directory

```
assets/
└── icons/
    ├── icon-192.png        # Standard PWA icon
    ├── icon-512.png        # High-res PWA icon
    └── maskable-512.png    # Maskable icon for Android adaptive icons
```

---

## `docs/` Directory

```
docs/
├── 00_EXECUTIVE_SUMMARY.md
├── 01_PROJECT_OVERVIEW.md
├── 02_TECH_STACK.md
├── 03_FOLDER_STRUCTURE.md          (this file)
├── 04_ARCHITECTURE.md
├── 05_CALENDAR_ENGINE.md
├── 06_ATTENDANCE_ENGINE.md
├── 07_QUIZ_ENGINE.md
├── 08_LABORATORY_ENGINE.md
├── 09_ACADEMIC_EVENT_SYSTEM.md
├── 10_STORAGE_AND_SYNC.md
├── 11_UI_ARCHITECTURE.md
├── 12_PWA_AND_DEPLOYMENT.md
├── 13_CODING_STANDARDS.md
├── 14_TESTING_AND_QA.md
├── 15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md
├── 16_ROADMAP.md
└── 17_AI_HANDOFF.md
```

---

## Root Scratch Files (Do Not Delete Without Understanding)

Several Python and JavaScript scratch files remain in the root from earlier development phases. These should be cleaned up but are not harmful:

| File | Origin | Status |
|---|---|---|
| `check_imports.js` | Import case-sensitivity checker | Useful for regression |
| `check_ui.js` | UI element checker | Debug script |
| `extract-engine.py` | Engine code extraction helper | Obsolete |
| `extract-ui.py` | UI code extraction helper | Obsolete |
| `fix-engine.py` | One-time engine fix script | Obsolete |
| `fix-syntax.py` | One-time syntax fix script | Obsolete |
| `patch-*.py` | One-time patch scripts | Obsolete |
| `refactor-events.py` | Events refactor helper | Obsolete |
| `split.py` | Code splitting helper | Obsolete |
| `run-*.js` | Puppeteer/HTTP test runners | Keep for QA |
| `test-*.js` | Browser/engine test scripts | Keep for QA |
| `regression_report.md` | Phase S1.10 regression fix notes | Archival |
| `verification_report.md` | Phase verification notes | Archival |
