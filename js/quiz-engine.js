import { getQuizPolicy } from './calendar-engine.js';
import { getSubjectQuizOptimization } from './attendance-engine.js';

/* ═══════════════════════════════════════════════════════════════════════
   QUIZ ELIGIBILITY ENGINE
   Evaluates a single subject's quiz eligibility against configured rules.
═══════════════════════════════════════════════════════════════════════ */

/**
 * Domain Result Object for Quiz Eligibility
 * Contains only structured academic information.
 */
export class QuizEligibilityResult {
  constructor({
    applicable = false,
    eligible = null,
    requiredPercentage = null,
    policyId = null,
    optResult = null
  } = {}) {
    this.applicable = applicable;
    this.eligible = eligible;
    this.requiredPercentage = requiredPercentage;
    this.policyId = policyId;
    this.optResult = optResult;
  }
}

/**
 * Calculates quiz eligibility for a subject based on its Quiz Window raw stats.
 * Independent of the forecast engine's pre-calculated percentages.
 * Returns: QuizEligibilityResult
 */
export function computeQuizEligibility(subjectMeta, states, quizCycle) {
  if (!subjectMeta || !subjectMeta.quizApplicable) {
    return new QuizEligibilityResult({ applicable: false });
  }

  const policy = getQuizPolicy(quizCycle);
  const targetPercentage = policy.targetPercentage;

  // Unified Optimizer call replacing duplicate business logic
  const optResult = getSubjectQuizOptimization(subjectMeta.code, quizCycle, states, targetPercentage);

  if (!optResult) {
    return new QuizEligibilityResult({ applicable: false });
  }

  const eligible = optResult.reachable && optResult.lectureDeficit === 0 && optResult.tutorialDeficit === 0;

  return new QuizEligibilityResult({
    applicable: true,
    eligible,
    requiredPercentage: targetPercentage,
    policyId: `quiz${quizCycle}`,
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
 * @param {Object} states - The local storage attendance states
 * @param {number} quizCycle - The active quiz cycle (1-indexed)
 * @param {Object} timetable - The academic model
 * @returns {QuizDashboardModel}
 */
export function computeQuizDashboard(states, quizCycle, timetable) {
  const policy = getQuizPolicy(quizCycle);
  
  const summary = {
    totalSubjects: 0,
    quizApplicable: 0,
    eligible: 0,
    needsAttendance: 0,
    notApplicable: 0,
    requiredAverage: policy.targetPercentage
  };
  
  const subjects = [];

  // Maintain academic order by iterating over the timetable natively
  for (const subjectMeta of timetable.subjects) {
    summary.totalSubjects++;

    // Evaluate core eligibility rules
    const eligibility = computeQuizEligibility(subjectMeta, states, quizCycle);

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
