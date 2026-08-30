"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AdminQuizScheduleResponse, ScheduleStatus, UpdateQuizScheduleRequest } from "@/types/api";

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

/**
 * Phase 24.8 — Edit quiz schedule dialog (HEAD_ADMIN only).
 * Update date and/or status. Subject/cycle/elective slot are immutable after
 * creation. The backend synchronizes the QUIZ_DAY event atomically.
 */
export function EditQuizScheduleDialog({
  schedule,
  isSubmitting,
  onUpdate,
  onOpenChange,
}: {
  schedule: AdminQuizScheduleResponse;
  isSubmitting: boolean;
  onUpdate: (scheduleId: string, payload: UpdateQuizScheduleRequest) => Promise<void>;
  onOpenChange: (open: boolean) => void;
}) {
  const [date, setDate] = useState(schedule.date ?? "");
  const [status, setStatus] = useState<ScheduleStatus>(schedule.schedule_status);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (status === ScheduleStatus.SCHEDULED && !date) {
      setError("A scheduled quiz requires a date");
      return;
    }
    setError(null);
    try {
      await onUpdate(schedule.id, {
        date: date || null,
        schedule_status: status,
      });
      onOpenChange(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update quiz schedule");
    }
  };

  return (
    <Dialog open={true} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Quiz Schedule</DialogTitle>
          <DialogDescription>
            <strong>{schedule.subject_code}</strong> — {schedule.cycle_label}
            {schedule.is_elective && (
              <span className="ml-1">
                <Badge variant="primary" className="ml-2 text-xs">
                  {schedule.elective_slot === "ELECTIVE_I" ? "DE-I" : "DE-II"}
                </Badge>
              </span>
            )}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Status</label>
              <select className={selectClass} value={status} onChange={(e) => setStatus(e.target.value as ScheduleStatus)}>
                <option value={ScheduleStatus.SCHEDULED}>Scheduled</option>
                <option value={ScheduleStatus.UNRESOLVED}>Unresolved</option>
                <option value={ScheduleStatus.CANCELLED}>Cancelled</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Date</label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>Cancel</Button>
            <Button onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save changes
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}