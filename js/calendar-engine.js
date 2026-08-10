/**
 * calendar-engine.js
 * 
 * Single authoritative temporal engine for AttendanceDash Pro.
 * Provides completely stateless, pure functional resolution of dates, holidays,
 * working overrides, and academic events based on a loaded AcademicCalendar.
 */
import { getMergedDaySchedule, normalizeClassType } from './utils.js';

/* ═══════════════════════════════════════════════════════════════════════
   CACHE & STATE (Internal Singleton)
═══════════════════════════════════════════════════════════════════════ */

let l1StaticData = null;
let l2MemoryCache = new Map();
let runtimeEvents = {}; // Date-indexed: YYYY-MM-DD -> AcademicEvent[]

/* ═══════════════════════════════════════════════════════════════════════
   INITIALIZATION & VALIDATION
═══════════════════════════════════════════════════════════════════════ */

/**
 * Validates a YYYY-MM-DD date string.
 */
function isValidDateString(str) {
  if (!str || typeof str !== 'string') return false;
  const regex = /^\d{4}-\d{2}-\d{2}$/;
  if (!regex.test(str)) return false;
  const d = new Date(str);
  return !isNaN(d.getTime());
}

/**
 * Validates and initializes the calendar engine with static L1 data.
 * @param {Object} calendarData - The AcademicCalendar aggregate root.
 */
export function initCalendarEngine(calendarData) {
  if (!calendarData || typeof calendarData !== 'object') {
    throw new Error('initCalendarEngine: Invalid calendar data provided.');
  }
  
  if (!isValidDateString(calendarData.semesterStart) || !isValidDateString(calendarData.semesterEnd)) {
    throw new Error('initCalendarEngine: semesterStart and semesterEnd must be valid YYYY-MM-DD strings.');
  }

  if (calendarData.semesterStart > calendarData.semesterEnd) {
    throw new Error('initCalendarEngine: semesterStart cannot be after semesterEnd.');
  }

  if (!Array.isArray(calendarData.defaultWeekends)) {
    throw new Error('initCalendarEngine: defaultWeekends must be an array of integers (0-6).');
  }

  const eventIds = new Set();
  const events = Array.isArray(calendarData.events) ? calendarData.events : [];
  
  events.forEach(event => {
    if (!event.eventId) throw new Error('initCalendarEngine: Event missing eventId.');
    if (eventIds.has(event.eventId)) {
      throw new Error(`initCalendarEngine: Duplicate eventId detected: ${event.eventId}`);
    }
    eventIds.add(event.eventId);
    
    if (!isValidDateString(event.startDate)) {
      throw new Error(`initCalendarEngine: Event ${event.eventId} has invalid startDate.`);
    }
    if (!isValidDateString(event.endDate)) {
      throw new Error(`initCalendarEngine: Event ${event.eventId} has invalid endDate.`);
    }
    if (event.startDate > event.endDate) {
      throw new Error(`initCalendarEngine: Event ${event.eventId} startDate > endDate.`);
    }
  });

  const timelines = Array.isArray(calendarData.subjectTimelines) ? calendarData.subjectTimelines : [];
  const subjectCodes = new Set();
  
  timelines.forEach(tl => {
    if (!tl.subjectCode) throw new Error('initCalendarEngine: Timeline missing subjectCode');
    if (subjectCodes.has(tl.subjectCode)) throw new Error(`initCalendarEngine: Duplicate timeline for subject ${tl.subjectCode}`);
    subjectCodes.add(tl.subjectCode);
    
    if (!isValidDateString(tl.commencementDate)) throw new Error(`initCalendarEngine: Invalid commencementDate for ${tl.subjectCode}`);
    if (tl.completionDate && !isValidDateString(tl.completionDate)) throw new Error(`initCalendarEngine: Invalid completionDate for ${tl.subjectCode}`);
    
    const mIds = new Set();
    let lastDate = '0000-00-00';
    let hasFirstLecture = false;
    let quizBeforeFirstLecture = false;

    (tl.milestones || []).forEach(m => {
      if (!m.milestoneId) throw new Error(`initCalendarEngine: Milestone missing id in ${tl.subjectCode}`);
      if (mIds.has(m.milestoneId)) throw new Error(`initCalendarEngine: Duplicate milestoneId ${m.milestoneId} in ${tl.subjectCode}`);
      mIds.add(m.milestoneId);
      
      if (!isValidDateString(m.date)) throw new Error(`initCalendarEngine: Invalid date for milestone ${m.milestoneId}`);
      if (m.date < lastDate) throw new Error(`initCalendarEngine: Out-of-order milestone ${m.milestoneId} in ${tl.subjectCode}`);
      lastDate = m.date;
      
      if (m.type === 'FIRST_LECTURE') hasFirstLecture = true;
      if (m.type === 'QUIZ' && !hasFirstLecture) quizBeforeFirstLecture = true;
    });

    if (quizBeforeFirstLecture) {
      throw new Error(`initCalendarEngine: Quiz milestone before FIRST_LECTURE in ${tl.subjectCode}`);
    }
  });

  // Freeze static data to ensure immutability
  l1StaticData = Object.freeze({
    ...calendarData,
    events: Object.freeze(events.map(e => Object.freeze({
      ...e,
      metadata: Object.freeze({ ...e.metadata })
    }))),
    subjectTimelines: Object.freeze(timelines.map(tl => Object.freeze({
      ...tl,
      milestones: Object.freeze((tl.milestones || []).map(m => Object.freeze({
        ...m,
        metadata: Object.freeze({ ...m.metadata })
      })))
    }))),
    policies: Object.freeze({ ...calendarData.policies })
  });

  l2MemoryCache.clear();
}

