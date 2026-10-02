import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthGate } from "./AuthGate";

let authState: { loading: boolean; hasSession: boolean };

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => authState,
}));

/**
 * UIA-013 regression coverage: an anonymous visit to a protected route must
 * never paint the authenticated shell while the redirect is in flight.
 */
describe("UIA-013: AuthGate", () => {
  it("suppresses the shell while auth is still resolving", () => {
    authState = { loading: true, hasSession: false };
    render(
      <AuthGate>
        <div>authenticated shell</div>
      </AuthGate>
    );
    expect(screen.queryByText("authenticated shell")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("suppresses the shell when no session token exists (redirect in flight)", () => {
    authState = { loading: false, hasSession: false };
    render(
      <AuthGate>
        <div>authenticated shell</div>
      </AuthGate>
    );
    expect(screen.queryByText("authenticated shell")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders the shell once a session token exists", () => {
    authState = { loading: false, hasSession: true };
    render(
      <AuthGate>
        <div>authenticated shell</div>
      </AuthGate>
    );
    expect(screen.getByText("authenticated shell")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
