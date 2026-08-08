import { getTimetable, normalizeClassType } from './utils.js';

/* ═══════════════════════════════════════════════════════════════════════
   LABORATORY RULES CONFIGURATION
   Centralized rules to support future scalability without engine changes.
═══════════════════════════════════════════════════════════════════════ */
export const LAB_RULES = {
  default: {
    totalExperiments: 10,
    milestones: [
      { id: 'mid', triggerAfter: 5, label: 'Mid Practical Examination' },
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

/* ═══════════════════════════════════════════════════════════════════════
   LABORATORY DOMAIN ENTITIES
═══════════════════════════════════════════════════════════════════════ */

/**
 * Core atomic academic entity for a practical session.
 * Contains both persistent fields and composed derived fields.
 */
export class LabExperiment {
  constructor({
    // Persistent fields
    experimentNumber,
    title = null,
    dateConducted = null,
    signatureStatus = 'pending',
    signedOn = null,
    marks = null,
    remarks = null,
    // Derived fields (Composed by the Engine)
    attendanceStatus = null,
    isCompleted = false
  }) {
    this.experimentNumber = experimentNumber;
    this.title = title;
    this.dateConducted = dateConducted;
    this.signatureStatus = signatureStatus;
    this.signedOn = signedOn;
    this.marks = marks;
    this.remarks = remarks;
    this.attendanceStatus = attendanceStatus;
    this.isCompleted = isCompleted;
  }
}

/**
 * Subject-level summary model wrapping a Timetable Subject and its LabExperiments.
 */
export class LaboratorySubjectModel {
  constructor({
    subject,
    experiments = [],
    completedExperiments = 0,
    pendingExperiments = 0,
    remainingExperiments = 10,
    currentExperiment = 1,
    attendancePercentage = 0,
    progressPercentage = 0,
    activeMilestones = [],
    nextMilestone = null
  }) {
    this.subject = subject;
    this.experiments = experiments;
    this.completedExperiments = completedExperiments;
    this.pendingExperiments = pendingExperiments;
    this.remainingExperiments = remainingExperiments;
    this.currentExperiment = currentExperiment;
    this.attendancePercentage = attendancePercentage;
    this.progressPercentage = progressPercentage;
    this.activeMilestones = activeMilestones;
    this.nextMilestone = nextMilestone;
  }
}

/**
 * Root Data Transfer Object for the entire Laboratory UI Dashboard.
 */
export class LaboratoryDashboardModel {
  constructor({ summary, subjects } = {}) {
    this.summary = summary || {
      totalLabSubjects: 0,
      totalCompletedExperiments: 0,
      milestonesReached: 0
    };
    this.subjects = subjects || [];
  }
}

/* ═══════════════════════════════════════════════════════════════════════
   LABORATORY ENGINE LOGIC
═══════════════════════════════════════════════════════════════════════ */

/**
 * Validates the physical attendance status of an experiment for a given date.
 */
function getExperimentAttendanceStatus(dateConducted, subjectCode, attendanceDataMap) {
  if (!dateConducted) return null;
  
  const prefix = `${dateConducted}:${subjectCode}:`;
  let finalState = null;

  // Resolve normalized P1/P2 records (or direct P) to an aggregate state.
  // Hierarchy: Attended > Missed > Pending
  for (const [classId, state] of Object.entries(attendanceDataMap)) {
    if (classId.startsWith(prefix)) {
      const type = classId.substring(prefix.length);
      if (normalizeClassType(type) === 'P') {
        if (state === 'Attended') {
          return 'Attended';
        }
        if (state === 'Missed') {
          finalState = 'Missed';
        }
        if (state === 'Pending' && !finalState) {
          finalState = 'Pending';
        }
      }
    }
  }
  
  return finalState;
}

/**
 * Composes the Laboratory Dashboard Model for UI rendering.
 * @param {Object} rawLabState - The raw persistence layer state (AppState.laboratory)
 * @param {Object} rawAttendanceState - The raw physical attendance state (AppState.attendance)
 * @param {Array} subjectStatsArray - Array of precomputed subject stats (for attendance percentages)
 * @param {Object} timetable - The academic model
 * @returns {LaboratoryDashboardModel}
 */
export function computeLaboratoryDashboard(rawLabState, rawAttendanceState, subjectStatsArray, timetable) {
  const rules = LAB_RULES.default;
  const summary = {
    totalLabSubjects: 0,
    totalCompletedExperiments: 0,
    milestonesReached: 0
  };
  const subjects = [];

  for (const subjectMeta of timetable.subjects) {
    if (subjectMeta.category !== 'lab') continue;

    summary.totalLabSubjects++;

    // 1. Rehydrate raw persistent experiments
    const rawExperiments = rawLabState[subjectMeta.code] || [];
    
    // 2. Fetch subject attendance stats for percentage (if any)
    const stats = subjectStatsArray.find(s => s.code === subjectMeta.code);
    let attPercentage = 0;
    if (stats && stats.totP > 0) {
      attPercentage = ((stats.attP_done + stats.pendingP) / stats.totP) * 100;
    }

    // 3. Compose full LabExperiment objects
    let completedCount = 0;
    let pendingCount = 0;
    const composedExperiments = [];

    // Pre-fill the array with 10 empty experiments to represent the full lifecycle
    for (let i = 1; i <= rules.totalExperiments; i++) {
      const existingRaw = rawExperiments.find(e => e.experimentNumber === i);
      
      let exp;
      if (existingRaw) {
        // Resolve physical attendance
        const attStatus = getExperimentAttendanceStatus(existingRaw.dateConducted, subjectMeta.code, rawAttendanceState);
        const isComp = (existingRaw.signatureStatus === 'signed' && attStatus === 'Attended');
        
        if (isComp) completedCount++;
        else if (existingRaw.dateConducted) pendingCount++;

        exp = new LabExperiment({
          ...existingRaw,
          attendanceStatus: attStatus,
          isCompleted: isComp
        });
      } else {
        // Empty upcoming experiment
        exp = new LabExperiment({ experimentNumber: i });
      }
      composedExperiments.push(exp);
    }

    // 4. Evaluate Milestones
    const activeMilestones = [];
    let nextMilestone = null;

    for (const ms of rules.milestones) {
      if (completedCount >= ms.triggerAfter) {
        activeMilestones.push(ms);
        summary.milestonesReached++;
      } else if (!nextMilestone) {
        nextMilestone = {
          ...ms,
          remainingRequired: ms.triggerAfter - completedCount
        };
      }
    }

    // 5. Build Subject Summary
    summary.totalCompletedExperiments += completedCount;

    const currentExp = completedCount < rules.totalExperiments ? completedCount + 1 : rules.totalExperiments;

    subjects.push(new LaboratorySubjectModel({
      subject: subjectMeta,
      experiments: composedExperiments,
      completedExperiments: completedCount,
      pendingExperiments: pendingCount,
      remainingExperiments: rules.totalExperiments - (completedCount + pendingCount),
      currentExperiment: currentExp,
      attendancePercentage: attPercentage,
      progressPercentage: (completedCount / rules.totalExperiments) * 100,
      activeMilestones,
      nextMilestone
    }));
  }

  return new LaboratoryDashboardModel({ summary, subjects });
}
