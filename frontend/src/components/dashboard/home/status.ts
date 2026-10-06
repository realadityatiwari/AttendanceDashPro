import { DashboardClassStatus, AttendanceStatusLabel } from "@/types/api";
import {
  getSessionStatus,
  getSubjectHealthStatus,
  type BadgeVariant,
} from "@/lib/canonicalStatus";

export function classStatusVariant(status: DashboardClassStatus): BadgeVariant {
  return getSessionStatus(status).variant;
}

export function classStatusLabel(status: DashboardClassStatus): string {
  // D-07: canonical attendance state vocabulary (Present/Absent/Pending/
  // Cancelled) — normalized in one place.
  return getSessionStatus(status).label;
}

export function attendanceStatusVariant(
  status: AttendanceStatusLabel | null
): BadgeVariant {
  return getSubjectHealthStatus(status).variant;
}

// 25.UX-1: the dashboard's classTypeLabel is gone — consumers use the ONE
// canonical contract (lib/canonicalStatus), which returns null for unknown
// class types instead of guessing a default.
// 25.UX-3: the dashboard's eventTypeLabel is gone too — event-type labels
// flow through the canonical humanizeEventType.
