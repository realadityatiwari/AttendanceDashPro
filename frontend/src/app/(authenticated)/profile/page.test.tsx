import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import ProfilePage from "./page";

const {
  profileState,
  retryMock,
  globalMutateMock,
  updateProfileNameMock,
} = vi.hoisted(() => ({
  profileState: {
    profile: {
      id: "fc9b5093-ff46-43b6-a6d7-329921913ca3",
      display_name: "Test Student",
      roll_number: "2401220999001",
      section_name: "CSE-A",
      role: "STUDENT",
    } as Record<string, unknown>,
    isLoading: false,
    isError: null as unknown,
  },
  retryMock: vi.fn(),
  globalMutateMock: vi.fn().mockResolvedValue(undefined),
  updateProfileNameMock: vi.fn(),
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: "fc9b5093-ff46-43b6-a6d7-329921913ca3",
      display_name: "Test Student",
    },
    loading: false,
    logout: vi.fn(),
  }),
}));

vi.mock("@/hooks/useApi", () => ({
  useProfile: () => ({ ...profileState, mutate: retryMock }),
  useProfileMutation: () => ({ updateProfileName: updateProfileNameMock }),
}));

vi.mock("swr", async () => {
  const actual = await vi.importActual<typeof import("swr")>("swr");
  return {
    ...actual,
    useSWRConfig: () => ({ mutate: globalMutateMock }),
  };
});

beforeEach(() => {
  profileState.profile = {
    id: "fc9b5093-ff46-43b6-a6d7-329921913ca3",
    display_name: "Test Student",
    roll_number: "2401220999001",
    section_name: "CSE-A",
    role: "STUDENT",
  };
  profileState.isError = null;
  retryMock.mockClear();
  globalMutateMock.mockClear();
  updateProfileNameMock.mockReset();
});

describe("UIA-007: Profile Page UUID removal", () => {
  it("renders roll number and student details but never displays the raw internal UUID", () => {
    render(<ProfilePage />);

    expect(screen.getByText("2401220999001")).toBeInTheDocument();
    expect(screen.getByText("CSE-A")).toBeInTheDocument();
    expect(screen.getByText("Test Student")).toBeInTheDocument();

    expect(
      screen.queryByText("fc9b5093-ff46-43b6-a6d7-329921913ca3")
    ).not.toBeInTheDocument();

    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("shows the roll number exactly once on the single profile surface", () => {
    render(<ProfilePage />);
    expect(screen.getAllByText("2401220999001")).toHaveLength(1);
  });

  it("renders read-only identity captions as spans (no orphan <label>)", () => {
    // The Change Password form moved to /login, so the profile page has no
    // form controls and must render no <label> elements at all.
    const { container } = render(<ProfilePage />);
    expect(container.querySelectorAll("label")).toHaveLength(0);
    expect(screen.getByText("Display Name")).toBeInTheDocument();
    expect(screen.getByText("Roll Number")).toBeInTheDocument();
    expect(screen.getByText("Section")).toBeInTheDocument();
  });
});

describe("25.UX-5: profile error retry", () => {
  it("offers a retry that re-triggers the profile request", () => {
    profileState.isError = new Error("failed");
    render(<ProfilePage />);
    const retry = screen.getByRole("button", { name: /try again/i });
    fireEvent.click(retry);
    expect(retryMock).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });
});

describe("Stage 1: profile name edit", () => {
  it("renders the current name and an edit control", () => {
    render(<ProfilePage />);
    expect(screen.getByText("Test Student")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit display name/i })).toBeInTheDocument();
  });

  it("opens the input pre-filled with the current name on Edit", () => {
    render(<ProfilePage />);
    fireEvent.click(screen.getByRole("button", { name: /edit display name/i }));
    const input = screen.getByLabelText<HTMLInputElement>(/display name/i);
    expect(input).toBeInTheDocument();
    expect(input.value).toBe("Test Student");
  });

  it("submits the new name and revalidates the shared profile resource", async () => {
    updateProfileNameMock.mockResolvedValue({
      id: "fc9b5093-ff46-43b6-a6d7-329921913ca3",
      display_name: "Renamed Student",
      roll_number: "2401220999001",
      section_name: "CSE-A",
      role: "STUDENT",
    });
    render(<ProfilePage />);
    fireEvent.click(screen.getByRole("button", { name: /edit display name/i }));
    const input = screen.getByLabelText<HTMLInputElement>(/display name/i);
    fireEvent.change(input, { target: { value: "Renamed Student" } });
    fireEvent.click(screen.getByRole("button", { name: /save name/i }));

    await waitFor(() =>
      expect(updateProfileNameMock).toHaveBeenCalledWith("Renamed Student")
    );
    expect(globalMutateMock).toHaveBeenCalledWith(
      "/api/v1/student/me",
      expect.objectContaining({ display_name: "Renamed Student" }),
      { revalidate: true }
    );
  });

  it("cancel discards unsaved changes and restores the read-only name", () => {
    render(<ProfilePage />);
    fireEvent.click(screen.getByRole("button", { name: /edit display name/i }));
    const input = screen.getByLabelText<HTMLInputElement>(/display name/i);
    fireEvent.change(input, { target: { value: "Discarded" } });
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByText("Test Student")).toBeInTheDocument();
    expect(updateProfileNameMock).not.toHaveBeenCalled();
  });

  it("shows a validation error for an empty name and does not submit", () => {
    render(<ProfilePage />);
    fireEvent.click(screen.getByRole("button", { name: /edit display name/i }));
    const input = screen.getByLabelText<HTMLInputElement>(/display name/i);
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: /save name/i }));

    expect(screen.getByRole("alert")).toHaveTextContent(/required/i);
    expect(updateProfileNameMock).not.toHaveBeenCalled();
  });

  it("displays an API error and preserves the current name on failure", async () => {
    updateProfileNameMock.mockRejectedValue(new Error("Unable to save"));
    render(<ProfilePage />);
    fireEvent.click(screen.getByRole("button", { name: /edit display name/i }));
    const input = screen.getByLabelText<HTMLInputElement>(/display name/i);
    fireEvent.change(input, { target: { value: "New Name" } });
    fireEvent.click(screen.getByRole("button", { name: /save name/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Unable to save")
    );
    // Still in edit mode with the typed value preserved; cache untouched.
    expect(updateProfileNameMock).toHaveBeenCalledTimes(1);
    expect(globalMutateMock).not.toHaveBeenCalled();
  });

  it("disables the save control while the request is in flight (no duplicate submit)", async () => {
    let resolveUpdate: (v: unknown) => void = () => {};
    updateProfileNameMock.mockImplementation(
      () => new Promise((resolve) => { resolveUpdate = resolve; })
    );
    render(<ProfilePage />);
    fireEvent.click(screen.getByRole("button", { name: /edit display name/i }));
    const input = screen.getByLabelText<HTMLInputElement>(/display name/i);
    fireEvent.change(input, { target: { value: "New Name" } });
    const save = screen.getByRole("button", { name: /save name/i });
    fireEvent.click(save);

    await waitFor(() => expect(save).toBeDisabled());
    fireEvent.click(save);
    expect(updateProfileNameMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveUpdate({
        id: "x",
        display_name: "New Name",
        roll_number: "2401220999001",
        section_name: "CSE-A",
        role: "STUDENT",
      });
    });
  });

  it("does not render the Change Password control (moved to /login)", () => {
    render(<ProfilePage />);
    expect(screen.queryByRole("button", { name: /change password/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/change password/i)).not.toBeInTheDocument();
  });
});