import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SegmentedControl } from "./segmented-control";
import { FlaskConical } from "lucide-react";

const OPTIONS = [
  { value: "one", label: "One" },
  { value: "two", label: "Two", icon: FlaskConical },
  { value: "three", label: "Three" },
] as const;

/**
 * 25.UX-2: the segmented control consolidates the quiz-cycle selector, the
 * laboratory section switcher, and the feedback type chips. Guards the
 * shared interaction contract: named group, aria-pressed selection, native
 * button toggles, and the UIA-030 touch floor (h-10 touch / sm:h-8 pointer).
 */
describe("25.UX-2: SegmentedControl", () => {
  it("renders one named group with a button per option", () => {
    render(
      <SegmentedControl
        value="one"
        onValueChange={() => {}}
        options={OPTIONS}
        aria-label="Test group"
      />
    );
    const group = screen.getByRole("group", { name: "Test group" });
    expect(group).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "One" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Two" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Three" })).toBeInTheDocument();
  });

  it("exposes the selection via aria-pressed on native buttons", () => {
    render(
      <SegmentedControl
        value="two"
        onValueChange={() => {}}
        options={OPTIONS}
        aria-label="Test group"
      />
    );
    expect(screen.getByRole("button", { name: "Two" })).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    expect(screen.getByRole("button", { name: "One" })).toHaveAttribute(
      "aria-pressed",
      "false"
    );
  });

  it("fires onValueChange with the option value", () => {
    const onValueChange = vi.fn();
    render(
      <SegmentedControl
        value="one"
        onValueChange={onValueChange}
        options={OPTIONS}
        aria-label="Test group"
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Three" }));
    expect(onValueChange).toHaveBeenCalledWith("three");
  });

  it("supports a null selection (no option pressed)", () => {
    render(
      <SegmentedControl
        value={null}
        onValueChange={() => {}}
        options={OPTIONS}
        aria-label="Test group"
      />
    );
    for (const name of ["One", "Two", "Three"]) {
      expect(screen.getByRole("button", { name })).toHaveAttribute(
        "aria-pressed",
        "false"
      );
    }
  });

  it("keeps every option on the UIA-030 touch floor (h-10 touch / sm:h-8 pointer)", () => {
    const { container } = render(
      <SegmentedControl
        value="one"
        onValueChange={() => {}}
        options={OPTIONS}
        aria-label="Test group"
      />
    );
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(3);
    for (const button of buttons) {
      expect(button.className).toContain("h-10");
      expect(button.className).toContain("sm:h-8");
      expect(button.className).toContain("focus-visible:ring-2");
    }
  });

  it("renders option icons as decorative and composes container className", () => {
    const { container } = render(
      <SegmentedControl
        value="one"
        onValueChange={() => {}}
        options={OPTIONS}
        variant="track"
        aria-label="Test group"
        className="extra-class"
      />
    );
    const group = screen.getByRole("group", { name: "Test group" });
    expect(group.className).toContain("extra-class");
    expect(group.className).toContain("bg-muted");
    const icon = container.querySelector("svg");
    expect(icon).toHaveAttribute("aria-hidden", "true");
  });

  it("forwards aria-describedby for an associated inline error (25.UX-7)", () => {
    render(
      <SegmentedControl
        value={null}
        onValueChange={() => {}}
        options={OPTIONS}
        aria-label="Feedback type"
        aria-describedby="feedback-type-error"
      />
    );
    expect(screen.getByRole("group")).toHaveAttribute(
      "aria-describedby",
      "feedback-type-error"
    );
  });
});
