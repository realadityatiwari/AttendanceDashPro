import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { GreetingHeader, formatGreetingName } from "./GreetingHeader";

vi.mock("@/lib/date", () => ({
  getGreeting: () => "Good Morning",
  formatLongDate: () => "Tuesday · 29 Sep 2026",
}));

let mockProfile: { display_name?: string | null } | null = null;
let mockIsLoading = false;

vi.mock("@/hooks/useApi", () => ({
  useProfile: () => ({
    profile: mockProfile,
    isLoading: mockIsLoading,
  }),
}));

describe("UIA-009: Greeting Name Handling", () => {
  describe("formatGreetingName", () => {
    it("preserves normal names", () => {
      expect(formatGreetingName("Jane Doe")).toBe("Jane Doe");
    });

    it("preserves multi-word names without truncating to the first word", () => {
      expect(formatGreetingName("UI Audit Runner")).toBe("UI Audit Runner");
      expect(formatGreetingName("A. P. J. Abdul Kalam")).toBe(
        "A. P. J. Abdul Kalam"
      );
    });

    it("handles long names safely", () => {
      expect(
        formatGreetingName("Dr. Alexander Bartholomew-Fitzgerald III")
      ).toBe("Dr. Alexander Bartholomew-Fitzgerald III");
    });

    it("handles unusually long single tokens", () => {
      const longToken = "SupercalifragilisticexpialidociousWithExtraLongToken";
      expect(formatGreetingName(longToken)).toBe(longToken);
    });

    it("handles whitespace and edge cases cleanly", () => {
      expect(formatGreetingName("   John    Smith   ")).toBe("John Smith");
      expect(formatGreetingName("")).toBe("");
      expect(formatGreetingName("   ")).toBe("");
      expect(formatGreetingName(null)).toBe("");
      expect(formatGreetingName(undefined)).toBe("");
    });
  });

  describe("GreetingHeader component rendering", () => {
    it("renders full greeting for multi-word student name", () => {
      mockProfile = { display_name: "UI Audit Runner" };
      mockIsLoading = false;
      render(<GreetingHeader />);

      expect(
        screen.getByRole("heading", { name: "Good Morning, UI Audit Runner" })
      ).toBeInTheDocument();
    });

    it("falls back to bare greeting when profile name is missing or blank", () => {
      mockProfile = { display_name: "" };
      mockIsLoading = false;
      render(<GreetingHeader />);

      expect(
        screen.getByRole("heading", { name: "Good Morning" })
      ).toBeInTheDocument();
    });

    it("renders heading with break-words to protect against overflow on long names", () => {
      mockProfile = {
        display_name: "VeryLongStudentNameThatCouldWrapAcrossDevices Safely",
      };
      mockIsLoading = false;
      const { container } = render(<GreetingHeader />);

      const heading = container.querySelector("h1");
      expect(heading).toHaveClass("break-words");
    });
  });
});
