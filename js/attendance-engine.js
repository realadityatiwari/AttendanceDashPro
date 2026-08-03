import { getTimetable, parseDateString, isScheduledClass, getLocalDateString, CLASS_TYPES, normalizeClassType } from './utils.js';

const TARGET_ATTENDANCE = 0.75;

export function calcCurrentPct(attended, completed) {
  if (!completed || completed <= 0) return null;
  return (attended / completed) * 100;
}

/**
 * Forecast attendance % = (attended + all_pending) / total.
 * Assumes ALL pending classes will be attended — best-case from here.
 * Returns null if total is 0.
 */
export function calcForecastPct(attended, pending, total) {
  if (!total || total <= 0) return null;
  return ((attended + pending) / total) * 100;
}

/**
 * Average of lec% and tut% following the eligibility formula.
 * If tutPct is null (no tutorials for this subject), returns lecPct.
 * If lecPct is null, returns tutPct. If both null, returns null.
 */
export function calcAvgPct(lecPct, tutPct) {
  if (lecPct === null && tutPct === null) return null;
  if (tutPct === null) return lecPct;
  if (lecPct === null) return tutPct;
  return (lecPct + tutPct) / 2;
}

/**
 * Check the eligibility rule using fractions, avoiding rounding errors at 75%.
 * A subject with only one class type is evaluated using that available type.
 */
export function meetsAttendanceTarget(attL, totL, attT, totT) {
  const lecRatio = totL > 0 ? attL / totL : null;
  const tutRatio = totT > 0 ? attT / totT : null;
  if (lecRatio === null && tutRatio === null) return false;
  const average = lecRatio === null ? tutRatio : tutRatio === null ? lecRatio : (lecRatio + tutRatio) / 2;
  return average + Number.EPSILON >= TARGET_ATTENDANCE;
}

/**
 * Determine status badge from forecast average.
 * Status is ALWAYS based on forecast, never current.
 * N/A (no data) uses neutral class.
 */
export function getSubjectStatus(forecastAvgPct) {
  if (forecastAvgPct === null) return {text: 'N/A',      cls: 'status-warning'};
  if (forecastAvgPct >= 80)    return {text: 'SAFE',     cls: 'status-safe'};
  if (forecastAvgPct >= 75)    return {text: 'WARNING',  cls: 'status-warning'};
  return                              {text: 'CRITICAL', cls: 'status-critical'};
}

/** Color for a percentage value (green ≥75, amber ≥60, red otherwise). */
export function pctColor(pct) {
  if (pct === null) return 'var(--text3)';
  if (pct >= 75)    return 'var(--green)';
  if (pct >= 60)    return 'var(--amber)';
  return 'var(--red)';
}

/** Bar fill color — same thresholds as pctColor. */
export function barColor(pct) {
  return pctColor(pct);
}

/** Dim background color for average cell highlight. */
export function dimColor(pct) {
  if (pct === null) return 'transparent';
  if (pct >= 75)    return 'var(--green-dim)';
  if (pct >= 60)    return 'var(--amber-dim)';
  return 'var(--red-dim)';
}

/* ═══════════════════════════════════════════════════════════════════════
   OPTIMIZATION ENGINE
   Finds minimum classes to attend to achieve (Lec% + Tut%)/2 ≥ 75%.
═══════════════════════════════════════════════════════════════════════ */

/**
 * Static optimizer — used for pre-computed ALL_DATA reference (no live state).
 * Returns: {attL, attT, skipL, skipT, lecPct, tutPct, avgPct}
 */
