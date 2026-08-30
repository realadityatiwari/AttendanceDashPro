"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useAdminSessions, useAdminSemesters, useAdminSubjects } from "@/hooks/useApi";
import { CreateAdminEventRequest, ClassType, EventType } from "@/types/api";
import { getRule, defaultDurationMode, CLASS_TYPE_LABELS, SUBSTITUTION_DAYS, ELECTIVE_SLOT_LABELS } from "@/components/events/eventRules";

const EVENT_TYPE_LABELS: Record<string, string> = {
  EXTRA_LECTURE: "Extra Lecture", EXTRA_TUTORIAL: "Extra Tutorial",
  EXTRA_PRACTICAL: "Extra Practical", CLASS_CANCELLED: "Class Cancelled",
  CLASS_MODIFIED: "Class Modified", SURPRISE_QUIZ: "Surprise Quiz",
  QUIZ_DAY: "Quiz Day", HOLIDAY: "Holiday", PUBLIC_HOLIDAY: "Public Holiday",
  INSTITUTE_HOLIDAY: "Institute Holiday", FESTIVAL_HOLIDAY: "Festival Holiday",
  EMERGENCY_CLOSURE: "Emergency Closure", SEMESTER_BREAK: "Semester Break",
  MID_SEMESTER_BREAK: "Mid-Semester Break", WORKING_DAY_OVERRIDE: "Working Day Override",
  WORKING_SATURDAY: "Working Saturday", LAB_CANCELLED: "Lab Cancelled",
  MID_SEM_PRACTICAL: "Mid-Sem Practical",
};

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

/** Field-visibility helper: does this event type show a note (reason)? */
function supportsNote(eventType: EventType): boolean {
  return eventType === EventType.HOLIDAY;
}

/**
 * Phase 24.9 — Create Event dialog (HEAD_ADMIN only; backend authoritative).
 * Field visibility mirrors the shared eventRules map; the backend registry is
 * the final validator. QUIZ_DAY creation is allowed for standalone quiz-day
 * events; schedule-managed quiz dates belong to /admin/quizzes.
 */
export function CreateEventDialog({
  open, isSubmitting, onCreate, onOpenChange,
}: {
  open: boolean;
  isSubmitting: boolean;
  onCreate: (payload: CreateAdminEventRequest) => Promise<void>;
  onOpenChange: (open: boolean) => void;
}) {
  const { sessions } = useAdminSessions();
  const [sessionId, setSessionId] = useState("");
  const { semesters } = useAdminSemesters(sessionId || null);
  const [semesterId, setSemesterId] = useState("");
  const { subjects } = useAdminSubjects();

  const [eventType, setEventType] = useState<EventType>(EventType.EXTRA_LECTURE);
  const [subjectId, setSubjectId] = useState("");
  const [classType, setClassType] = useState<ClassType | "">("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [subDay, setSubDay] = useState("");
  const [note, setNote] = useState("");
  const isWorkingDay: "" | boolean = "";
  const [error, setError] = useState<string | null>(null);

  const rule = getRule(eventType);
  const durationMode = defaultDurationMode(eventType);

  const scopedSubjects = (subjects?.items ?? []).filter(
    (s) => !semesterId || s.semester_id === semesterId
  );

  const handleSubmit = async () => {
    if (!startDate) { setError("Start date is required"); return; }
    if (rule.requiresSubject && !subjectId) { setError("This event type requires a subject"); return; }
    if (rule.requiresClassType && !classType) { setError("This event type requires a class type"); return; }
    const effectiveEnd = durationMode === "single" ? startDate : (endDate || startDate);
    if (effectiveEnd < startDate) { setError("End date must not be before start date"); return; }
    setError(null);
    try {
      await onCreate({
        event_type: eventType,
        start_date: startDate,
        end_date: effectiveEnd,
        subject_id: rule.requiresSubject ? subjectId : null,
        elective_slot: null,
        class_type: rule.requiresClassType ? (classType as ClassType) : null,
        substitution_schedule_override: subDay || null,
        note: supportsNote(eventType) && note ? note : null,
        is_working_day: isWorkingDay === "" ? null : isWorkingDay,
        active: true,
      });
      onOpenChange(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create event");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Event</DialogTitle>
          <DialogDescription>
            Create an academic event through the canonical event architecture.
            Field availability follows the event type; the backend validates.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="space-y-2">
            <label className="text-sm font-medium">Event type</label>
            <select className={selectClass} value={eventType}
              onChange={(e) => { setEventType(e.target.value as EventType); setSubjectId(""); setClassType(""); }}>
              {Object.entries(EVENT_TYPE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Start date</label>
              <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </div>
            {durationMode === "range" && (
              <div className="space-y-2">
                <label className="text-sm font-medium">End date</label>
                <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
            )}
          </div>

          {rule.requiresSubject && (
            <>
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
                      {s.elective_slot ? ` (${ELECTIVE_SLOT_LABELS[s.elective_slot]})` : ""}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}

          {rule.requiresClassType && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Class type</label>
              <select className={selectClass} value={classType} onChange={(e) => setClassType(e.target.value as ClassType)}>
                <option value="">Select class type</option>
                {rule.allowedClassTypes.map((ct) => (
                  <option key={ct} value={ct}>{CLASS_TYPE_LABELS[ct]}</option>
                ))}
              </select>
            </div>
          )}

          {rule.isGlobal && !rule.isClosure && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Substitution day (optional)</label>
              <select className={selectClass} value={subDay} onChange={(e) => setSubDay(e.target.value)}>
                <option value="">None</option>
                {SUBSTITUTION_DAYS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          )}

          {supportsNote(eventType) && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Reason / occasion (required for Holiday)</label>
              <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} />
            </div>
          )}

          {eventType === EventType.QUIZ_DAY && (
            <div className="rounded-md border border-warning/40 bg-warning/10 p-2 text-xs text-warning">
              Quiz Day events that match a scheduled quiz are managed by the
              Quiz Schedule Manager. Use /admin/quizzes to manage quiz dates and
              status. Standalone quiz-day events may be created here.
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>Cancel</Button>
            <Button onClick={handleSubmit} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create event
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}