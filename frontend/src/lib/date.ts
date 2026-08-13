const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
];

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function toDate(value: string | Date): Date {
  if (value instanceof Date) return value;
  const parsed = new Date(`${value}T00:00:00`);
  return isNaN(parsed.getTime()) ? new Date() : parsed;
}

export function getLocalDateString(date: Date = new Date()): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function parseLocalDate(value: string): Date {
  return toDate(value);
}

export function formatLongDate(value: string | Date): string {
  const d = toDate(value);
  return `${WEEKDAYS[d.getDay()]} · ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function formatShortDate(value: string | Date): string {
  const d = toDate(value);
  return `${d.getDate()} ${MONTHS[d.getMonth()].toUpperCase()}`;
}

export function formatDayHeader(value: string | Date): string {
  const d = toDate(value);
  return `${d.getDate()} ${MONTHS[d.getMonth()].toUpperCase()}`;
}

export function formatDayInitial(value: string | Date): string {
  const d = toDate(value);
  return WEEKDAYS[d.getDay()].slice(0, 2);
}

export function getGreeting(date: Date = new Date()): string {
  const hour = date.getHours();
  if (hour < 12) return 'Good Morning';
  if (hour < 17) return 'Good Afternoon';
  return 'Good Evening';
}

export function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) return '—';
  return `${Math.round(value)}%`;
}

export function formatDelta(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}`;
}