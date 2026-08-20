"use client";

import { ReactNode } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

type ShellDialogWidth = "sm" | "md" | "lg";

const WIDTH_CLASSES: Record<ShellDialogWidth, string> = {
  sm: "sm:max-w-sm",
  md: "sm:max-w-md",
  lg: "sm:max-w-lg",
};

interface ShellDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  width?: ShellDialogWidth;
  children: ReactNode;
}

/**
 * Shared modal foundation for the global shell dialogs (Profile,
 * Appearance, Settings, Feedback, Install App).
 *
 * Provides the consistent backdrop, focus management, Escape handling,
 * body scroll lock (Base UI Dialog modal mode), responsive width,
 * accessible dialog semantics, header and close button.
 *
 * Phase 12A: the dialog is capped at 90dvh and scrolls vertically so its
 * content stays reachable on short mobile screens (same pattern as
 * EventFormDialog). On desktop viewports the cap only engages for content
 * taller than 90% of the viewport, so existing dialog appearance is
 * preserved.
 */
export function ShellDialog({
  open,
  onOpenChange,
  title,
  description,
  width = "sm",
  children,
}: ShellDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={cn("max-h-[90dvh] gap-0 overflow-y-auto p-0", WIDTH_CLASSES[width])}>
        <DialogHeader className="border-b border-border px-5 py-4">
          <DialogTitle>{title}</DialogTitle>
          {description && (
            <DialogDescription className="mt-0.5">{description}</DialogDescription>
          )}
        </DialogHeader>
        <div className="px-5 py-4">{children}</div>
      </DialogContent>
    </Dialog>
  );
}

interface ShellFieldProps {
  label: string;
  value?: ReactNode;
  unavailable?: boolean;
  mono?: boolean;
}

/**
 * Consistent label/value row used by the Profile modal.
 */
export function ShellField({ label, value, unavailable, mono }: ShellFieldProps) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      {unavailable ? (
        <span className="text-sm text-muted-foreground" title="Not available in the backend data model">
          —
        </span>
      ) : (
        <span
          className={cn(
            "text-right text-sm font-medium text-foreground",
            mono && "font-mono"
          )}
        >
          {value ?? "—"}
        </span>
      )}
    </div>
  );
}