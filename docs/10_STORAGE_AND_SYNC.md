# 10 — Storage and Synchronization

**File**: `js/storage.js`  
**Lines**: 271  
**Status**: ✅ Complete, production-stable

---

## Purpose

The storage module owns:
1. The `AppState` singleton — the single in-memory state container.
2. `localStorage` persistence — local-first hydration and save.
3. Firestore cloud synchronization — debounced background sync.
4. Legacy V1 migration helpers.

---

## `AppState` — The Global State Singleton

```javascript
export const AppState = {
  profile: {},                   // { name, rollNumber, createdAt }
  attendance: {},                // { "YYYY-MM-DD:CODE:TYPE": "Attended|Missed" }
  laboratory: {},                // { "CODE": LabExperiment[] }
  history: [],                   // Reserved — not actively used
  settings: {
    theme: 'dark',
    simulationMode: false        // Currently unused — simulation is in dateContext
  },
  academicEvents: {},            // { "YYYY-MM-DD": AcademicEvent[] }
  isDirty: false                 // true if local > cloud
};
```

**Rules for `AppState`**:
- Never passed as a parameter to engine functions (engines have their own data loading paths).
- Never directly mutated by the UI layer (`ui.js` calls dedicated storage functions).
- Mutated by: `storage.js` internal functions, `events-controller.js` (for academic events), `ui.js:logExperiment()` (lab only — this should ideally be in a controller).

---

## localStorage Strategy

### Key Format

```
app_state_{uid}
```

Each Firebase Auth user gets their own key. This prevents data leakage between accounts on the same device.

### Hydration (`initLocalState(uid)`)

Called immediately after Firebase confirms the user is authenticated. Reads `localStorage`, parses JSON, and merges each sub-object into `AppState` with type guards (only merge if it's a plain object/array):

- `attendance`, `laboratory`, `settings`, `profile`, `academicEvents` are all safely merged.
- `history` is **not** hydrated from localStorage (no write path exists for it).

### Persistence (`persistLocalState(uid)`)

Calls `JSON.stringify(AppState)` and writes to localStorage. Called:
- After every cloud sync attempt.
- After every mutation via `saveStates()`, `saveLaboratoryStates()`, and `triggerCloudSync()`.

---

## Cloud Synchronization

### `triggerCloudSync(isResetting = false)`

Debounced (1000ms) function that uploads `AppState` to Firestore.

**Algorithm**:
1. Immediately calls `persistLocalState()` to secure local write first.
2. Clears any pending sync timeout.
3. After 1000ms, builds a `payload` object.
4. Payload construction guards:
   - **Profile**: Only included if `isProfileComplete(AppState.profile)`.
   - **Settings**: Only included if `isValidSettings(AppState.settings)`.
   - **Academic Events**: Only included if not empty OR if resetting.
   - **Laboratory**: Only included if not empty OR if resetting.
   - **Attendance**: Only included if not empty OR if resetting.
5. If payload is non-empty: `db.collection('students').doc(uid).set(payload, { merge: true })`.
6. Sets `AppState.isDirty = false`, calls `persistLocalState()` again.

### `fetchCloudStates()`

Called once after login (background, after first local render). Fetches the Firestore document and merges each field into `AppState` using `isPlainObject()` guards. Returns `true` if any state changed.

### `clearStates()`

Resets `laboratory`, `attendance`, and `academicEvents` to empty objects, then triggers cloud sync with `isResetting = true` to explicitly upload empty state. Used by "Reset All Data" in Profile.

---

## Firestore Collection: `feedback`

The feedback module (`js/feedback.js`) writes to a separate `feedback` collection with schema:

```javascript
{
  uid, name, rollNumber, category, message, version,
  platform: { browser, os, mobile },
  screen, createdAt, status: 'open'
}
```

This is a write-only collection for users (read, update, delete are denied by rules). An admin dashboard (not yet built) would read from this.

---

## Legacy Migration (V1 → V2)

The V1 app stored attendance under the key `attendance_tracker_states`. During Phase S1 (stabilization), the key was migrated to `app_state_{uid}`.

`getLocalAttendance()` and `clearLocalAttendance()` handle the migration:
- On login, if `attendance_tracker_states` exists in localStorage, the app shows a migration modal offering to import or discard.
- If imported: `saveStates(localData)` writes V1 data into V2 format.
- In either case: `clearLocalAttendance()` removes the old key.

This migration path should remain until at least mid-2027 to handle users who haven't logged in since V1.

---

## Public API

| Function | Description |
|---|---|
| `initLocalState(uid)` | Hydrate AppState from localStorage |
| `persistLocalState(uid)` | Save AppState to localStorage |
| `loadStates()` | Returns `AppState.attendance` |
| `saveStates(states)` | Updates attendance, persists, triggers cloud sync |
| `loadLaboratoryStates()` | Returns `AppState.laboratory` |
| `saveLaboratoryStates(labState)` | Serializes lab state, persists, triggers cloud sync |
| `clearStates()` | Resets all data to empty, triggers cloud sync with reset flag |
| `fetchCloudStates()` | Fetches Firestore doc and merges into AppState |
| `triggerCloudSync(isResetting?)` | Debounced upload to Firestore |
| `isProfileComplete(profile)` | Checks `name` and `rollNumber` are present |
| `getLocalAttendance()` | Legacy V1 data reader |
| `clearLocalAttendance()` | Legacy V1 data cleaner |

---

## Known Issues

1. **`firestore.rules` does not include `laboratory` or `academicEvents`**: The `isValidStudentDoc` function on line 48 only allows `['attendance', 'settings', 'profile']`. Writing `laboratory` or `academicEvents` to Firestore will fail validation with a "permission denied" error. **This is a critical production bug.**

2. **`AppState.history` is never populated**: The field exists in `AppState` but no write path creates history entries in it. The history displayed in the History tab is derived from `AppState.attendance` keys at render time, not from this field. The field should either be removed or properly implemented.

3. **No optimistic UI on sync failure**: If cloud sync fails, the local state remains accurate, but there is no visual indicator to the user. The error is only logged to console.

4. **No conflict resolution for simultaneous edits**: If two devices edit attendance simultaneously, the last cloud write wins. No merge strategy exists for conflicting attendance records.

5. **`AppState` is mutated by `events-controller.js` after `addAcademicEvent()`**: This creates a dual-write situation where both the Calendar Engine's `runtimeEvents` and `AppState.academicEvents` are updated separately. If either fails, they can go out of sync.
