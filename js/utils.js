export const APP_VERSION = '2.0.1';

let timetable = null;

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
  const d = parseDateString(dateStr);
  if (!d || d < timetable.start_date) return false;
  const dow = d.getDay();
  const monIdx = (dow + 6) % 7;
  const sched = timetable.day_schedule[monIdx];
  if (!sched) return false;
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
