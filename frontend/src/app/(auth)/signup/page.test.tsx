import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import SignupPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ refreshUser: vi.fn() }),
}));

/**
 * UIA-015 regression coverage: the signup summary error is announced with
 * role="alert", and the two password visibility toggles have distinct
 * accessible names ("Show password" vs "Show confirm password").
 */
describe("UIA-015: signup accessibility", () => {
  it("announces validation failures with role=alert", async () => {
    render(<SignupPage />);
    fireEvent.click(screen.getByRole("button", { name: /create account/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/full name is required/i);
  });

  it("gives each password toggle a distinct accessible name", () => {
    render(<SignupPage />);
    expect(screen.getByRole("button", { name: "Show password" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Show confirm password" })
    ).toBeInTheDocument();
  });

  it("reflects the visible/hidden state on each toggle", () => {
    render(<SignupPage />);
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(screen.getByRole("button", { name: "Hide password" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Show confirm password" })
    ).toBeInTheDocument();
  });
});
