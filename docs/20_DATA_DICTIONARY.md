# 20 — Data Dictionary

This document details every persistent data structure in the application, including its owner, lifecycle, and schema.

---

## The Global State: `AppState`

The root object representing the user's entire dataset. Kept in memory, persisted to `localStorage`, and synced to Firestore.

- **Owner**: `storage.js`
- **Persistence**: `localStorage` (key: `app_state_{uid}`), Firestore (collection: `students`, doc: `{uid}`)
- **Lifecycle**: Hydrated on login. Serialized to JSON on every mutation. Cleared on logout.

```javascript
{
  profile: ProfileData,
  settings: SettingsData,
  attendance: Record<String, String>,
  laboratory: Record<String, LabExperiment[]>,
  academicEvents: Record<String, AcademicEvent[]>,
  history: Array,  // Reserved, currently unused
  isDirty: boolean // In-memory only flag
}
```

---

## 1. Profile (`AppState.profile`)

Basic user identity information.

- **Type**: Object
- **Owner**: `auth.js`
- **Lifecycle**: Created during signup or the Profile Recovery modal. Never deleted unless account is deleted.

| Field | Type | Description |
|---|---|---|
| `name` | string | Full name of the student |
| `rollNumber` | string | 13-digit university roll number |
| `createdAt` | string | ISO timestamp of profile creation |

---

## 2. Settings (`AppState.settings`)

User preferences.

- **Type**: Object
- **Owner**: `ui.js` / Profile Tab
- **Lifecycle**: Created on signup with defaults. Updated via UI toggles.

| Field | Type | Description |
|---|---|---|
| `theme` | `'dark' | 'light'` | UI theme preference |
| `simulationMode` | boolean | Reserved (simulation state is currently managed in `dateContext`) |

---

## 3. Attendance Log (`AppState.attendance`)

The core tracking data for physical class attendance.

- **Type**: Map (Key-Value pairs)
- **Owner**: `ui.js` (via `logClassState`)
- **Lifecycle**: Created when a user clicks an attendance button. Overwritten if clicked again. Deleted if toggled to "Pending" (key removed).

**Key Format**: `YYYY-MM-DD:SUBJECT_CODE:CLASS_TYPE`
- Example: `"2026-08-10:KCS-501:L"`

**Value**: `'Attended' | 'Missed'`

*Note: For practicals, the key uses the specific slot (e.g., `P1` or `P2`).*

---

## 4. Laboratory (`AppState.laboratory`)

Progress tracking for lab experiments.

- **Type**: Dictionary mapping Subject Code to an Array of Experiments.
- **Owner**: `laboratory-engine.js` (via `logExperiment`)
- **Lifecycle**: Created via the Laboratory Dashboard UI.

```javascript
{
  "BCS-551": [
    {
      experimentNumber: 1, // 1 to 10
      title: "SQL Basics", // Optional string
      dateConducted: "2026-08-15", // YYYY-MM-DD
      signatureStatus: "pending", // 'pending' | 'signed'
      signedOn: null, // YYYY-MM-DD | null
      marks: null, // number | null
      remarks: null // string | null
    }
  ]
}
```

---

## 5. Academic Events (`AppState.academicEvents`)

Runtime event data that modifies the academic calendar.

- **Type**: Dictionary mapping Date to an Array of Events.
- **Owner**: `events-controller.js`
- **Lifecycle**: Created via Event Form. Soft-deleted via `archived` flag.

```javascript
{
  "2026-08-15": [
    {
      id: "evt_3a8b2_1785943", // Unique ID
      version: 1, // Incremented on update
      eventType: "EXTRA_LECTURE", // From AcademicEventRegistry
      subjectCode: "KCS-501", // Or null for global events
      classType: "L", // Or null
      effectiveDate: "2026-08-15", // YYYY-MM-DD
      metadata: {}, 
      createdAt: "2026-08-14T10:00:00.000Z",
      source: "USER",
      active: true, // Disabled if false
      archived: false, // Soft-deleted if true
      history: [
        { action: "Created", timestamp: "...", user: "uid" }
      ]
    }
  ]
}
```

