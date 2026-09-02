"use client";

import { useState } from "react";
import { Switch } from "@base-ui/react/switch";
import {
  AlertTriangle,
  Bell,
  BellRing,
  CalendarDays,
  CheckCircle2,
  Info,
  Loader2,
  RefreshCw,
  Save,
  UserCheck,
} from "lucide-react";
import { ShellDialog } from "@/components/shell/ShellDialog";
import { Button } from "@/components/ui/button";
import { usePreferences, usePreferenceMutation } from "@/hooks/useApi";
import { usePushSubscription } from "@/hooks/usePushSubscription";
import { isVapidConfigured } from "@/lib/push";
import { UserPreferencesUpdate, WeekStart } from "@/types/api";

interface SettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type SaveState =
  | { status: "idle" }
  | { status: "saving" }
  | { status: "saved" }
  | { status: "error"; message: string };

const WEEK_OPTIONS: { value: WeekStart; label: string }[] = [
  { value: "SUNDAY", label: "Sunday" },
  { value: "MONDAY", label: "Monday" },
];

/**
 * Settings — Phase 10D.
 *
 * The three controls are real, API-backed user preferences
 * (GET/PUT /api/v1/student/preferences). Values are initialized from the
 * backend (never hardcoded), changes are reflected locally, and saving is a
 * full-object PUT with honest loading/saving/saved/error states — success is
 * never faked and retry stays available after a failure.
 *
 * Phase 11 wiring: `class_reminders` gates the bell-icon CLASS_REMINDER
 * notifications (shown in the notification center when enabled). The other
 * two are STORAGE/PREFERENCE DATA ONLY: saving them marks no attendance and
 * changes no calendar/analytics calculation.
 */
