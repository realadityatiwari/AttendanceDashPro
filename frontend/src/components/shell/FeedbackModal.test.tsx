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
