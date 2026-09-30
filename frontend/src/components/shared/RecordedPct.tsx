import { formatPct } from "@/lib/date";

interface RecordedPctProps {
  /** Recorded-only percentage from the analytics read model. Null means no
   * sessions have been recorded yet — rendered as an em dash with no basis
   * suffix, so an empty semester never reads as a real percentage. */
  value: number | null | undefined;
  /** Classes for the numeric value itself (size/weight vary per surface). */
  valueClassName?: string;
  /** Classes for the "of recorded" basis qualifier. */
  suffixClassName?: string;
}

/**
 * UIA-001: shared presentation for the app's recorded-only attendance
 * percentage. The calculation lives in the backend and counts only recorded
 * sessions (pending is never treated as absent); every headline rendering of
 * that percentage pairs it with an explicit "of recorded" basis qualifier so
 * "83%" next to "280 pending" can never read as 83% of all sessions.
 *
 * This is presentation only — it never recomputes attendance.
 */
export function RecordedPct({ value, valueClassName, suffixClassName }: RecordedPctProps) {
  const hasValue = value !== null && value !== undefined && !Number.isNaN(value);
  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-1.5">
      <span className={valueClassName}>{formatPct(value)}</span>
      {hasValue && (
        <span className={suffixClassName}>of recorded</span>
      )}
    </span>
  );
}
