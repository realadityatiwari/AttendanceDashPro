import { getTimetable } from './utils.js';
import { optimizeLive } from './attendance-engine.js';

/* ═══════════════════════════════════════════════════════════════════════
   QUIZ ELIGIBILITY ENGINE
   Evaluates a single subject's quiz eligibility against configured rules.
═══════════════════════════════════════════════════════════════════════ */

export const QUIZ_RULES = {
  quiz1: { targetPercentage: 70 },
  quiz2: { targetPercentage: 75 },
  quiz3: { targetPercentage: 75 }
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
    optResult = null
  } = {}) {
    this.applicable = applicable;
    this.eligible = eligible;
    this.lecturePercentage = lecturePercentage;
    this.tutorialPercentage = tutorialPercentage;
    this.average = average;
    this.optResult = optResult;
  }
}

/**
 * Calculates quiz eligibility for a subject based on its raw attendance stats.
 * Independent of the forecast engine's pre-calculated percentages.
 * Returns: QuizEligibilityResult
 */
export function computeQuizEligibility(subjectStats) {
  const rules = QUIZ_RULES.quiz1; // Using quiz1 rules per architecture

  // Retrieve subject metadata from the academic model (Single Source of Truth)
  const timetable = getTimetable();
  const subjectMeta = timetable.subjects.find(s => s.code === subjectStats.code);

  if (!subjectMeta || !subjectMeta.quizApplicable) {
    return new QuizEligibilityResult({ applicable: false });
  }

  // Unified Optimizer call replacing duplicate business logic
  const optResult = optimizeLive(
    subjectStats.totL, subjectStats.totT,
    subjectStats.attL_done, subjectStats.missL_done,
    subjectStats.attT_done, subjectStats.missT_done,
    subjectStats.pendingL, subjectStats.pendingT,
    rules.targetPercentage
  );

  const eligible = optResult.reachable && optResult.lectureDeficit === 0 && optResult.tutorialDeficit === 0;

  return new QuizEligibilityResult({
    applicable: true,
    eligible,
    lecturePercentage: optResult.lecturePercentage,
    tutorialPercentage: optResult.tutorialPercentage,
    average: optResult.averagePercentage,
    optResult
  });
}

/* ═══════════════════════════════════════════════════════════════════════
   QUIZ DASHBOARD MODEL ENGINE
   Generates a pure business data model for the Quiz UI.
═══════════════════════════════════════════════════════════════════════ */

/**
 * Domain Object representing the full state of the Quiz Dashboard.
 */
export class QuizDashboardModel {
  constructor({ summary, subjects } = {}) {
    this.summary = summary || {
      totalSubjects: 0,
      quizApplicable: 0,
      eligible: 0,
      needsAttendance: 0,
      notApplicable: 0,
      requiredAverage: null
    };
    this.subjects = subjects || [];
  }
}

/**
 * Entry point for the Quiz UI.
 * Iterates through every subject in the academic model, evaluates eligibility,
 * and compiles a structured Dashboard Model.
 * 
 * @param {Array} subjectStatsArray - Array of precomputed subject stats
 * @param {Object} timetable - The academic model
 * @returns {QuizDashboardModel}
 */
export function computeQuizDashboard(subjectStatsArray, timetable) {
  const rules = QUIZ_RULES.quiz1;
  
  const summary = {
    totalSubjects: 0,
    quizApplicable: 0,
    eligible: 0,
    needsAttendance: 0,
    notApplicable: 0,
    requiredAverage: rules.targetPercentage
  };
  
  const subjects = [];

  // Maintain academic order by iterating over the timetable natively
  for (const subjectMeta of timetable.subjects) {
    summary.totalSubjects++;

    const stats = subjectStatsArray.find(s => s.code === subjectMeta.code);
    if (!stats) continue;

    // Evaluate core eligibility rules
    const eligibility = computeQuizEligibility(stats);

    // Aggregate summary counts
    if (!eligibility.applicable) {
      summary.notApplicable++;
    } else {
      summary.quizApplicable++;
      if (eligibility.eligible === true) {
        summary.eligible++;
      } else {
        summary.needsAttendance++;
      }
    }

    // Build composed subject item
    subjects.push({
      subject: subjectMeta,
      eligibility
    });
  }

  return new QuizDashboardModel({ summary, subjects });
}
