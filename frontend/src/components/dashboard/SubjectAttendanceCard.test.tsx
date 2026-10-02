import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SubjectAttendanceCard } from "./SubjectAttendanceCard";
import type { AnalyticsSubjectItem, SubjectResponse } from "@/types/api";
import { SubjectCategory } from "@/types/api";

const subject: SubjectResponse = {
  id: "s1",
  code: "CSE301",
  name: "Operating Systems",
  tag: null,
  category: SubjectCategory.THEORY,
  quiz_applicable: true,
  attendance_applicable: true,
};

const summary: AnalyticsSubjectItem = {
  subject_code: "CSE301",
  subject_name: "Operating Systems",
  lecture: { total: 10, attended: 8, missed: 2, pending: 0 },
  tutorial: { total: 4, attended: 3, missed: 1, pending: 0 },
  practical: { total: 0, attended: 0, missed: 0, pending: 0 },
  current_lecture_pct: 80,
  current_tutorial_pct: 75,
  current_avg_pct: 78.6,
  forecast_lecture_pct: 80,
  forecast_tutorial_pct: 75,
  forecast_avg_pct: 78.6,
  current_practical_pct: null,
  forecast_practical_pct: null,
  optimization: null,
  required_pct: 75,
  status: "SAFE",
  health: "HEALTHY",
  mid_sem_session_id: null,
  mid_sem_session_date: null,
};

/**
 * UIA-004/UIA-018 regression coverage: the subject card uses the shared
 * Progress primitive (size md) and no longer repeats the pooled formula as
 * per-card body text.
 */
describe("UIA-004/UIA-018: SubjectAttendanceCard", () => {
  it("uses the shared progress primitive at the md size", () => {
    const { container } = render(<SubjectAttendanceCard subject={subject} summary={summary} />);
    const track = container.querySelector('[data-slot="progress-track"]');
    expect(track).toBeInTheDocument();
    expect(track).toHaveClass("h-1.5");
    expect(track).toHaveClass("bg-muted-foreground/20");
  });

  it("does not repeat the formula on the card", () => {
    render(<SubjectAttendanceCard subject={subject} summary={summary} />);
    expect(screen.queryByText(/combined attendance/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/formula/i)).not.toBeInTheDocument();
  });

  it("keeps the recorded-only basis explanation in the expanded details", () => {
    render(<SubjectAttendanceCard subject={subject} summary={summary} />);
    fireEvent.click(screen.getByRole("button", { name: /view details/i }));
    expect(
      screen.getByText(/percentages are current and recorded-only/i)
    ).toBeInTheDocument();
  });
});
