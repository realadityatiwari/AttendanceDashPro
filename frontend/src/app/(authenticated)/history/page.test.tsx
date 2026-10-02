import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import HistoryPage from "./page";

// The factory runs once, so the payload object stays referentially stable
// across renders (a fresh object per render would loop the page's setRows
// effect).
vi.mock("@/hooks/useApi", () => {
  const profile = {
    semester_name: null,
    semester_start: "2026-07-15",
    semester_end: "2026-12-31",
  };
  const history = {
    items: [
      {
        id: "h1",
        date: "2026-10-05",
        start_time: "10:00",
        end_time: "10:50",
        subject_code: "CSE301",
        subject_name: "Operating Systems",
        class_type: "L", // ClassType.LECTURE (API value)
        status: "Attended", // AttendanceStatus.ATTENDED (API value)
        is_cancelled: false,
        is_extra: false,
        designation: null,
        marked_at: "2026-10-05T02:09:00Z",
      },
    ],
    total_count: 1,
    summary: { total: 1, attended: 1, missed: 0, pending: 0, cancelled: 0, pct: 100 },
    semester_start: "2026-07-15",
    semester_end: "2026-12-31",
  };
  return {
    useProfile: () => ({ profile }),
    useSubjects: () => ({ subjects: [] }),
    useAttendanceHistory: () => ({
      history,
      isLoading: false,
      isError: false,
      mutate: vi.fn(),
    }),
  };
});

/**
 * UIA-026/UIA-027 regression coverage: History uses the user-facing "Status"
 * vocabulary and no longer surfaces the raw record-creation timestamp. The
 * semantic date-range subtitle and the date companion strategy (UIA-025) are
 * also asserted.
 */
describe("UIA-026/UIA-027: History metadata and status vocabulary", () => {
  it("labels the status filter with the page's status vocabulary", () => {
    render(<HistoryPage />);
    expect(screen.getByText("Status", { selector: "label" })).toBeInTheDocument();
    expect(screen.getByText("All statuses")).toBeInTheDocument();
    expect(screen.queryByText("All states")).not.toBeInTheDocument();
  });

  it("does not render the internal 'Logged' record timestamp", () => {
    render(<HistoryPage />);
    expect(screen.queryByText(/logged/i)).not.toBeInTheDocument();
    // The session time (student-facing) remains.
    expect(screen.getByText("10:00")).toBeInTheDocument();
  });

  it("renders the semester range in the canonical human-readable format", () => {
    render(<HistoryPage />);
    expect(screen.getByText("15 Jul 2026 – 31 Dec 2026")).toBeInTheDocument();
  });

  it("pairs both native date filters with the formatted companion", () => {
    render(<HistoryPage />);
    expect(screen.getAllByText("Any date")).toHaveLength(2);
    expect(screen.getByLabelText("From")).toHaveAttribute("type", "date");
    expect(screen.getByLabelText("To")).toHaveAttribute("type", "date");
  });
});
