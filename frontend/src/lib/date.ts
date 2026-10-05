const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
];

const MONTHS_FULL = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
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

/** Weekday and date without the dot separator: "Monday 5 Oct 2026". Same
 * vocabulary as formatLongDate — use it when concatenating into a sentence
 * instead of post-processing formatLongDate output. */
export function formatWeekdayDate(value: string | Date): string {
  const d = toDate(value);
  return `${WEEKDAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

/** Full month name: "October". Canonical month label for calendar surfaces. */
export function getMonthName(value: string | Date): string {
  const d = toDate(value);
  return MONTHS_FULL[d.getMonth()];
}

/** Month and year: "October 2026". Canonical month header format. */
export function formatMonthYear(value: string | Date): string {
  const d = toDate(value);
  return `${MONTHS_FULL[d.getMonth()]} ${d.getFullYear()}`;
}

/** Structured date parts for tile layouts: { day: "5", month: "OCT" } — the
 * exact strings formatShortDate renders, without callers splitting its
 * output. */
export function formatDateParts(
  value: string | Date
): { day: string; month: string } {
  const d = toDate(value);
  return { day: String(d.getDate()), month: MONTHS[d.getMonth()].toUpperCase() };
}

/** Formats a full backend timestamp (ISO date-time, e.g. a `created_at`
 * datetime) as its local calendar date. Date-only strings keep the local
 * calendar contract of toDate; true timestamps parse through the standard
 * Date constructor so the time component is honored. Unparseable input
 * renders as an em dash — never silently today's date. */
export function formatTimestampDate(value: string | Date): string {
  if (value instanceof Date) return formatDateMedium(value);
  const parsed = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? toDate(value)
    : new Date(value);
  return isNaN(parsed.getTime()) ? "—" : formatDateMedium(parsed);
}

export function formatShortDate(value: string | Date): string {
  const d = toDate(value);
  return `${d.getDate()} ${MONTHS[d.getMonth()].toUpperCase()}`;
}

/** Medium canonical date (D-09): "5 Sep 2026". Deterministic English —
 * never device-locale. Date-only strings parse as local calendar dates
 * (T00:00:00), so the displayed calendar date can never shift by a day. */
export function formatDateMedium(value: string | Date): string {
  const d = toDate(value);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

/** Formatted date range: "28 Sep 2026 – 4 Oct 2026". Consistent separator and
 * human-readable dates for week/semester bounds. */
export function formatDateRange(start: string | Date, end: string | Date): string {
  return `${formatDateMedium(start)} – ${formatDateMedium(end)}`;
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

/** One-decimal percentage (D-10 as corrected in the Phase 7 follow-up):
 * calculated attendance/eligibility values keep meaningful precision
 * (72.2%), because the decimal reflects the actual computed attendance.
 * Null/undefined renders as an em dash. Display only — never alters the
 * underlying number. */
export function formatPct1(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) return '—';
  return `${value.toFixed(1)}%`;
}

export function formatDelta(value: number | null | undefined): string {
  if (value === null || value === undefined || isNaN(value)) return '—';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}`;
}

export function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

export function isToday(date: Date): boolean {
  const today = new Date();
  return date.getDate() === today.getDate() &&
    date.getMonth() === today.getMonth() &&
    date.getFullYear() === today.getFullYear();
}