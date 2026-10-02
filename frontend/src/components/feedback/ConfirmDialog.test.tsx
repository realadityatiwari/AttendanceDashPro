import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfirmDialog } from "./ConfirmDialog";

/**
 * UIA-016 regression coverage: the confirmation action can match the page
 * CTA's semantic color (success for "Mark all present"), while the
 * destructive and default treatments stay unchanged.
 */
function confirmButton(variant: "default" | "destructive" | "success") {
  render(
    <ConfirmDialog
      open
      onOpenChange={vi.fn()}
      title="Mark 4 classes present?"
      description="This will mark all currently pending classes as present."
      confirmLabel="Mark all present"
      variant={variant}
      onConfirm={vi.fn()}
    />
  );
  return screen.getByRole("button", { name: /mark all present/i });
}

describe("UIA-016: ConfirmDialog action variants", () => {
  it("renders the success treatment for positive confirmations", () => {
    const button = confirmButton("success");
    expect(button.className).toContain("bg-success");
    expect(button.className).toContain("text-success-foreground");
  });

  it("keeps the destructive treatment unchanged", () => {
    const button = confirmButton("destructive");
    expect(button.className).toContain("bg-destructive/10");
    expect(button.className).toContain("text-destructive");
  });

  it("keeps the default treatment unchanged", () => {
    const button = confirmButton("default");
    expect(button.className).toContain("bg-primary");
  });
});
