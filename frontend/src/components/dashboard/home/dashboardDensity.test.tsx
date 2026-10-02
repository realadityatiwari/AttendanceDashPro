import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { AttentionRequiredCard } from "./AttentionRequiredCard";
import { QuizSnapshotCard } from "./QuizSnapshotCard";
import type { QuizSnapshotSection } from "@/types/api";

/**
 * UIA-024 regression coverage: sparse dashboard cards distribute their
 * available height through the shared grid row instead of stranding a void.
 * (OverallAttendanceCard's zero-record state is covered by its own test.)
 */
describe("UIA-024: dashboard card density", () => {
  it("lets the Attention Required empty state fill and center in the row", () => {
    const { container } = render(<AttentionRequiredCard items={[]} />);
    const content = container.querySelector('[data-slot="card-content"]');
    expect(content?.className).toContain("flex-1");
    const emptyState = content?.firstElementChild as HTMLElement | null;
    expect(emptyState?.className).toContain("flex-1");
    expect(emptyState?.className).toContain("justify-center");
  });

  it("centers the Quiz Snapshot content in the shared row height", () => {
    const emptySnapshot: QuizSnapshotSection = {
      quiz_cycle: null,
      quiz_label: null,
      quiz_date: null,
      threshold: null,
      eligible: 0,
      attention: 0,
      not_eligible: 0,
      total_theory: 0,
      has_snapshot: false,
    };
    const { container } = render(<QuizSnapshotCard quiz={emptySnapshot} />);
    const content = container.querySelector('[data-slot="card-content"]');
    expect(content?.className).toContain("flex-1");
    expect(content?.className).toContain("justify-center");
  });

  it("centers the populated Quiz Snapshot content too", () => {
    const snapshot: QuizSnapshotSection = {
      quiz_cycle: 1,
      quiz_label: "Quiz1",
      quiz_date: "2026-10-15",
      threshold: 75,
      eligible: 3,
      attention: 1,
      not_eligible: 0,
      total_theory: 4,
      has_snapshot: true,
    };
    const { container } = render(<QuizSnapshotCard quiz={snapshot} />);
    const content = container.querySelector('[data-slot="card-content"]');
    expect(content?.className).toContain("flex-1");
    expect(content?.className).toContain("justify-center");
  });
});
