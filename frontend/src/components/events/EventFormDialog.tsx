"use client";

import { useMemo, useState } from "react";
import { AcademicEventPayload, AcademicEventResponse, ClassType, EventType } from "@/types/api";
import { useSubjects, useEventMutations } from "@/hooks/useApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { humanizeEventType } from "@/components/events/EventRow";
import { getRule, SUBSTITUTION_DAYS, CLASS_TYPE_LABELS, STUDENT_CREATABLE_EVENT_TYPES } from "@/components/events/eventRules";
import { AlertCircle } from "lucide-react";

const TYPE_OPTIONS = Object.values(EventType);

interface EventFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Existing event for edit mode; null = create mode. */
  event: AcademicEventResponse | null;
  onSaved: () => void;
  /**
   * Attendance-spec alignment: admins may create every event type; students
   * are limited to the flexible subject-scoped types (extras, cancellations,
   * surprise quizzes) for their own enrolled subjects. The backend remains
   * authoritative — this only drives which options the form exposes.
   */
  isAdmin?: boolean;
}

interface FormState {
  event_type: EventType;
  start_date: string;
  end_date: string;
  subject_id: string;
  class_type: string;
  is_working_day: string;
  substitution_schedule_override: string;
  note: string;
  active: boolean;
}

function initialState(event: AcademicEventResponse | null, isAdmin: boolean): FormState {
  const defaultType = event?.event_type ?? (isAdmin ? EventType.PUBLIC_HOLIDAY : EventType.EXTRA_LECTURE);
  return {
    event_type: defaultType,
    start_date: event?.start_date ?? "",
    end_date: event?.end_date ?? "",
    subject_id: event?.subject_id ?? "",
    class_type: event?.class_type ?? "",
    is_working_day: event?.is_working_day === null || event?.is_working_day === undefined
      ? "" : String(event.is_working_day),
    substitution_schedule_override: event?.substitution_schedule_override ?? "",
    note: event?.note ?? "",
    active: event?.active ?? true,
  };
}

const selectClass =
  "h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30 [color-scheme:dark]";
const fieldClass = "flex flex-col gap-1";
const labelClass = "text-[10px] uppercase tracking-wider text-muted-foreground";

/**
 * Event create/edit form (Phase 6.5 + attendance-spec alignment). Exposes
 * only fields the AcademicEvent model actually has; field visibility is
 * driven by the registry mirror (eventRules.ts), while the backend validation
 * registry remains authoritative. Handles loading, validation, 403/404/409/
 * 422, and successful mutations.
 */
