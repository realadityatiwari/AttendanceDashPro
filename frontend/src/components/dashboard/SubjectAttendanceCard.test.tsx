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

const labSubject: SubjectResponse = {
  id: "s2",
  code: "BCS-351",
  name: "DBMS Lab",
  tag: null,
  category: SubjectCategory.LAB,
  quiz_applicable: false,
  attendance_applicable: true,
};

const labSummary: AnalyticsSubjectItem = {
  ...summary,
  subject_code: "BCS-351",
  subject_name: "DBMS Lab",
  practical: { total: 9, attended: 6, missed: 1, pending: 2 },
  current_practical_pct: 85.7,
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

/**
 * UIA-037/UIA-044 regression coverage: expanded detail rows use the canonical
 * "absent" wording, and lab cards only render the mid-sem row once a session
 * is actually designated (no inert "Not scheduled" line on every lab card).
 */
describe("UIA-037/UIA-044: detail vocabulary and mid-sem noise", () => {
  it("labels missed sessions as absent in the expanded details", () => {
    render(<SubjectAttendanceCard subject={subject} summary={summary} />);
    fireEvent.click(screen.getByRole("button", { name: /view details/i }));
    expect(screen.getByText(/· 2 absent/)).toBeInTheDocument();
    expect(screen.queryByText(/· 2 missed/)).not.toBeInTheDocument();
  });

  it("omits the mid-sem row on an unscheduled lab card", () => {
    render(<SubjectAttendanceCard subject={labSubject} summary={labSummary} />);
    expect(screen.getByText("Practical sessions attended")).toBeInTheDocument();
    expect(screen.queryByText("Mid-Sem Practical")).not.toBeInTheDocument();
    expect(screen.queryByText("Not scheduled")).not.toBeInTheDocument();
  });

  it("renders the mid-sem row once a session is designated", () => {
    render(
      <SubjectAttendanceCard
        subject={labSubject}
        summary={{ ...labSummary, mid_sem_session_date: "2026-11-03" }}
      />
    );
    expect(screen.getByText("Mid-Sem Practical")).toBeInTheDocument();
    expect(screen.getByText("3 Nov 2026")).toBeInTheDocument();
  });
});

/**
 * 25.UX-1 regression: health labels flow from the canonical vocabulary —
 * backend WATCH renders the canonical "At Risk" (never "Watch"), while the
 * preserved Phase 8.2 per-band visual mapping keeps WATCH on the warning
 * token and CRITICAL on the solid destructive treatment.
 */
describe("25.UX-1: canonical health labels", () => {
  it("renders backend WATCH as the canonical At Risk label on the warning token", () => {
    render(
      <SubjectAttendanceCard
        subject={subject}
        summary={{ ...summary, health: "WATCH" }}
      />
    );
    const badge = screen.getByText("At Risk");
    expect(badge.className).toContain("text-warning");
    expect(screen.queryByText("Watch")).not.toBeInTheDocument();
  });

  it("renders backend HEALTHY as Healthy", () => {
    render(<SubjectAttendanceCard subject={subject} summary={summary} />);
    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });

  it("keeps CRITICAL on the solid destructive treatment", () => {
    render(
      <SubjectAttendanceCard
        subject={subject}
        summary={{ ...summary, health: "CRITICAL" }}
      />
    );
    const badge = screen.getByText("Critical");
    expect(badge.className).toContain("bg-destructive");
    expect(badge.className).toContain("text-destructive-foreground");
  });
});
