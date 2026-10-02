import { describe, it, expect } from "vitest";
import {
  formatDateMedium,
  formatDateRange,
  formatLongDate,
  formatShortDate,
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
