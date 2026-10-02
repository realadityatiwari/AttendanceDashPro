// Canonical student-facing status vocabulary (Phase 7, D-08; consolidated in
// UIA-006). Presentation only — backend enum values remain the domain truth.
//
// The dashboard/analytics surfaces emit the legacy bands SAFE/WATCH/CRITICAL;
// every other surface emits HEALTHY/WATCH/AT_RISK/CRITICAL. Both are
// normalized to the ONE canonical health vocabulary in `lib/canonicalStatus`:
// Healthy / At Risk / Critical / N/A. No per-surface label map lives here.

import { getSubjectHealthStatus, type BadgeVariant } from "@/lib/canonicalStatus";

/** Maps a legacy attendance status (SAFE/WATCH/CRITICAL) to its canonical
 * student-facing label (Healthy/At Risk/Critical). Unknown/null values fall
 * back to "N/A" so missing data stays explicit. */
export function attendanceStatusLabel(
  status: string | null | undefined
): string {
  return getSubjectHealthStatus(status).label;
}

/** Canonical badge variant for the same legacy attendance status. */
export function attendanceStatusVariant(
  status: string | null | undefined
): BadgeVariant {
  return getSubjectHealthStatus(status).variant;
}

// Weekly trend bar thresholds (UI-013). PRESENTATION ONLY — the values mirror
// the backend's legacy bands (backend/app/engines/attendance_engine.py:
// SAFE_BAND_PCT = ATTENDANCE_TARGET_PCT + 5 = 80; WATCH_BAND_PCT =
// ATTENDANCE_TARGET_PCT - 15 = 60) so a week's bar color agrees with the
// status the backend would assign to it. No threshold is changed here; the
// backend remains the sole authority on attendance status.
export const WEEKLY_BAR_SAFE_PCT = 80;
export const WEEKLY_BAR_WATCH_PCT = 60;
