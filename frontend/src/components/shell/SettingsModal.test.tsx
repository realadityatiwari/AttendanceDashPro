import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { SettingsModal } from "./SettingsModal";
import { usePushSubscription } from "@/hooks/usePushSubscription";
import type { UserPreferences } from "@/types/api";

// Minimal stand-in for the DOM PushSubscription the hook would return.
const fakeSubscription = { endpoint: "https://example.test" } as PushSubscription;

/**
 * UIA-002 regression coverage: the Settings modal must open clean (Save and
 * Discard disabled, no unsaved-changes message), turn dirty only after a real
 * modification, clear dirty when edits are reverted, save only real drafts,
 * and reset on discard / close-reopen.
 *
 * usePreferences / usePreferenceMutation / usePushSubscription are mocked so
 * the test exercises the component's dirty-state logic (the actual bug)
 * against a fixed persisted snapshot, exactly as the backend delivers it.
 */

vi.mock("@/hooks/useApi", () => ({
  usePreferences: vi.fn(),
  usePreferenceMutation: vi.fn(),
}));

vi.mock("@/hooks/usePushSubscription", () => ({
  usePushSubscription: vi.fn(),
}));

import { usePreferenceMutation, usePreferences } from "@/hooks/useApi";

const PERSISTED: UserPreferences = {
  class_reminders: false,
  auto_mark_present: false,
  week_starts_on: "MONDAY",
};

const mutate = vi.fn();
const savePreferences = vi.fn();
const pushMock = vi.mocked(usePushSubscription);

function mockBackend(preferences: UserPreferences | null = PERSISTED) {
  (usePreferences as unknown as Mock).mockReturnValue({
    preferences,
    isLoading: false,
    isError: false,
    mutate,
  });
  (usePreferenceMutation as unknown as Mock).mockReturnValue({ savePreferences });
}

function mockPushPermissionGranted() {
  pushMock.mockReturnValue({
    supported: true,
    pushSupported: true,
    permission: "granted",
    isWorking: false,
    browserSubscription: fakeSubscription,
    backendSubscription: null,
    requestPermission: vi.fn(),
    error: null,
    enable: vi.fn(),
    disable: vi.fn(),
    clearError: vi.fn(),
  });
}

// The state observed at runtime in dev: browser permission granted, no VAPID
// configuration → the widest action ("Enable push notifications") and the
// long "aren't fully set up yet" description in the same row.
function mockPushNotConfigured() {
  pushMock.mockReturnValue({
    supported: true,
    pushSupported: true,
    permission: "granted",
    isWorking: false,
    browserSubscription: null,
    backendSubscription: null,
    requestPermission: vi.fn(),
    error: null,
    enable: vi.fn(),
    disable: vi.fn(),
    clearError: vi.fn(),
  });
}

const remindersSwitch = () =>
  screen.getByRole("switch", { name: /class reminders/i });

beforeEach(() => {
  vi.clearAllMocks();
  mockBackend();
  mockPushPermissionGranted();
  savePreferences.mockResolvedValue(PERSISTED);
});

