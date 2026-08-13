"use client";

import { Moon, Sun, Monitor, Check, Info } from "lucide-react";
import { ShellDialog } from "@/components/shell/ShellDialog";
import { cn } from "@/lib/utils";

interface AppearanceModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const THEMES = [
  { id: "dark", label: "Dark", icon: Moon, supported: true },
  { id: "light", label: "Light", icon: Sun, supported: false },
  { id: "system", label: "System", icon: Monitor, supported: false },
] as const;

/**
 * Appearance: Dark is the only theme currently supported by the product
 * (the design tokens in globals.css are locked to the dark palette and the
 * root layout hard-codes the `dark` class). Light/System are shown in an
 * explicit disabled state instead of pretending to work. There is nothing
 * to persist until a light palette exists, so no local preference is stored.
 */
export function AppearanceModal({ open, onOpenChange }: AppearanceModalProps) {
  return (
    <ShellDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Appearance"
      description="Choose how the app looks on this device"
    >
      <div className="space-y-2" role="radiogroup" aria-label="Theme">
        {THEMES.map(({ id, label, icon: Icon, supported }) => {
          const selected = id === "dark";
          return (
            <button
              key={id}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={!supported}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg border border-border bg-background px-3 py-2.5 text-left transition-colors",
                supported
                  ? "cursor-default ring-1 ring-primary/30"
                  : "cursor-not-allowed opacity-50"
              )}
            >
              <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
              <span className="flex-1 text-sm font-medium text-foreground">
                {label}
              </span>
              {supported && (
                <span className="flex items-center gap-1.5 text-xs font-medium text-primary">
                  <Check className="size-3.5" aria-hidden="true" />
                  Current
                </span>
              )}
              {!supported && (
                <span className="text-xs text-muted-foreground">Coming soon</span>
              )}
            </button>
          );
        })}
      </div>

      <div className="mt-4 flex gap-2.5 rounded-lg border border-border bg-background p-3">
        <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <p className="text-xs leading-relaxed text-muted-foreground">
          Only Dark mode is currently supported. Light and System themes need a
          light palette in the Phase 1 design tokens before they can be enabled;
          the preference will be persisted once switching is implemented.
        </p>
      </div>
    </ShellDialog>
  );
}