/* ═══════════════════════════════════════════════════════════════════════
   POLICY API
═══════════════════════════════════════════════════════════════════════ */

/**
 * Retrieves a specific policy configuration domain.
 * @param {string} policyDomain - E.g., 'quiz', 'attendance'
 * @returns {Object|null} Immutable policy object
 */
export function getPolicy(policyDomain) {
  if (!l1StaticData) throw new Error('Calendar Engine not initialized.');
  if (!l1StaticData.policies) return null;
  return l1StaticData.policies[policyDomain] || null;
}

/**
 * Retrieves the specific policy for a given quiz cycle.
 * @param {number} quizCycle - 1-indexed quiz cycle
 * @returns {Object} Policy for the quiz cycle
 */
export function getQuizPolicy(quizCycle) {
  const quizPolicies = getPolicy('quiz');
  if (!quizPolicies) return { targetPercentage: 70 }; // Fallback
  return quizPolicies[`quiz${quizCycle}`] || quizPolicies.default || { targetPercentage: 70 };
}

/* ═══════════════════════════════════════════════════════════════════════
   EVENT API
═══════════════════════════════════════════════════════════════════════ */

/**
 * Retrieves all events matching a specific type.
 * @param {string} eventType 
 * @returns {Array<Object>}
 */
export function getCalendarEventsByType(eventType) {
  if (!l1StaticData) throw new Error('Calendar Engine not initialized.');
  return l1StaticData.events.filter(e => e.type === eventType);
}

export function syncRuntimeEvents(eventsMap) {
  runtimeEvents = eventsMap || {};
  l2MemoryCache.clear();
}

/* ═══════════════════════════════════════════════════════════════════════
   ACADEMIC EVENT REGISTRY
═══════════════════════════════════════════════════════════════════════ */

