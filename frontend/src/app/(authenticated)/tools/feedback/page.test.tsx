import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FeedbackAdminPage from "./page";

/**
 * UIA-008 regression coverage: the /tools/feedback route is admin-only.
 * A student who deep-links or refreshes here must be redirected to the
 * dashboard and must never see the admin surface (nor the old misleading
 * "Failed to load data" error). Admins keep the working review surface.
 */

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), back: vi.fn() }),
}));

let authState: { user: { id: string; display_name: string } | null; loading: boolean };
vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => authState,
}));

type Profile = { role: string; display_name: string };
let profileState: {
  profile: Profile | null;
  isLoading: boolean;
  isError: boolean;
};
let feedbackState: {
  feedback: unknown;
  isLoading: boolean;
  isError: boolean;
};

vi.mock("@/hooks/useApi", () => ({
  useProfile: () => profileState,
  useAdminFeedback: () => feedbackState,
}));

const STUDENT = { role: "STUDENT", display_name: "UI Audit Runner" };
const ADMIN = { role: "ADMIN", display_name: "Aditya Tiwari" };
const FEEDBACK_LIST = {
  items: [
    {
      id: "fb-1",
      name: "UI Audit Runner",
      roll_number: "2401220999001",
      feedback_type: "BUG",
      message: "Something looks off",
      created_at: "2026-09-29",
    },
  ],
  page: 1,
  pages: 1,
  total: 1,
};

beforeEach(() => {
  vi.clearAllMocks();
  authState = { user: { id: "u1", display_name: "UI Audit Runner" }, loading: false };
  profileState = { profile: STUDENT, isLoading: false, isError: false };
  feedbackState = { feedback: null, isLoading: false, isError: false };
});

describe("/tools/feedback route guard (UIA-008)", () => {
  it("redirects a student to /dashboard and renders no admin content", async () => {
    render(<FeedbackAdminPage />);
    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/dashboard");
    });
    expect(screen.queryByText("Feedback submitted by students.")).not.toBeInTheDocument();
    expect(screen.queryByText("Refresh")).not.toBeInTheDocument();
    // The old misleading failure copy must be gone for students.
    expect(screen.queryByText(/Failed to load data/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/feedback admin surface/i)).not.toBeInTheDocument();
  });

  it("renders no error state for a student while redirecting", () => {
    const { container } = render(<FeedbackAdminPage />);
    expect(container.textContent).toBe("");
  });

  it("keeps the working review surface for admins", async () => {
    profileState = { profile: ADMIN, isLoading: false, isError: false };
    feedbackState = { feedback: FEEDBACK_LIST, isLoading: false, isError: false };
    render(<FeedbackAdminPage />);
    expect(await screen.findByText("Feedback submitted by students.")).toBeInTheDocument();
    expect(screen.getByText("Something looks off")).toBeInTheDocument();
    expect(screen.getByText("Refresh")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("shows neutral skeletons (no admin surface, no error) while the profile loads", () => {
    profileState = { profile: null, isLoading: true, isError: false };
    const { container } = render(<FeedbackAdminPage />);
    expect(screen.getByText("Feedback", { selector: "h1" })).toBeInTheDocument();
    expect(container.querySelectorAll("[class*='animate-pulse']").length).toBeGreaterThan(0);
    expect(replace).not.toHaveBeenCalled();
    expect(screen.queryByText("Refresh")).not.toBeInTheDocument();
  });

  it("renders nothing for unauthenticated visitors (AuthContext owns the login redirect)", () => {
    authState = { user: null, loading: false };
    const { container } = render(<FeedbackAdminPage />);
    expect(container.textContent).toBe("");
    expect(replace).not.toHaveBeenCalled();
    expect(screen.queryByText("Refresh")).not.toBeInTheDocument();
    expect(screen.queryByText("Feedback submitted by students.")).not.toBeInTheDocument();
  });

  it("does not render the admin surface while the profile request has failed", () => {
    profileState = { profile: null, isLoading: false, isError: true };
    render(<FeedbackAdminPage />);
    expect(screen.queryByText("Refresh")).not.toBeInTheDocument();
    expect(screen.queryByText("Feedback submitted by students.")).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