describe("SettingsModal dirty state (UIA-002)", () => {
  it("opens clean: no unsaved-changes message, Save and Discard disabled", () => {
    render(<SettingsModal open onOpenChange={vi.fn()} />);
    expect(screen.getByText("All changes saved")).toBeInTheDocument();
    expect(
      screen.queryByText("You have unsaved changes")
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /discard/i })).toBeDisabled();
  });

  it("shows the persisted values on open", () => {
    render(<SettingsModal open onOpenChange={vi.fn()} />);
    expect(remindersSwitch()).toHaveAttribute("aria-checked", "false");
  });

  it("turns dirty after a real modification and enables Save and Discard", () => {
    render(<SettingsModal open onOpenChange={vi.fn()} />);
    fireEvent.click(remindersSwitch());
    expect(screen.getByText("You have unsaved changes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeEnabled();
    expect(screen.getByRole("button", { name: /discard/i })).toBeEnabled();
  });

  it("clears the dirty state when the edit is reverted to the persisted value", () => {
    render(<SettingsModal open onOpenChange={vi.fn()} />);
    fireEvent.click(remindersSwitch());
    expect(screen.getByText("You have unsaved changes")).toBeInTheDocument();
    fireEvent.click(remindersSwitch()); // back to persisted value
    expect(screen.getByText("All changes saved")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /discard/i })).toBeDisabled();
  });

  it("saves the draft when dirty, then returns to the clean state", async () => {
    render(<SettingsModal open onOpenChange={vi.fn()} />);
    fireEvent.click(remindersSwitch());
    savePreferences.mockResolvedValue({ ...PERSISTED, class_reminders: true });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => {
      expect(savePreferences).toHaveBeenCalledWith({
        class_reminders: true,
        auto_mark_present: false,
        week_starts_on: "MONDAY",
      });
    });
    // Success feedback is the distinct "Saved" confirmation…
    await waitFor(() => {
      expect(screen.getByText("Saved")).toBeInTheDocument();
    });
    // …announced to screen readers (25.UX-7: the save outcome is a direct
    // consequence of the user's action, so the status slot has role=status).
    expect(screen.getByText("Saved")).toHaveAttribute("role", "status");
    // …and the dirty state has cleared: Save disabled again.
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    expect(
      screen.queryByText("You have unsaved changes")
    ).not.toBeInTheDocument();
  });

  it("does not call the API when Save is triggered with no draft", () => {
    render(<SettingsModal open onOpenChange={vi.fn()} />);
    const save = screen.getByRole("button", { name: /save/i });
    expect(save).toBeDisabled();
    fireEvent.click(save);
    expect(savePreferences).not.toHaveBeenCalled();
  });

  it("resets the draft when Discard is clicked", () => {
    render(<SettingsModal open onOpenChange={vi.fn()} />);
    fireEvent.click(remindersSwitch());
    expect(screen.getByText("You have unsaved changes")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /discard/i }));
    expect(screen.getByText("All changes saved")).toBeInTheDocument();
    expect(remindersSwitch()).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });

  it("resets to the clean state after close and reopen", async () => {
    const { rerender } = render(<SettingsModal open onOpenChange={vi.fn()} />);
    fireEvent.click(remindersSwitch());
    expect(screen.getByText("You have unsaved changes")).toBeInTheDocument();

    rerender(<SettingsModal open={false} onOpenChange={vi.fn()} />);
    rerender(<SettingsModal open onOpenChange={vi.fn()} />);

    expect(await screen.findByText("All changes saved")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
    expect(remindersSwitch()).toHaveAttribute("aria-checked", "false");
  });
});

describe("SettingsModal browser notifications row (UIA-010)", () => {
  it("keeps title, full description and action rendered in the granted state", () => {
    render(<SettingsModal open onOpenChange={vi.fn()} />);
    expect(screen.getByText("Browser notifications")).toBeInTheDocument();
    expect(
      screen.getByText("Browser notifications enabled.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^disable$/i })).toBeInTheDocument();
  });

  it("renders the wide enable action with the full description intact (no collapsed copy)", () => {
    mockPushNotConfigured();
    render(<SettingsModal open onOpenChange={vi.fn()} />);
    expect(
      screen.getByRole("button", { name: /enable push notifications/i })
    ).toBeInTheDocument();
    // The exact full sentence must survive rendering — a squeezed row used to
    // wrap this copy one word per line (visual collapse verified at runtime).
    expect(
      screen.getByText(
        "Browser permission is enabled, but push notifications aren't fully set up yet."
      )
    ).toBeInTheDocument();
  });

  it("structures the row so the text block keeps a readable minimum width", () => {
    render(<SettingsModal open onOpenChange={vi.fn()} />);
    const row = screen
      .getByText("Browser notifications")
      .closest("div[class*='rounded-lg']");
    expect(row).not.toBeNull();
    expect(row?.className).toContain("flex-wrap");
    const textBlock = screen
      .getByText("Browser notifications")
      .closest("div.min-w-48");
    expect(textBlock).not.toBeNull();
  });
});
