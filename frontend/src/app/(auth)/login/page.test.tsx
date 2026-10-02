import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import LoginPage from "./page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ refreshUser: vi.fn() }),
}));

afterEach(() => {
  vi.unstubAllGlobals();
});

/**
 * UIA-015 regression coverage: auth error banners are announced to assistive
 * technology (role="alert") and the visibility toggle keeps an accessible
 * name. Authentication behavior itself is unchanged.
 */
describe("UIA-015: login accessibility", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("announces a failed sign-in with role=alert", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Incorrect roll number or password" }),
      })
    );

    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/roll number/i), {
      target: { value: "2401220999001" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "secret123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^sign in$/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Incorrect roll number or password");
  });

  it("keeps an accessible name on the password visibility toggle", () => {
    render(<LoginPage />);
    expect(screen.getByRole("button", { name: /show password/i })).toBeInTheDocument();
  });
});
