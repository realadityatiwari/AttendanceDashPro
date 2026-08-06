# 14 — Testing and QA

## Testing Philosophy

AttendanceDash Pro uses a layered testing strategy:

| Layer | Tool | What It Tests |
|---|---|---|
| Engine unit tests | Custom Node.js harness (ESM) | Calendar Engine, Attendance Engine logic |
| Syntax validation | `acorn` AST parser | `ui.js` module parse integrity |
| Import validation | `check_imports.js` | Case-sensitive imports (catches Vercel 404s) |
| Browser integration | Puppeteer | Full application flow in headless Chrome |
| Manual QA | Browser dev tools | UI rendering, responsiveness, PWA behavior |

---

## Engine Unit Tests

### `js/test-calendar-engine.js`

Tests the Calendar Engine in isolation.

**Execution**:
```bash
node --experimental-vm-modules js/test-calendar-engine.js
```

**Note**: This will fail with a Firebase error if `firebase.js` is imported transitively. The test file imports from `calendar-engine.js` only, which has no Firebase dependency. Tests should pass cleanly.

**Coverage**:
- `getAcademicDay()` with public holidays, working Saturdays, emergency closures.
- `getPreviousWorkingDay()`, `getNextWorkingDay()`.
- `getTeachingDaysBetween()` with various event overlaps.
- `getAttendanceWindow()` with subject-specific milestones.
- `addAcademicEvent()`, `archiveAcademicEvent()`, `syncRuntimeEvents()`.
- Event priority resolution conflicts.
- Validation rejection tests (`expectThrow`).

### `js/test-attendance-engine.js`

Tests the Attendance Engine optimizer.

**Execution**:
```bash
node --experimental-vm-modules js/test-attendance-engine.js
```

**Coverage**:
- `optimize()` with L-only, T-only, and L+T combinations.
- `optimizeLive()` with various pending/done class distributions.
- `meetsAttendanceTarget()` fraction comparison accuracy.
- Tie-breaking rule (fewest lectures preferred).
- Edge cases: 0 total classes, 100% attended, impossible targets.

### `js/test-calendar-window.js`

Integration test combining Calendar Engine and Attendance Engine.

**Execution**:
```bash
node --experimental-vm-modules js/test-calendar-window.js
```

**Coverage**:
- Attendance window boundaries with subject-specific timelines.
- Mixed timeline validation (custom + global fallback subjects).
- Laboratory subject timeline compatibility.
- Cross-semester window computation.

---

## Syntax Validation

The `ui.js` file is the largest file (1468 lines) and is edited frequently. After significant changes, validate the AST:

```bash
node -e "
const fs = require('fs');
const acorn = require('acorn');
const src = fs.readFileSync('./js/ui.js', 'utf8');
try { acorn.parse(src, { ecmaVersion: 2022, sourceType: 'module' }); console.log('✅ Syntax OK'); }
catch(e) { console.error('❌', e.message, 'at line', e.loc?.line); process.exit(1); }
"
```

**When to run**: After any edit to `ui.js` that modifies template literals or adds/removes closing braces.

---

## Import Validation (`check_imports.js`)

This script validates that all import paths in JavaScript files use the exact file case (important for Linux/Vercel which are case-sensitive):

```bash
node check_imports.js
```

**When to run**: Before deploying to Vercel or any Linux-based host.

---

## Browser Integration Tests

### Puppeteer Test (`run-puppeteer.js`)

Headless Chrome browser test:

```bash
node run-puppeteer.js
```

Tests:
- Page load without console errors.
- Login flow (requires valid test credentials in `.env` or hardcoded).
- Dashboard renders subject data.
- Attendance logging button functionality.
- Quiz tab switching.

**Known issue**: Puppeteer tests require a running local server. Start `npx serve . -p 8080` first.

### Proof Script (`run-proof.js`)

Quick smoke test for a specific feature or regression fix:

```bash
node run-proof.js
```

---

## Manual QA Checklist

### Before Any Major Release

- [ ] Login flow works (both roll number + password).
- [ ] Signup flow works (validation errors shown correctly).
- [ ] Profile recovery modal shows when profile is incomplete.
- [ ] Dashboard shows correct subject data for today.
- [ ] All quiz tabs show correct counts.
- [ ] Attendance logging (Attended/Missed/Pending) persists across refresh.
- [ ] Cloud sync occurs (check Firestore in Firebase Console).
- [ ] Theme toggle (dark/light) persists across refresh.
- [ ] Date navigator works (Yesterday/Today/Tomorrow + custom date).
- [ ] Simulation mode activates for future dates, does not persist.
- [ ] Lab dashboard renders for lab subjects.
- [ ] Lab experiment logging persists.
- [ ] Academic Event creation works (all event types).
- [ ] Academic Event toggle (enable/disable) updates attendance calculation.
- [ ] Academic Event archive moves event out of active list.
- [ ] Events view correctly shows active vs. archived tabs.
- [ ] Offline banner appears when network disconnected.
- [ ] App installs as PWA on Android Chrome.
- [ ] Installed PWA has no browser chrome (standalone mode).
- [ ] All views render correctly on iPhone-sized viewport (375px).
- [ ] All views render correctly on desktop (1280px).
- [ ] Logout clears auth state, shows auth screen.

---

## Regression Baseline

The `regression_report.md` file documents the Phase S1.10 regression event:
- Root cause: duplicate `const labSectionHTML` declaration + unclosed template literal in `ui.js`.
- Impact: complete JS parse failure, login button non-functional after hard refresh.
- Fix: removed duplicate declaration, fixed malformed template literal.

**Lessons learned**:
1. Always validate `ui.js` AST after template literal edits.
2. Always test with hard refresh (bypassing service worker cache) after service worker changes.
3. Mobile Subjects tab and Dashboard tab have separate injection targets — verify both after rendering changes.

---

## Known Test Infrastructure Limitations

1. **Firebase global not available in Node.js**: `firebase.js` uses the global `firebase` object loaded by CDN script tags. In Node.js tests, this global doesn't exist. Engine tests that don't transitively import `firebase.js` work fine. Tests for `storage.js` or `auth.js` require mocking `firebase`.

2. **Service worker interferes with live-reload**: When testing locally with the service worker active, cached responses may be served instead of updated files. Use `?v=X` cache busting or disable service worker in Chrome DevTools.

3. **Puppeteer tests require Firebase credentials**: Login tests require a real Firebase project. Credentials should be stored in `.env` and not committed to git. Currently they may be hardcoded in test scripts — this should be fixed.

4. **No CI/CD pipeline**: Tests are run manually. There is no automated test run on git push. This should be set up eventually.