export function optimize(totL, totT) {
  if (totL <= 0 && totT <= 0) {
    return {attL: 0, attT: 0, skipL: 0, skipT: 0, lecPct: null, tutPct: null, avgPct: null};
  }

  let bestAttL  = totL, bestAttT = totT;
  let bestTotal = totL + totT + 1; // sentinel

  for (let attL = 0; attL <= totL; attL++) {
    for (let attT = 0; attT <= totT; attT++) {
      if (!meetsAttendanceTarget(attL, totL, attT, totT)) continue;
      const total = attL + attT;
      // Prefer fewer total; on tie prefer fewer lectures (max lecture skips).
      if (total < bestTotal || (total === bestTotal && attL < bestAttL)) {
        bestTotal = total;
        bestAttL  = attL;
        bestAttT  = attT;
      }
    }
  }

  const lecPct = totL > 0 ? (bestAttL / totL) * 100 : null;
  const tutPct = totT > 0 ? (bestAttT / totT) * 100 : null;
  return {
    attL: bestAttL, attT: bestAttT,
    skipL: totL - bestAttL, skipT: totT - bestAttT,
    lecPct, tutPct, avgPct: calcAvgPct(lecPct, tutPct)
  };
}

/**
 * Live optimizer — accounts for already-attended, missed, and pending classes.
 * Parameters:
 *   totL, totT       — total scheduled classes
 *   attL_done, missL_done, attT_done, missT_done — logged outcomes
 *   pendingL, pendingT — not yet logged (future + unlogged past)
 *
 * Returns: {infeasible, addL, addT, skipL_budget, skipT_budget, lecPct, tutPct, avgPct}
 * Where addL/addT = how many MORE pending classes must be attended to qualify.
 */
export function optimizeLive(totL, totT, attL_done, missL_done, attT_done, missT_done, pendingL, pendingT) {
  // Guard: degenerate totals
  if (totL <= 0 && totT <= 0) {
    return {
      infeasible: false,
      addL: 0, addT: 0,
      skipL_budget: 0, skipT_budget: 0,
      lecPct: null, tutPct: null, avgPct: null
    };
  }

  // Exhaustive search over every valid remaining combination. This is deliberately
  // integer-based so 75% boundary cases cannot be altered by floating-point ceil().
  let bestAddL  = pendingL, bestAddT = pendingT;
  let bestTotal = pendingL + pendingT + 1; // sentinel
  let found     = false;

  for (let addL = 0; addL <= pendingL; addL++) {
    for (let addT = 0; addT <= pendingT; addT++) {
      if (!meetsAttendanceTarget(attL_done + addL, totL, attT_done + addT, totT)) continue;
      found = true;
      const total = addL + addT;
      if (total < bestTotal || (total === bestTotal && addL < bestAddL)) {
        bestTotal = total;
        bestAddL  = addL;
        bestAddT  = addT;
      }
    }
  }

  if (!found) {
    // Even attending every pending class isn't enough
    const bestLecPct = totL > 0 ? ((attL_done + pendingL) / totL) * 100 : null;
    const bestTutPct = totT > 0 ? ((attT_done + pendingT) / totT) * 100 : null;
    return {
      infeasible: true,
      addL: pendingL, addT: pendingT,
      skipL_budget: 0, skipT_budget: 0,
      lecPct: bestLecPct, tutPct: bestTutPct,
      avgPct: calcAvgPct(bestLecPct, bestTutPct)
    };
  }

  const finalLecPct = totL > 0 ? ((attL_done + bestAddL) / totL) * 100 : null;
  const finalTutPct = totT > 0 ? ((attT_done + bestAddT) / totT) * 100 : null;
  return {
    infeasible: false,
    addL: bestAddL, addT: bestAddT,
    skipL_budget: Math.max(0, pendingL - bestAddL),
    skipT_budget: Math.max(0, pendingT - bestAddT),
    lecPct: finalLecPct, tutPct: finalTutPct,
    avgPct: calcAvgPct(finalLecPct, finalTutPct)
  };
}

/* ═══════════════════════════════════════════════════════════════════════
   PRECOMPUTED REFERENCE DATA (static, no live state)
   Used only for internal checks — live rendering uses getAttendanceData.
═══════════════════════════════════════════════════════════════════════ /*
   INTERNAL ASSERTIONS
   Called after every getAttendanceData() to detect data inconsistencies.
═══════════════════════════════════════════════════════════════════════ */
export function assertConsistency(code, d) {
  const validTypes = Object.keys(CLASS_TYPES);
  validTypes.forEach(t => {
    const c = d.counts[t];
    const sum = c.att_done + c.miss_done + c.pending;
    if (sum !== c.tot) {
      console.error(
        `[ASSERT FAIL] ${code} ${t}: ` +
        `att(${c.att_done}) + miss(${c.miss_done}) + pending(${c.pending}) = ${sum} ≠ tot(${c.tot})`
      );
    }
    if (c.pending < 0) {
      console.error(`[ASSERT FAIL] ${code}: negative pending (${t}:${c.pending})`);
    }
  });
}

