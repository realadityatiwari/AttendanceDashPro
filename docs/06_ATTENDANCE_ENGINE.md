# 06 — Attendance Engine

**File**: `js/attendance-engine.js`  
**Lines**: 709  
**Status**: ✅ Complete, production-stable

---

## Purpose

The Attendance Engine is the **single source of truth for all attendance mathematics**. It owns the computation of:
- Class counts per subject per type (L, T, P)
- Current attendance percentages (based on completed classes only)
- Forecast percentages (assuming all pending classes are attended)
- Minimum-attendance optimization (how many more classes must be attended)
- Safe skip calculation (how many remaining classes can be skipped)
- Overall/ERP-style aggregate statistics across all subjects

No other module performs attendance calculations. The Quiz Engine delegates to this module. The UI reads from this module's outputs.

---

## Why It Exists As a Separate Engine

Prior to Phase A2.4, attendance math was partially duplicated in the Quiz Engine. This meant changing the 75% threshold required updates in two places, and the two implementations could drift. The Quiz Engine was refactored to be a pure academic rules engine that receives `OptimizationResult` objects from this module instead of recalculating.

---

## Core Algorithm: The Optimizer

The eligibility formula for AKTU/SRMCEM is:

```
Eligibility = (Lecture% + Tutorial%) / 2 >= 75%
Where:
  Lecture%  = attended_lectures / total_lectures × 100
  Tutorial% = attended_tutorials / total_tutorials × 100
```

Subjects with no tutorials are evaluated on lecture percentage alone.

### `optimize(totL, totT, targetPercentage)` — Static Optimizer

Used for pre-computed reference data. Finds the minimum (attL, attT) combination such that the above formula is satisfied:

```javascript
// O(totL × totT) exhaustive search
for (let attL = 0; attL <= totL; attL++) {
  for (let attT = 0; attT <= totT; attT++) {
    if (!meetsAttendanceTarget(attL, totL, attT, totT, target)) continue;
    if (total < bestTotal || (total === bestTotal && attL < bestAttL)) {
      bestTotal = total; bestAttL = attL; bestAttT = attT;
    }
  }
}
```

**Tie-breaking rule**: When multiple (attL, attT) combinations achieve the same minimum total, the combination with **fewest lectures attended** (maximum lecture skips) is preferred. This is mathematically correct because lectures and tutorials are weighted equally in the average.

### `optimizeLive(...)` — Live Optimizer

Same algorithm but accounts for already-attended, missed, and pending classes. Returns:
- `lectureDeficit` — how many MORE pending lectures must be attended
- `tutorialDeficit` — how many MORE pending tutorials must be attended
- `safeSkipLecture` — how many remaining lectures can be safely skipped
- `safeSkipTutorial` — how many remaining tutorials can be safely skipped
- `reachable` — false if even attending all pending classes is insufficient

---

## Domain Models

### `OptimizationResult`

```javascript
class OptimizationResult {
  targetPercentage    // The threshold applied (e.g. 75)
  reachable           // boolean — can target still be achieved?
  lectureDeficit      // Must-attend count for lectures
  tutorialDeficit     // Must-attend count for tutorials
  safeSkipLecture     // Safe skip count for lectures
  safeSkipTutorial    // Safe skip count for tutorials
  lecturePercentage   // Projected lecture % if deficits are met
  tutorialPercentage  // Projected tutorial % if deficits are met
  averagePercentage   // Projected average % if deficits are met
}
```

### Subject Stats Object (output of `computeSubjectStats`)

```javascript
{
  code, name, tag,           // Subject identity
  totL, totT, totComb,       // Total scheduled classes (lecture, tutorial, combined)
  attL_done, missL_done,     // Attended/missed lectures
  attT_done, missT_done,     // Attended/missed tutorials
  pendingL, pendingT,        // Pending (unlogged or future) classes
  completedL, completedT,    // att_done + miss_done per type
  currentLecPct,             // Lecture % based on completed only (null if none)
  currentTutPct,             // Tutorial % based on completed only
  currentAvgPct,             // Average of current percentages
  forecastLecPct,            // Lecture % assuming all pending attended
  forecastTutPct,            // Tutorial % assuming all pending attended
  forecastAvgPct,            // Average of forecast percentages
  optResult                  // OptimizationResult for 75% target
}
```

