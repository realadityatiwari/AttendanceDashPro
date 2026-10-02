import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ProfilePage from "./page";

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: "fc9b5093-ff46-43b6-a6d7-329921913ca3",
      display_name: "Test Student",
    },
    loading: false,
    logout: vi.fn(),
  }),
}));

vi.mock("@/hooks/useApi", () => ({
  useProfile: () => ({
    profile: {
      id: "fc9b5093-ff46-43b6-a6d7-329921913ca3",
      display_name: "Test Student",
      roll_number: "2401220999001",
      section_name: "CSE-A",
      role: "STUDENT",
    },
    isLoading: false,
    isError: null,
  }),
}));

describe("UIA-007: Profile Page UUID removal", () => {
  it("renders roll number and student details but never displays the raw internal UUID", () => {
    render(<ProfilePage />);

    // Roll number remains visible
    expect(screen.getByText("2401220999001")).toBeInTheDocument();
    expect(screen.getByText("CSE-A")).toBeInTheDocument();
    expect(screen.getByText("Test Student")).toBeInTheDocument();

    // Raw UUID must not appear anywhere in rendered content
    expect(
      screen.queryByText("fc9b5093-ff46-43b6-a6d7-329921913ca3")
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/account identifier/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/authentication identity/i))
    .not.toBeInTheDocument();

    // Sign out button remains present
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("shows the roll number exactly once on the single profile surface", () => {
    // UIA-045: the former ProfileModal duplicated the roll number (avatar
    // block + field); the canonical page renders it once.
    render(<ProfilePage />);
    expect(screen.getAllByText("2401220999001")).toHaveLength(1);
  });
});