---

## 6. Feedback Submissions (Firestore only)

User-submitted feedback forms.

- **Type**: Firestore Document
- **Owner**: `feedback.js`
- **Persistence**: Firestore `feedback` collection (no local storage).
- **Lifecycle**: Written once. Never read by the client application.

```javascript
{
  uid: "firebase_auth_uid",
  name: "Student Name",
  rollNumber: "1234567890123",
  category: "bug" | "feature" | "general",
  message: "Text...",
  version: "2.0.2",
  platform: {
    browser: "Chrome",
    os: "Windows",
    mobile: false
  },
  screen: { width: 1920, height: 1080 },
  createdAt: "2026-08-06T12:00:00Z",
  status: "open"
}
```

---

## 7. SubjectStats Aggregate (`computeSubjectStats` return value)

Computed per-subject aggregate produced by `attendance-engine.js` and consumed by all downstream engines and the UI. This is **not** persisted — it is recomputed on every render from `AppState.attendance`.

- **Producer**: `attendance-engine.js → computeSubjectStats()`
- **Consumers**: `ui.js`, `quiz-engine.js`, `laboratory-engine.js`

| Field | Type | Description |
|---|---|---|
| `code` | string | Subject code |
| `name` | string | Subject display name |
| `tag` | string\|null | Optional tag |
| `totL` | number | Total scheduled lectures |
| `totT` | number | Total scheduled tutorials |
| `totP` | number | Total scheduled practicals (P1+P2 normalized to P) — *added S3.4* |
| `totComb` | number | `totL + totT` |
| `attL_done` | number | Attended lectures |
| `missL_done` | number | Missed lectures |
| `attT_done` | number | Attended tutorials |
| `missT_done` | number | Missed tutorials |
| `attP_done` | number | Attended practicals — *added S3.4* |
| `missP_done` | number | Missed practicals — *added S3.4* |
| `pendingL` | number | Future/unlogged lectures |
| `pendingT` | number | Future/unlogged tutorials |
| `pendingP` | number | Future/unlogged practicals — *added S3.4* |
| `completedL` | number | `attL_done + missL_done` |
| `completedT` | number | `attT_done + missT_done` |
| `completedP` | number | `attP_done + missP_done` — *added S3.4* |
| `currentLecPct` | number\|null | Current lecture % (over completed only) |
| `currentTutPct` | number\|null | Current tutorial % |
| `currentAvgPct` | number\|null | Weighted average |
| `forecastLecPct` | number\|null | Best-case forecast % |
| `forecastTutPct` | number\|null | Best-case forecast % |
| `forecastAvgPct` | number\|null | Best-case average |
| `optResult` | OptimizationResult | Optimization result for target % |

> [!IMPORTANT]
> **Laboratory engine contract**: `laboratory-engine.js` reads `totP`, `attP_done`, and `pendingP` from this aggregate. These fields are **required** and always present as of S3.4. Prior to S3.4, they were missing (DEBT-003), causing permanent 0% laboratory attendance.

---

## 8. Academic Event Ownership Model (S3.4)

```
AppState.academicEvents   ← sole persistent authority
        │
        │  events-controller.js (processEventMutation)
        │  pipeline: validate → normalize → mutate → persist → sync → render
        ▼
Calendar Engine runtimeEvents  ← derived runtime state (never independently persisted)
        │
        ▼
Calendar / Attendance calculations
```

**Key invariants** (enforced as of S3.4):
- `AppState.academicEvents` is the **only** place academic events are stored persistently.
- `runtimeEvents` (Calendar Engine internal) is populated exclusively via `syncRuntimeEvents(AppState.academicEvents)`.
- `Calendar Engine` does not mutate `AppState.academicEvents` (no circular dependencies).
- All mutations are atomic: a pre-mutation snapshot allows full rollback if `persistLocalState` fails.
- After cloud hydration via `fetchCloudStates()`, `syncRuntimeEvents` is immediately re-called to keep the Calendar Engine current.