export const AcademicEventRegistry = {
  EXTRA_LECTURE: {
    displayName: 'Extra Lecture',
    icon: 'plus-circle',
    color: 'blue',
    requiresSubject: true,
    requiresClassType: true,
    allowedClassTypes: ['L'],
    badge: 'Extra'
  },
  EXTRA_TUTORIAL: {
    displayName: 'Extra Tutorial',
    icon: 'plus-circle',
    color: 'blue',
    requiresSubject: true,
    requiresClassType: true,
    allowedClassTypes: ['T'],
    badge: 'Extra'
  },
  EXTRA_PRACTICAL: {
    displayName: 'Extra Practical',
    icon: 'plus-circle',
    color: 'blue',
    requiresSubject: true,
    requiresClassType: true,
    allowedClassTypes: ['P1', 'P2'],
    badge: 'Extra'
  },
  CLASS_CANCELLED: {
    displayName: 'Cancelled Class',
    icon: 'x-circle',
    color: 'red',
    requiresSubject: true,
    requiresClassType: true,
    allowedClassTypes: ['L', 'T', 'P1', 'P2'],
    badge: 'Cancelled'
  },
  SURPRISE_QUIZ: {
    displayName: 'Surprise Quiz',
    icon: 'file-text',
    color: 'purple',
    requiresSubject: true,
    requiresClassType: true,
    allowedClassTypes: ['L', 'T'],
    badge: 'Quiz'
  },
  QUIZ_DAY: {
    displayName: 'Quiz Day',
    icon: 'file-text',
    color: 'purple',
    requiresSubject: true,
    requiresClassType: false,
    allowedClassTypes: [],
    badge: 'Quiz'
  },
  PUBLIC_HOLIDAY: {
    displayName: 'Public Holiday',
    icon: 'calendar',
    color: 'red',
    requiresSubject: false,
    requiresClassType: false,
    allowedClassTypes: [],
    badge: 'Holiday'
  },
  INSTITUTE_HOLIDAY: {
    displayName: 'Institute Holiday',
    icon: 'home',
    color: 'red',
    requiresSubject: false,
    requiresClassType: false,
    allowedClassTypes: [],
    badge: 'Holiday'
  },
  WORKING_DAY_OVERRIDE: {
    displayName: 'Working Day Override',
    icon: 'briefcase',
    color: 'orange',
    requiresSubject: false,
    requiresClassType: false,
    allowedClassTypes: [],
    badge: 'Working'
  },
  EMERGENCY_CLOSURE: {
    displayName: 'Emergency Closure',
    icon: 'alert-triangle',
    color: 'red',
    requiresSubject: false,
    requiresClassType: false,
    allowedClassTypes: [],
    badge: 'Emergency'
  }
};

/**
 * Validates an event against the registry schema.
 */
export function validateAcademicEvent(raw) {
  if (!raw.eventType || !AcademicEventRegistry[raw.eventType]) {
    throw new Error(`Invalid eventType: ${raw.eventType}`);
  }
  const schema = AcademicEventRegistry[raw.eventType];
  
  if (schema.requiresSubject && !raw.subjectCode) {
    throw new Error(`${schema.displayName} requires a subjectCode.`);
  }
  if (!schema.requiresSubject && raw.subjectCode) {
    throw new Error(`${schema.displayName} must not have a subjectCode.`);
  }
  
  if (schema.requiresClassType && !raw.classType) {
    throw new Error(`${schema.displayName} requires a classType.`);
  }
  if (!schema.requiresClassType && raw.classType) {
    throw new Error(`${schema.displayName} must not have a classType.`);
  }
  
  if (schema.requiresClassType && !schema.allowedClassTypes.includes(raw.classType)) {
    throw new Error(`${schema.displayName} does not support classType ${raw.classType}.`);
  }
  
  return true;
}

/**
 * Validates and creates a normalized AcademicEvent.
 */
export function createAcademicEvent(raw) {
  if (!raw.id || typeof raw.id !== 'string') throw new Error('Invalid event id');
  if (!isValidDateString(raw.effectiveDate)) throw new Error('Invalid effectiveDate');
  
  validateAcademicEvent(raw);
  
  const history = raw.history && Array.isArray(raw.history) ? [...raw.history] : [];
  if (history.length === 0) {
    history.push({
      action: 'Created',
      timestamp: new Date().toISOString(),
      user: 'system' // This could be passed via raw.sourceUser if needed
    });
  }

  return Object.freeze({
    id: raw.id,
    version: raw.version || 1,
    eventType: raw.eventType,
    subjectCode: raw.subjectCode || null,
    classType: raw.classType || null,
    effectiveDate: raw.effectiveDate,
    metadata: Object.freeze({ ...(raw.metadata || {}) }),
    createdAt: raw.createdAt || new Date().toISOString(),
    source: raw.source || 'USER',
    active: raw.active !== false,
    archived: raw.archived === true,
    history: Object.freeze(history)
  });
}

