import { ClassType, DashboardClassStatus, AttendanceStatusLabel } from "@/types/api";

export function classStatusVariant(
  status: DashboardClassStatus
): "success" | "danger" | "neutral" | "outline" {
  switch (status) {
    case DashboardClassStatus.ATTENDED:
      return "success";
    case DashboardClassStatus.MISSED:
      return "danger";
    case DashboardClassStatus.CANCELLED:
      return "neutral";
    default:
      return "outline";
  }
}

export function classStatusLabel(status: DashboardClassStatus): string {
  switch (status) {
    case DashboardClassStatus.ATTENDED:
      return "Attended";
    case DashboardClassStatus.MISSED:
      return "Missed";
    case DashboardClassStatus.CANCELLED:
      return "Cancelled";
    default:
      return "Attendance pending";
  }
}

export function attendanceStatusVariant(
  status: AttendanceStatusLabel | null
): "success" | "warning" | "danger" | "neutral" {
  switch (status) {
    case "SAFE":
      return "success";
    case "WATCH":
      return "warning";
    case "CRITICAL":
      return "danger";
    default:
      return "neutral";
  }
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