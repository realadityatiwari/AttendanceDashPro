import { describe, it, expect } from "vitest";
import {
  formatDateMedium,
  formatDateParts,
  formatDateRange,
  formatLongDate,
  formatMonthYear,
  formatShortDate,
  formatTimestampDate,
  formatTime,
  formatWeekdayDate,
  getMonthName,
} from "./date";

describe("date formatting (UIA-011 regression)", () => {
  it("formats dates in medium canonical format: D Mon YYYY", () => {
    expect(formatDateMedium("2026-09-29")).toBe("29 Sep 2026");
    expect(formatDateMedium("2026-10-04")).toBe("4 Oct 2026");
    expect(formatDateMedium("2026-01-01")).toBe("1 Jan 2026");
  });

  it("formats date ranges with an en-dash: 'Start – End'", () => {
    expect(formatDateRange("2026-09-28", "2026-10-04")).toBe(
      "28 Sep 2026 – 4 Oct 2026"
    );
    expect(formatDateRange("2026-07-15", "2026-12-31")).toBe(
      "15 Jul 2026 – 31 Dec 2026"
    );
  });

  it("formats long date with weekday and dot separator", () => {
    expect(formatLongDate("2026-09-29")).toBe("Tuesday · 29 Sep 2026");
  });

  it("formats short date as day and uppercase month", () => {
    expect(formatShortDate("2026-09-29")).toBe("29 SEP");
  });
});

describe("25.UX-1: canonical month/part/timestamp formatting", () => {
  it("formats the full month name and month-year header", () => {
    expect(getMonthName("2026-01-01")).toBe("January");
    expect(getMonthName("2026-10-05")).toBe("October");
    expect(formatMonthYear("2026-10-05")).toBe("October 2026");
    expect(formatMonthYear(new Date(2026, 8, 29))).toBe("September 2026");
  });

  it("formats structured tile parts without splitting formatted output", () => {
    expect(formatDateParts("2026-09-29")).toEqual({ day: "29", month: "SEP" });
    expect(formatDateParts("2026-10-04")).toEqual({ day: "4", month: "OCT" });
  });

  it("formats weekday + date without the dot separator", () => {
    expect(formatWeekdayDate("2026-09-29")).toBe("Tuesday 29 Sep 2026");
  });

  it("formats backend timestamps by their local calendar date", () => {
    // No timezone suffix → parsed as local time, so the calendar date is
    // stable in every environment.
    expect(formatTimestampDate("2026-10-05T14:23:45")).toBe("5 Oct 2026");
    // Date-only strings keep the local-calendar contract.
    expect(formatTimestampDate("2026-10-05")).toBe("5 Oct 2026");
    // Unparseable input renders an em dash — never silently today's date.
    expect(formatTimestampDate("not-a-date")).toBe("—");
  });
});

describe("25.UX-3: canonical time-of-day formatting", () => {
  it("renders backend HH:MM:SS times as 24h HH:MM", () => {
    expect(formatTime("09:30:00")).toBe("09:30");
    expect(formatTime("14:05:00")).toBe("14:05");
    expect(formatTime("9:30:00")).toBe("09:30");
  });

  it("never invents a time: empty/null passes through empty, unknown shapes pass through raw", () => {
    expect(formatTime(null)).toBe("");
    expect(formatTime(undefined)).toBe("");
    expect(formatTime("")).toBe("");
    expect(formatTime("not-a-time")).toBe("not-a-time");
  });
});
