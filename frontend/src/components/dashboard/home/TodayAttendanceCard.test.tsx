import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TodayAttendanceCard } from "./TodayAttendanceCard";
import type { TodaySection } from "@/types/api";

/**
 * UIA-019 regression coverage: the badge names the state it actually
 * represents ("Teaching day") instead of the misleading "LIVE".
 */
function today(overrides: Partial<TodaySection> = {}): TodaySection {
  return {
    date: "2026-10-01",
    is_working_day: true,
    is_teaching_day: true,
    day_note: null,
    classes: [],
    attended: 0,
    total: 0,
    ...overrides,
  };
}

describe("UIA-019: Today's Attendance badge wording", () => {
  it("shows 'Teaching day' and never 'LIVE' on a working teaching day", () => {
    render(<TodayAttendanceCard today={today()} />);
    expect(screen.getByText("Teaching day")).toBeInTheDocument();
    expect(screen.queryByText("LIVE")).not.toBeInTheDocument();
  });

  it("shows 'Teaching day' on a non-working teaching day too", () => {
    render(<TodayAttendanceCard today={today({ is_working_day: false })} />);
    expect(screen.getByText("Teaching day")).toBeInTheDocument();
    expect(screen.queryByText("LIVE")).not.toBeInTheDocument();
  });

  it("renders no day badge when the day is not a teaching day", () => {
    render(
      <TodayAttendanceCard
        today={today({ is_teaching_day: false, is_working_day: false })}
      />
    );
    expect(screen.queryByText("Teaching day")).not.toBeInTheDocument();
    expect(screen.queryByText("LIVE")).not.toBeInTheDocument();
  });
});
