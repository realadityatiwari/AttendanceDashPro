import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QuizEligibilityCard } from "./QuizEligibilityCard";
import { EligibilityState, type EligibilityResult } from "@/types/api";

let mockEligibility: EligibilityResult | null = null;
const mockIsLoading = false;
const mockIsError: unknown = null;

vi.mock("@/hooks/useApi", () => ({
  useQuizEligibility: () => ({
    eligibility: mockEligibility,
    isLoading: mockIsLoading,
    isError: mockIsError,
    mutate: vi.fn(),
  }),
}));

describe("UIA-012 & UIA-028: QuizEligibilityCard redesign & zero-data handling", () => {
  it("UIA-028: renders neutral No Data state when student has zero recorded classes (never FAIL or NOT ELIGIBLE)", () => {
    mockEligibility = {
      quiz_cycle: 1,
      subject_code: "CSE301",
      subject_name: "Operating Systems",
      category: "THEORY",
      quiz_date: "2026-10-15",
      window_start: "2026-08-01",
      window_end: "2026-10-14",
      lecture_threshold: 75,
      combined_threshold: null,
      required_percentage: 75,
      lecture: { total: 0, attended: 0, missed: 0, pending: 8 },
      tutorial: { total: 0, attended: 0, missed: 0, pending: 0 },
      lecture_pct: null,
      tutorial_pct: null,
      average_pct: null,
      state: EligibilityState.RECOVERABLE,
      recoverable: true,
      criterion_i: {
        name: "Criterion I — Lecture + Tutorial Average",
        value: null,
        threshold: 75,
        passed: false,
        explanation: "0/0 attended in window",
      },
      criterion_ii: {
        name: "Criterion II — Lecture + Tutorial Average",
        value: null,
        threshold: 75,
        passed: false,
        explanation: "0/0 attended semester-wide",
      },
      final_criterion: {
        combination: "Criterion I or II",
        passed: false,
        explanation: "Neither criterion passed",
      },
      is_eligible: false,
      optimization: {
        lecture_deficit: 6,
        tutorial_deficit: 0,
        safe_skip_lecture: 0,
        safe_skip_tutorial: 0,
        is_reachable: true,
      },
      must_attend_criterion: "Criterion I",
      safe_skip_optimization: null,
      safe_skip_criterion: null,
      explanation: "No sessions recorded",
      policy_ambiguity_notes: null,
    };

    render(
      <QuizEligibilityCard
        subjectCode="CSE301"
        cycle={1}
        cycleLabel="Quiz I"
      />
    );

    // Header badge must be neutral "No data yet", NOT "NOT ELIGIBLE" or "FAIL"
    expect(screen.getByText("No data yet")).toBeInTheDocument();
    expect(screen.queryByText("NOT ELIGIBLE")).not.toBeInTheDocument();
    expect(screen.queryByText("FAIL")).not.toBeInTheDocument();

    // Guidance callout explains that data must be recorded
    expect(
      screen.getByText(/attendance needs to be recorded before eligibility can be determined/i)
    ).toBeInTheDocument();

    // In calculation view, criteria should show NO DATA rather than FAIL
    const viewCalcBtn = screen.getByRole("button", { name: /view calculation/i });
    fireEvent.click(viewCalcBtn);

    const noDataBadges = screen.getAllByText("NO DATA");
    expect(noDataBadges.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("NO DATA YET")).toBeInTheDocument();
  });

  it("UIA-012: renders clear action-oriented guidance for RECOVERABLE student", () => {
    mockEligibility = {
      quiz_cycle: 1,
      subject_code: "CSE302",
      subject_name: "Database Systems",
      category: "THEORY",
      quiz_date: "2026-10-20",
      window_start: "2026-08-01",
      window_end: "2026-10-19",
      lecture_threshold: 75,
      combined_threshold: null,
      required_percentage: 75,
      lecture: { total: 10, attended: 6, missed: 4, pending: 6 },
      tutorial: { total: 0, attended: 0, missed: 0, pending: 0 },
      lecture_pct: 60,
      tutorial_pct: null,
      average_pct: 60,
      state: EligibilityState.RECOVERABLE,
      recoverable: true,
      criterion_i: {
        name: "Criterion I — Lecture + Tutorial Average",
        value: 60,
        threshold: 75,
        passed: false,
        explanation: "6/10 attended in window",
      },
      criterion_ii: {
        name: "Criterion II — Lecture + Tutorial Average",
        value: 60,
        threshold: 75,
        passed: false,
        explanation: "6/10 attended semester-wide",
      },
      final_criterion: {
        combination: "Criterion I or II",
        passed: false,
        explanation: "Currently 60%, below 75%",
      },
      is_eligible: false,
      optimization: {
        lecture_deficit: 5,
        tutorial_deficit: 0,
        safe_skip_lecture: 0,
        safe_skip_tutorial: 0,
        is_reachable: true,
      },
      must_attend_criterion: "Criterion I",
      safe_skip_optimization: null,
      safe_skip_criterion: null,
      explanation: "Below 75%, recoverable by attending upcoming classes.",
      policy_ambiguity_notes: null,
    };

    render(
      <QuizEligibilityCard
        subjectCode="CSE302"
        cycle={1}
        cycleLabel="Quiz I"
      />
    );

    // Canonical badge: "Recoverable" (warning)
    expect(screen.getByText("Recoverable")).toBeInTheDocument();

    // Action-oriented callout directly tells student how many classes they need
    expect(
      screen.getByText(/you need to attend the next 5 lectures to qualify \(Criterion I\)/i)
    ).toBeInTheDocument();
  });

  it("UIA-012: renders clear safe-skip message for ELIGIBLE student", () => {
    mockEligibility = {
      quiz_cycle: 1,
      subject_code: "CSE303",
      subject_name: "Computer Networks",
      category: "THEORY",
      quiz_date: "2026-10-25",
      window_start: "2026-08-01",
      window_end: "2026-10-24",
      lecture_threshold: 75,
      combined_threshold: null,
      required_percentage: 75,
      lecture: { total: 12, attended: 11, missed: 1, pending: 6 },
      tutorial: { total: 0, attended: 0, missed: 0, pending: 0 },
      lecture_pct: 91.7,
      tutorial_pct: null,
      average_pct: 91.7,
      state: EligibilityState.ELIGIBLE,
      recoverable: false,
      criterion_i: {
        name: "Criterion I — Lecture + Tutorial Average",
        value: 91.7,
        threshold: 75,
        passed: true,
        explanation: "11/12 attended",
      },
      criterion_ii: {
        name: "Criterion II — Lecture + Tutorial Average",
        value: 91.7,
        threshold: 75,
        passed: true,
        explanation: "11/12 attended semester-wide",
      },
      final_criterion: {
        combination: "Criterion I or II",
        passed: true,
        explanation: "91.7% satisfies threshold",
      },
      is_eligible: true,
      optimization: {
        lecture_deficit: 0,
        tutorial_deficit: 0,
        safe_skip_lecture: 2,
        safe_skip_tutorial: 0,
        is_reachable: true,
      },
      must_attend_criterion: null,
      safe_skip_optimization: {
        lecture_deficit: 0,
        tutorial_deficit: 0,
        safe_skip_lecture: 2,
        safe_skip_tutorial: 0,
        is_reachable: true,
      },
      safe_skip_criterion: "Criterion I",
      explanation: "Eligible for Quiz I",
      policy_ambiguity_notes: null,
    };

    render(
      <QuizEligibilityCard
        subjectCode="CSE303"
        cycle={1}
        cycleLabel="Quiz I"
      />
    );

    // Canonical badge: "Eligible"
    expect(screen.getByText("Eligible")).toBeInTheDocument();

    // Guidance callout tells student safe-skip count
    expect(
      screen.getByText(/you can safely miss up to 2 lectures \(Criterion I\)/i)
    ).toBeInTheDocument();
  });

  it("renders Unscheduled for UNRESOLVED quiz schedule", () => {
    mockEligibility = {
      quiz_cycle: 2,
      subject_code: "CSE304",
      subject_name: "Algorithms",
      category: "THEORY",
      quiz_date: null,
      window_start: "",
      window_end: "",
      lecture_threshold: 75,
      combined_threshold: null,
      required_percentage: 75,
      lecture: { total: 0, attended: 0, missed: 0, pending: 0 },
      tutorial: { total: 0, attended: 0, missed: 0, pending: 0 },
      lecture_pct: null,
      tutorial_pct: null,
      average_pct: null,
      state: EligibilityState.UNRESOLVED,
      recoverable: false,
      criterion_i: null,
      criterion_ii: null,
      final_criterion: null,
      is_eligible: false,
      optimization: null,
      must_attend_criterion: null,
      safe_skip_optimization: null,
      safe_skip_criterion: null,
      explanation: "No confirmed schedule for this cycle yet.",
      policy_ambiguity_notes: null,
    };

    render(
      <QuizEligibilityCard
        subjectCode="CSE304"
        cycle={2}
        cycleLabel="Quiz II"
      />
    );

    expect(screen.getByText("Unscheduled")).toBeInTheDocument();
    expect(
      screen.getByText(/no confirmed schedule for this cycle yet/i)
    ).toBeInTheDocument();
  });

  it("renders Not eligible for genuinely in-deficit unreachable student", () => {
    mockEligibility = {
      quiz_cycle: 1,
      subject_code: "CSE305",
      subject_name: "Software Engineering",
      category: "THEORY",
      quiz_date: "2026-10-30",
      window_start: "2026-08-01",
      window_end: "2026-10-29",
      lecture_threshold: 75,
      combined_threshold: null,
      required_percentage: 75,
      lecture: { total: 16, attended: 2, missed: 14, pending: 1 },
      tutorial: { total: 0, attended: 0, missed: 0, pending: 0 },
      lecture_pct: 12.5,
      tutorial_pct: null,
      average_pct: 12.5,
      state: EligibilityState.NOT_ELIGIBLE,
      recoverable: false,
      criterion_i: {
        name: "Criterion I — Lecture + Tutorial Average",
        value: 12.5,
        threshold: 75,
        passed: false,
        explanation: "2/16 attended",
      },
      criterion_ii: {
        name: "Criterion II — Lecture + Tutorial Average",
        value: 12.5,
        threshold: 75,
        passed: false,
        explanation: "2/16 attended semester-wide",
      },
      final_criterion: {
        combination: "Criterion I or II",
        passed: false,
        explanation: "Cannot reach threshold",
      },
      is_eligible: false,
      optimization: {
        lecture_deficit: 8,
        tutorial_deficit: 0,
        safe_skip_lecture: 0,
        safe_skip_tutorial: 0,
        is_reachable: false,
      },
      must_attend_criterion: null,
      safe_skip_optimization: null,
      safe_skip_criterion: null,
      explanation: "The required 75% cannot be reached within the remaining attendance window.",
      policy_ambiguity_notes: null,
    };

    render(
      <QuizEligibilityCard
        subjectCode="CSE305"
        cycle={1}
        cycleLabel="Quiz I"
      />
    );

    // Canonical badge: "Not eligible"
    expect(screen.getByText("Not eligible")).toBeInTheDocument();
    expect(
      screen.getByText(/attendance requirement cannot be met within the remaining attendance window/i)
    ).toBeInTheDocument();
  });
});
