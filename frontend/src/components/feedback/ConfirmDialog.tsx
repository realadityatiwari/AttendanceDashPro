"use client";

import { useState, type ReactNode } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: ReactNode;
  /** Label describing the actual operation (never generic "Yes"/"OK"). */
  confirmLabel: string;
  cancelLabel?: string;
  /** "destructive" renders the confirm action in the destructive treatment. */
  variant?: "destructive" | "default";
  /**
   * The confirmed action. The dialog disables its controls and stays open
   * until the promise settles, then closes — the caller owns mutation
   * semantics and feedback (toasts/inline errors).
   */
  onConfirm: () => Promise<void> | void;
}

/**
 * Shared confirmation dialog for destructive/meaningful actions (Phase 3,
 * D-11 policy). Built on the existing Dialog primitive — focus management,
 * Escape handling and scroll lock are inherited; no second modal framework.
 *
 * The confirm action always requires this explicit step: the triggering
 * control must never mutate directly. Double-submission is prevented by a
 * pending lock on the confirm control.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  variant = "default",
  onConfirm,
}: ConfirmDialogProps) {
  const [pending, setPending] = useState(false);

  const handleConfirm = async () => {
    if (pending) return;
    setPending(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={pending}
          >
            {cancelLabel}
          </Button>
          <Button
            variant={variant === "destructive" ? "destructive" : "default"}
            onClick={handleConfirm}
            disabled={pending}
          >
            {pending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : null}
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
