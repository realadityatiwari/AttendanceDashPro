import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import QuizEligibilityPage from "./page";

/**
 * UIA-041 regression coverage: the page defines the "Recoverable" status once,
 * in the explanatory info card, so a first-time visitor meets the badge with
 * its meaning (the per-card guidance callout keeps the actionable on-ramp).
 */

vi.mock("@/hooks/useApi", () => ({
  useSubjects: () => ({ subjects: [], isLoading: false, isError: false }),
  useCurrentQuizCycle: () => ({ currentCycle: null }),
}));

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
