import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { OverallAttendanceCard } from "./OverallAttendanceCard";
import type { OverallSection } from "@/types/api";

describe("UIA-014: OverallAttendanceCard N/A State", () => {
  it("renders a clear N/A zero-record state without misleading danger or 0%", () => {
    const zeroRecordData: OverallSection = {
      overall_pct: null,
      attended: 0,
      recorded: 0,
      pending: 12,
      weekly_delta_pct: null,
      status: null,
      semester_start: "2026-01-01",
    };

    const { container } = render(
      <OverallAttendanceCard overall={zeroRecordData} />
    );

    // Percentage should be an em dash, NOT 0%
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();

    // Neutral N/A badge
    const badge = screen.getByText("N/A");
    expect(badge).toBeInTheDocument();

    // Friendly explanation of no recorded data and pending classes
    expect(screen.getByText(/no sessions recorded yet/i)).toBeInTheDocument();
    expect(
      screen.getByText(/12 upcoming scheduled/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/attendance tracking begins once your first class is marked/i)
    ).toBeInTheDocument();

    // Progress bar must have neutral variant and NOT danger/destructive
    const progressTrack = container.querySelector(
      "[data-slot=progress] [data-slot=progress-track]"
    );
    expect(progressTrack).toBeInTheDocument();
    const indicator = progressTrack?.querySelector("div");
    expect(indicator?.className).toContain("bg-muted-foreground");
    expect(indicator?.className).not.toContain("bg-destructive");
  });

  it("renders Healthy status with success variant for on-track student", () => {
    const healthyData: OverallSection = {
      overall_pct: 85,
      attended: 17,
      recorded: 20,
      pending: 5,
      weekly_delta_pct: 2.5,
      status: "SAFE",
      semester_start: "2026-01-01",
    };

    const { container } = render(
      <OverallAttendanceCard overall={healthyData} />
    );

    expect(screen.getByText(/85%/)).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();

    const indicator = container.querySelector(
      "[data-slot=progress-track] div"
    );
    expect(indicator?.className).toContain("bg-success");
  });

  it("renders At Risk status with warning variant for watch student (UIA-006 canonical mapping)", () => {
    const watchData: OverallSection = {
      overall_pct: 65,
      attended: 13,
      recorded: 20,
      pending: 5,
      weekly_delta_pct: -1.0,
      status: "WATCH",
      semester_start: "2026-01-01",
    };

    const { container } = render(
      <OverallAttendanceCard overall={watchData} />
    );

    expect(screen.getByText(/65%/)).toBeInTheDocument();
    expect(screen.getByText("At Risk")).toBeInTheDocument();

    const indicator = container.querySelector(
      "[data-slot=progress-track] div"
    );
    expect(indicator?.className).toContain("bg-warning");
  });

  it("renders Critical status with danger variant for critical student", () => {
    const criticalData: OverallSection = {
      overall_pct: 45,
      attended: 9,
      recorded: 20,
      pending: 5,
      weekly_delta_pct: -5.0,
      status: "CRITICAL",
      semester_start: "2026-01-01",
    };

    const { container } = render(
      <OverallAttendanceCard overall={criticalData} />
    );

    expect(screen.getByText(/45%/)).toBeInTheDocument();
    expect(screen.getByText("Critical")).toBeInTheDocument();

    const indicator = container.querySelector(
      "[data-slot=progress-track] div"
    );
    expect(indicator?.className).toContain("bg-destructive");
  });
});