/* ═══════════════════════════════════════════════════════════════════════
   ATTENDANCE DATA LOADER
   Rebuilds per-subject counts from timetable + localStorage states.
═══════════════════════════════════════════════════════════════════════ */
export function getAttendanceData(quizDate, states = {}) {
  const data   = {};
  const validTypes = Object.keys(CLASS_TYPES);

  getTimetable().subjects.forEach(({code}) => {
    data[code] = { counts: {} };
    validTypes.forEach(t => {
      data[code].counts[t] = {
        tot: 0,
        att_done: 0, miss_done: 0,
        pending: 0
      };
    });
  });

  const cur   = new Date(getTimetable().start_date);
  const limit = new Date(quizDate);
  limit.setHours(12, 0, 0, 0);

  while (cur < limit) {
    const monIdx  = (cur.getDay() + 6) % 7;
    const dateStr = getLocalDateString(cur);

    if (getTimetable().day_schedule[monIdx]) {
      getTimetable().day_schedule[monIdx].forEach(({s, t}) => {
        // Normalize slot identifier to canonical class type (P1/P2 → P)
        const statType = normalizeClassType(t);
        if (!data[s] || !data[s].counts[statType]) return;
        
        data[s].counts[statType].tot++;

        // Attendance ID preserves raw slot identifier for storage uniqueness
        const classId = `${dateStr}:${s}:${t}`;
        const state   = states[classId] || 'Pending';

        if (state === 'Attended') {
          data[s].counts[statType].att_done++;
        } else if (state === 'Missed') {
          data[s].counts[statType].miss_done++;
        } else {
          data[s].counts[statType].pending++;
        }
      });
    }

    cur.setDate(cur.getDate() + 1);
  }

  // Run consistency checks on every subject
  getTimetable().subjects.forEach(({code}) => assertConsistency(code, data[code]));
  return data;
}

/* ═══════════════════════════════════════════════════════════════════════
   SINGLE SOURCE OF TRUTH — computeSubjectStats()
   All rendering functions consume from this one object.
═══════════════════════════════════════════════════════════════════════ */
export function computeSubjectStats(code, name, tag, rawData) {
  const d = rawData;
  // Compatibility Layer
  const safeCount = (type) => d.counts[type] ?? {
    tot: 0, att_done: 0, miss_done: 0, pending: 0
  };

  const flat = {
    totL: safeCount('L').tot,
    totT: safeCount('T').tot,
    attL_done: safeCount('L').att_done,
    missL_done: safeCount('L').miss_done,
    attT_done: safeCount('T').att_done,
    missT_done: safeCount('T').miss_done,
    pendingL: safeCount('L').pending,
    pendingT: safeCount('T').pending
  };

  // Completed = classes with a definitive outcome (attended or missed)
  const completedL = flat.attL_done + flat.missL_done;
  const completedT = flat.attT_done + flat.missT_done;

  // Current %: only over completed classes. null if nothing done yet.
  const currentLecPct = calcCurrentPct(flat.attL_done, completedL);
  const currentTutPct = flat.totT > 0 ? calcCurrentPct(flat.attT_done, completedT) : null;
  const currentAvgPct = calcAvgPct(currentLecPct, currentTutPct);

  // Forecast %: assumes all pending are attended (best case from here).
  const forecastLecPct = calcForecastPct(flat.attL_done, flat.pendingL, flat.totL);
  const forecastTutPct = flat.totT > 0 ? calcForecastPct(flat.attT_done, flat.pendingT, flat.totT) : null;
  const forecastAvgPct = calcAvgPct(forecastLecPct, forecastTutPct);

  // Status always based on forecast (what you'll achieve if you attend everything remaining)
  const status = getSubjectStatus(forecastAvgPct);

  // Optimizer: how many remaining pending must be attended to just qualify?
  const hasLorT = (safeCount('L').tot + safeCount('T').tot) > 0;
  const optResult = hasLorT ? optimizeLive(
    flat.totL,      flat.totT,
    flat.attL_done, flat.missL_done,
    flat.attT_done, flat.missT_done,
    flat.pendingL,  flat.pendingT
  ) : {
    infeasible: true,
    addL: 0, addT: 0,
    skipL_budget: 0, skipT_budget: 0,
    lecPct: 0, tutPct: 0, avgPct: 0
  };

  return {
    code, name, tag,
    // raw counts
    totL: flat.totL,    totT: flat.totT,    totComb: flat.totL + flat.totT,
    attL_done: flat.attL_done,   missL_done: flat.missL_done,
    attT_done: flat.attT_done,   missT_done: flat.missT_done,
    pendingL:  flat.pendingL,    pendingT:   flat.pendingT,
    completedL, completedT,
    // percentages
    currentLecPct, currentTutPct, currentAvgPct,
    forecastLecPct, forecastTutPct, forecastAvgPct,
    // status
    status,
    // optimizer
    optResult
  };
}

