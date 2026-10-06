import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import QuizEligibilityPage from "./page";

/**
 * UIA-041 regression coverage: the page defines the "Recoverable" status once,
 * in the explanatory info card, so a first-time visitor meets the badge with
 * its meaning (the per-card guidance callout keeps the actionable on-ramp).
 * 25.UX-4: the page-level failure state offers the same retry as every other
 * screen's error state.
 */

const { subjectsState, retryMock } = vi.hoisted(() => ({
  subjectsState: {
    subjects: undefined as unknown[] | undefined,
    isLoading: false,
    isError: false as boolean,
  },
  retryMock: vi.fn(),
}));

vi.mock("@/hooks/useApi", () => ({
  useSubjects: () => ({ ...subjectsState, mutate: retryMock }),
  useCurrentQuizCycle: () => ({ currentCycle: null }),
}));

beforeEach(() => {
  subjectsState.subjects = [];
  subjectsState.isLoading = false;
  subjectsState.isError = false;
  retryMock.mockClear();
});

describe("UIA-041: Recoverable badge definition", () => {
  it("explains what Recoverable means in the page info card", () => {
    render(<QuizEligibilityPage />);

    expect(
      screen.getByText(/still reach it before the quiz is labeled/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Recoverable")).toBeInTheDocument();
  });

  it("keeps the consolidated formula explanation intact", () => {
    render(<QuizEligibilityPage />);
    expect(screen.getByText(/\(lecture \+ tutorial present\)/)).toBeInTheDocument();
  });
});

describe("25.UX-4: page-level error retry", () => {
  it("offers a retry that re-triggers the subjects request", () => {
    subjectsState.isError = true;
    render(<QuizEligibilityPage />);
    const retry = screen.getByRole("button", { name: /try again/i });
    fireEvent.click(retry);
    expect(retryMock).toHaveBeenCalledTimes(1);
  });
});
