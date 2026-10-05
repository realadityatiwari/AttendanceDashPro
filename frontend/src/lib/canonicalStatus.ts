import {
  AlertCircle,
  AlertTriangle,
  Ban,
  CheckCircle2,
  Clock,
  HelpCircle,
  XCircle,
} from "lucide-react";
import type { ComponentType } from "react";
import {
  AttendanceStatus,
  ClassType,
  DashboardClassStatus,
  EligibilityState,
  FeedbackType,
  type AttendanceStatusLabel,
} from "@/types/api";

export type BadgeVariant =
  | "success"
  | "warning"
  | "danger"
  | "neutral"
  | "outline";

export interface StatusPresentation {
  label: string;
  variant: BadgeVariant;
  icon?: ComponentType<{ className?: string }>;
}

// ---------------------------------------------------------------------------
// 1. SESSION STATUS (Present, Absent, Pending, Cancelled)
// ---------------------------------------------------------------------------
export type SessionStateKey = "PRESENT" | "ABSENT" | "PENDING" | "CANCELLED";

export const SESSION_STATUS: Record<SessionStateKey, StatusPresentation> = {
  PRESENT: {
    label: "Present",
    variant: "success",
    icon: CheckCircle2,
  },
  ABSENT: {
    label: "Absent",
    variant: "danger",
    icon: XCircle,
  },
  PENDING: {
    label: "Pending",
    variant: "outline",
    icon: Clock,
  },
  CANCELLED: {
    label: "Cancelled",
    variant: "neutral",
    icon: Ban,
  },
};

/**
 * Normalizes any session attendance status (AttendanceStatus enum, DashboardClassStatus enum,
 * or raw strings from attendance/history endpoints) into the canonical 4-state session vocabulary.
 */
export function getSessionStatus(
  status: AttendanceStatus | DashboardClassStatus | string | null | undefined,
  isCancelled = false
): StatusPresentation {
  if (isCancelled) return SESSION_STATUS.CANCELLED;
  if (!status) return SESSION_STATUS.PENDING;

  const normalized = String(status).toUpperCase();
  if (
    normalized === "PRESENT" ||
    normalized === "ATTENDED" ||
    normalized === AttendanceStatus.ATTENDED.toUpperCase()
  ) {
    return SESSION_STATUS.PRESENT;
  }
  if (
    normalized === "ABSENT" ||
    normalized === "MISSED" ||
    normalized === AttendanceStatus.MISSED.toUpperCase()
  ) {
    return SESSION_STATUS.ABSENT;
  }
  if (normalized === "CANCELLED" || normalized === "CANCELED") {
    return SESSION_STATUS.CANCELLED;
  }
  return SESSION_STATUS.PENDING;
}

// ---------------------------------------------------------------------------
// 2. SUBJECT HEALTH STATUS (Healthy, At Risk, Critical)
// ---------------------------------------------------------------------------
export type SubjectHealthKey = "HEALTHY" | "AT_RISK" | "CRITICAL" | "NA";

export const SUBJECT_HEALTH_STATUS: Record<SubjectHealthKey, StatusPresentation> = {
  HEALTHY: {
    label: "Healthy",
    variant: "success",
    icon: CheckCircle2,
  },
  AT_RISK: {
    label: "At Risk",
    variant: "warning",
    icon: AlertTriangle,
  },
  CRITICAL: {
    label: "Critical",
    variant: "danger",
    icon: AlertCircle,
  },
  NA: {
    label: "N/A",
    variant: "neutral",
  },
};

/**
 * Normalizes subject health or legacy banding (SAFE/WATCH/CRITICAL/HEALTHY/AT_RISK)
 * into the canonical 3-state health vocabulary: Healthy, At Risk, Critical.
 */
export function getSubjectHealthStatus(
  status: AttendanceStatusLabel | string | null | undefined
): StatusPresentation {
  if (!status) return SUBJECT_HEALTH_STATUS.NA;

  const normalized = String(status).toUpperCase();
  if (normalized === "SAFE" || normalized === "HEALTHY") {
    return SUBJECT_HEALTH_STATUS.HEALTHY;
  }
  if (normalized === "WATCH" || normalized === "AT_RISK" || normalized === "AT RISK") {
    return SUBJECT_HEALTH_STATUS.AT_RISK;
  }
  if (normalized === "CRITICAL") {
    return SUBJECT_HEALTH_STATUS.CRITICAL;
  }
  return SUBJECT_HEALTH_STATUS.NA;
}

// ---------------------------------------------------------------------------
// 3. QUIZ ELIGIBILITY STATUS (Eligible, Recoverable, Not eligible, Unscheduled)
// ---------------------------------------------------------------------------
export type QuizStateKey =
  | "ELIGIBLE"
  | "RECOVERABLE"
  | "NOT_ELIGIBLE"
  | "UNSCHEDULED"
  | "NO_DATA";

