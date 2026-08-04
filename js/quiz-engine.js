import { getTimetable } from './utils.js';

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
    deficit = null,
    status = 'not-applicable',
    statusLabel = 'Not Applicable',
    displayDeficit = null
  } = {}) {
    this.applicable = applicable;
    this.eligible = eligible;
    this.lecturePercentage = lecturePercentage;
    this.tutorialPercentage = tutorialPercentage;
    this.average = average;
    this.required = required;
    this.deficit = deficit;
    this.status = status;
    this.statusLabel = statusLabel;
    this.displayDeficit = displayDeficit;
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
      deficit: null,
      status: 'pending',
      statusLabel: 'Pending',
      displayDeficit: null
    });
  }

  // Use Number.EPSILON to account for floating point inaccuracies near exact boundaries
  const eligible = (average + Number.EPSILON) >= rules.minimumAverage;
  const deficit = eligible ? 0 : Math.max(0, rules.minimumAverage - average);

  const status = eligible ? 'eligible' : 'needs-attendance';
  const statusLabel = eligible ? 'Eligible' : 'Needs Attendance';
  const displayDeficit = eligible ? null : `Need ${deficit.toFixed(1)}% more to reach ${rules.minimumAverage}% threshold`;

  return new QuizEligibilityResult({
    applicable: true,
    eligible,
    lecturePercentage,
    tutorialPercentage,
    average,
    required: rules.minimumAverage,
    deficit,
    status,
    statusLabel,
    displayDeficit
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
  const rules = QUIZ_RULES.firstQuiz;
  
  const summary = {
    totalSubjects: 0,
    quizApplicable: 0,
    eligible: 0,
    needsAttendance: 0,
    notApplicable: 0,
    requiredAverage: rules.minimumAverage
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
