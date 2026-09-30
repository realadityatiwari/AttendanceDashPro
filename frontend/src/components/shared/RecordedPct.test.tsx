import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RecordedPct } from "./RecordedPct";

/**
 * UIA-001 regression coverage: every headline rendering of the app's
 * recorded-only attendance percentage must (a) keep the backend value
 * unchanged and (b) carry an explicit "of recorded" basis qualifier — except
 * the zero-record state, which renders an em dash with no percentage at all.
 */
describe("RecordedPct", () => {
  it("renders a normal recorded-only percentage with its basis qualifier", () => {
    // 5 present / 1 absent / 280 pending → backend pct 83.333…
    render(<RecordedPct value={83.333} />);
    expect(screen.getByText("83%")).toBeInTheDocument();
    expect(screen.getByText("of recorded")).toBeInTheDocument();
  });

  it("keeps the mathematical value unchanged (rounding only, as before)", () => {
    render(<RecordedPct value={72.6} />);
    expect(screen.getByText("73%")).toBeInTheDocument();
  });

  it("renders 100% recorded with the basis qualifier", () => {
    render(<RecordedPct value={100} />);
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText("of recorded")).toBeInTheDocument();
  });

  it("renders 0% recorded with the basis qualifier", () => {
    render(<RecordedPct value={0} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("of recorded")).toBeInTheDocument();
  });

  it("renders an em dash and NO basis qualifier when nothing is recorded", () => {
    render(<RecordedPct value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("of recorded")).not.toBeInTheDocument();
    // A zero-record student must never see a percentage that could be read
    // as poor attendance.
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("treats undefined the same as null", () => {
    render(<RecordedPct value={undefined} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("of recorded")).not.toBeInTheDocument();
  });
});
