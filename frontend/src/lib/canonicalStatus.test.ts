import { describe, it, expect } from "vitest";
import {
  classTypeLabel,
  feedbackTypeBadgeClass,
  getSessionStatus,
  getSubjectHealthStatus,
  getQuizEligibilityStatus,
  quizCycleLabel,
  FEEDBACK_TYPES,
  humanizeEventType,
  ELECTIVE_SLOT_LABELS,
  SESSION_STATUS,
  SUBJECT_HEALTH_STATUS,
  QUIZ_STATUS,
} from "./canonicalStatus";
import {
  AttendanceStatus,
  ClassType,
  DashboardClassStatus,
  ElectiveSlot,
  EligibilityState,
} from "@/types/api";

describe("UIA-006: Canonical Status Vocabulary", () => {
  describe("SESSION status", () => {
    it("maps attended/present statuses to Present (success)", () => {
      expect(getSessionStatus(AttendanceStatus.ATTENDED)).toEqual(
        SESSION_STATUS.PRESENT
      );
      expect(getSessionStatus("Present")).toEqual(SESSION_STATUS.PRESENT);
      expect(getSessionStatus(DashboardClassStatus.ATTENDED)).toEqual(
        SESSION_STATUS.PRESENT
      );
    });

    it("maps missed/absent statuses to Absent (danger)", () => {
      expect(getSessionStatus(AttendanceStatus.MISSED)).toEqual(
        SESSION_STATUS.ABSENT
      );
      expect(getSessionStatus("Absent")).toEqual(SESSION_STATUS.ABSENT);
      expect(getSessionStatus(DashboardClassStatus.MISSED)).toEqual(
        SESSION_STATUS.ABSENT
      );
    });

    it("maps cancelled status to Cancelled (neutral)", () => {
      expect(getSessionStatus("Cancelled")).toEqual(SESSION_STATUS.CANCELLED);
      expect(getSessionStatus(DashboardClassStatus.CANCELLED)).toEqual(
        SESSION_STATUS.CANCELLED
      );
      expect(getSessionStatus(AttendanceStatus.ATTENDED, true)).toEqual(
        SESSION_STATUS.CANCELLED
      );
    });

    it("maps pending/null/unknown to Pending (outline)", () => {
      expect(getSessionStatus(AttendanceStatus.PENDING)).toEqual(
        SESSION_STATUS.PENDING
      );
      expect(getSessionStatus(null)).toEqual(SESSION_STATUS.PENDING);
      expect(getSessionStatus(undefined)).toEqual(SESSION_STATUS.PENDING);
    });
  });

  describe("SUBJECT HEALTH status", () => {
    it("maps SAFE and HEALTHY to Healthy (success)", () => {
      expect(getSubjectHealthStatus("SAFE")).toEqual(
        SUBJECT_HEALTH_STATUS.HEALTHY
      );
      expect(getSubjectHealthStatus("HEALTHY")).toEqual(
        SUBJECT_HEALTH_STATUS.HEALTHY
      );
    });

    it("maps WATCH and AT_RISK to At Risk (warning)", () => {
      expect(getSubjectHealthStatus("WATCH")).toEqual(
        SUBJECT_HEALTH_STATUS.AT_RISK
      );
      expect(getSubjectHealthStatus("AT_RISK")).toEqual(
        SUBJECT_HEALTH_STATUS.AT_RISK
      );
      expect(getSubjectHealthStatus("At Risk")).toEqual(
        SUBJECT_HEALTH_STATUS.AT_RISK
      );
    });

    it("maps CRITICAL to Critical (danger)", () => {
      expect(getSubjectHealthStatus("CRITICAL")).toEqual(
        SUBJECT_HEALTH_STATUS.CRITICAL
      );
    });

    it("maps null/undefined to N/A (neutral)", () => {
      expect(getSubjectHealthStatus(null)).toEqual(SUBJECT_HEALTH_STATUS.NA);
      expect(getSubjectHealthStatus(undefined)).toEqual(
        SUBJECT_HEALTH_STATUS.NA
      );
      expect(getSubjectHealthStatus("")).toEqual(SUBJECT_HEALTH_STATUS.NA);
    });
  });

  describe("QUIZ eligibility status", () => {
    it("maps ELIGIBLE to Eligible (success)", () => {
      expect(getQuizEligibilityStatus(EligibilityState.ELIGIBLE)).toEqual(
        QUIZ_STATUS.ELIGIBLE
      );
    });

    it("maps RECOVERABLE to Recoverable (warning)", () => {
      expect(getQuizEligibilityStatus(EligibilityState.RECOVERABLE)).toEqual(
        QUIZ_STATUS.RECOVERABLE
      );
    });

    it("maps NOT_ELIGIBLE to Not eligible (danger)", () => {
      expect(getQuizEligibilityStatus(EligibilityState.NOT_ELIGIBLE)).toEqual(
        QUIZ_STATUS.NOT_ELIGIBLE
      );
    });

    it("maps UNRESOLVED to Unscheduled (neutral)", () => {
      expect(getQuizEligibilityStatus(EligibilityState.UNRESOLVED)).toEqual(
        QUIZ_STATUS.UNSCHEDULED
      );
    });

    it("maps zero-recorded-data to No data yet (neutral) for scheduled quizzes", () => {
      expect(
        getQuizEligibilityStatus(EligibilityState.RECOVERABLE, true)
      ).toEqual(QUIZ_STATUS.NO_DATA);
      expect(
        getQuizEligibilityStatus(EligibilityState.NOT_ELIGIBLE, true)
      ).toEqual(QUIZ_STATUS.NO_DATA);
    });
  });
});

