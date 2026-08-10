export const APP_VERSION = '2.0.4';

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
  if (type.startsWith('L_extra_')) return 'L';
  if (type.startsWith('T_extra_')) return 'T';
  if (type.startsWith('P1_extra_') || type.startsWith('P2_extra_') || type.startsWith('P_extra_')) return 'P';
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
  return timetable;
}

export function getTimetable() {
  return timetable;
}

/**
 * Returns the day schedule with contiguous P1/P2 slots merged into a single 'P' session.
 * Also computes merged time slots (e.g. "01:00 PM - 03:00 PM").
 */
export function getMergedDaySchedule(monIdx) {
  const sched = timetable.day_schedule[monIdx];
  if (!sched) return null;
  const merged = [];
  let currentLab = null;

  for (let i = 0; i < sched.length; i++) {
    const c = sched[i];
    const normType = normalizeClassType(c.t);
    const ts = timetable.time_slots[i] || 'TBD';

    if (normType === 'P') {
      if (currentLab && currentLab.s === c.s) {
        // Merge time slot
        const tsStart = currentLab.mergedTimeSlot.split(' - ')[0];
        const tsEnd = ts.split(' - ')[1] || ts.split(' - ')[0];
        if (tsStart && tsEnd) {
          currentLab.mergedTimeSlot = `${tsStart} - ${tsEnd}`;
        }
        continue;
      }
      currentLab = { ...c, t: 'P', originalIndex: i, mergedTimeSlot: ts };
      merged.push(currentLab);
    } else {
      currentLab = null;
      merged.push({ ...c, originalIndex: i, mergedTimeSlot: ts });
    }
  }
  return merged;
}

export function getLocalDateString(date) {
  const yyyy = date.getFullYear();
  const mm   = String(date.getMonth() + 1).padStart(2, '0');
  const dd   = String(date.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
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
  // Match the raw type string (P1/P2) or the normalized type ('P')
  return sched.some(c => c.s === subjectCode && (c.t === type || normalizeClassType(c.t) === type));
}

export function formatTodayHeader(dateVal) {
  let date = dateVal;
  if (typeof dateVal === 'string') {
    date = parseDateString(dateVal);
  }
  if (!date || typeof date.toLocaleDateString !== 'function') {
    date = new Date(dateVal);
    if (isNaN(date.getTime())) return String(dateVal);
  }
  try {
    const dName = date.toLocaleDateString('en-US', { weekday: 'long' });
    const dStr  = date.toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' });
    return `${dName} • ${dStr}`;
  } catch(e) {
    return String(dateVal);
  }
}

export function formatHistoryDate(dateStr) {
  const d = parseDateString(dateStr);
  if (!d) return dateStr;
  return d.toLocaleDateString('en-US', { day: '2-digit', month: 'short' });
}

export function isSimulationMode() {
  return false;
}
