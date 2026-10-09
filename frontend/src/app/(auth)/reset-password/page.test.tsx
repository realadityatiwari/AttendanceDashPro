import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import ResetPasswordPage from "./page";

const { resetPasswordMock } = vi.hoisted(() => ({ resetPasswordMock: vi.fn() }));

vi.mock("@/hooks/useApi", () => ({
  useResetPassword: () => ({ resetPassword: resetPasswordMock }),
}));

afterEach(() => {
  vi.unstubAllGlobals();
});

function fill({
  token = "tok-abc123",
  next = "NewPassw0rd",
  confirm = "NewPassw0rd",
}: { token?: string; next?: string; confirm?: string } = {}) {
  fireEvent.change(document.getElementById("resetToken") as HTMLInputElement, {
    target: { value: token },
  });
  fireEvent.change(document.getElementById("newPassword") as HTMLInputElement, {
    target: { value: next },
  });
  fireEvent.change(document.getElementById("confirmPassword") as HTMLInputElement, {
    target: { value: confirm },
  });
}

describe("Stage 3A: public /reset-password page", () => {
  beforeEach(() => {
    resetPasswordMock.mockReset();
    window.history.replaceState(null, "", "/reset-password");
    localStorage.clear();
  });

  it("renders token, new password and confirmation inputs", () => {
    render(<ResetPasswordPage />);
    expect(screen.getByLabelText(/reset token/i)).toBeInTheDocument();
    expect(document.getElementById("newPassword")).toBeInTheDocument();
    expect(document.getElementById("confirmPassword")).toBeInTheDocument();
  });

  it("prefills the token from the URL fragment and strips it from the address bar", () => {
    window.history.replaceState(null, "", "/reset-password#token=fragment-token-xyz");
    render(<ResetPasswordPage />);
    return waitFor(() => {
      expect((document.getElementById("resetToken") as HTMLInputElement).value).toBe(
        "fragment-token-xyz"
      );
      expect(window.location.hash).toBe("");
    });
  });

  it("blocks submission when the confirmation does not match", () => {
    render(<ResetPasswordPage />);
    fill({ confirm: "Different1" });
    fireEvent.click(screen.getByRole("button", { name: /^reset password$/i }));
    expect(screen.getByText("Passwords do not match.")).toBeInTheDocument();
    expect(resetPasswordMock).not.toHaveBeenCalled();
  });

  it("rejects a new password that violates the policy", () => {
    render(<ResetPasswordPage />);
    fill({ next: "short1", confirm: "short1" });
    fireEvent.click(screen.getByRole("button", { name: /^reset password$/i }));
    expect(document.getElementById("newPassword-error")).toHaveTextContent(
      /at least 8 characters/i
    );
    expect(resetPasswordMock).not.toHaveBeenCalled();
  });

  it("requires a reset token", () => {
    render(<ResetPasswordPage />);
    fill({ token: "   " });
    fireEvent.click(screen.getByRole("button", { name: /^reset password$/i }));
    expect(document.getElementById("resetToken-error")).toHaveTextContent(
      /enter the reset token/i
    );
    expect(resetPasswordMock).not.toHaveBeenCalled();
  });

  it("submits the token and new password, then shows success and clears sensitive fields", async () => {
    resetPasswordMock.mockResolvedValue(undefined);
    render(<ResetPasswordPage />);
    fill();
    fireEvent.click(screen.getByRole("button", { name: /^reset password$/i }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(/password has been reset/i)
    );
    expect(resetPasswordMock).toHaveBeenCalledWith("tok-abc123", "NewPassw0rd");
    // Sensitive inputs removed after success; the page offers sign-in.
    expect(document.getElementById("newPassword")).toBeNull();
    // The Button-as-link renders with role="button" (Base UI composition).
    expect(
      screen.getByRole("button", { name: /go to sign in/i })
    ).toBeInTheDocument();
    // Redemption never starts a session.
    expect(localStorage.getItem("access_token")).toBeNull();
  });

  it("does not clear fields and shows a generic error on failure", async () => {
    resetPasswordMock.mockRejectedValue(new Error("Invalid or expired reset token"));
    render(<ResetPasswordPage />);
    fill();
    fireEvent.click(screen.getByRole("button", { name: /^reset password$/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Invalid or expired reset token");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    // Drafts preserved for retry.
    expect((document.getElementById("newPassword") as HTMLInputElement).value).toBe(
      "NewPassw0rd"
    );
  });

  it("prevents duplicate submission while a reset is in flight", async () => {
    let resolveReset: () => void = () => {};
    resetPasswordMock.mockImplementation(
      () => new Promise<void>((resolve) => { resolveReset = resolve; })
    );
    render(<ResetPasswordPage />);
    fill();
    const button = screen.getByRole("button", { name: /^reset password$/i });
    fireEvent.click(button);
    await waitFor(() => expect(resetPasswordMock).toHaveBeenCalledTimes(1));
    fireEvent.click(button);
    expect(resetPasswordMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolveReset();
    });
  });
});