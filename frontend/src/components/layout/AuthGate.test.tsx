import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { AuthGate } from "./AuthGate";

let authState: { authResolved: boolean; hasSession: boolean };

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => authState,
}));

/**
 * UIA-013 regression coverage: an anonymous visit to a protected route must
 * never paint the authenticated shell while the redirect is in flight.
 *
 * Perf batch 1: the gate opens on `authResolved` + `hasSession` (token
 * presence) — the profile fetch no longer blocks the shell, so page data
 * hooks start in parallel with GET /student/me.
 */
describe("UIA-013: AuthGate", () => {
  it("suppresses the shell while auth is still resolving", () => {
    authState = { authResolved: false, hasSession: false };
    render(
      <AuthGate>
        <div>authenticated shell</div>
      </AuthGate>
    );
    expect(screen.queryByText("authenticated shell")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("suppresses the shell when no session token exists (redirect in flight)", () => {
    authState = { authResolved: true, hasSession: false };
    render(
      <AuthGate>
        <div>authenticated shell</div>
      </AuthGate>
    );
    expect(screen.queryByText("authenticated shell")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders the shell once a session token exists", () => {
    authState = { authResolved: true, hasSession: true };
    render(
      <AuthGate>
        <div>authenticated shell</div>
      </AuthGate>
    );
    expect(screen.getByText("authenticated shell")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does not block the shell on the profile fetch when a token is present", () => {
    // Token present, /student/me still in flight (profile not yet resolved):
    // the shell and its data hooks must start immediately.
    authState = { authResolved: true, hasSession: true };
    render(
      <AuthGate>
        <div>authenticated shell</div>
      </AuthGate>
    );
    expect(screen.getByText("authenticated shell")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
