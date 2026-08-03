export const APP_VERSION = '2.0.1';

let timetable = null;

export const CLASS_TYPES = {
  'L': {
    id: 'L',
    label: 'Lecture',
    shortLabel: 'Lec',
    displayOrder: 1,
    countsTowardsQuiz: true,
    countsTowardsOverall: true,
    supportsAttendance: true,
    supportsForecast: true,
    supportsOptimization: true
  },
  'T': {
    id: 'T',
    label: 'Tutorial',
    shortLabel: 'Tut',
    displayOrder: 2,
    countsTowardsQuiz: true,
    countsTowardsOverall: true,
    supportsAttendance: true,
    supportsForecast: true,
    supportsOptimization: true
  },
  'P': {
    id: 'P',
    label: 'Practical',
    shortLabel: 'Prac',
    displayOrder: 3,
    countsTowardsQuiz: false,
    countsTowardsOverall: true,
    supportsAttendance: true,
    supportsForecast: true,
    supportsOptimization: true
  }
};

/**
 * normalizeClassType(type) — the ONLY place that knows P1/P2 are aliases of P.
 * Maps slot identifiers to their canonical academic class type.
 * All other values are returned unchanged.
 */
export function normalizeClassType(type) {
  if (type === 'P1' || type === 'P2') return 'P';
  return type;
}

/**
 * isValidClassType — normalizes before registry lookup.
 * Accepts P1/P2 as valid (they normalize to P).
 */
export function isValidClassType(type) {
  return CLASS_TYPES.hasOwnProperty(normalizeClassType(type));
}
export async function initTimetable() {
  const res = await fetch('timetable.json');
  timetable = await res.json();
  
  // Hydrate dates
  timetable.start_date = new Date(timetable.start_date);
  timetable.start_date.setHours(12, 0, 0, 0);
  
  timetable.quiz_dates.forEach(q => {
    q.date = new Date(q.date);
    q.date.setHours(12, 0, 0, 0);
  });
  
  return timetable;
}

export function getTimetable() {
  return timetable;
}

export function getLocalDateString(date) {
  const yyyy = date.getFullYear();
  const mm   = String(date.getMonth() + 1).padStart(2, '0');
  const dd   = String(date.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

export function getTodayString() {
  return getLocalDateString(new Date());
}

export function parseDateString(str) {
  const parts = str.split('-');
  if (parts.length !== 3) return null;
  const d = new Date(+parts[0], +parts[1] - 1, +parts[2]);
  d.setHours(12, 0, 0, 0);
  return d;
}

export function isScheduledClass(dateStr, subjectCode, type) {
  if (!isValidClassType(type)) return false;
  const d = parseDateString(dateStr);
  if (!d || d < timetable.start_date) return false;
  const dow = d.getDay();
  const monIdx = (dow + 6) % 7;
  const sched = timetable.day_schedule[monIdx];
  if (!sched) return false;
  // Match the raw type string (P1/P2 must match exactly against timetable slots)
  return sched.some(c => c.s === subjectCode && c.t === type);
}

export function formatTodayHeader(date) {
  const dName = date.toLocaleDateString('en-US', { weekday: 'long' });
  const dStr  = date.toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' });
  return `${dName} • ${dStr}`;
}

export function formatHistoryDate(dateStr) {
  const d = parseDateString(dateStr);
  if (!d) return dateStr;
  return d.toLocaleDateString('en-US', { day: '2-digit', month: 'short' });
}

export function isSimulationMode() {
  return false;
}
