# 13 — Coding Standards

## Module Structure

Every JavaScript file is an ES module. All exports are named (no default exports except where unavoidable). Import paths are always relative (`./utils.js`, not `utils.js`).

```javascript
// Correct
import { getTimetable, parseDateString } from './utils.js';

// Incorrect — no default imports used in this project
import utils from './utils.js';
```

---

## Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Functions | `camelCase` | `computeSubjectStats` |
| Constants | `SCREAMING_SNAKE_CASE` | `CLASS_TYPES`, `LAB_RULES`, `APP_VERSION` |
| Classes | `PascalCase` | `OptimizationResult`, `QuizEligibilityResult` |
| Variables | `camelCase` | `rawData`, `subjectStats` |
| Module-level singletons | `camelCase` | `dateContext`, `AppState` |
| DOM IDs | `camelCase` | `todayClassList`, `eventsView` |
| Data attributes | `camelCase` (via `dataset`) | `data-date-str`, `data-subject-code` |
| CSS classes | `kebab-case` | `status-safe`, `mobile-att-cards` |
| CSS custom properties | `--kebab-case` | `--text`, `--surface2`, `--accent` |

---

## File Organization

Each file has a clear single responsibility:

- **Engine files** (`calendar-engine.js`, etc.): Pure computation. No DOM. No global state reads (except their own internal singletons).
- **UI file** (`ui.js`): HTML string builders and DOM manipulation only. No business logic.
- **Controller files** (`events-controller.js`): Orchestrate mutation → persistence → re-render. No HTML.
- **Storage file** (`storage.js`): State container and persistence only. No rendering.
- **App entry** (`app.js`): Bootstrap, event listeners, view routing. No business logic.

---

## State Ownership Rules

| State | Owner | Who Reads | Who Writes |
|---|---|---|---|
| `AppState` | `storage.js` | All modules | `storage.js` (via dedicated functions), `events-controller.js` (events), `auth.js` (profile) |
| `dateContext` | `dateContext.js` | `ui.js`, `dateContext.js` | `dateContext.js` (via `selectDateByString`, `logClassState`) |
| `l1StaticData` | `calendar-engine.js` | `calendar-engine.js` only | `initCalendarEngine()` only (once) |
| `runtimeEvents` | `calendar-engine.js` | `calendar-engine.js` only | `addAcademicEvent()`, `archiveAcademicEvent()`, `syncRuntimeEvents()` |
| `currentQuiz` | `ui.js` | `ui.js`, `app.js` (reads) | `ui.js` (on tab switch) |

---

## Engine Rules

1. **Engines are stateless between calls** (except their own internal caches).
2. **Engines never import from `ui.js`** or `app.js`.
3. **Engines never read `AppState` directly** (except `attendance-engine.js` which reads via `states` parameter and never touches `AppState` globally).
4. **Engines return frozen, immutable objects** where possible (see `AcademicDay`, `AcademicEvent`).
5. **Engines throw on invalid input** rather than returning null/undefined silently.

---

## Controller Rules

1. Every mutation flows through: `validate → mutate AppState → persist → sync → re-render`.
2. Controllers return `{ success: boolean, error?: string }`.
3. Controllers never contain rendering logic.
4. Controllers never contain business rule logic (business logic is in engines or validators).

---

## UI Rules

1. `ui.js` renders from data — it never calculates.
2. All component builders return HTML strings (template literals). They do not directly manipulate the DOM.
3. Single injection point: computed HTML is injected into a container element once per render cycle.
4. Component builders are pure functions (same input = same output).
5. Interactive state (e.g., attendance button current state) is read from `getEffectiveStates()` at render time — never cached locally in the component.

---

## Error Handling

- **Engines**: `throw new Error(message)` for validation failures. Callers catch.
- **Controllers**: `try/catch` around `processEventMutation`. Return `{ success, error }`.
- **Storage**: `try/catch` around all localStorage and Firestore operations. Log to console.
- **Bootstrap**: Wrapped in `try/catch`. Non-fatal errors logged, execution continues.
- **UI**: No throws. Silently degrade (empty state, fallback text).

Never use `console.error` for known/expected conditions. Use `console.warn` for expected edge cases and `console.error` only for unexpected failures.

---

## Comment Style

Module-level block comments use the `═══` border style:

```javascript
/* ═══════════════════════════════════════════════════════════════════════
   SECTION TITLE
   Description of what this section does.
═══════════════════════════════════════════════════════════════════════ */
```

Function comments use JSDoc:

```javascript
/**
 * Brief description.
 * @param {Type} paramName - Description
 * @returns {ReturnType} Description
 */
```

---

## CSS Conventions

- All colors through CSS custom properties only. Never hardcode hex/rgb values in component styles.
- All spacing through predefined values (`--radius-sm`, `--radius-md`, `--radius-full`, etc.).
- Dark/light themes toggled by `data-theme="dark|light"` on `<html>` element.
- Mobile overrides in `responsive.css`, not inline styles.
- Inline styles in HTML/JS are acceptable only for dynamic values that must be computed at runtime (e.g., progress bar widths, color interpolation).

---

## Import Rules

- No circular imports.
- `app.js` is the only file that imports from all other modules.
- `events-controller.js` may import from `ui.js` only the `recalculateAndRender` function (single allowed reverse-layer reference).
- CSS is linked directly in `index.html` — no CSS-in-JS.

---

## Testing Standards

- Engine tests use a custom `assert(label, condition)` harness with `console.log/error` output.
- Tests must pass with `node --experimental-vm-modules` for ESM support.
- All test files are co-located in `js/` prefixed with `test-`.
- New engine functions must have corresponding tests before being considered production-stable.
- The `acorn` parser is used to validate `ui.js` syntax after major edits (see `check_imports.js`).

---

## Do Not

- Do not use `var` — use `const` or `let`.
- Do not use `document.write()`.
- Do not use `eval()`.
- Do not use jQuery or any UI library.
- Do not add new CSS frameworks (no Tailwind, Bootstrap, etc.).
- Do not use `innerHTML` for untrusted user content (XSS risk).
- Do not import Firebase modular SDK — use compat SDK only (no bundler).
- Do not add build tools without explicit architectural approval.