describe("25.UX-1: canonical presentation vocabularies", () => {
  describe("class type labels", () => {
    it("maps the known class types", () => {
      expect(classTypeLabel(ClassType.LECTURE)).toBe("Lecture");
      expect(classTypeLabel(ClassType.TUTORIAL)).toBe("Tutorial");
      expect(classTypeLabel(ClassType.PRACTICAL)).toBe("Practical");
      expect(classTypeLabel(ClassType.PRACTICAL2)).toBe("Practical");
    });

    it("returns null for unknown/missing class types (no guessed default)", () => {
      expect(classTypeLabel(null)).toBeNull();
      expect(classTypeLabel(undefined)).toBeNull();
      expect(classTypeLabel("SOMETHING_ELSE")).toBeNull();
    });
  });

  describe("quiz cycle labels", () => {
    it("maps cycle numbers and backend label shapes to Quiz I/II/III", () => {
      expect(quizCycleLabel(1)).toBe("Quiz I");
      expect(quizCycleLabel(2)).toBe("Quiz II");
      expect(quizCycleLabel(3)).toBe("Quiz III");
      expect(quizCycleLabel("Quiz1")).toBe("Quiz I");
      expect(quizCycleLabel("QUIZ_2")).toBe("Quiz II");
    });

    it("keeps the former fallback behavior for out-of-range and pre-labeled values", () => {
      expect(quizCycleLabel(4)).toBe("Quiz IV");
      expect(quizCycleLabel(11)).toBe("Quiz 11");
      expect(quizCycleLabel("Quiz IV")).toBe("Quiz IV");
      expect(quizCycleLabel(null)).toBe("Quiz");
    });
  });

  describe("feedback type vocabulary", () => {
    it("exposes the four canonical feedback types", () => {
      expect(FEEDBACK_TYPES.map((t) => t.value)).toEqual([
        "BUG",
        "SUGGESTION",
        "QUESTION",
        "PRAISE",
      ]);
    });

    it("maps feedback types to semantic-token badge classes", () => {
      expect(feedbackTypeBadgeClass("BUG")).toContain("text-destructive");
      expect(feedbackTypeBadgeClass("SUGGESTION")).toContain("text-warning");
      expect(feedbackTypeBadgeClass("QUESTION")).toContain("text-primary");
      expect(feedbackTypeBadgeClass("PRAISE")).toContain("text-success");
    });
  });
});

describe("25.UX-3: canonical academic label vocabularies", () => {
  it("humanizes event type enum values and unknown future types", () => {
    expect(humanizeEventType("SURPRISE_QUIZ")).toBe("Surprise Quiz");
    expect(humanizeEventType("CLASS_CANCELLED")).toBe("Class Cancelled");
    expect(humanizeEventType("SOME_FUTURE_TYPE")).toBe("Some Future Type");
  });

  it("uses the backend's Department Elective register for the DE slots", () => {
    expect(ELECTIVE_SLOT_LABELS[ElectiveSlot.ELECTIVE_I]).toBe(
      "Department Elective-I"
    );
    expect(ELECTIVE_SLOT_LABELS[ElectiveSlot.ELECTIVE_II]).toBe(
      "Department Elective-II"
    );
  });
});