export function EventFormDialog({ open, onOpenChange, event, onSaved, isAdmin = true }: EventFormDialogProps) {
  const isEdit = event !== null;
  const { subjects } = useSubjects();
  const { createEvent, updateEvent } = useEventMutations();
  const [form, setForm] = useState<FormState>(() => initialState(event, isAdmin));
  const [localError, setLocalError] = useState("");
  const [serverError, setServerError] = useState("");
  const [loading, setLoading] = useState(false);

  // Students may only create the flexible subject-scoped types.
  const typeOptions = isAdmin ? TYPE_OPTIONS : STUDENT_CREATABLE_EVENT_TYPES;

  // Re-seed the form whenever the dialog is (re)opened for a different event.
  const [lastKey, setLastKey] = useState<string | null>(null);
  const key = `${open ? "open" : "closed"}:${event?.id ?? "new"}`;
  if (key !== lastKey) {
    setLastKey(key);
    if (open) {
      setForm(initialState(event, isAdmin));
      setLocalError("");
      setServerError("");
    }
  }

  const rule = getRule(form.event_type);
  const subjectsForEvent = useMemo(() => subjects ?? [], [subjects]);

  const set = <K extends keyof FormState>(field: K, value: FormState[K]) => {
    setForm(prev => ({ ...prev, [field]: value }));
    setServerError("");
  };

  // Phase 9.1: event types with a single allowed class type (the laboratory
  // events — practical only) auto-fill it; the class-type selector is hidden
  // because there is nothing to disambiguate.
  const singleClassType = rule.requiresClassType && rule.allowedClassTypes.length === 1
    ? rule.allowedClassTypes[0]
    : null;
  if (singleClassType && form.class_type !== singleClassType) {
    set("class_type", singleClassType);
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError("");
    setLocalError("");

    if (!form.start_date || !form.end_date) {
      setLocalError("Start and end dates are required.");
      return;
    }
    if (form.start_date > form.end_date) {
      setLocalError("Start date must be on or before the end date.");
      return;
    }
    if (rule.requiresSubject && !form.subject_id) {
      setLocalError("This event type requires a subject.");
      return;
    }
    if (rule.requiresClassType && !form.class_type) {
      setLocalError("This event type requires a class type.");
      return;
    }

    const payload: AcademicEventPayload = {
      event_type: form.event_type,
      start_date: form.start_date,
      end_date: form.end_date,
      subject_id: rule.requiresSubject ? form.subject_id : null,
      class_type: rule.requiresClassType ? (form.class_type as ClassType) : null,
      is_working_day: form.is_working_day === "" ? null : form.is_working_day === "true",
      substitution_schedule_override: form.substitution_schedule_override || null,
      note: form.note.trim() === "" ? null : form.note.trim(),
      active: form.active,
    };

    setLoading(true);
    try {
      if (isEdit) {
        await updateEvent(event.id, payload);
      } else {
        await createEvent(payload);
      }
      onSaved();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unable to save the event. Please try again.";
      setServerError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Event" : "Add Event"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update the event details. Empty optional fields keep or clear their stored value."
              : isAdmin
                ? "Create a new academic event. The server validation registry enforces the final rules."
                : "Record what actually happened: extra classes, cancellations, or surprise quizzes for your enrolled subjects."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          {(localError || serverError) && (
            <p className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/15 p-3 text-sm text-destructive">
              <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
              {serverError || localError}
            </p>
          )}

          <div className={fieldClass}>
            <label className={labelClass} htmlFor="event-form-type">Event type</label>
            <select
              id="event-form-type"
              className={selectClass}
              value={form.event_type}
              onChange={e => set("event_type", e.target.value as EventType)}
            >
              {typeOptions.map(type => (
                <option key={type} value={type}>{humanizeEventType(type)}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-start">Start date</label>
              <Input
                id="event-form-start"
                type="date"
                className={selectClass}
                value={form.start_date}
                onChange={e => set("start_date", e.target.value)}
              />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-end">End date</label>
              <Input
                id="event-form-end"
                type="date"
                className={selectClass}
                value={form.end_date}
                onChange={e => set("end_date", e.target.value)}
              />
            </div>
          </div>

          {rule.requiresSubject && (
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-subject">Subject</label>
              <select
                id="event-form-subject"
                className={selectClass}
                value={form.subject_id}
                onChange={e => set("subject_id", e.target.value)}
              >
                <option value="">Select a subject</option>
                {subjectsForEvent.map(subject => (
                  <option key={subject.id} value={subject.id}>
                    {subject.code} — {subject.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {rule.requiresClassType && (singleClassType ? (
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-class">Class type</label>
              <div className="h-8 rounded-lg border border-input bg-input/20 px-3 text-sm text-muted-foreground flex items-center">
                {CLASS_TYPE_LABELS[singleClassType]}
              </div>
            </div>
          ) : (
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-class">Class type</label>
              <select
                id="event-form-class"
                className={selectClass}
                value={form.class_type}
                onChange={e => set("class_type", e.target.value)}
              >
                <option value="">Select a class type</option>
                {rule.allowedClassTypes.map(classType => (
                  <option key={classType} value={classType}>
                    {CLASS_TYPE_LABELS[classType]}
                  </option>
                ))}
              </select>
            </div>
          ))}

          {(form.event_type === EventType.MID_SEM_PRACTICAL || form.event_type === EventType.LAB_CANCELLED) && (
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-note">
                {form.event_type === EventType.LAB_CANCELLED ? "Reason (optional)" : "Note (optional)"}
              </label>
              <Input
                id="event-form-note"
                type="text"
                className={selectClass}
                placeholder={form.event_type === EventType.LAB_CANCELLED ? "e.g. Technical issue" : "e.g. Mid-semester practical"}
                value={form.note}
                maxLength={200}
                onChange={e => set("note", e.target.value)}
              />
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-working">Working day state</label>
              <select
                id="event-form-working"
                className={selectClass}
                value={form.is_working_day}
                onChange={e => set("is_working_day", e.target.value)}
                disabled={rule.isClosure}
              >
                <option value="">Not specified</option>
                <option value="true">Working</option>
                <option value="false">Non-working</option>
              </select>
              {rule.isClosure && (
                <p className="text-[10px] text-muted-foreground">
                  Closure types are always non-working (engine rule).
                </p>
              )}
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-substitution">Substitution schedule</label>
              <select
                id="event-form-substitution"
                className={selectClass}
                value={form.substitution_schedule_override}
                onChange={e => set("substitution_schedule_override", e.target.value)}
              >
                <option value="">None</option>
                {SUBSTITUTION_DAYS.map(day => (
                  <option key={day} value={day}>{day[0] + day.slice(1).toLowerCase()}</option>
                ))}
              </select>
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={form.active}
              onChange={e => set("active", e.target.checked)}
              className="h-4 w-4 rounded border-input accent-primary"
            />
            Active (visible in calendar and event reads)
          </label>

          <DialogFooter>
            <Button variant="outline" type="button" disabled={loading} onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? (isEdit ? "Saving…" : "Creating…") : isEdit ? "Save changes" : "Create event"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}