/* ═══════════════════════════════════════════════════════════════════════
   TOOLTIP ENGINE — calcForecastImpact()
   Handles all 6 state transitions correctly:
     Pending→Attended, Pending→Missed
     Attended→Missed,  Attended→Pending
     Missed→Attended,  Missed→Pending
═══════════════════════════════════════════════════════════════════════ */
export function calcForecastImpact(rawData, subjectCode, classType, currentState, newAction) {
  const d = rawData[subjectCode];
  if (!d || !d.counts[classType]) return null;

  // Start with current counts
  let attL = d.counts['L'].att_done, pendL = d.counts['L'].pending;
  let attT = d.counts['T'].att_done, pendT = d.counts['T'].pending;
  let totL = d.counts['L'].tot;
  let totT = d.counts['T'].tot;

  // Step 1: Remove the contribution of the CURRENT state for this class
  if (classType === 'L') {
    if (currentState === 'Attended') attL--;
    else if (currentState === 'Pending') pendL--;
  } else if (classType === 'T') {
    if (currentState === 'Attended') attT--;
    else if (currentState === 'Pending') pendT--;
  }

  // Step 2: Add the contribution of the NEW state for this class
  if (classType === 'L') {
    if (newAction === 'Attended') attL++;
    else if (newAction === 'Pending') pendL++;
  } else if (classType === 'T') {
    if (newAction === 'Attended') attT++;
    else if (newAction === 'Pending') pendT++;
  }

  // Compute before and after forecast averages
  const curFL  = calcForecastPct(d.counts['L'].att_done, d.counts['L'].pending, totL);
  const curFT  = totT > 0 ? calcForecastPct(d.counts['T'].att_done, d.counts['T'].pending, totT) : null;
  const curAvg = calcAvgPct(curFL, curFT);

  const newFL  = calcForecastPct(attL, pendL, totL);
  const newFT  = totT > 0 ? calcForecastPct(attT, pendT, totT) : null;
  const newAvg = calcAvgPct(newFL, newFT);

  return {
    curAvg,
    newAvg,
    stillEligible: newAvg !== null && newAvg >= 75
  };
}


