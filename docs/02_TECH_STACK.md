# 02 — Technology Stack

## Frontend

| Technology | Version / Detail | Usage |
|---|---|---|
| HTML5 | Semantic, single `index.html` | Application shell, all static layout |
| Vanilla CSS | `css/styles.css` (64 KB), `css/responsive.css` (8.7 KB) | Design system, responsive layout |
| JavaScript (ES Modules) | ES2020+, no bundler | All business logic, rendering, controllers |
| Google Fonts | Loaded via CDN in `<head>` | Typography (Inter, etc.) |

No build step. No bundler. No framework. ES modules are loaded natively by the browser.

---

## Backend / Cloud

| Technology | Detail | Usage |
|---|---|---|
| Firebase Authentication | Firebase SDK v10.7.1 (compat) | Email/password auth using internal email derivation |
| Firestore | Firebase SDK v10.7.1 (compat) | Cloud persistence, cross-device sync |
| Firebase Hosting | `firebase.json` configured | Deployment target (not yet used — app is on Vercel) |

### Firebase SDK Loading Strategy

The app uses the **compat CDN** approach. The three Firebase SDKs are loaded as synchronous `<script>` tags in `index.html` before the module script:

```html
<script src="https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.7.1/firebase-auth-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore-compat.js"></script>
<script type="module" src="js/app.js?v=2"></script>
```

This loads the `firebase` global before `js/firebase.js` executes, which is why `firebase.apps.length` can be checked directly. This is a **deliberate decision** — the modular Firebase SDK (`firebase/app`) cannot be used here without a bundler, and this approach was chosen to avoid any build tooling.

> ⚠️ **Critical**: Never switch to the modular Firebase SDK without adding a bundler (Vite/Rollup). `firebase.js` will break in Node.js test environments because `firebase` is not defined — this is expected and acceptable.

---

## Firestore Database

- **Project**: `attendancedashpro`
- **Location**: `asia-south2` (Mumbai)
- **Collection**: `students/{uid}` — one document per authenticated user
- **Collection**: `feedback/{docId}` — one document per feedback submission
- **Rules**: `firestore.rules` — strict schema validation server-side

### Firestore Document Schema (`students/{uid}`)

```
{
  profile: { name, rollNumber, createdAt },
  settings: { theme, simulationMode },
  attendance: { "YYYY-MM-DD:SUBJ_CODE:TYPE": "Attended|Missed" },
  laboratory: { "SUBJ_CODE": [ LabExperiment[] ] },
  academicEvents: { "YYYY-MM-DD": [ AcademicEvent[] ] }
}
```

> ⚠️ **Known issue**: Firestore rules in `firestore.rules` currently only allow `['attendance', 'settings', 'profile']` at the root level (line 48). This is outdated — `laboratory` and `academicEvents` are also written. The rules need updating to include these fields.

---

## Authentication

- **Strategy**: Roll number is converted to an internal email format: `{rollNumber}@student.app`.
- **Provider**: Firebase Email/Password.
- **Session persistence**: `LOCAL` (survives browser restarts).
- **Validation**: Roll number must be exactly 13 digits (`/^\d{13}$/`). Password must be ≥8 characters.

---

## PWA

| Component | Detail |
|---|---|
| Service Worker | `service-worker.js` — cache-first for static assets, network-first for navigation |
| Web App Manifest | `manifest.json` — standalone display, portrait orientation |
| Cache Strategy | Version-based cache name `attendance-dash-v{version}`. Old caches purged on activate. |
| Install Trigger | Deferred via `beforeinstallprompt`. Install button shown in Profile tab. |
| Offline Fallback | `offline.html` served when offline and no cached navigation match |
| Icons | `assets/icons/icon-192.png`, `icon-512.png`, `maskable-512.png` |

---

## Development Tooling

| Tool | Version | Usage |
|---|---|---|
| Node.js | v24.11.1 | Test runner, scratch scripts |
| npm | Bundled with Node | Package management |
| `npx serve` | via npm | Local dev server on port 8080 |
| `acorn` | ^8.18.0 | AST validation of `ui.js` (prevents syntax errors) |
| `jsdom` | ^29.1.1 | DOM simulation for unit tests |
| `puppeteer` | ^25.4.0 | Browser automation tests |
| `express` | ^5.2.1 | Used in HTTP debug scripts |

There is **no Webpack, Vite, Rollup, Babel, or TypeScript**. The project is intentionally zero-build.

---

## Testing Tools

| Tool | File | Purpose |
|---|---|---|
| Custom assertion harness | `js/test-calendar-engine.js` | Calendar engine unit tests (Node ESM) |
| Custom assertion harness | `js/test-attendance-engine.js` | Attendance engine unit tests |
| Custom assertion harness | `js/test-calendar-window.js` | Attendance window integration tests |
| Puppeteer | `run-puppeteer.js`, `run-proof.js` | Browser automation regression tests |
| acorn parser | `check_imports.js` | Import case-sensitivity validation |

---

## Deployment

Currently deployed via `npx serve . -p 8080` for local development. Firebase Hosting is configured but not yet actively used for production deployment. The application was previously also hosted on Vercel (referenced in regression report).

---

## File-Level Module Graph

```
index.html
  └── js/app.js (ES module entry point)
        ├── js/utils.js           (CLASS_TYPES, timetable, date helpers)
        ├── js/firebase.js        (auth, db exports)
        ├── js/storage.js         (AppState, persistence, cloud sync)
        ├── js/auth.js            (login, signup, logout)
        ├── js/validation.js      (roll, password validators)
        ├── js/calendar-engine.js (temporal authority, AcademicEventRegistry)
        ├── js/attendance-engine.js (optimizer, computeSubjectStats)
        ├── js/quiz-engine.js     (eligibility, QuizDashboardModel)
        ├── js/laboratory-engine.js (LabExperiment, LaboratoryDashboardModel)
        ├── js/dateContext.js     (date selection, simulation mode)
        ├── js/events-controller.js (CRUD for AcademicEvents)
        ├── js/ui.js              (all rendering, recalculateAndRender)
        ├── js/feedback.js        (feedback form, Firestore write)
        └── js/pwa.js             (service worker registration, install prompt)
```
