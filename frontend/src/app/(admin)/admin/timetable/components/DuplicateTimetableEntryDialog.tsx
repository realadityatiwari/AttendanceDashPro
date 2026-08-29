"use client";

import { useState } from "react";
import { Copy, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  TimetableEntryAdminResponse,
  DuplicateTimetableEntryRequest,
  TimetableConflict,
  TimetableConflictResponse,
} from "@/types/api";

const DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

/**
 * Phase 24.7-D/E — Duplicate timetable entry dialog.
 *
 * Server-side duplication: the source entry's subject, section, subsection,
 * class type, elective slot, and active state are copied by the backend.
 * The user may override day, time, and room. Full validation + conflict
 * detection run on the backend (409 on conflict — never silently overwrites).
 * The dialog displays the backend's error message verbatim (only fields
 * the backend returned) and distinguishes 409 conflict with a styled banner.
 */
export function DuplicateTimetableEntryDialog({
  entry,
  isSubmitting,
  onDuplicate,
  onOpenChange,
}: {
  entry: TimetableEntryAdminResponse;
  isSubmitting: boolean;
  onDuplicate: (entryId: string, payload: DuplicateTimetableEntryRequest) => Promise<void>;
  onOpenChange: (open: boolean) => void;
}) {
  const [day, setDay] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [room, setRoom] = useState("");
  const [error, setError] = useState<{ message: string; status?: number; conflicts?: TimetableConflict[] } | null>(null);

  const handleSubmit = async () => {
    if (day !== "" && (startTime === "" || endTime === "")) {
      setError({ message: "When overriding the day, both start and end time are required" });
      return;
    }
    if (startTime && endTime && endTime <= startTime) {
      setError({ message: "End time must be after start time" });
      return;
    }
    setError(null);
    const payload: DuplicateTimetableEntryRequest = {};
    if (day !== "") payload.day_of_week = parseInt(day, 10);
    if (startTime) payload.start_time = startTime;
    if (endTime) payload.end_time = endTime;
    if (room) payload.room = room;
    payload.is_active = entry.is_active;
    try {
      await onDuplicate(entry.id, payload);
    } catch (err: unknown) {
      const e2 = err as Error & { status?: number; body?: TimetableConflictResponse };
      const structuredDetail = e2.body?.detail;
      setError({
        message: e2.message || "Duplicate failed",
        status: e2.status,
        conflicts: structuredDetail && typeof structuredDetail === "object"
          ? structuredDetail.conflicts
          : undefined,
      });
    }
  };

  const selectClass =
    "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <Dialog open={true} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Duplicate Timetable Entry</DialogTitle>
          <DialogDescription>
            Copy <strong>{entry.subject_code}</strong> ({entry.start_time.slice(0, 5)}–
            {entry.end_time.slice(0, 5)} on {DAY_LABELS[entry.day_of_week]}).
            The source entry&apos;s subject, section, class type, elective slot, and
            active state are preserved. Leave the fields below empty to copy
            the source day/time/room, or override them. The backend runs full
            validation + conflict detection.
          </DialogDescription>
        </DialogHeader>
        {error && (
          <div
            className={`rounded-md border p-2 text-sm ${
              error.status === 409
                ? "border-warning/40 bg-warning/10 text-warning"
                : "border-destructive/30 bg-destructive/10 text-destructive"
            }`}
          >
            {error.status === 409 && (
              <p className="mb-1 font-medium">Schedule conflict — the backend rejected this duplicate.</p>
            )}
            <p>{error.message}</p>
            {error.conflicts && error.conflicts.length > 0 && (
              <ul className="mt-1 space-y-0.5">
                {error.conflicts.map((c, i) => (
                  <li key={i} className="text-xs">
                    &#8226; {c.subject_code} ({c.section_name}) on {DAY_LABELS[c.day_of_week]} {c.start_time.slice(0, 5)}&ndash;{c.end_time.slice(0, 5)}
                    {c.subsection_name ? ` \u00B7 ${c.subsection_name}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Day (override)</label>
            <select className={selectClass} value={day} onChange={(e) => setDay(e.target.value)}>
              <option value="">Copy source day</option>
              {DAY_LABELS.map((l, i) => (
                <option key={i} value={i}>{l}</option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Room (override)</label>
            <Input placeholder="e.g. 201" value={room} onChange={(e) => setRoom(e.target.value)} maxLength={100} />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Start time (override)</label>
            <Input type="time" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">End time (override)</label>
            <Input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Copy className="mr-2 h-4 w-4" />}
            Duplicate
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}