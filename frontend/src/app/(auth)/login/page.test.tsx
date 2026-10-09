import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import LoginPage from "./page";

const { changePasswordMock } = vi.hoisted(() => ({ changePasswordMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({ refreshUser: vi.fn() }),
}));

vi.mock("@/hooks/useApi", () => ({
  useChangePassword: () => ({ changePassword: changePasswordMock }),
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
    changePasswordMock.mockReset();
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

/**
 * Change-password placement: the control lives on the login page but performs
 * a RE-AUTH flow — it uses the existing login endpoint to authenticate with
 * the current credentials, then calls the existing authenticated
 * change-password endpoint with the in-memory token. No session is started
 * (nothing is written to localStorage), and the backend authorization is
 * unchanged.
 */
describe("Login page: change-password re-auth flow", () => {
  function enterChangeMode() {
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /change your password/i }));
  }

  function fillChangeForm({
    roll = "2401220999001",
    current = "OldPassw0rd",
    next = "NewPassw0rd",
    confirm = "NewPassw0rd",
  } = {}) {
    fireEvent.change(document.getElementById("rollNumber") as HTMLInputElement, {
      target: { value: roll },
    });
    fireEvent.change(document.getElementById("password") as HTMLInputElement, {
      target: { value: current },
    });
    fireEvent.change(document.getElementById("newPassword") as HTMLInputElement, {
      target: { value: next },
    });
    fireEvent.change(document.getElementById("confirmPassword") as HTMLInputElement, {
      target: { value: confirm },
    });
  }

  function loginOk(token = "temp-token") {
    return {
      ok: true,
      json: async () => ({ access_token: token, token_type: "bearer" }),
    };
  }

  function loginFail(detail = "Incorrect roll number or password") {
    return { ok: false, json: async () => ({ detail }) };
  }

  beforeEach(() => {
    sessionStorage.clear();
    changePasswordMock.mockReset();
  });

  it("opens change mode with current, new and confirm inputs", () => {
    enterChangeMode();
    expect(screen.getByLabelText(/current password/i)).toBeInTheDocument();
    expect(document.getElementById("newPassword")).toBeInTheDocument();
    expect(document.getElementById("confirmPassword")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show new password" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show confirm password" })).toBeInTheDocument();
  });

  it("blocks submission when the confirmation does not match", () => {
    enterChangeMode();
    fillChangeForm({ confirm: "Different1" });
    fireEvent.click(screen.getByRole("button", { name: /^change password$/i }));
    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
    expect(changePasswordMock).not.toHaveBeenCalled();
  });

  it("rejects a new password that violates the policy", () => {
    enterChangeMode();
    fillChangeForm({ next: "short1", confirm: "short1" });
    fireEvent.click(screen.getByRole("button", { name: /^change password$/i }));
    expect(document.getElementById("newPassword-error")).toHaveTextContent(/at least 8 characters/i);
    expect(changePasswordMock).not.toHaveBeenCalled();
  });

  it("requires a 13-digit roll number", () => {
    enterChangeMode();
    fillChangeForm({ roll: "123" });
    fireEvent.click(screen.getByRole("button", { name: /^change password$/i }));
    expect(screen.getByText("Roll number must be 13 digits.")).toBeInTheDocument();
    expect(changePasswordMock).not.toHaveBeenCalled();
  });

  it("authenticates via login, then changes the password with the in-memory token, starting no session", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(loginOk("temp-token")) // POST /auth/login
      .mockResolvedValueOnce({ ok: true, json: async () => ({}) }); // POST /auth/logout
    vi.stubGlobal("fetch", fetchMock);
    changePasswordMock.mockResolvedValue(undefined);

    enterChangeMode();
    fillChangeForm();
    fireEvent.click(screen.getByRole("button", { name: /^change password$/i }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/password has been changed/i)
    );
    // Login was called with the current credentials.
    const loginCall = fetchMock.mock.calls.find(([u]) => String(u).includes("/auth/login"));
    expect(loginCall).toBeTruthy();
    expect(JSON.parse((loginCall![1] as RequestInit).body as string)).toEqual({
      roll_number: "2401220999001",
      password: "OldPassw0rd",
    });
    // The change used the explicit temporary token.
    expect(changePasswordMock).toHaveBeenCalledWith("OldPassw0rd", "NewPassw0rd", "temp-token");
    // No session was started.
    expect(localStorage.getItem("access_token")).toBeNull();
  });

  it("clears the new-password drafts only after a confirmed success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(loginOk()).mockResolvedValueOnce({ ok: true, json: async () => ({}) })
    );
    changePasswordMock.mockResolvedValue(undefined);
    enterChangeMode();
    fillChangeForm();
    fireEvent.click(screen.getByRole("button", { name: /^change password$/i }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/password has been changed/i)
    );
    expect((document.getElementById("newPassword") as HTMLInputElement | null)?.value ?? "").toBe("");
    expect((document.getElementById("confirmPassword") as HTMLInputElement | null)?.value ?? "").toBe("");
  });

  it("shows a login failure (wrong current credentials) without calling change-password", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(loginFail("Incorrect roll number or password")));
    enterChangeMode();
    fillChangeForm();
    fireEvent.click(screen.getByRole("button", { name: /^change password$/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Incorrect roll number or password");
    expect(changePasswordMock).not.toHaveBeenCalled();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows a change-password API error without reporting success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(loginOk()));
    changePasswordMock.mockRejectedValue(new Error("Current password is incorrect"));
    enterChangeMode();
    fillChangeForm();
    fireEvent.click(screen.getByRole("button", { name: /^change password$/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Current password is incorrect");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("prevents duplicate submission while a change is in flight", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(loginOk()).mockResolvedValueOnce({ ok: true, json: async () => ({}) })
    );
    let resolveChange: () => void = () => {};
    changePasswordMock.mockImplementation(
      () => new Promise<void>((resolve) => { resolveChange = resolve; })
    );
    enterChangeMode();
    fillChangeForm();
    const button = screen.getByRole("button", { name: /^change password$/i });
    fireEvent.click(button);
    // The login round-trip resolves before change-password is invoked.
    await waitFor(() => expect(changePasswordMock).toHaveBeenCalledTimes(1));
    fireEvent.click(button);
    expect(changePasswordMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolveChange();
    });
  });

  it("returns to sign-in mode", () => {
    enterChangeMode();
    fireEvent.click(screen.getByRole("button", { name: /back to sign in/i }));
    expect(screen.getByRole("button", { name: /^sign in$/i })).toBeInTheDocument();
    expect(screen.queryByLabelText(/current password/i)).not.toBeInTheDocument();
  });
});