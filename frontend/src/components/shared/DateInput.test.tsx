import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DateInput } from "./DateInput";

/**
 * UIA-025 regression coverage: the native, machine-readable date input is
 * preserved; a visible formatted companion communicates the date in the app's
 * canonical format.
 */
describe("UIA-025: DateInput", () => {
  it("keeps the native date input and its ISO value", () => {
    render(<DateInput value="2026-10-05" onValueChange={vi.fn()} aria-label="From" />);
    const input = screen.getByLabelText("From");
    expect(input).toHaveAttribute("type", "date");
    expect(input).toHaveValue("2026-10-05");
  });

  it("renders the formatted human-readable companion", () => {
    render(<DateInput value="2026-10-05" onValueChange={vi.fn()} aria-label="From" />);
    expect(screen.getByText("5 Oct 2026")).toBeInTheDocument();
  });

  it("shows a stable hint while no date is chosen", () => {
    render(<DateInput value="" onValueChange={vi.fn()} aria-label="From" />);
    expect(screen.getByText("Any date")).toBeInTheDocument();
  });

  it("accepts a custom empty hint", () => {
    render(<DateInput value="" onValueChange={vi.fn()} aria-label="Event date" emptyHint="Pick a date" />);
    expect(screen.getByText("Pick a date")).toBeInTheDocument();
  });

  it("reports changes with the native ISO value", () => {
    const onValueChange = vi.fn();
    render(<DateInput value="" onValueChange={onValueChange} aria-label="From" />);
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-11-01" } });
    expect(onValueChange).toHaveBeenCalledWith("2026-11-01");
  });
});
