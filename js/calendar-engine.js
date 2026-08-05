/**
 * calendar-engine.js
 * 
 * Single authoritative temporal engine for AttendanceDash Pro.
 * Provides completely stateless, pure functional resolution of dates, holidays,
 * working overrides, and academic events based on a loaded AcademicCalendar.
 */

/* ═══════════════════════════════════════════════════════════════════════
   CACHE & STATE (Internal Singleton)
═══════════════════════════════════════════════════════════════════════ */

let l1StaticData = null;
let l2MemoryCache = new Map();

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

  // Freeze static data to ensure immutability
  l1StaticData = Object.freeze({
    ...calendarData,
    events: Object.freeze(events.map(e => Object.freeze({
      ...e,
      metadata: Object.freeze({ ...e.metadata })
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

/**
 * Fetches events occurring on a specific date.
 */
function getEventsForDate(dateString) {
  return l1StaticData.events.filter(e => 
    dateString >= e.startDate && dateString <= e.endDate
  );
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
  const sortedEvents = [...events].sort((a, b) => getEventPriority(b.type) - getEventPriority(a.type));

  if (sortedEvents.length > 0) {
    const dominantEvent = sortedEvents[0];
    isWorkingDay = dominantEvent.isWorkingDay;
    workingStatus = isWorkingDay ? 'FULL_DAY' : 'CANCELLED';
    dayType = isWorkingDay ? 'WORKING_DAY' : 'NON_WORKING_DAY';
    
    // Check if this dominant event is overriding normal behavior
    const normallyWorking = !l1StaticData.defaultWeekends.includes(dow);
    if (isWorkingDay !== normallyWorking) {
      isOverride = true;
    }
    
    if (dominantEvent.substitutionScheduleOverride) {
      substitutionScheduleOverride = dominantEvent.substitutionScheduleOverride;
      isOverride = true;
    }
  }

  // Build the immutable AcademicDay
  const academicDay = Object.freeze({
    date: dateString,
    dayType,
    workingStatus,
    academicEvents: sortedEvents,
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

/* ═══════════════════════════════════════════════════════════════════════
   DATE TRAVERSAL & MATH API
═══════════════════════════════════════════════════════════════════════ */

/** Helper to add/subtract days to YYYY-MM-DD */
function addDays(dateString, days) {
  const d = new Date(dateString);
  d.setDate(d.getDate() + days);
  return d.toISOString().split('T')[0];
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
