# 07 — Quiz Engine

**File**: `js/quiz-engine.js`  
**Lines**: 134  
**Status**: ✅ Complete, production-stable

---

## Purpose

The Quiz Engine is a **pure academic rules engine**. Its only job is to evaluate whether a student meets the attendance requirement to be eligible for a given quiz cycle, for each subject. It does **not** calculate attendance. It delegates all attendance math to the Attendance Engine and uses the result to evaluate rules.

---

## Why It Exists As a Separate Engine

Before Phase A2.4, the Quiz Engine duplicated attendance calculations. This was eliminated. The Quiz Engine now:
- Receives a `states` map from storage.
- Calls the Attendance Engine for optimization results.
- Applies the quiz policy (target percentage) from the Calendar Engine.
- Returns a structured `QuizEligibilityResult`.

The UI reads `QuizDashboardModel` objects. The UI never calls the Attendance Engine directly for quiz purposes.

---

## Domain Models

### `QuizEligibilityResult`

```javascript
class QuizEligibilityResult {
  applicable         // boolean — false if subject is not quiz-applicable (e.g. labs)
  eligible           // boolean|null — true if currently meets threshold
  requiredPercentage // number — the threshold applied (from quiz policy)
  policyId           // string — e.g. 'quiz1', 'quiz2'
  optResult          // OptimizationResult — the full optimization from Attendance Engine
}
```

The `optResult` field is crucial — the UI uses it to show "must attend X more lectures" information. This is NOT recalculated in the UI; it comes directly from the Attendance Engine via this object.

### `QuizDashboardModel`

```javascript
class QuizDashboardModel {
  summary: {
    totalSubjects,
    quizApplicable,  // Subjects where quiz attendance applies
    eligible,        // Subjects currently meeting threshold
    needsAttendance, // Subjects not yet meeting threshold
    notApplicable,   // e.g. lab subjects
    requiredAverage  // Policy target for this quiz cycle
  },
  subjects: [{
    subject: SubjectMeta,        // From timetable.json
    eligibility: QuizEligibilityResult
  }]
}
```

---

## Public API

### `computeQuizEligibility(subjectMeta, states, quizCycle)`

Single-subject eligibility evaluation:

1. If `subjectMeta.quizApplicable === false` → return `QuizEligibilityResult({ applicable: false })`.
2. Call `getQuizPolicy(quizCycle)` to get `targetPercentage`.
3. Call `getSubjectQuizOptimization(subjectMeta.code, quizCycle, states, targetPercentage)` from Attendance Engine.
4. `eligible = optResult.reachable && optResult.lectureDeficit === 0 && optResult.tutorialDeficit === 0`.
5. Return `QuizEligibilityResult` with all fields populated.

**Eligibility definition**: A student is eligible if the optimizer confirms that (a) the target is reachable with remaining classes, AND (b) no additional classes need to be attended to meet the threshold right now (deficit is zero).

### `computeQuizDashboard(states, quizCycle, timetable)`

Full dashboard model generation:

1. Reads `getQuizPolicy(quizCycle)` for the summary's `requiredAverage`.
2. Iterates every subject in `timetable.subjects` (maintains order).
3. Calls `computeQuizEligibility()` for each.
4. Aggregates summary counters.
5. Returns `QuizDashboardModel`.

---

## Policy Resolution

Quiz policies come from the Calendar Engine (`getQuizPolicy`):

```javascript
quiz1: { targetPercentage: 70 },
quiz2: { targetPercentage: 75 },
quiz3: { targetPercentage: 75 },
default: { targetPercentage: 70 }
```

If a specific quiz cycle policy isn't found, it falls back to `default`. If `default` isn't found, it returns `70` as a hardcoded fallback.

---

## Known Limitations

1. **No surprise quiz handling yet**: The `SURPRISE_QUIZ` event type exists in the Academic Event Registry but the Quiz Engine does not yet evaluate surprise quiz attendance separately.
2. **Quiz eligibility definition is binary**: Currently "eligible" or "not eligible." Future versions may want a "warning" state (e.g., reachable but risky).
3. **`quizCycle` is derived from `quizDate` index in `getAttendanceData`**: This is a legacy dependency that should be eliminated in favor of direct subject timeline queries.

---

## Extension Points

- To add new eligibility criteria: add logic in `computeQuizEligibility()` after the optimizer call.
- To add surprise quiz scoring: introduce a new result field in `QuizEligibilityResult`.
- To add per-subject quiz policies: extend the `policies` configuration and update `getQuizPolicy()` to accept a subject code.