/* ═══════════════════════════════════════════════════════════════════════
   ERP OVERALL ATTENDANCE ENGINE — computeCurrentOverallAttendance()
   Mirrors the SRMCEM / AKTU ERP formula:
     Overall = Σ attended_done / Σ completed × 100

   Rules:
   • Completed = att_done + miss_done (pending excluded)
   • Subjects with conducted = 0 are fully ignored
   • No percentage averaging — only raw class counts
   • Uses CLASS_TYPES registry — no hardcoded L/T/P
   • rawData = output of getAttendanceData() (keyed by subject code)
   • subjects = getTimetable().subjects array
═══════════════════════════════════════════════════════════════════════ */
export function computeCurrentOverallAttendance(rawData, subjects) {
  const attendanceTypes = Object.entries(CLASS_TYPES)
    .filter(([, meta]) => meta.supportsAttendance)
    .map(([key]) => key);

  let totalAttended  = 0;
  let totalConducted = 0;

  for (const { code } of subjects) {
    const d = rawData[code];
    if (!d) continue;

    let subjectAttended  = 0;
    let subjectConducted = 0;

    for (const type of attendanceTypes) {
      const bucket = d.counts[type];
      if (!bucket) continue;

      // Completed = classes with a definitive outcome only (pending excluded)
      const completed = bucket.att_done + bucket.miss_done;
      subjectAttended  += bucket.att_done;
      subjectConducted += completed;
    }

    // Subjects with zero conducted classes contribute nothing
    if (subjectConducted === 0) continue;

    totalAttended  += subjectAttended;
    totalConducted += subjectConducted;
  }

  if (totalConducted === 0) {
    return {
      attended: 0,
      conducted: 0,
      percentage: null,
      formattedPercentage: null
    };
  }

  const percentage = (totalAttended / totalConducted) * 100;
  return {
    attended: totalAttended,
    conducted: totalConducted,
    percentage,
    formattedPercentage: percentage.toFixed(2)
  };
}

/* ═══════════════════════════════════════════════════════════════════════
   ERP FORECAST OVERALL ATTENDANCE ENGINE — computeForecastOverallAttendance()
   Predicts overall attendance if every remaining scheduled class is attended.

   Formula:
     forecastAttended  = Σ (att_done + pending)
     forecastConducted = Σ (att_done + miss_done + pending)   [= tot]
     percentage        = forecastAttended / forecastConducted × 100

   Rules:
   • Pending classes are assumed fully attended (best-case from here)
   • Missed classes stay missed — historical data is never modified
   • Subjects with tot = 0 across all types contribute nothing
   • Uses CLASS_TYPES registry — no hardcoded L/T/P
   • rawData  = output of getAttendanceData() (keyed by subject code)
   • subjects = getTimetable().subjects array
═══════════════════════════════════════════════════════════════════════ */
export function computeForecastOverallAttendance(rawData, subjects) {
  const attendanceTypes = Object.entries(CLASS_TYPES)
    .filter(([, meta]) => meta.supportsAttendance)
    .map(([key]) => key);

  let totalForecastAttended  = 0;
  let totalForecastConducted = 0;
  let totalRemaining         = 0;

  for (const { code } of subjects) {
    const d = rawData[code];
    if (!d) continue;

    let subjectForecastAttended  = 0;
    let subjectForecastConducted = 0;
    let subjectRemaining         = 0;

    for (const type of attendanceTypes) {
      const bucket = d.counts[type];
      if (!bucket) continue;

      // Forecast: pending classes are treated as attended
      subjectForecastAttended  += bucket.att_done + bucket.pending;
      // Forecast conducted = all scheduled classes for this type
      subjectForecastConducted += bucket.att_done + bucket.miss_done + bucket.pending;
      subjectRemaining         += bucket.pending;
    }

    // Subjects with no scheduled classes at all contribute nothing
    if (subjectForecastConducted === 0) continue;

    totalForecastAttended  += subjectForecastAttended;
    totalForecastConducted += subjectForecastConducted;
    totalRemaining         += subjectRemaining;
  }

  if (totalForecastConducted === 0) {
    return {
      attended: 0,
      conducted: 0,
      remainingClasses: 0,
      percentage: null,
      formattedPercentage: null
    };
  }

  const percentage = (totalForecastAttended / totalForecastConducted) * 100;
  return {
    attended: totalForecastAttended,
    conducted: totalForecastConducted,
    remainingClasses: totalRemaining,
    percentage,
    formattedPercentage: percentage.toFixed(2)
  };
}

