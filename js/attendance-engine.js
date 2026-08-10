import { getTimetable, parseDateString, isScheduledClass, getMergedDaySchedule, getLocalDateString, normalizeClassType, CLASS_TYPES } from './utils.js';
import { getQuizWindow, getAcademicDay, getSubjectEventDeltas, getPolicy, getEffectiveDaySchedule } from './calendar-engine.js';

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
 * Check the eligibility rule using fractions, avoiding rounding errors at target.
 * A subject with only one class type is evaluated using that available type.
 */
export function meetsAttendanceTarget(attL, totL, attT, totT, targetPercentage) {
  const targetFraction = targetPercentage / 100;
  const lecRatio = totL > 0 ? attL / totL : null;
  const tutRatio = totT > 0 ? attT / totT : null;
  if (lecRatio === null && tutRatio === null) return false;
  const average = lecRatio === null ? tutRatio : tutRatio === null ? lecRatio : (lecRatio + tutRatio) / 2;
  return average + Number.EPSILON >= targetFraction;
}

/**
 * Domain model representing the output of the optimization engine.
 */
export class OptimizationResult {
  constructor({
    targetPercentage,
    reachable,
    lectureDeficit,
    tutorialDeficit,
    safeSkipLecture,
    safeSkipTutorial,
    lecturePercentage,
    tutorialPercentage,
    averagePercentage
  }) {
    this.targetPercentage = targetPercentage;
    this.reachable = reachable;
    this.lectureDeficit = lectureDeficit;
    this.tutorialDeficit = tutorialDeficit;
    this.safeSkipLecture = safeSkipLecture;
    this.safeSkipTutorial = safeSkipTutorial;
    this.lecturePercentage = lecturePercentage;
    this.tutorialPercentage = tutorialPercentage;
    this.averagePercentage = averagePercentage;
  }
}

/* ═══════════════════════════════════════════════════════════════════════
   OPTIMIZATION ENGINE
   Finds minimum classes to attend to achieve (Lec% + Tut%)/2 ≥ 75%.
═══════════════════════════════════════════════════════════════════════ */

/**
 * Static optimizer — used for pre-computed ALL_DATA reference (no live state).
 * Returns: {attL, attT, skipL, skipT, lecPct, tutPct, avgPct}
 */
