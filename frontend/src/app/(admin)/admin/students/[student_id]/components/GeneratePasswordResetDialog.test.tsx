import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { GeneratePasswordResetDialog } from "./GeneratePasswordResetDialog";
import { AdminStudentDetail } from "@/types/api";

const { issuePasswordResetMock } = vi.hoisted(() => ({
  issuePasswordResetMock: vi.fn(),
}));

vi.mock("@/hooks/useApi", () => ({
  usePasswordResetIssuance: () => ({ issuePasswordReset: issuePasswordResetMock }),
}));

const student = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Test Student",
  roll_number: "2401220999001",
} as unknown as AdminStudentDetail;

function renderDialog(open = true) {
  const onOpenChange = vi.fn();
  render(
    <GeneratePasswordResetDialog student={student} open={open} onOpenChange={onOpenChange} />
  );
  return { onOpenChange };
}

describe("Stage 3A: admin GeneratePasswordResetDialog", () => {
  beforeEach(() => {
    issuePasswordResetMock.mockReset();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the generate action and the private-delivery guidance", () => {
    renderDialog();
    expect(
      screen.getByRole("button", { name: /generate reset token/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/privately/i)).toBeInTheDocument();
  });

  it("issues a token and displays it exactly once", async () => {
    issuePasswordResetMock.mockResolvedValue({
      reset_token: "one-time-token-ABC",
      expires_at: "2026-10-10T12:00:00Z",
    });
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: /generate reset token/i }));

    await waitFor(() =>
      expect(issuePasswordResetMock).toHaveBeenCalledWith(student.id)
    );
    expect(screen.getByText("one-time-token-ABC")).toBeInTheDocument();
    // The generate button is replaced by the one-time display.
    expect(
      screen.queryByRole("button", { name: /generate reset token/i })
    ).not.toBeInTheDocument();
  });

  it("shows an inline error and no token when issuance fails", async () => {
    issuePasswordResetMock.mockRejectedValue(new Error("Student not found"));
    renderDialog();
    fireEvent.click(screen.getByRole("button", { name: /generate reset token/i }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Student not found");
    expect(screen.queryByText(/one-time-token/i)).not.toBeInTheDocument();
  });

  it("prevents duplicate issuance while in flight", async () => {
    let resolveIssue: (v: unknown) => void = () => {};
    issuePasswordResetMock.mockImplementation(
      () => new Promise((resolve) => { resolveIssue = resolve; })
    );
    renderDialog();
    const button = screen.getByRole("button", { name: /generate reset token/i });
    fireEvent.click(button);
    await waitFor(() => expect(issuePasswordResetMock).toHaveBeenCalledTimes(1));
    fireEvent.click(button);
    expect(issuePasswordResetMock).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolveIssue({ reset_token: "t", expires_at: "2026-10-10T12:00:00Z" });
    });
  });

  it("clears the once-shown token when the dialog is closed and reopened", async () => {
    issuePasswordResetMock.mockResolvedValue({
      reset_token: "secret-once",
      expires_at: "2026-10-10T12:00:00Z",
    });
    const { rerender } = render(
      <GeneratePasswordResetDialog student={student} open={true} onOpenChange={() => {}} />
    );
    fireEvent.click(screen.getByRole("button", { name: /generate reset token/i }));
    await waitFor(() => expect(screen.getByText("secret-once")).toBeInTheDocument());

    // Close then reopen: the raw token must not persist.
    rerender(
      <GeneratePasswordResetDialog student={student} open={false} onOpenChange={() => {}} />
    );
    rerender(
      <GeneratePasswordResetDialog student={student} open={true} onOpenChange={() => {}} />
    );
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /generate reset token/i })
      ).toBeInTheDocument()
    );
    expect(screen.queryByText("secret-once")).not.toBeInTheDocument();
  });
});