export function SettingsModal({ open, onOpenChange }: SettingsModalProps) {
  // SWR key is gated on `open` so preferences are fetched when the modal is
  // opened, not unconditionally at shell mount.
  const {
    preferences,
    isLoading,
    isError,
    mutate,
  } = usePreferences(open);
  const { savePreferences } = usePreferenceMutation();
  const {
    supported: browserNotificationsSupported,
    pushSupported: browserPushSupported,
    permission: browserNotificationPermission,
    isWorking: browserPushWorking,
    browserSubscription,
    error: browserPushError,
    enable: enableBrowserNotifications,
    disable: disableBrowserNotifications,
    clearError: clearBrowserPushError,
  } = usePushSubscription(open);

  const [draft, setDraft] = useState<UserPreferencesUpdate | null>(null);
  const [saveState, setSaveState] = useState<SaveState>({ status: "idle" });

  // Reset local state when the modal closes (reopening re-fetches). Follows the
  // "adjust state during render" pattern used by EventFormDialog.
  const [lastOpen, setLastOpen] = useState<boolean | null>(null);
  if (open !== lastOpen) {
    setLastOpen(open);
    if (!open) {
      setDraft(null);
      setSaveState({ status: "idle" });
    }
  }

  const base = draft ?? {
    class_reminders: preferences?.class_reminders ?? false,
    auto_mark_present: preferences?.auto_mark_present ?? false,
    week_starts_on: preferences?.week_starts_on ?? "MONDAY",
  };

  const dirty =
    !!preferences &&
    (draft?.class_reminders !== preferences.class_reminders ||
      draft?.auto_mark_present !== preferences.auto_mark_present ||
      draft?.week_starts_on !== preferences.week_starts_on);

  const controlsDisabled = isLoading || !preferences || saveState.status === "saving";

  const updateDraft = (patch: Partial<UserPreferencesUpdate>) => {
    setDraft((prev) => ({ ...(prev ?? base), ...patch }));
    if (saveState.status !== "idle") setSaveState({ status: "idle" });
  };

  const handleSave = async () => {
    if (!draft || saveState.status === "saving") return;
    setSaveState({ status: "saving" });
    try {
      const saved = await savePreferences(draft);
      mutate(saved, false);
      setDraft(null);
      setSaveState({ status: "saved" });
    } catch (error) {
      const detail =
        error instanceof Error && error.message !== "API request failed"
          ? error.message
          : "The backend did not accept the request.";
      setSaveState({ status: "error", message: detail });
    }
  };

  return (
    <ShellDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Settings"
      description="Preferences are saved to your account"
    >
      <div className="space-y-5">
        {isLoading && !preferences ? (
          <div className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            Loading your preferences…
          </div>
        ) : isError && !preferences ? (
          <div className="flex flex-col gap-3">
            <div className="flex gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
              <p className="text-xs leading-relaxed text-destructive">
                Your preferences could not be loaded. Nothing was changed.
              </p>
            </div>
            <Button variant="outline" onClick={() => mutate()}>
              <RefreshCw className="size-4" aria-hidden="true" />
              Retry
            </Button>
          </div>
        ) : (
          <>
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Notifications
              </h3>
              <div className="mt-2 flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2.5">
                <div className="flex items-center gap-3">
                  <Bell className="size-4 text-muted-foreground" aria-hidden="true" />
                  <span className="text-sm font-medium text-foreground">
                    Class reminders
                  </span>
                </div>
                <Switch.Root
                  checked={base.class_reminders}
                  onCheckedChange={(checked) =>
                    updateDraft({ class_reminders: checked })
                  }
                  disabled={controlsDisabled}
                  className="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-border bg-muted transition-colors data-checked:bg-primary data-disabled:opacity-50"
                >
                  <Switch.Thumb className="block size-3.5 translate-x-0.5 rounded-full bg-foreground/70 transition-transform data-checked:translate-x-[18px] data-checked:bg-white" />
                </Switch.Root>
              </div>
              <div className="mt-2 flex items-start justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2.5">
                <div className="flex min-w-0 items-start gap-3">
                  <BellRing className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground">
                      Browser notifications
                    </p>
                    <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                      {!browserNotificationsSupported ? (
                        "Browser notifications are not supported on this device or browser."
                      ) : browserNotificationPermission === "denied" ? (
                        "Notifications are blocked for this site. Allow them in your browser's site settings."
                      ) : browserNotificationPermission === "default" ? (
                        "Allow this site to show browser notifications."
                      ) : !browserPushSupported ? (
                        "Browser permission is enabled, but push setup is unavailable on this browser."
                      ) : browserSubscription ? (
                        "Browser notifications enabled."
                      ) : browserPushError ? (
                        browserPushError
                      ) : !isVapidConfigured ? (
                        "Browser permission is enabled, but push setup is incomplete — the server VAPID key is configured in a later phase."
                      ) : (
                        "Browser permission is enabled, but push setup is incomplete."
                      )}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {!browserNotificationsSupported ? null
                  : browserNotificationPermission === "denied" ? (
                    <AlertTriangle className="size-4 shrink-0 text-destructive" aria-hidden="true" />
                  ) : browserNotificationPermission === "default" ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => enableBrowserNotifications()}
                      disabled={browserPushWorking}
                    >
                      {browserPushWorking ? (
                        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                      ) : (
                        <BellRing className="size-3.5" aria-hidden="true" />
                      )}
                      Enable browser notifications
                    </Button>
                  ) : browserPushWorking ? (
                    <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden="true" />
                  ) : browserSubscription ? (
                    <>
                      <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden="true" />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => disableBrowserNotifications()}
                        disabled={browserPushWorking}
                      >
                        Disable
                      </Button>
                    </>
                  ) : browserPushError ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => { clearBrowserPushError(); enableBrowserNotifications(); }}
                      disabled={browserPushWorking}
                    >
                      Retry
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => enableBrowserNotifications()}
                      disabled={browserPushWorking}
                    >
                      <BellRing className="size-3.5" aria-hidden="true" />
                      Enable push notifications
                    </Button>
                  )}
                </div>
              </div>
            </section>

            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Attendance
              </h3>
              <div className="mt-2 flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2.5">
                <div className="flex items-center gap-3">
                  <UserCheck className="size-4 text-muted-foreground" aria-hidden="true" />
                  <span className="text-sm font-medium text-foreground">
                    Auto-mark present
                  </span>
                </div>
                <Switch.Root
                  checked={base.auto_mark_present}
                  onCheckedChange={(checked) =>
                    updateDraft({ auto_mark_present: checked })
                  }
                  disabled={controlsDisabled}
                  className="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-border bg-muted transition-colors data-checked:bg-primary data-disabled:opacity-50"
                >
                  <Switch.Thumb className="block size-3.5 translate-x-0.5 rounded-full bg-foreground/70 transition-transform data-checked:translate-x-[18px] data-checked:bg-white" />
                </Switch.Root>
              </div>
            </section>

            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Calendar
              </h3>
              <div className="mt-2 flex items-center justify-between gap-3 rounded-lg border border-border bg-background px-3 py-2.5">
                <div className="flex items-center gap-3">
                  <CalendarDays className="size-4 text-muted-foreground" aria-hidden="true" />
                  <span className="text-sm font-medium text-foreground">
                    Week starts on
                  </span>
                </div>
                <select
                  value={base.week_starts_on}
                  onChange={(e) =>
                    updateDraft({ week_starts_on: e.target.value as WeekStart })
                  }
                  disabled={controlsDisabled}
                  aria-label="Week starts on"
                  className="h-9 sm:h-7 rounded-md border border-border bg-background px-2 text-sm text-foreground disabled:opacity-50"
                >
                  {WEEK_OPTIONS.map(({ value, label }) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            </section>

            <div className="flex gap-2.5 rounded-lg border border-border bg-background p-3">
              <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <p className="text-xs leading-relaxed text-muted-foreground">
                Class reminders are shown in the bell icon when enabled. The
                other preferences are saved to your account for future features
                — saving them does not mark attendance or change calendar
                calculations.
              </p>
            </div>

            {saveState.status === "error" && (
              <div className="flex gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
                <p className="text-xs leading-relaxed text-destructive">
                  Your changes could not be saved: {saveState.message}. Your
                  selections are kept — try again or close to discard.
                </p>
              </div>
            )}

            <div className="flex items-center justify-between gap-2">
              {saveState.status === "saved" ? (
                <span className="flex items-center gap-1.5 text-xs font-medium text-success">
                  <CheckCircle2 className="size-4" aria-hidden="true" />
                  Saved
                </span>
              ) : (
                <span className="text-xs text-muted-foreground">
                  {dirty ? "You have unsaved changes" : "All changes saved"}
                </span>
              )}
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setDraft(null);
                    setSaveState({ status: "idle" });
                  }}
                  disabled={!dirty || saveState.status === "saving"}
                >
                  Discard
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={!dirty || saveState.status === "saving"}
                >
                  {saveState.status === "saving" ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden="true" />
                  ) : (
                    <Save className="size-4" aria-hidden="true" />
                  )}
                  Save
                </Button>
              </div>
            </div>
          </>
        )}
      </div>
    </ShellDialog>
  );
}