/* ═══════════════════════════════════════════════════════════════════════
   OVERALL ATTENDANCE ENGINE
   Single source of truth for dashboard-wide statistics.
═══════════════════════════════════════════════════════════════════════ */
export function computeOverallStats(subjectStats) {
  let totalSubjects = 0;
  let totalClasses = 0;
  let totalCompleted = 0;
  let totalPending = 0;
  let totalAttended = 0;
  let totalMissed = 0;
  let totalMustAttend = 0;
  let totalSafeSkips = 0;

  for (const r of subjectStats) {
    totalSubjects++;
    totalClasses += r.totComb;
    totalCompleted += r.completedL + r.completedT;
    totalPending += r.pendingL + r.pendingT;
    totalAttended += r.attL_done + r.attT_done;
    totalMissed += r.missL_done + r.missT_done;
    totalMustAttend += r.optResult.addL + r.optResult.addT;
    totalSafeSkips += r.optResult.skipL_budget + r.optResult.skipT_budget;
  }

  return {
    totalSubjects,
    totalClasses,
    totalCompleted,
    totalPending,
    totalAttended,
    totalMissed,
    totalMustAttend,
    totalSafeSkips
  };
}

/* ═══════════════════════════════════════════════════════════════════════
   QUIZ ELIGIBILITY ENGINE
   Evaluates a single subject's quiz eligibility against configured rules.
═══════════════════════════════════════════════════════════════════════ */

export const QUIZ_RULES = {
  firstQuiz: {
    minimumAverage: 70,
    includedTypes: ['L', 'T'],
    calculationMethod: 'average',
    useForecast: true,
    ignorePracticals: true
  }
};

/**
 * Domain Result Object for Quiz Eligibility
 */
export class QuizEligibilityResult {
  constructor({
    applicable = false,
    eligible = null,
    lecturePercentage = null,
    tutorialPercentage = null,
    average = null,
    required = null,
    deficit = null
  } = {}) {
    this.applicable = applicable;
    this.eligible = eligible;
    this.lecturePercentage = lecturePercentage;
    this.tutorialPercentage = tutorialPercentage;
    this.average = average;
    this.required = required;
    this.deficit = deficit;
  }
}

/**
 * Calculates quiz eligibility for a subject based on its raw attendance stats.
 * Independent of the forecast engine's pre-calculated percentages.
 * Returns: QuizEligibilityResult
 */
export function computeQuizEligibility(subjectStats) {
  const rules = QUIZ_RULES.firstQuiz;

  // Retrieve subject metadata from the academic model (Single Source of Truth)
  const timetable = getTimetable();
  const subjectMeta = timetable.subjects.find(s => s.code === subjectStats.code);

  if (!subjectMeta || !subjectMeta.quizApplicable) {
    return new QuizEligibilityResult({ applicable: false });
  }

  const percentages = [];
  let lecturePercentage = null;
  let tutorialPercentage = null;

  // Compute percentage dynamically for every configured type (e.g. L, T, P)
  for (const type of rules.includedTypes) {
    const tot = subjectStats[`tot${type}`] || 0;
    const att_done = subjectStats[`att${type}_done`] || 0;
    const pending = subjectStats[`pending${type}`] || 0;

    if (tot > 0) {
      const pct = ((att_done + pending) / tot) * 100;
      percentages.push(pct);
      
      // Preserve explicit L/T properties on the output payload for existing API consumers
      if (type === 'L') lecturePercentage = pct;
      if (type === 'T') tutorialPercentage = pct;
    }
  }

  let average = null;
  if (percentages.length > 0) {
    if (rules.calculationMethod === 'average') {
      const sum = percentages.reduce((acc, val) => acc + val, 0);
      average = sum / percentages.length;
    }
  }

  // Handle cases where the semester hasn't started or no applicable classes exist
  if (average === null) {
    return new QuizEligibilityResult({
      applicable: true,
      eligible: null,
      lecturePercentage,
      tutorialPercentage,
      average: null,
      required: rules.minimumAverage,
      deficit: null
    });
  }

  // Use Number.EPSILON to account for floating point inaccuracies near exact boundaries
  const eligible = (average + Number.EPSILON) >= rules.minimumAverage;
  const deficit = eligible ? 0 : Math.max(0, rules.minimumAverage - average);

  return new QuizEligibilityResult({
    applicable: true,
    eligible,
    lecturePercentage,
    tutorialPercentage,
    average,
    required: rules.minimumAverage,
    deficit
  });
}
