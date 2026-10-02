import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import LaboratoryPage from "./page";

vi.mock("@/hooks/useApi", () => ({
  useSubjects: () => ({
    subjects: [
      {
        id: "lab1",
        code: "BCS-351",
        name: "DBMS Lab",
        tag: null,
        category: "lab",
        quiz_applicable: false,
        attendance_applicable: true,
      },
    ],
    isLoading: false,
  }),
  useProfile: () => ({ profile: { role: "STUDENT" } }),
  useLabSummary: () => ({
    summary: {
      subject_code: "BCS-351",
      practical_attendance: {
        attended: 6,
        missed: 1,
        pending: 2,
        total: 9,
        current_practical_pct: 85.7,
      },
      mid_sem: { designated: false, session_id: null, session_date: null, attendance_status: null },
      experiment_progress: {
        catalog_available: true,
        total: 10,
        signed: 4,
        pending_self_tracked: 2,
        advisory: "4 of 10 experiments officially completed",
      },
    },
    isLoading: false,
    isError: false,
  }),
  useLabExperiments: () => ({ experiments: [], isLoading: false, isError: false, mutate: vi.fn() }),
  useLabRecords: () => ({ records: [], isLoading: false, isError: false, mutate: vi.fn() }),
  useLabActivity: () => ({ activity: { items: [] }, isLoading: false, isError: false }),
  useLabMutations: () => ({}),
}));

/**
 * UIA-043 regression coverage: the default Laboratory tab uses the
 * backend-provided experiment progress as a third full-width block, so the
 * page reads dense at desktop without inventing data or fixed heights.
 */
describe("UIA-043: Laboratory default-tab density", () => {
  it("renders the practical, mid-sem, and experiment-progress blocks", () => {
    render(<LaboratoryPage />);
    // Headings, not the identically named "Practical Attendance" tab button.
    expect(screen.getByRole("heading", { name: "Practical Attendance" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Mid-Semester Practical" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Experiment Progress" })).toBeInTheDocument();
  });

  it("surfaces the backend advisory and pending sign-off count", () => {
    render(<LaboratoryPage />);
    expect(screen.getByText("4 of 10 experiments officially completed")).toBeInTheDocument();
    expect(screen.getByText("2 awaiting sign-off")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view experiments/i })).toBeInTheDocument();
  });

  it("gives the experiment-progress block the full row width", () => {
    render(<LaboratoryPage />);
    const card = screen.getByText("Experiment Progress").closest('[data-slot="card"]');
    expect(card?.className).toContain("lg:col-span-2");
  });
});
