import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import DashboardPage from "./page";

/**
 * UIA-022 regression coverage: the first-use hint's dismiss control sits in
 * the card's top-right corner (Card is a column by default, so the hint uses
 * flex-row + justify-between) instead of floating below the text at the
 * bottom-left, and dismissing it is remembered.
 *
 * The dashboard's data cards are mocked: this test is scoped to the page's
 * own Getting Started branch (the cards have their own suites).
 */

const mockState = vi.hoisted(() => ({ recorded: 0 }));

vi.mock("@/hooks/useApi", () => ({
  useDashboardSummary: () => ({
    summary: { overall: { recorded: mockState.recorded } },
    isLoading: false,
    isError: false,
    mutate: vi.fn(),
  }),
  useAnalyticsOverview: () => ({
    overview: null,
    isError: false,
    mutate: vi.fn(),
  }),
}));

vi.mock("@/components/dashboard/home/GreetingHeader", () => ({
  GreetingHeader: () => null,
}));
vi.mock("@/components/dashboard/home/TodayAttendanceCard", () => ({
  TodayAttendanceCard: () => null,
  TodayAttendanceCardSkeleton: () => null,
}));
vi.mock("@/components/dashboard/home/OverallAttendanceCard", () => ({
  OverallAttendanceCard: () => null,
  OverallAttendanceCardSkeleton: () => null,
}));
vi.mock("@/components/dashboard/home/WeeklyAttendanceCard", () => ({
  WeeklyAttendanceCard: () => null,
  WeeklyAttendanceCardSkeleton: () => null,
}));
vi.mock("@/components/dashboard/home/QuizSnapshotCard", () => ({
  QuizSnapshotCard: () => null,
  QuizSnapshotCardSkeleton: () => null,
}));
vi.mock("@/components/dashboard/home/AttentionRequiredCard", () => ({
  AttentionRequiredCard: () => null,
  AttentionRequiredCardSkeleton: () => null,
}));
vi.mock("@/components/dashboard/home/UpcomingEventsCard", () => ({
  UpcomingEventsCard: () => null,
  UpcomingEventsCardSkeleton: () => null,
}));

const DISMISS_KEY = "adp_getting_started_dismissed";

beforeEach(() => {
  mockState.recorded = 0;
  window.localStorage.clear();
});

describe("UIA-022: Getting Started dismiss placement", () => {
  it("pins the dismiss control to the hint card's top-right", () => {
    render(<DashboardPage />);

    expect(screen.getByText("Getting started")).toBeInTheDocument();

    const dismiss = screen.getByRole("button", {
      name: /dismiss getting started hint/i,
    });
    const card = dismiss.closest('[data-slot="card"]');
    expect(card?.className).toContain("flex-row");
    expect(card?.className).toContain("justify-between");
    expect(dismiss.className).toContain("shrink-0");
  });

  it("dismisses the hint and remembers the choice", () => {
    render(<DashboardPage />);
    fireEvent.click(
      screen.getByRole("button", { name: /dismiss getting started hint/i })
    );

    expect(screen.queryByText("Getting started")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(DISMISS_KEY)).toBe("1");
  });

  it("hides the hint once the account has recorded sessions", () => {
    mockState.recorded = 5;
    render(<DashboardPage />);
    expect(screen.queryByText("Getting started")).not.toBeInTheDocument();
  });
});
