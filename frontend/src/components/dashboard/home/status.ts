import { ClassType, DashboardClassStatus, AttendanceStatusLabel } from "@/types/api";
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

export function classTypeLabel(classType: ClassType): string {
  switch (classType) {
    case ClassType.LECTURE:
      return "Lecture";
    case ClassType.TUTORIAL:
      return "Tutorial";
    default:
      return "Practical";
  }
}

export function eventTypeLabel(eventType: string): string {
  return eventType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}
