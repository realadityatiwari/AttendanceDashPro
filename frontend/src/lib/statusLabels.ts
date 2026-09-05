// Canonical student-facing status vocabulary (Phase 7, D-08).
//
// Backend enum values remain the domain truth; only presentation mappings
// live here. The dashboard/analytics surfaces emit the legacy bands
// SAFE/WATCH/CRITICAL; the per-subject Attendance Health set
// (HEALTHY/WATCH/AT_RISK/CRITICAL) already renders canonical labels in
// SubjectAttendanceCard. Both vocabularies use the same student-facing words.

const ATTENDANCE_STATUS_LABELS: Record<string, string> = {
  SAFE: "Healthy",
  WATCH: "Watch",
  CRITICAL: "Critical",
};

/** Maps a legacy attendance status (SAFE/WATCH/CRITICAL) to its
 * student-facing label (Healthy/Watch/Critical). Unknown/null values fall
 * back to "N/A" so missing data stays explicit. */
export function attendanceStatusLabel(
  status: string | null | undefined
): string {
  if (!status) return "N/A";
  return ATTENDANCE_STATUS_LABELS[status] ?? status;
}

// Weekly trend bar thresholds (UI-013). PRESENTATION ONLY — the values mirror
// the backend's legacy bands (backend/app/engines/attendance_engine.py:
// SAFE_BAND_PCT = ATTENDANCE_TARGET_PCT + 5 = 80; WATCH_BAND_PCT =
// ATTENDANCE_TARGET_PCT - 15 = 60) so a week's bar color agrees with the
// status the backend would assign to it. No threshold is changed here; the
// backend remains the sole authority on attendance status.
export const WEEKLY_BAR_SAFE_PCT = 80;
export const WEEKLY_BAR_WATCH_PCT = 60;
