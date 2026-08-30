"use client";

import { useState } from "react";
import { Loader2, Power } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AdminEventResponse, UpdateAdminEventRequest, ClassType } from "@/types/api";
import { getRule, CLASS_TYPE_LABELS, SUBSTITUTION_DAYS } from "@/components/events/eventRules";

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

/**
 * Phase 24.9 — Edit/Deactivate Event dialog (HEAD_ADMIN only; backend
 * authoritative). Quiz-schedule-managed QUIZ_DAY events are read-only here
 * (their date/subject/active state is owned by the Quiz Schedule Manager).
 * Deactivation is safe/reversible (no physical deletion).
 */
export function EditEventDialog({
  event, isSubmitting, onUpdate, onDeactivate, onOpenChange,
}: {
  event: AdminEventResponse;
  isSubmitting: boolean;
  onUpdate: (eventId: string, payload: UpdateAdminEventRequest) => Promise<void>;
  onDeactivate: (eventId: string) => Promise<void>;
  onOpenChange: (open: boolean) => void;
}) {
  const rule = getRule(event.event_type);
  const readOnly = event.quiz_schedule_managed;

  const [startDate, setStartDate] = useState(event.start_date);
  const [endDate, setEndDate] = useState(event.end_date);
  const [classType, setClassType] = useState<ClassType | "">(event.class_type ?? "");
  const [subDay, setSubDay] = useState(event.substitution_schedule_override ?? "");
  const [note, setNote] = useState(event.note ?? "");
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (readOnly) { setError("This event is managed by the Quiz Schedule Manager and cannot be edited here."); return; }
    if (endDate < startDate) { setError("End date must not be before start date"); return; }
    setError(null);
    try {
      const payload: UpdateAdminEventRequest = {};
      if (startDate !== event.start_date) payload.start_date = startDate;
      if (endDate !== event.end_date) payload.end_date = endDate;
      if (rule.requiresClassType && classType !== (event.class_type ?? "")) {
        payload.class_type = classType as ClassType;
      }
      if (subDay !== (event.substitution_schedule_override ?? "")) {
        payload.substitution_schedule_override = subDay || null;
      }
      if (event.event_type === "HOLIDAY" && note !== (event.note ?? "")) payload.note = note || null;
      await onUpdate(event.id, payload);
      onOpenChange(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update event");
    }
  };

  const handleDeactivate = async () => {
    if (!confirmDeactivate) { setConfirmDeactivate(true); return; }
    setError(null);
    try { await onDeactivate(event.id); } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to deactivate event");
    }
  };

  return (
    <Dialog open={true} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Event</DialogTitle>
          <DialogDescription>
            {event.event_type} {event.subject_code ? `· ${event.subject_code}` : ""} — {event.start_date}
            {event.end_date !== event.start_date ? ` to ${event.end_date}` : ""}
            {event.quiz_schedule_managed && (
              <span className="mt-1 block">
                <Badge variant="warning">Quiz-managed</Badge> This event is owned by the Quiz
                Schedule Manager — edit it through /admin/quizzes.
              </span>
            )}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Start date</label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} disabled={readOnly} />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">End date</label>
              <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} disabled={readOnly} />
            </div>
          </div>

          {rule.requiresClassType && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Class type</label>
              <select className={selectClass} value={classType} onChange={(e) => setClassType(e.target.value as ClassType)} disabled={readOnly}>
                <option value="">Select class type</option>
                {rule.allowedClassTypes.map((ct) => (
                  <option key={ct} value={ct}>{CLASS_TYPE_LABELS[ct]}</option>
                ))}
              </select>
            </div>
          )}

          {rule.isGlobal && !rule.isClosure && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Substitution day</label>
              <select className={selectClass} value={subDay} onChange={(e) => setSubDay(e.target.value)} disabled={readOnly}>
                <option value="">None</option>
                {SUBSTITUTION_DAYS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          )}

          {event.event_type === "HOLIDAY" && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Reason / occasion</label>
              <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} disabled={readOnly} />
            </div>
          )}

          <DialogFooter className="gap-2">
            {!readOnly && (
              <>
                <Button variant="destructive" onClick={handleDeactivate} disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  <Power className="mr-2 h-4 w-4" />
                  {confirmDeactivate ? "Confirm deactivate" : "Deactivate"}
                </Button>
                <Button onClick={handleSubmit} disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Save changes
                </Button>
              </>
            )}
            <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}