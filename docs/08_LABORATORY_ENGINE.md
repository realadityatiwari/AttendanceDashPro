# 08 — Laboratory Engine

**File**: `js/laboratory-engine.js`  
**Lines**: 216  
**Status**: ✅ Complete, basic feature set stable

---

## Purpose

The Laboratory Engine manages practical session tracking independently from the regular attendance system. Laboratory subjects (category: `'lab'` in `timetable.json`) have 10 experiments over the semester, tracked differently from theory classes:

- Physical attendance is tracked via the regular Attendance Engine (using the `P` class type).
- Experiment completion requires both: the practical being attended **AND** the teacher's signature obtained.
- Milestones trigger at 5 and 10 completed experiments.

---

## Why It Is a Separate Engine

Lab tracking has domain-specific rules (experiment numbers, signatures, milestones, signature status) that are conceptually distinct from the percentage-based attendance system. Separating it allows lab features to evolve independently.

---

## Domain Models

### `LabExperiment`

```javascript
class LabExperiment {
  // Persistent fields (saved to AppState.laboratory)
  experimentNumber    // 1–10
  title               // string|null — experiment title (optional)
  dateConducted       // YYYY-MM-DD|null — when lab session was held
  signatureStatus     // 'pending' | 'signed'
  signedOn            // YYYY-MM-DD|null — when teacher signed
  marks               // number|null — marks obtained
  remarks             // string|null

  // Derived fields (computed by engine, never persisted)
  attendanceStatus    // 'Attended' | 'Missed' | null (from physical attendance state)
  isCompleted         // true if signed AND Attended
}
```

**Completion rule**: An experiment is `isCompleted = (signatureStatus === 'signed' && attendanceStatus === 'Attended')`. Both conditions must be true simultaneously.

### `LaboratorySubjectModel`

```javascript
class LaboratorySubjectModel {
  subject               // SubjectMeta from timetable
  experiments           // LabExperiment[10] — always 10, pre-filled with empty
  completedExperiments  // Count of isCompleted === true
  pendingExperiments    // Count of dateConducted set but not completed
  remainingExperiments  // 10 - (completed + pending)
  currentExperiment     // Next experiment number to work on
  attendancePercentage  // From subjectStatsArray (if available)
  progressPercentage    // completedExperiments / 10 × 100
  activeMilestones      // Milestones reached (triggerAfter <= completedExperiments)
  nextMilestone         // Next upcoming milestone with remainingRequired count
}
```

### `LaboratoryDashboardModel`

```javascript
class LaboratoryDashboardModel {
  summary: {
    totalLabSubjects,
    totalCompletedExperiments,
    milestonesReached
  },
  subjects: LaboratorySubjectModel[]
}
```

---

## Rules Configuration (`LAB_RULES`)

```javascript
export const LAB_RULES = {
  default: {
    totalExperiments: 10,
    milestones: [
      { id: 'mid',   triggerAfter: 5,  label: 'Mid Practical Examination' },
      { id: 'final', triggerAfter: 10, label: 'Final Practical Completed' }
    ],
    signatureRequired: true,
    attendanceRequiredPerExperiment: 1,
    periodsPerLabSession: 2,
    grading: {
      enabled: false,
      maxMarksPerExperiment: 10,
      vivaEnabled: false
    }
  }
};
```

This is the single configurable source for lab rules. No experiment counts, milestone triggers, or grading rules should be hardcoded elsewhere.

---

## Public API

### `computeLaboratoryDashboard(rawLabState, rawAttendanceState, subjectStatsArray, timetable)`

Main entry point. Called from `recalculateAndRender()` in `ui.js`.

**Parameters**:
- `rawLabState` — `AppState.laboratory` (raw experiment data keyed by subject code)
- `rawAttendanceState` — The raw attendance state map (`AppState.attendance`)
- `subjectStatsArray` — Pre-computed subject stats from Attendance Engine (for attendance %)
- `timetable` — Full timetable object (to iterate lab subjects)

**Process**:
1. Filters subjects where `category === 'lab'`.
2. For each lab subject, rehydrates raw experiments from `AppState.laboratory`.
3. Checks physical attendance via `rawAttendanceState["YYYY-MM-DD:CODE:P"]`.
4. Determines `isCompleted` per experiment.
5. Evaluates milestones.
6. Returns `LaboratoryDashboardModel`.

---

## How Physical Attendance Connects

Lab attendance is stored in the regular `AppState.attendance` map using the practical class key:

```
"2026-08-05:BCS-551:P1" → "Attended"
"2026-08-05:BCS-551:P2" → "Attended"  (both P1 and P2 slots)
```

The Laboratory Engine looks up `"YYYY-MM-DD:CODE:P"` (normalized) from `rawAttendanceState`. This means a student must log their practical attendance normally first, and then the lab dashboard will reflect it.

---

## Storage Format

`AppState.laboratory` is serialized as:

```javascript
{
  "BCS-551": [
    {
      experimentNumber: 1,
      title: "Introduction to SQL",
      dateConducted: "2026-08-05",
      signatureStatus: "signed",
      signedOn: "2026-08-07",
      marks: null,
      remarks: null
    }
  ]
}
```

Only the fields listed in `saveLaboratoryStates()` in `storage.js` are persisted — derived fields (`attendanceStatus`, `isCompleted`) are re-computed on every load.

---

## Known Limitations

1. **Grading is not implemented** (`LAB_RULES.default.grading.enabled = false`). The data model supports marks but no UI exists to input them.
2. **Viva tracking is not implemented**.
3. **Lab attendance lookup uses only `P` (not `P1`/`P2` individually)**: The engine looks up `"DATE:CODE:P"` but the actual log entries are `P1`/`P2`. The lookup should use `P1` since that's what `logAttendance` stores.
4. **`subjectStatsArray` attendance percentage**: References `stats.totP`, `stats.attP_done`, `stats.pendingP` which don't exist in the current `computeSubjectStats` output. This is a bug — the stats object uses `totL`, `totT` etc., not `totP`.

---

## Extension Points

- To add grading: enable `LAB_RULES.default.grading.enabled` and add a `marks` input to the lab UI.
- To change experiment count: change `LAB_RULES.default.totalExperiments`.
- To add milestones: add entries to `LAB_RULES.default.milestones`.
- To add per-subject rules: support subject-specific keys in `LAB_RULES` (e.g., `LAB_RULES['BCS-551']`).