export function optimize(totL, totT, targetPercentage) {
  if (totL <= 0 && totT <= 0) {
    return new OptimizationResult({
      targetPercentage,
      reachable: true,
      lectureDeficit: 0, tutorialDeficit: 0,
      safeSkipLecture: 0, safeSkipTutorial: 0,
      lecturePercentage: null, tutorialPercentage: null, averagePercentage: null
    });
  }

  let bestAttL  = totL, bestAttT = totT;
  let bestTotal = totL + totT + 1; // sentinel

  for (let attL = 0; attL <= totL; attL++) {
    for (let attT = 0; attT <= totT; attT++) {
      if (!meetsAttendanceTarget(attL, totL, attT, totT, targetPercentage)) continue;
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
  
  return new OptimizationResult({
    targetPercentage,
    reachable: true, // For static optimization, assuming possible if attending all, wait, static always reachable if target <= 100 and it's mathematically sound, but anyway this is precomputed reference.
    lectureDeficit: bestAttL,
    tutorialDeficit: bestAttT,
    safeSkipLecture: totL - bestAttL,
    safeSkipTutorial: totT - bestAttT,
    lecturePercentage: lecPct,
    tutorialPercentage: tutPct,
    averagePercentage: calcAvgPct(lecPct, tutPct)
  });
}

/**
 * Live optimizer — accounts for already-attended, missed, and pending classes.
 * Parameters:
 *   totL, totT       — total scheduled classes
 *   attL_done, missL_done, attT_done, missT_done — logged outcomes
 *   pendingL, pendingT — not yet logged (future + unlogged past)
 *
 * Returns: OptimizationResult (lectureDeficit, tutorialDeficit, safeSkipLecture, safeSkipTutorial, etc)
 * Where lectureDeficit/tutorialDeficit = how many MORE pending classes must be attended to qualify.
 */
export function optimizeLive(totL, totT, attL_done, missL_done, attT_done, missT_done, pendingL, pendingT, targetPercentage) {
  // Guard: degenerate totals
  if (totL <= 0 && totT <= 0) {
    return new OptimizationResult({
      targetPercentage,
      reachable: true,
      lectureDeficit: 0, tutorialDeficit: 0,
      safeSkipLecture: 0, safeSkipTutorial: 0,
      lecturePercentage: null, tutorialPercentage: null, averagePercentage: null
    });
  }

  // Exhaustive search over every valid remaining combination.
  let bestAddL  = pendingL, bestAddT = pendingT;
  let bestTotal = pendingL + pendingT + 1; // sentinel
  let found     = false;

  for (let addL = 0; addL <= pendingL; addL++) {
    for (let addT = 0; addT <= pendingT; addT++) {
      if (!meetsAttendanceTarget(attL_done + addL, totL, attT_done + addT, totT, targetPercentage)) continue;
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
    return new OptimizationResult({
      targetPercentage,
      reachable: false,
      lectureDeficit: pendingL,
      tutorialDeficit: pendingT,
      safeSkipLecture: 0,
      safeSkipTutorial: 0,
      lecturePercentage: bestLecPct,
      tutorialPercentage: bestTutPct,
      averagePercentage: calcAvgPct(bestLecPct, bestTutPct)
    });
  }

  const finalLecPct = totL > 0 ? ((attL_done + bestAddL) / totL) * 100 : null;
  const finalTutPct = totT > 0 ? ((attT_done + bestAddT) / totT) * 100 : null;
  
  return new OptimizationResult({
    targetPercentage,
    reachable: true,
    lectureDeficit: bestAddL,
    tutorialDeficit: bestAddT,
    safeSkipLecture: Math.max(0, pendingL - bestAddL),
    safeSkipTutorial: Math.max(0, pendingT - bestAddT),
    lecturePercentage: finalLecPct,
    tutorialPercentage: finalTutPct,
    averagePercentage: calcAvgPct(finalLecPct, finalTutPct)
  });
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

  // Resolve current quiz cycle by matching the passed quizDate (from legacy UI flow)
  const quizDateStr = typeof quizDate === 'string' ? quizDate : quizDate.toISOString().split('T')[0];
  const qIdx = getTimetable().quiz_dates.findIndex(q => {
    const qStr = typeof q.date === 'string' ? q.date : q.date.toISOString().split('T')[0];
    return qStr === quizDateStr;
  });
  const quizCycle = qIdx >= 0 ? qIdx + 1 : 1; // Fallback to 1

  // Use Calendar Engine API directly (A2.3 Architecture Lock)
  getTimetable().subjects.forEach(({code}) => {
    let window;
    try {
      window = getQuizWindow(code, quizCycle);
    } catch (e) {
      // Fallback if subject has no timeline (e.g., test mocks)
      return;
    }

    window.effectiveTeachingDates.forEach(dateStr => {
      const academicDay = getAcademicDay(dateStr);
      
      const effectiveSchedule = getEffectiveDaySchedule(dateStr);
      
      const statTypesToApplyDeltas = new Set(['L', 'T', 'P']);

      if (effectiveSchedule) {
        effectiveSchedule.forEach(({s, t}) => {
          if (s !== code) return; // Process ONLY this subject
          
          const statType = normalizeClassType(t);
          if (!data[s] || !data[s].counts[statType]) return;
          
          data[s].counts[statType].tot++;
          
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
      
      // Removed manual getSubjectEventDeltas loop. getEffectiveDaySchedule applies deltas natively.
    });
  });

  // Run consistency checks on every subject
  getTimetable().subjects.forEach(({code}) => assertConsistency(code, data[code]));
  return data;
}

/**
 * Specifically computes optimization for a single subject's quiz window.
 * Used exclusively by the Quiz Engine to prevent recalculating duplicated attendance.
 */
export function getSubjectQuizOptimization(subjectCode, quizCycle, states, targetPercentage) {
  let window;
  try {
    window = getQuizWindow(subjectCode, quizCycle);
  } catch (e) {
    return null;
  }

  const counts = {
    L: { tot: 0, att_done: 0, miss_done: 0, pending: 0 },
    T: { tot: 0, att_done: 0, miss_done: 0, pending: 0 },
    P: { tot: 0, att_done: 0, miss_done: 0, pending: 0 }
  };

  window.effectiveTeachingDates.forEach(dateStr => {
    const effectiveSchedule = getEffectiveDaySchedule(dateStr);
    
    if (effectiveSchedule) {
      effectiveSchedule.forEach(({s, t}) => {
        if (s !== subjectCode) return;
        
        const statType = normalizeClassType(t);
        if (!counts[statType]) return;
        
        counts[statType].tot++;

        const classId = `${dateStr}:${s}:${t}`;
        const state   = states[classId] || 'Pending';

        if (state === 'Attended') {
          counts[statType].att_done++;
        } else if (state === 'Missed') {
          counts[statType].miss_done++;
        } else {
          counts[statType].pending++;
        }
      });
    }

    // Removed manual event deltas here.
  });

  const hasLorT = (counts.L.tot + counts.T.tot) > 0;
  if (!hasLorT) {
    return new OptimizationResult({
      targetPercentage,
      reachable: false,
      lectureDeficit: 0, tutorialDeficit: 0,
      safeSkipLecture: 0, safeSkipTutorial: 0,
      lecturePercentage: 0, tutorialPercentage: 0, averagePercentage: 0
    });
  }

  return optimizeLive(
    counts.L.tot, counts.T.tot,
    counts.L.att_done, counts.L.miss_done,
    counts.T.att_done, counts.T.miss_done,
    counts.L.pending, counts.T.pending,
    targetPercentage
  );
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
    totP: safeCount('P').tot,
    attL_done: safeCount('L').att_done,
    missL_done: safeCount('L').miss_done,
    attT_done: safeCount('T').att_done,
    missT_done: safeCount('T').miss_done,
    attP_done: safeCount('P').att_done,
    missP_done: safeCount('P').miss_done,
    pendingL: safeCount('L').pending,
    pendingT: safeCount('T').pending,
    pendingP: safeCount('P').pending
  };

  // Completed = classes with a definitive outcome (attended or missed)
  const completedL = flat.attL_done + flat.missL_done;
  const completedT = flat.attT_done + flat.missT_done;
  const completedP = flat.attP_done + flat.missP_done;

  // Current %: only over completed classes. null if nothing done yet.
  const currentLecPct = calcCurrentPct(flat.attL_done, completedL);
  const currentTutPct = flat.totT > 0 ? calcCurrentPct(flat.attT_done, completedT) : null;
  const currentAvgPct = calcAvgPct(currentLecPct, currentTutPct);

  // Forecast %: assumes all pending are attended (best case from here).
  const forecastLecPct = calcForecastPct(flat.attL_done, flat.pendingL, flat.totL);
  const forecastTutPct = flat.totT > 0 ? calcForecastPct(flat.attT_done, flat.pendingT, flat.totT) : null;
  const forecastAvgPct = calcAvgPct(forecastLecPct, forecastTutPct);

  // Status is purely a UI concept now; we only return data.

  // Optimizer: how many remaining pending must be attended to just qualify? (Default 75% for main dash)
  const hasLorT = (safeCount('L').tot + safeCount('T').tot) > 0;
  let optResult = null;
  if (hasLorT) {
    optResult = optimizeLive(
      flat.totL,      flat.totT,
      flat.attL_done, flat.missL_done,
      flat.attT_done, flat.missT_done,
      flat.pendingL,  flat.pendingT,
      (getPolicy('attendance') || { targetPercentage: 75 }).targetPercentage
    );
  } else {
    optResult = new OptimizationResult({
      targetPercentage: (getPolicy('attendance') || { targetPercentage: 75 }).targetPercentage,
      reachable: false,
      lectureDeficit: 0, tutorialDeficit: 0,
      safeSkipLecture: 0, safeSkipTutorial: 0,
      lecturePercentage: 0, tutorialPercentage: 0, averagePercentage: 0
    });
  }

  return {
    code, name, tag,
    // raw counts
    totL: flat.totL,    totT: flat.totT,    totComb: flat.totL + flat.totT,
    totP: flat.totP,
    attL_done: flat.attL_done,   missL_done: flat.missL_done,
    attT_done: flat.attT_done,   missT_done: flat.missT_done,
    attP_done: flat.attP_done,   missP_done: flat.missP_done,
    pendingL:  flat.pendingL,    pendingT:   flat.pendingT,
    pendingP:  flat.pendingP,
    completedL, completedT, completedP,
    currentLecPct, currentTutPct, currentAvgPct,
    forecastLecPct, forecastTutPct, forecastAvgPct,
    optResult,
    
    // S4.2 Clean Engine Contract: Explicitly separated Current and Forecast domains
    // Legacy flat fields above are preserved temporarily for ui.js compatibility.
    current: {
      lecture: currentLecPct,
      tutorial: currentTutPct,
      practical: flat.totP > 0 ? calcCurrentPct(flat.attP_done, completedP) : null,
      overall: currentAvgPct
    },
    forecast: {
      lecture: forecastLecPct,
      tutorial: forecastTutPct,
      practical: flat.totP > 0 ? calcForecastPct(flat.attP_done, flat.pendingP, flat.totP) : null,
      overall: forecastAvgPct
    }
  };
}

/* ═══════════════════════════════════════════════════════════════════════
   TOOLTIP ENGINE — calcForecastImpact()
   Handles all 6 state transitions correctly:
     Pending→Attended, Pending→Missed
     Attended→Missed,  Attended→Pending
     Missed→Attended,  Missed→Pending
═══════════════════════════════════════════════════════════════════════ */
export function calcForecastImpact(rawData, subjectCode, classType, currentState, newAction, targetPercentage) {
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
    stillEligible: newAvg !== null && newAvg >= targetPercentage
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
    totalMustAttend += r.optResult.lectureDeficit + r.optResult.tutorialDeficit;
    totalSafeSkips += r.optResult.safeSkipLecture + r.optResult.safeSkipTutorial;
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

