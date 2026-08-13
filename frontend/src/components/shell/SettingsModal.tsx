"use client";

import { Switch } from "@base-ui/react/switch";
import { Bell, UserCheck, CalendarDays, Info } from "lucide-react";
import { ShellDialog } from "@/components/shell/ShellDialog";

interface SettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Settings are intentionally NOT wired to fake local persistence: the
 * backend has no user-preferences table or endpoint, and these features
 * (notifications, auto-marking, calendar week start) do not exist anywhere
 * in the current architecture. The controls are rendered in an explicit
 * disabled state with the required backend work documented in task.md.
 */
export function SettingsModal({ open, onOpenChange }: SettingsModalProps) {
  return (
    <ShellDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Settings"
      description="Preferences are pending backend persistence support"
    >
      <div className="space-y-5">
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
              disabled
              className="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-border bg-muted transition-colors data-checked:bg-primary data-disabled:opacity-50"
            >
              <Switch.Thumb className="block size-3.5 translate-x-0.5 rounded-full bg-foreground/70 transition-transform data-checked:translate-x-[18px] data-checked:bg-white" />
            </Switch.Root>
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
              disabled
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
              disabled
              defaultValue="monday"
              aria-label="Week starts on"
              className="h-7 rounded-md border border-border bg-background px-2 text-sm text-muted-foreground disabled:opacity-50"
            >
              <option value="sunday">Sunday</option>
              <option value="monday">Monday</option>
            </select>
          </div>
        </section>

        <div className="flex gap-2.5 rounded-lg border border-border bg-background p-3">
          <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <p className="text-xs leading-relaxed text-muted-foreground">
            These settings are disabled because no persistence layer exists
            yet. A user-preferences table and GET/PUT endpoints are required
            before they can be made real (tracked in task.md). Nothing here
            would survive a reload, so no fake state is stored.
          </p>
        </div>
      </div>
    </ShellDialog>
  );
}