export const QUIZ_STATUS: Record<QuizStateKey, StatusPresentation> = {
  ELIGIBLE: {
    label: "Eligible",
    variant: "success",
    icon: CheckCircle2,
  },
  RECOVERABLE: {
    label: "Recoverable",
    variant: "warning",
    icon: AlertTriangle,
  },
  NOT_ELIGIBLE: {
    label: "Not eligible",
    variant: "danger",
    icon: XCircle,
  },
  UNSCHEDULED: {
    label: "Unscheduled",
    variant: "neutral",
    icon: HelpCircle,
  },
  NO_DATA: {
    label: "No data yet",
    variant: "neutral",
    icon: HelpCircle,
  },
};

/**
 * Normalizes quiz eligibility status into canonical presentation vocabulary.
 * If hasZeroRecordedData is true, maps to a neutral "No data yet" status rather than FAIL/NOT ELIGIBLE (UIA-028).
 */
export function getQuizEligibilityStatus(
  state: EligibilityState | string | null | undefined,
  hasZeroRecordedData = false
): StatusPresentation {
  if (!state) return QUIZ_STATUS.UNSCHEDULED;

  const normalized = String(state).toUpperCase();
  if (
    normalized === EligibilityState.UNRESOLVED ||
    normalized === "UNRESOLVED" ||
    normalized === "UNSCHEDULED"
  ) {
    return QUIZ_STATUS.UNSCHEDULED;
  }

  if (hasZeroRecordedData) {
    return QUIZ_STATUS.NO_DATA;
  }

  if (normalized === EligibilityState.ELIGIBLE || normalized === "ELIGIBLE") {
    return QUIZ_STATUS.ELIGIBLE;
  }
  if (normalized === EligibilityState.RECOVERABLE || normalized === "RECOVERABLE") {
    return QUIZ_STATUS.RECOVERABLE;
  }
  if (
    normalized === EligibilityState.NOT_ELIGIBLE ||
    normalized === "NOT_ELIGIBLE" ||
    normalized === "NOT ELIGIBLE"
  ) {
    return QUIZ_STATUS.NOT_ELIGIBLE;
  }

  return {
    label: "Unknown",
    variant: "neutral",
  };
}

// ---------------------------------------------------------------------------
// 4. CLASS TYPE (Lecture, Tutorial, Practical)
// ---------------------------------------------------------------------------
/**
 * Canonical class-type label. Null for values without a display label
 * (unknown/legacy) so callers can skip rendering instead of showing a wrong
 * default. This is the ONE class-type label contract — the dashboard's
 * status.ts helper and the events module both delegate here (25.UX-1).
 */
export function classTypeLabel(
  type: ClassType | string | null | undefined
): string | null {
  if (type === ClassType.LECTURE) return "Lecture";
  if (type === ClassType.TUTORIAL) return "Tutorial";
  if (type === ClassType.PRACTICAL || type === ClassType.PRACTICAL2) {
    return "Practical";
  }
  return null;
}

// ---------------------------------------------------------------------------
// 5. QUIZ CYCLE LABELS (Quiz I, Quiz II, Quiz III)
// ---------------------------------------------------------------------------
const QUIZ_CYCLE_ROMAN = [
  "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
];

/**
 * Canonical quiz-cycle label from any backend shape: 1/2/3, "Quiz1",
 * "QUIZ_2" → "Quiz I/II/III". Values beyond the roman table fall back to the
 * bare number; already-humanized labels pass through unchanged.
 */
export function quizCycleLabel(
  cycle: number | string | null | undefined
): string {
  if (cycle === null || cycle === undefined || cycle === "") return "Quiz";
  if (typeof cycle === "number") {
    return `Quiz ${QUIZ_CYCLE_ROMAN[cycle - 1] ?? cycle}`;
  }
  const match = String(cycle).match(/(\d+)/);
  if (match) {
    const n = Number(match[1]);
    return `Quiz ${QUIZ_CYCLE_ROMAN[n - 1] ?? n}`;
  }
  return String(cycle);
}

// ---------------------------------------------------------------------------
// 6. FEEDBACK TYPE (Bug, Suggestion, Question, Praise)
// ---------------------------------------------------------------------------
/** Canonical feedback-type vocabulary, shared by the feedback form (student)
 * and the feedback review surface (admin) so the labels can never drift. */
export const FEEDBACK_TYPES: ReadonlyArray<{
  value: FeedbackType;
  label: string;
}> = [
  { value: "BUG", label: "Bug" },
  { value: "SUGGESTION", label: "Suggestion" },
  { value: "QUESTION", label: "Question" },
  { value: "PRAISE", label: "Praise" },
];

/** Semantic-token badge classes for a feedback type. */
export function feedbackTypeBadgeClass(type: FeedbackType): string {
  switch (type) {
    case "BUG":
      return "bg-destructive/10 text-destructive";
    case "SUGGESTION":
      return "bg-warning/10 text-warning";
    case "QUESTION":
      return "bg-primary/10 text-primary";
    case "PRAISE":
      return "bg-success/10 text-success";
  }
}
