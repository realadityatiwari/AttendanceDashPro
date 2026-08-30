"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useAdminQuizCycles, useAdminSessions, useAdminSemesters, useAdminSubjects } from "@/hooks/useApi";
import { CreateQuizScheduleRequest, ScheduleStatus } from "@/types/api";

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

/**
 * Phase 24.8 — Create quiz schedule dialog (HEAD_ADMIN only; backend enforces).
 * Fields come from REAL backend capability; targets are the subject catalog
 * (common subject vs elective slot via the subject's catalog marker).
 */
export function CreateQuizScheduleDialog({
  open,
  isSubmitting,
  onCreate,
  onOpenChange,
}: {
  open: boolean;
  isSubmitting: boolean;
  onCreate: (payload: CreateQuizScheduleRequest) => Promise<void>;
  onOpenChange: (open: boolean) => void;
}) {
  const { cycles } = useAdminQuizCycles();
  const { sessions } = useAdminSessions();
  const [sessionId, setSessionId] = useState("");
  const { semesters } = useAdminSemesters(sessionId || null);
  const [semesterId, setSemesterId] = useState("");
  const { subjects } = useAdminSubjects();

  const [subjectId, setSubjectId] = useState("");
  const [cycleId, setCycleId] = useState("");
  const [date, setDate] = useState("");
  const [status, setStatus] = useState<ScheduleStatus>(ScheduleStatus.SCHEDULED);
  const [error, setError] = useState<string | null>(null);

  // UX filter only — the backend re-validates scope and semester context.
  const scopedSubjects = (subjects?.items ?? []).filter((s) =>
    !semesterId || s.semester_id === semesterId
  );

  const handleSubmit = async () => {
    if (!subjectId || !cycleId) {
      setError("Subject and cycle are required");
      return;
    }
    if (status === ScheduleStatus.SCHEDULED && !date) {
      setError("A scheduled quiz requires a date");
      return;
    }
    setError(null);
    try {
      await onCreate({
        subject_id: subjectId,
        quiz_cycle_id: cycleId,
        date: date || null,
        schedule_status: status,
      });
      onOpenChange(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create quiz schedule");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Create Quiz Schedule</DialogTitle>
          <DialogDescription>
            Configure a quiz for a subject (common or elective catalog) and cycle.
            The derived QUIZ_DAY event is synchronized by the backend.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="space-y-2">
            <label className="text-sm font-medium">Academic session</label>
            <select className={selectClass} value={sessionId} onChange={(e) => { setSessionId(e.target.value); setSemesterId(""); }}>
              <option value="">Select a session</option>
              {(sessions ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.name}{s.is_active ? " (active)" : ""}</option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Semester</label>
            <select className={selectClass} value={semesterId} onChange={(e) => setSemesterId(e.target.value)} disabled={!sessionId}>
              <option value="">Select a semester</option>
              {(semesters ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Subject</label>
            <select className={selectClass} value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
              <option value="">Select subject</option>
              {scopedSubjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.code} — {s.name}
                  {s.elective_slot ? ` (${s.elective_slot === "ELECTIVE_I" ? "DE-I" : "DE-II"})` : " (common)"}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">Cycle</label>
            <select className={selectClass} value={cycleId} onChange={(e) => setCycleId(e.target.value)}>
              <option value="">Select cycle</option>
              {(cycles ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label} (threshold {c.lecture_threshold}%)
                </option>
              ))}
            </select>
          </div>
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
              Create schedule
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}