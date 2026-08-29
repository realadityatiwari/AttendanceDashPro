"use client";

import { useState } from "react";
import { Loader2, Square } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { TimetableEntryAdminResponse } from "@/types/api";

const DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

/**
 * Phase 24.7-D/E — Explicit deactivation confirmation dialog.
 * Never silently deletes timetable entries. Deactivation is soft
 * (is_active=false) server-side; the entry remains for history. Any backend
 * failure (403 scope, 404, 409) is surfaced inside the dialog — the entry is
 * NOT removed and no success is claimed.
 */
export function DeactivateTimetableEntryDialog({
  entry,
  isSubmitting,
  onDeactivate,
  onOpenChange,
}: {
  entry: TimetableEntryAdminResponse;
  isSubmitting: boolean;
  onDeactivate: (entryId: string) => Promise<void>;
  onOpenChange: (open: boolean) => void;
}) {
  const [error, setError] = useState<string | null>(null);

  const handleDeactivate = async () => {
    setError(null);
    try {
      await onDeactivate(entry.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Deactivation failed");
    }
  };

  const handleCancel = () => {
    setError(null);
    onOpenChange(false);
  };

  return (
    <Dialog open={true} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Deactivate timetable entry?</DialogTitle>
          <DialogDescription>
            <strong>{entry.subject_code}</strong> — {entry.start_time.slice(0, 5)}–
            {entry.end_time.slice(0, 5)} on {DAY_LABELS[entry.day_of_week]}
            {entry.subsection_name ? ` (${entry.subsection_name})` : ""}. Deactivated
            entries no longer block new schedule entries and remain visible as
            historical data.
          </DialogDescription>
        </DialogHeader>
        {error && (
          <p className="text-sm text-destructive bg-destructive/10 border border-destructive/30 rounded-md p-2">
            {error}
          </p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={handleCancel} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={handleDeactivate} disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Square className="mr-2 h-4 w-4" />}
            Deactivate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}