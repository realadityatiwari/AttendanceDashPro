import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FeedbackModal } from "./FeedbackModal";

/**
 * UIA-038 regression coverage: after a genuinely successful submission the
 * success state offers an explicit "Done" action that closes the dialog —
 * previously the only close affordance was the header ✕.
 */

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from "@/lib/api";
import type { Mock } from "vitest";

const apiFetchMock = apiFetch as unknown as Mock;

beforeEach(() => {
  vi.clearAllMocks();
  apiFetchMock.mockResolvedValue({});
});

describe("UIA-038: feedback success state", () => {
  it("offers a Done button that closes the dialog after success", async () => {
    const onOpenChange = vi.fn();
    render(<FeedbackModal open onOpenChange={onOpenChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Bug" }));
    fireEvent.change(screen.getByLabelText(/message/i), {
      target: { value: "The dashboard is genuinely useful, thanks!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    expect(await screen.findByText("Thank you!")).toBeInTheDocument();

    const done = screen.getByRole("button", { name: "Done" });
    fireEvent.click(done);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("does not show the Done action in the idle state", () => {
    render(<FeedbackModal open onOpenChange={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Done" })).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 25.UX-7: form state announcements and error association.
// ---------------------------------------------------------------------------

describe("25.UX-7: feedback form announcements", () => {
  it("announces the success outcome via role=status", async () => {
    render(<FeedbackModal open onOpenChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Bug" }));
    fireEvent.change(screen.getByLabelText(/message/i), {
      target: { value: "The dashboard is genuinely useful, thanks!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    const successPanel = await screen.findByText("Thank you!");
    expect(successPanel.closest('[role="status"]')).not.toBeNull();
  });

  it("announces submission failures via role=alert and keeps the retry path", async () => {
    apiFetchMock.mockRejectedValueOnce(new Error("503 Service Unavailable"));
    render(<FeedbackModal open onOpenChange={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Bug" }));
    fireEvent.change(screen.getByLabelText(/message/i), {
      target: { value: "The dashboard is genuinely useful, thanks!" },
    });
    fireEvent.click(screen.getByRole("button", { name: /submit/i }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("associates the inline message error with the textarea", () => {
    render(<FeedbackModal open onOpenChange={vi.fn()} />);
    const textarea = screen.getByLabelText(/message/i);

    // Below the minimum: aria-invalid set and the error is the describedby
    // target (one stable id serves the counter and the error).
    fireEvent.change(textarea, { target: { value: "too short" } });
    expect(textarea).toHaveAttribute("aria-invalid", "true");
    expect(textarea).toHaveAttribute("aria-describedby", "feedback-message-hint");
    expect(screen.getByText(/at least 10 characters/i)).toHaveAttribute(
      "id",
      "feedback-message-hint"
    );

    // Back above the minimum: the id stays and validity clears.
    fireEvent.change(textarea, {
      target: { value: "The dashboard is genuinely useful, thanks!" },
    });
    expect(textarea).not.toHaveAttribute("aria-invalid");
    expect(textarea).toHaveAttribute("aria-describedby", "feedback-message-hint");
  });

  it("associates the type error with the segmented control via aria-describedby", () => {
    render(<FeedbackModal open onOpenChange={vi.fn()} />);
    const textarea = screen.getByLabelText(/message/i);

    fireEvent.change(textarea, { target: { value: "no type selected yet" } });
    // The wrapping <fieldset> is also a group named by the same legend, so
    // pick the control div via its explicit aria-labelledby reference.
    const control = screen
      .getAllByRole("group", { name: "Feedback type" })
      .find((el) => el.getAttribute("aria-labelledby") === "feedback-type-legend");
    expect(control).toBeDefined();
    expect(control).toHaveAttribute("aria-describedby", "feedback-type-error");
    expect(screen.getByText("Select a feedback type")).toHaveAttribute(
      "id",
      "feedback-type-error"
    );
  });
});