/**
 * Fetches events occurring on a specific date, merging static L1 events and runtime events.
 */
function getEventsForDate(dateString) {
  const staticEvents = l1StaticData.events.filter(e => 
    dateString >= e.startDate && dateString <= e.endDate
  );
  const dynamicEvents = runtimeEvents[dateString] ? runtimeEvents[dateString].filter(e => e.active) : [];
  return [...staticEvents, ...dynamicEvents];
}

/**
 * Normalizes event meaning for downstream engines.
 * Returns an integer delta indicating the shift in required classes (+1, -1, 0).
 */
export function getSubjectEventDeltas(dateString, subjectCode, classType) {
  const events = getEventsForDate(dateString);
  let delta = 0;
  
  // Sort events by priority descending to apply highest precedence
  const sortedEvents = [...events].sort((a, b) => getEventPriority(b.type || b.eventType) - getEventPriority(a.type || a.eventType));
  
  for (const event of sortedEvents) {
    const type = event.type || event.eventType;
    // Skip if it doesn't apply to this subject/classType
    if (event.subjectCode && event.subjectCode !== subjectCode) continue;
    if (event.classType && event.classType !== classType) continue;

    // High-priority closures skip standard calculation completely; handled by dayType
    if (['EMERGENCY_CLOSURE', 'PUBLIC_HOLIDAY', 'INSTITUTE_HOLIDAY', 'FESTIVAL_HOLIDAY', 'SEMESTER_BREAK'].includes(type)) {
      return 0;
    }

    if (type === 'CLASS_CANCELLED') {
      delta -= 1;
    } else if (['EXTRA_LECTURE', 'EXTRA_TUTORIAL', 'EXTRA_PRACTICAL', 'SURPRISE_QUIZ'].includes(type)) {
      delta += 1;
    }
  }

  return delta;
}

/* ═══════════════════════════════════════════════════════════════════════
   DAY RESOLUTION API
═══════════════════════════════════════════════════════════════════════ */

