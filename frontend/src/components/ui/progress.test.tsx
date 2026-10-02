import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Progress } from "./progress";

/**
 * UIA-018 regression coverage: one progress primitive with explicit sizes and
 * semantic-token variants. The track must stay visible on cards (--muted
 * equals --card), and the neutral fill is reserved for zero-record states.
 */
describe("UIA-018: Progress primitive", () => {
  it("defaults to the compact sm track (4px) with the primary fill", () => {
    const { container } = render(<Progress value={40} />);
    const track = container.querySelector('[data-slot="progress-track"]');
    expect(track).toHaveClass("h-1");
    const indicator = container.querySelector('[data-slot="progress-indicator"]');
    expect(indicator).toHaveClass("bg-primary");
  });

  it("supports the md (6px) size used by subject and criterion bars", () => {
    const { container } = render(<Progress value={40} size="md" />);
    expect(container.querySelector('[data-slot="progress-track"]')).toHaveClass("h-1.5");
  });

  it("supports the lg (8px) size used by page-level summary bars", () => {
    const { container } = render(<Progress value={40} size="lg" />);
    expect(container.querySelector('[data-slot="progress-track"]')).toHaveClass("h-2");
  });

  it("keeps the track visible on cards and renders the neutral zero-record fill", () => {
    const { container } = render(<Progress value={0} variant="neutral" />);
    const track = container.querySelector('[data-slot="progress-track"]');
    expect(track).toHaveClass("bg-muted-foreground/20");
    // The old `bg-muted` track was invisible because --muted === --card.
    expect(track).not.toHaveClass("bg-muted");
    const indicator = container.querySelector('[data-slot="progress-indicator"]');
    expect(indicator).toHaveClass("bg-muted-foreground/30");
    expect(indicator).not.toHaveClass("bg-destructive");
  });

  it("keeps the semantic status fills", () => {
    const { container, rerender } = render(<Progress value={80} variant="success" />);
    expect(container.querySelector('[data-slot="progress-indicator"]')).toHaveClass("bg-success");
    rerender(<Progress value={65} variant="warning" />);
    expect(container.querySelector('[data-slot="progress-indicator"]')).toHaveClass("bg-warning");
    rerender(<Progress value={30} variant="danger" />);
    expect(container.querySelector('[data-slot="progress-indicator"]')).toHaveClass("bg-destructive");
  });
});