---

## Public API

### Percentage Calculators

- `calcCurrentPct(attended, completed)` — `attended/completed * 100`. Returns `null` if no completed classes.
- `calcForecastPct(attended, pending, total)` — `(attended+pending)/total * 100`. Best-case.
- `calcAvgPct(lecPct, tutPct)` — Weighted average. Handles single-type subjects (null safety).
- `meetsAttendanceTarget(attL, totL, attT, totT, target)` — Fraction-based comparison (avoids rounding errors).

### Optimizers

- `optimize(totL, totT, targetPercentage)` — Static reference optimizer.
- `optimizeLive(totL, totT, attL_done, missL_done, attT_done, missT_done, pendingL, pendingT, targetPercentage)` — Live optimizer for dashboard.
- `getSubjectQuizOptimization(subjectCode, quizCycle, states, targetPercentage)` — Called exclusively by Quiz Engine. Computes optimization within the quiz attendance window.

### Data Loaders

- `getAttendanceData(quizDate, states)` — Core data loader. Iterates all subjects, all teaching days in their windows, applies timetable schedule, applies event deltas. Returns raw count map.
- `computeSubjectStats(code, name, tag, rawData)` — Composes full subject stats from raw counts.
- `assertConsistency(code, data)` — Internal invariant checker. Logs errors if `att + miss + pending ≠ total`.

### Aggregate Statistics

- `computeOverallStats(subjectStats)` — Totals across all subjects for the summary card.
- `computeCurrentOverallAttendance(rawData, subjects)` — ERP-style: `Σattended / Σconducted × 100`.
- `computeForecastOverallAttendance(rawData, subjects)` — ERP-style forecast: pending treated as attended.

### Tooltip Engine

- `calcForecastImpact(rawData, subjectCode, classType, currentState, newAction)` — Calculates the forecast % change from toggling a single class. Used for hover tooltips showing "if you attend this: X%" impact.

---

## How `getAttendanceData` Works

This is the most important function in the engine. For each subject:

1. Calls `getQuizWindow(code, quizCycle)` from Calendar Engine to get the effective teaching dates.
2. Iterates each teaching date.
3. Calls `getAcademicDay(dateStr)` to check for schedule substitutions.
4. Calls `getMergedDaySchedule(monIdx)` to get the timetable for that day.
5. For each class slot matching this subject: increments `tot`, reads class state from `states`, increments `att_done`, `miss_done`, or `pending`.
6. Calls `getSubjectEventDeltas(dateStr, code, t)` for extra/cancelled classes and adjusts counts.

The `states` object is `getEffectiveStates()` from `dateContext.js`, which transparently handles simulation overlay.

---

## Raw Count Structure (Internal)

```javascript
data[subjectCode] = {
  counts: {
    L: { tot: 0, att_done: 0, miss_done: 0, pending: 0 },
    T: { tot: 0, att_done: 0, miss_done: 0, pending: 0 },
    P: { tot: 0, att_done: 0, miss_done: 0, pending: 0 }
  }
}
```

P1 and P2 timetable slots are both merged into the `P` bucket via `normalizeClassType()`. Only the `P1` slot key is stored in `attendance` (see `logAttendance` in `ui.js`).

---

## Known Limitations

1. **O(totL × totT) optimizer**: Acceptable for current class counts (~30–40 classes per window). Would need optimization for very large windows.
2. **`getAttendanceData` recalculates from scratch every call**: No memoization. With 9 subjects × ~50 teaching days, this is fast enough for now but could become a bottleneck with many subjects.
3. **`calcForecastImpact` only handles L/T transitions**: Practical (P) class impacts are not computed in the tooltip engine.
4. **Hardcoded `75`** in `computeSubjectStats` line 458: The dashboard uses 75% as the optimization target. This should come from `getQuizPolicy(currentQuizCycle).targetPercentage`.

---

## Extension Points

- To add a new class type to attendance tracking: add it to `CLASS_TYPES` in `utils.js` with `supportsAttendance: true`.
- To change the eligibility formula: modify `meetsAttendanceTarget()` and `calcAvgPct()`.
- To change optimization tie-breaking: modify the comparison in `optimize()` and `optimizeLive()`.