const DAY_NAMES = ['SUNDAY', 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY'];

/**
 * Determines precedence of events for working day resolution.
 * Higher number = higher precedence.
 */
function getEventPriority(eventType) {
  switch (eventType) {
    case 'EMERGENCY_CLOSURE': return 100;
    case 'WORKING_DAY_OVERRIDE': return 90;
    case 'WORKING_SATURDAY': return 80;
    case 'PUBLIC_HOLIDAY': return 70;
    case 'SEMESTER_BREAK': return 60;
    case 'MID_SEMESTER_BREAK': return 60;
    case 'INSTITUTE_HOLIDAY': return 50;
    case 'FESTIVAL_HOLIDAY': return 40;
    case 'CLASS_CANCELLED': return 30;
    case 'EXTRA_LECTURE': return 30;
    case 'EXTRA_TUTORIAL': return 30;
    case 'EXTRA_PRACTICAL': return 30;
    case 'SURPRISE_QUIZ': return 30;
    case 'QUIZ_DAY': return 30;
    default: return 10;
  }
}

/**
 * Generates the canonical AcademicDay representation for a date.
 * Relies on deterministic conflict resolution.
 * @param {string} dateString - YYYY-MM-DD
 * @returns {Object} Immutable AcademicDay
 */
export function getAcademicDay(dateString) {
  if (!l1StaticData) throw new Error('Calendar Engine not initialized.');
  if (!isValidDateString(dateString)) throw new Error('getAcademicDay: Invalid date format.');

  if (l2MemoryCache.has(dateString)) {
    return l2MemoryCache.get(dateString);
  }

  const d = new Date(dateString);
  const dow = d.getDay();
  const originalDayOfWeek = DAY_NAMES[dow];
  
  // Base default state
  let isWorkingDay = !l1StaticData.defaultWeekends.includes(dow);
  let isOverride = false;
  let scheduleDayIndex = isWorkingDay ? (dow === 0 ? 6 : dow - 1) : null; // Mapping JS dow (0=Sun) to timetable index (0=Mon) where possible, though Timetable engine maps this later. We just return original schedule day string if needed.
  let substitutionScheduleOverride = null;
  let workingStatus = isWorkingDay ? 'FULL_DAY' : 'CANCELLED';
  let dayType = isWorkingDay ? 'WORKING_DAY' : 'NON_WORKING_DAY';
  
  const events = getEventsForDate(dateString);

  // Sort events by priority descending to determine the definitive state
  const sortedEvents = [...events].sort((a, b) => getEventPriority(b.type || b.eventType) - getEventPriority(a.type || a.eventType));

  if (sortedEvents.length > 0) {
    const dominantEvent = sortedEvents[0];
    
    if (dominantEvent.isWorkingDay !== undefined) {
      isWorkingDay = dominantEvent.isWorkingDay;
      workingStatus = isWorkingDay ? 'FULL_DAY' : 'CANCELLED';
      dayType = isWorkingDay ? 'WORKING_DAY' : 'NON_WORKING_DAY';
      
      const normallyWorking = !l1StaticData.defaultWeekends.includes(dow);
      if (isWorkingDay !== normallyWorking) {
        isOverride = true;
      }
    }
    
    if (dominantEvent.substitutionScheduleOverride) {
      substitutionScheduleOverride = dominantEvent.substitutionScheduleOverride;
      isOverride = true;
    }
  }

  // Build the immutable AcademicDay
  const academicDay = Object.freeze({
    date: dateString,
    dayOfWeek: dow,
    isWorkingDay,
    workingStatus,
    dayType,
    isOverride,
    events: Object.freeze(sortedEvents),
    metadata: Object.freeze({
      isOverride,
      originalDayOfWeek,
      substitutionScheduleOverride,
      isTeachingDay: isWorkingDay // Exposing this explicitly for downstream engines
    })
  });

  l2MemoryCache.set(dateString, academicDay);
  return academicDay;
}

/**
 * Returns the effective schedule for a given date by resolving the base timetable 
 * against the date's active academic events (e.g. EXTRA_LECTURE, CLASS_CANCELLED).
 * @param {string} dateString - YYYY-MM-DD
 * @returns {Array} Array of class occurrence objects
 */
export function getEffectiveDaySchedule(dateString) {
  const day = getAcademicDay(dateString);
  if (!day.isWorkingDay) return [];

  // Determine the base schedule index
  const scheduleDayName = day.metadata.substitutionScheduleOverride || day.metadata.originalDayOfWeek;
  const monIdx = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'].indexOf(scheduleDayName);
  
  const rawSchedule = getMergedDaySchedule(monIdx);
  if (!rawSchedule) return [];
  
  // clone baseSchedule to avoid mutating static array
  const baseSchedule = rawSchedule.map(c => ({...c}));

  // Sort events by priority descending to process cancellations deterministically
  const sortedEvents = [...day.events].sort((a, b) => getEventPriority(b.type || b.eventType) - getEventPriority(a.type || a.eventType));

  sortedEvents.forEach(e => {
    const type = e.type || e.eventType;
    
    // High-priority closures already set isWorkingDay = false in getAcademicDay
    if (['EMERGENCY_CLOSURE', 'PUBLIC_HOLIDAY', 'INSTITUTE_HOLIDAY', 'FESTIVAL_HOLIDAY', 'SEMESTER_BREAK'].includes(type)) {
      return;
    }

    if (type === 'CLASS_CANCELLED') {
      // Remove one matching class occurrence from the base schedule
      const idx = baseSchedule.findIndex(c => c.s === e.subjectCode && normalizeClassType(c.t) === normalizeClassType(e.classType));
      if (idx >= 0) {
        baseSchedule.splice(idx, 1);
      }
    } else if (['EXTRA_LECTURE', 'EXTRA_TUTORIAL', 'EXTRA_PRACTICAL', 'SURPRISE_QUIZ'].includes(type)) {
      // Inject one class occurrence
      baseSchedule.push({
        s: e.subjectCode,
        t: `${e.classType}_extra_${e.id}`, // Unique ID prevents state collision
        mergedTimeSlot: AcademicEventRegistry[type]?.displayName || 'Extra Class',
        isExtra: true
      });
    }
  });

  return baseSchedule;
}

/* ═══════════════════════════════════════════════════════════════════════
   DATE TRAVERSAL & MATH API
═══════════════════════════════════════════════════════════════════════ */

/** Helper to add/subtract days to YYYY-MM-DD */
export function addDays(dateString, days) {
  const d = new Date(dateString);
  d.setDate(d.getDate() + days);
  return d.toISOString().split('T')[0];
}

export function getTodayString() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm   = String(d.getMonth() + 1).padStart(2, '0');
  const dd   = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

/**
 * Returns the previous valid working day before the given date.
 */
export function getPreviousWorkingDay(dateString) {
  if (!isValidDateString(dateString)) throw new Error('Invalid dateString');
  let current = addDays(dateString, -1);
  // Prevent infinite loops if calendar boundaries are exceeded
  const minDate = l1StaticData.semesterStart;
  
  while (current >= minDate) {
    const day = getAcademicDay(current);
    if (day.metadata.isTeachingDay) return day.date;
    current = addDays(current, -1);
  }
  return null;
}

/**
 * Returns the next valid working day after the given date.
 */
export function getNextWorkingDay(dateString) {
  if (!isValidDateString(dateString)) throw new Error('Invalid dateString');
  let current = addDays(dateString, 1);
  const maxDate = l1StaticData.semesterEnd;
  
  while (current <= maxDate) {
    const day = getAcademicDay(current);
    if (day.metadata.isTeachingDay) return day.date;
    current = addDays(current, 1);
  }
  return null;
}

/**
 * Returns an array of working date strings exactly between start and end (inclusive).
 */
export function getTeachingDaysBetween(startDateString, endDateString) {
  if (!isValidDateString(startDateString) || !isValidDateString(endDateString)) {
    throw new Error('Invalid date strings');
  }
  if (startDateString > endDateString) return [];
  
  const workingDays = [];
  let current = startDateString;
  
  while (current <= endDateString) {
    if (getAcademicDay(current).metadata.isTeachingDay) {
      workingDays.push(current);
    }
    current = addDays(current, 1);
  }
  return workingDays;
}

/**
 * Counts the total working days from semester start until the given date.
 */
export function getWorkingDaysUntil(dateString) {
  if (!l1StaticData) throw new Error('Calendar Engine not initialized.');
  if (!isValidDateString(dateString)) throw new Error('Invalid dateString');
  
  const start = l1StaticData.semesterStart;
  // If target date is before semester starts
  if (dateString < start) return 0;
  
  const end = dateString > l1StaticData.semesterEnd ? l1StaticData.semesterEnd : dateString;
  
  return getTeachingDaysBetween(start, end).length;
}

/* ═══════════════════════════════════════════════════════════════════════
   SUBJECT TIMELINE API
═══════════════════════════════════════════════════════════════════════ */

/**
 * Retrieves the timeline for a given subject.
 */
export function getSubjectTimeline(subjectCode) {
  if (!l1StaticData) throw new Error('Calendar Engine not initialized.');
  const tl = l1StaticData.subjectTimelines.find(t => t.subjectCode === subjectCode);
  if (!tl) throw new Error(`Unknown subject timeline: ${subjectCode}`);
  return tl;
}

/**
 * Retrieves milestones for a given subject.
 */
export function getSubjectMilestones(subjectCode) {
  const tl = getSubjectTimeline(subjectCode);
  return tl.milestones;
}

/**
 * Retrieves the milestone occurring immediately before the specified milestone.
 */
export function getPreviousMilestone(subjectCode, milestoneId) {
  const milestones = getSubjectMilestones(subjectCode);
  const idx = milestones.findIndex(m => m.milestoneId === milestoneId);
  if (idx === -1) throw new Error(`Unknown milestone: ${milestoneId}`);
  if (idx === 0) return null;
  return milestones[idx - 1];
}

/**
 * Retrieves the milestone occurring immediately after the specified milestone.
 */
export function getNextMilestone(subjectCode, milestoneId) {
  const milestones = getSubjectMilestones(subjectCode);
  const idx = milestones.findIndex(m => m.milestoneId === milestoneId);
  if (idx === -1) throw new Error(`Unknown milestone: ${milestoneId}`);
  if (idx === milestones.length - 1) return null;
  return milestones[idx + 1];
}

/* ═══════════════════════════════════════════════════════════════════════
   ATTENDANCE WINDOW API
═══════════════════════════════════════════════════════════════════════ */

/**
 * Resolves the structured attendance window leading up to a specific milestone.
 */
export function getAttendanceWindow(subjectCode, milestoneId) {
  const tl = getSubjectTimeline(subjectCode);
  const milestone = tl.milestones.find(m => m.milestoneId === milestoneId);
  if (!milestone) throw new Error(`Unknown milestone: ${milestoneId}`);

  let windowStart = tl.commencementDate;
  
  if (milestone.metadata && typeof milestone.metadata.quizCycle === 'number' && milestone.metadata.quizCycle > 1) {
    const prevQuiz = tl.milestones.find(m => m.type === 'QUIZ' && m.metadata && m.metadata.quizCycle === (milestone.metadata.quizCycle - 1));
    if (prevQuiz) {
      windowStart = prevQuiz.date; // Quiz window starts from previous quiz date
    }
  }

  const windowEnd = addDays(milestone.date, -1); // Exactly one day before the milestone event

  if (windowStart > windowEnd) {
    throw new Error('Window end before window start');
  }

  const effectiveTeachingDates = getTeachingDaysBetween(windowStart, windowEnd);
  
  let holidayCount = 0;
  let weekendCount = 0;

  let current = windowStart;
  while (current <= windowEnd) {
    const day = getAcademicDay(current);
    if (!day.metadata.isTeachingDay) {
      if (day.events.length > 0) {
        holidayCount++;
      } else {
        weekendCount++;
      }
    }
    current = addDays(current, 1);
  }

  const activeMilestones = tl.milestones.filter(m => m.date >= windowStart && m.date <= windowEnd);

  return Object.freeze({
    subjectCode,
    windowStart,
    windowEnd,
    teachingDays: effectiveTeachingDates.length,
    workingDays: effectiveTeachingDates.length, // Aliased to teachingDays for this context
    holidayCount,
    weekendCount,
    effectiveTeachingDates: Object.freeze([...effectiveTeachingDates]),
    activeMilestones: Object.freeze([...activeMilestones])
  });
}

/**
 * Convenience wrapper to fetch the window leading up to a specific quiz cycle.
 */
export function getQuizWindow(subjectCode, quizCycle) {
  const tl = getSubjectTimeline(subjectCode);
  const quizMilestone = tl.milestones.find(m => m.type === 'QUIZ' && m.metadata && m.metadata.quizCycle === quizCycle);
  if (!quizMilestone) throw new Error(`Unknown quiz cycle ${quizCycle} for subject ${subjectCode}`);
  return getAttendanceWindow(subjectCode, quizMilestone.milestoneId);
}

/**
 * Returns the exact teaching days encapsulated by the window.
 */
export function getWindowTeachingDays(window) {
  if (!window || !window.effectiveTeachingDates) throw new Error('Invalid window object');
  return window.effectiveTeachingDates;
}

/**
 * Calculates remaining teaching days from TODAY until the end of the window.
 * Returns 0 if the window has already passed.
 */
export function getRemainingTeachingDays(window) {
  if (!window || !window.windowEnd) throw new Error('Invalid window object');
  const today = new Date().toISOString().split('T')[0];
  if (today > window.windowEnd) return 0;
  
  const effectiveStart = today > window.windowStart ? today : window.windowStart;
  return getTeachingDaysBetween(effectiveStart, window.windowEnd).length;
}
