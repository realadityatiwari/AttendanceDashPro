# Authentication Regression Recovery (S4.4 Post-mortem)

## 1. Symptom
After completing S4.4, hard-refreshing the application or opening the deployed site caused the user to be stuck on the Login screen. Clicking "Login securely" or "Create an account" did absolutely nothing.

## 2. Reproduction
Running a local `npx serve . -p 8080`, performing a hard refresh, and clicking the authentication buttons reproduced the issue.

## 3. Root Cause
The root cause was a Module Graph failure caused by an invalid import.
In S4.4, the new `js/daily-attendance.js` module contained the following line:
`import { getTodayString, isSimulationMode } from './dateContext.js';`

However, `getTodayString` is actually exported from `calendar-engine.js`, not `dateContext.js`. This invalid import caused a silent module parsing failure in the browser. 

## 4. Evidence
Because `app.js` imports `ui.js`, and `ui.js` imports `daily-attendance.js`, the failure in `daily-attendance.js` cascaded and prevented `app.js` from ever executing.
- `initDOMBindings()` was never called, meaning the Login and Signup buttons had no click listeners attached.
- `auth.onAuthStateChanged()` was never registered, meaning the app never knew the user was already logged in, forcing the Login screen to remain visible.

## 5. Regression Source
Phase S4.4 (Daily Attendance Experience module separation).

## 6. Fix
Corrected the import in `js/daily-attendance.js`:
- Removed `getTodayString` from the `dateContext.js` import.
- Added `getTodayString` to the `calendar-engine.js` import.
- Bumped the app version to `v=4` in `index.html` to force cache invalidation for all service workers and browsers.

## 7. Cache/Deployment Implications
The module failure triggered upon hard-refresh or fresh deploy because the browser attempted to parse the new `daily-attendance.js` file. The local browser subagent initially did not catch this because its session still retained the cached `ui.js` module graph from before S4.4 concluded. Bumping `v=4` ensures the fix propagates immediately.

## 8. Tests
Run automated tests across the engine:
- `test-attendance-engine.js`
- `test-calendar-engine.js`
- `test-calendar-window.js`
- `test-persistence-sync.js`
- `test-events-controller.js`
**Result:** 100% Passing (0 failures).

## 9. Browser Verification
A strict, focused UI browser verification was performed:
1. Fresh load + Hard refresh -> Login form appears correctly.
2. Login with empty fields -> UI validation error shown.
3. Login ↔ Signup form toggles -> Works perfectly.
4. Valid login -> Dashboard loads successfully.
5. Logout -> Login screen reappears.
6. Refresh -> User stays logged out.
7. Re-login -> Dashboard loads again.

## 10. Remaining Limitations
None regarding authentication. S4.5 is now safe to resume.
