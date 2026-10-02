import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WeeklyAttendanceCard } from "./WeeklyAttendanceCard";
import type { WeeklyAnalyticsItem, WeeklySection } from "@/types/api";

/**
 * UIA-036 regression coverage: a fully passed week describes its unrecorded
 * sessions as "unmarked" (they can no longer be marked), while the current
 * week keeps "pending"; the best/needs empty state is plain text, not a Badge.
 */

const weekly: WeeklySection = {
  week_start: "2026-09-28",
  week_end: "2026-10-04",
  days: [],
  weekly_pct: 100,
  recorded: 5,
  previous_week_pct: null,
  delta_pct: null,
  best_subject: null,
  needs_attention_subject: null,
};

const series: WeeklyAnalyticsItem[] = [
  { week_start: "2026-09-21", current_pct: null, attended: 0, recorded: 0, pending: 27 },
  { week_start: "2026-09-28", current_pct: 100, attended: 5, recorded: 5, pending: 21 },
];

describe("UIA-036: weekly card wording and empty state", () => {
  it("describes a passed week's unrecorded sessions as unmarked", () => {
    render(<WeeklyAttendanceCard weekly={weekly} series={series} />);
    expect(screen.getByText(/27 unmarked/)).toBeInTheDocument();
    expect(screen.queryByText(/27 pending/)).not.toBeInTheDocument();
  });

  it("keeps pending wording for the current week", () => {
    render(<WeeklyAttendanceCard weekly={weekly} series={series} />);
    expect(screen.getByText(/21 pending/)).toBeInTheDocument();
  });

  it("renders the empty best/needs state as plain text, not a badge", () => {
    render(<WeeklyAttendanceCard weekly={weekly} series={series} />);
    const empty = screen.getByText("No subjects with recorded attendance yet.");
    expect(empty.tagName).toBe("P");
    // Badge styling (pill radius + border) must not be applied to a sentence.
    expect(empty.className).not.toContain("rounded-4xl");
  });
});
