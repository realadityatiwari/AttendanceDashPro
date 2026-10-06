"use client";

import { useMemo, useState } from "react";
import { AcademicEventPayload, AcademicEventResponse, AdminOccurrenceOption, ClassType, ElectiveSlot, EventType, SubjectCategory } from "@/types/api";
import { useSubjects, useTimetable, useEventMutations, useOccurrenceOptions } from "@/hooks/useApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { DateInput } from "@/components/shared/DateInput";
import { formatDateMedium } from "@/lib/date";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  getRule,
  humanizeEventType,
  SUBSTITUTION_DAYS,
  CLASS_TYPE_LABELS,
  STUDENT_CREATABLE_EVENT_TYPES,
  defaultDurationMode,
  DurationMode,
  ELECTIVE_SLOT_LABELS,
  slotOptionValue,
  parseSlotOption,
  isOccurrenceEventType,
} from "@/components/events/eventRules";
import { AlertCircle } from "lucide-react";

// Unified holiday flow: the three legacy holiday types are consolidated into
// the single HOLIDAY option for NEW events. They remain fully supported
// backend types, so when EDITING an existing legacy-holiday event the form
// keeps its actual type (never silently converts it on save).
const LEGACY_HOLIDAY_TYPES: EventType[] = [
  EventType.PUBLIC_HOLIDAY,
  EventType.INSTITUTE_HOLIDAY,
  EventType.FESTIVAL_HOLIDAY,
];

function adminTypeOptions(isEdit: boolean, editingType: EventType | null): EventType[] {
  return Object.values(EventType).filter(
    t => !LEGACY_HOLIDAY_TYPES.includes(t) || (isEdit && t === editingType)
  );
}

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
  /** Duration UX: "single" collapses start/end to one date; "range" shows
      both pickers. Never sent to the API — the backend stays start/end. */
  duration_mode: DurationMode;
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
  const defaultType = event?.event_type ?? (isAdmin ? EventType.HOLIDAY : EventType.EXTRA_LECTURE);
  // Existing events carry their true duration: start_date == end_date means
  // single-day. New events default per event type (DEFAULT_DURATION_MODE).
  const hasDates = Boolean(event?.start_date && event?.end_date);
  const durationMode = event && hasDates
    ? (event.start_date === event.end_date ? "single" : "range")
    : defaultDurationMode(defaultType);
  // Phase 22.4: a slot-scoped event seeds the subject selector with the
  // logical Department Elective option (never the shared anchor UUID).
  const subjectSelection = event?.elective_slot
    ? slotOptionValue(event.elective_slot)
    : (event?.subject_id ?? "");
  return {
    event_type: defaultType,
    duration_mode: durationMode,
    start_date: event?.start_date ?? "",
    end_date: event?.end_date ?? "",
    subject_id: subjectSelection,
    class_type: event?.class_type ?? "",
    is_working_day: event?.is_working_day === null || event?.is_working_day === undefined
      ? "" : String(event.is_working_day),
    substitution_schedule_override: event?.substitution_schedule_override ?? "",
    note: event?.note ?? "",
    active: event?.active ?? true,
  };
}

const fieldClass = "flex flex-col gap-1";
const labelClass = "text-2xs uppercase tracking-wider text-muted-foreground";

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
  const { timetable } = useTimetable();
  const { createEvent, updateEvent } = useEventMutations();
  const [form, setForm] = useState<FormState>(() => initialState(event, isAdmin));
  const [localError, setLocalError] = useState("");
  const [serverError, setServerError] = useState("");
  const [loading, setLoading] = useState(false);
  // Whether the user deliberately chose a duration mode for the current event.
  // Until they do, switching event type follows the new type's default mode.
  const [durationModeTouched, setDurationModeTouched] = useState(false);

  // OCC-1 (admin occurrence mode): the selected scheduled occurrence and the
  // optional concrete-elective narrowing. Admins create cancellations by
  // picking an occurrence from the backend read model — never by naming a
  // subject and a class type.
  const [entryId, setEntryId] = useState(event?.timetable_entry_id ?? "");
  const [narrowToSubjectId, setNarrowToSubjectId] = useState("");
  const [narrowTouched, setNarrowTouched] = useState(false);
  const [lastEntryKey, setLastEntryKey] = useState<string | null>(
    event?.timetable_entry_id ?? null
  );

  // Students may only create the flexible subject-scoped types; admins see
  // every type with the legacy holiday trio consolidated into HOLIDAY (kept
  // in the list only when editing an event that already has that type).
  const typeOptions = isAdmin
    ? adminTypeOptions(isEdit, event?.event_type ?? null)
    : STUDENT_CREATABLE_EVENT_TYPES;

  // Re-seed the form whenever the dialog is (re)opened for a different event.
  const [lastKey, setLastKey] = useState<string | null>(null);
  const key = `${open ? "open" : "closed"}:${event?.id ?? "new"}`;
  if (key !== lastKey) {
    setLastKey(key);
    if (open) {
      setForm(initialState(event, isAdmin));
      setDurationModeTouched(false);
      setLocalError("");
      setServerError("");
      // OCC-1: re-seed the occurrence selection with the stored reference.
      setEntryId(event?.timetable_entry_id ?? "");
      setLastEntryKey(event?.timetable_entry_id ?? null);
      setNarrowTouched(false);
      setNarrowToSubjectId("");
    }
  }

  const rule = getRule(form.event_type);
  // Phase 9.1: the laboratory event types are scoped to the student's enrolled
  // practical/lab subjects (Subject.category === lab), mirroring the backend's
  // PRACTICAL-only rules. Quiz events (SURPRISE_QUIZ / QUIZ_DAY) are scoped to
  // quiz-bearing (theory) subjects via the canonical quiz_applicable flag —
  // practical subjects can never host quiz attendance (the backend registry
  // rejects them with 422). CLASS_CANCELLED is additionally date-aware: only
  // subjects with a class actually scheduled on the picked date (matching the
  // selected class type) may be cancelled that day. /api/v1/subjects is
  // already enrollment-scoped (authenticated student).
  const labScopedEvent = form.event_type === EventType.MID_SEM_PRACTICAL
    || form.event_type === EventType.LAB_CANCELLED;
  const quizScopedEvent = form.event_type === EventType.SURPRISE_QUIZ
    || form.event_type === EventType.QUIZ_DAY;
  const isClassCancelled = form.event_type === EventType.CLASS_CANCELLED;
  const isCancellation = isClassCancelled
    || form.event_type === EventType.LAB_CANCELLED;
  // Backend subject-category rule (mirrored): extra lecture/tutorial are
  // theory-subject events — practical/lab subjects can never host them.
  const isTheoryExtra = form.event_type === EventType.EXTRA_LECTURE
    || form.event_type === EventType.EXTRA_TUTORIAL;
  const subjectsForEvent = useMemo(() => {
    const all = subjects ?? [];
    if (isTheoryExtra) {
      return all.filter(s => s.category === SubjectCategory.THEORY);
    }
    if (labScopedEvent) {
      return all.filter(s => s.category === SubjectCategory.LAB);
    }
    if (quizScopedEvent) {
      return all.filter(s => s.quiz_applicable);
    }
    if (isClassCancelled) {
      const entries = timetable ?? [];
      const type = form.class_type === ClassType.LECTURE || form.class_type === ClassType.TUTORIAL
        ? form.class_type
        : "";
      if (!form.start_date) {
        return all.filter(s => entries.some(e =>
          e.subject.id === s.id
          && (e.class_type === ClassType.LECTURE || e.class_type === ClassType.TUTORIAL)));
      }
      // Backend day_of_week is 0=Monday; JS getDay() is 0=Sunday.
      const jsDow = new Date(`${form.start_date}T00:00:00`).getDay();
      const dow = (jsDow + 6) % 7;
      return all.filter(s => entries.some(e =>
        e.day_of_week === dow
        && e.subject.id === s.id
        && (e.class_type === ClassType.LECTURE || e.class_type === ClassType.TUTORIAL)
        && (!type || e.class_type === type)));
    }
    return all;
  }, [subjects, timetable, labScopedEvent, quizScopedEvent, isClassCancelled, isTheoryExtra, form.start_date, form.class_type]);

  // OCC-1: a cancellation must reference the exact scheduled timetable
  // occurrence. The student's own resolved timetable read model supplies the
  // entry — the backend validates it (existence, weekday, subject/class
  // match) and rejects any cancellation without one.
  const cancellationEntryId = useMemo(() => {
    if (!isCancellation || !form.subject_id || !form.start_date) return null;
    const jsDow = new Date(`${form.start_date}T00:00:00`).getDay();
    const dow = (jsDow + 6) % 7;
    const match = (timetable ?? []).find(e =>
      e.day_of_week === dow
      && e.subject.id === form.subject_id
      && e.class_type === form.class_type);
    return match ? match.id : null;
  }, [isCancellation, timetable, form.subject_id, form.class_type, form.start_date]);

  // OCC-1 (admin occurrence mode): admins create cancellations by picking a
  // REAL scheduled occurrence from the backend read model — subject, class
  // type and timetable reference are all derived from that selection and the
  // generic semester subject list is never shown. Students keep the
  // subject+class-type flow with the timetable-derived entry (no admin
  // endpoint access); the backend validates both paths identically.
  const adminOccurrenceMode = Boolean(isAdmin && isOccurrenceEventType(form.event_type));
  const {
    options: occurrenceOptions,
    dayInfo: occurrenceDayInfo,
    isLoading: occurrenceLoading,
    isError: occurrenceError,
    mutate: retryOccurrenceOptions,
  } = useOccurrenceOptions(
      adminOccurrenceMode ? form.start_date : null,
      adminOccurrenceMode ? form.event_type : null,
    );
  const selectedOccurrence: AdminOccurrenceOption | null =
    adminOccurrenceMode
      ? (occurrenceOptions ?? []).find(o => o.timetable_entry_id === entryId) ?? null
      : null;
  const storedEntryStillListed = Boolean(
    adminOccurrenceMode && event?.timetable_entry_id
      && (occurrenceOptions ?? []).some(o => o.timetable_entry_id === event.timetable_entry_id)
  );
  // The stored reference's own server label (from the same options read
  // model — never reconstructed client-side).
  const storedOccurrence: AdminOccurrenceOption | null = adminOccurrenceMode && event?.timetable_entry_id
    ? (occurrenceOptions ?? []).find(o => o.timetable_entry_id === event.timetable_entry_id) ?? null
    : null;

  // Narrowing derivation: whenever the selected occurrence identity changes,
  // reset any touched narrowing; prefill from the edited event's own subject
  // when it is a concrete member of the occurrence's slot (a narrowed event
  // edits as narrowed), else slot-wide.
  if (selectedOccurrence) {
    const entryKey = selectedOccurrence.timetable_entry_id;
    if (entryKey !== lastEntryKey) {
      setLastEntryKey(entryKey);
      setNarrowTouched(false);
      setNarrowToSubjectId("");
    }
    const prefilledNarrow =
      event?.subject_id
      && selectedOccurrence.elective_subjects.some(m => m.id === event.subject_id)
        ? event.subject_id
        : "";
    if (!narrowTouched && narrowToSubjectId !== prefilledNarrow) {
      setNarrowToSubjectId(prefilledNarrow);
    }
  }

  const set = <K extends keyof FormState>(field: K, value: FormState[K]) => {
    setForm(prev => ({ ...prev, [field]: value }));
    setServerError("");
  };

  // Event-type change: re-apply the new type's default duration only while the
  // user has not deliberately chosen a mode; dates are always preserved.
  const handleEventTypeChange = (value: EventType) => {
    setForm(prev => ({
      ...prev,
      event_type: value,
      duration_mode: durationModeTouched ? prev.duration_mode : defaultDurationMode(value),
    }));
    // OCC-1: switching types drops any occurrence selection (and its derived
    // subject/class-type state) so it can never leak into another type.
    setEntryId("");
    setLastEntryKey("__type_changed__");
    setNarrowTouched(false);
    setNarrowToSubjectId("");
    setServerError("");
  };

  const handleDurationModeChange = (mode: DurationMode) => {
    setDurationModeTouched(true);
    setForm(prev => {
      if (mode === "single") {
        // Collapse to the start date (fall back to the end when start is empty).
        const date = prev.start_date || prev.end_date;
        return { ...prev, duration_mode: mode, start_date: date, end_date: date };
      }
      // Expanding to a range keeps both dates; a missing end inherits the start.
      return { ...prev, duration_mode: mode, end_date: prev.end_date || prev.start_date };
    });
    setServerError("");
  };

  // Single-day mode always mirrors the picked date into both fields.
  // Range mode never leaves start > end: moving the start past the end pulls
  // the end up with it, and moving the end before the start pulls the start
  // back — the form can never hold an inverted range.
  const handleStartDateChange = (value: string) => {
    setForm(prev => {
      if (prev.duration_mode === "single") {
        return { ...prev, start_date: value, end_date: value };
      }
      if (prev.end_date && value > prev.end_date) {
        return { ...prev, start_date: value, end_date: value };
      }
      return { ...prev, start_date: value };
    });
    // OCC-1: the date changed — the occurrence options re-resolve for the new
    // date. Fall back to the stored reference (kept only if it is still
    // scheduled there); derived fields reset with the selection.
    if (adminOccurrenceMode && value !== form.start_date) {
      setEntryId(event?.timetable_entry_id ?? "");
      setLastEntryKey("__date_changed__");
      setNarrowTouched(false);
      setNarrowToSubjectId("");
    }
    setServerError("");
  };

  const handleEndDateChange = (value: string) => {
    setForm(prev => {
      if (prev.start_date && value < prev.start_date) {
        return { ...prev, end_date: value, start_date: value };
      }
      return { ...prev, end_date: value };
    });
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

  // Render-time guard (same pattern as the class-type auto-fill): when the
  // selected subject is no longer valid for the current event type — e.g. the
  // user switched from a lecture event to a lab event, or subjects arrived
  // after the dialog seeded an edit — clear it so a stale subject can never be
  // submitted. Runs only once subjects are loaded so edit-mode seeding is kept.
  // Phase 22.4: a logical elective-slot option (prefixed value) is never a
  // subject UUID, so it is exempt from this subject-clearing guard.
  // OCC-1: admin occurrence mode does not use the subject dropdown at all
  // (subject/class type derive from the selected occurrence), so it is exempt.
  if (
    subjects !== undefined
    && rule.requiresSubject
    && !adminOccurrenceMode
    && form.subject_id
    && parseSlotOption(form.subject_id) === null
    && !subjectsForEvent.some(s => s.id === form.subject_id)
  ) {
    set("subject_id", "");
  }

  const handleOccurrenceChange = (value: string) => {
    setEntryId(value);
    // Narrowing re-derives from the new occurrence (render-phase guard).
    setNarrowTouched(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError("");
    setLocalError("");

    if (form.duration_mode === "single") {
      if (!form.start_date) {
        setLocalError("An event date is required.");
        return;
      }
    } else if (!form.start_date || !form.end_date) {
      setLocalError("Start and end dates are required.");
      return;
    }
    if (form.start_date > form.end_date) {
      setLocalError("Start date must be on or before the end date.");
      return;
    }
    // OCC-1 (admin occurrence mode): the target IS a scheduled occurrence.
    if (adminOccurrenceMode) {
      if (occurrenceDayInfo && !occurrenceDayInfo.is_working_day) {
        setLocalError(
          `${form.start_date} is a non-working day (${occurrenceDayInfo.non_working_reason}) — there is nothing to cancel.`
        );
        return;
      }
      if (selectedOccurrence === null) {
        setLocalError(
          occurrenceError
            ? "The scheduled occurrences could not be loaded — retry before recording the cancellation."
            : "Select the scheduled occurrence to cancel — subject and class type derive from it."
        );
        return;
      }
    } else {
      if (rule.requiresSubject && !form.subject_id) {
        setLocalError("This event type requires a subject.");
        return;
      }
      if (rule.requiresClassType && !form.class_type) {
        setLocalError("This event type requires a class type.");
        return;
      }
    }
    // Unified holiday product rule: a reason/occasion is required for a new
    // Holiday (the backend enforces this too).
    if (form.event_type === EventType.HOLIDAY && form.note.trim() === "") {
      setLocalError("A reason/occasion is required for a holiday.");
      return;
    }
    // OCC-1 (student flow): a cancellation must reference a class actually
    // scheduled on the picked date (backend enforces it too — the honest
    // local guard).
    if (!adminOccurrenceMode && isCancellation && !cancellationEntryId) {
      setLocalError(
        "No matching scheduled class found on this date — check the date and class type before recording a cancellation."
      );
      return;
    }

    // Single-day is represented by start_date == end_date (the backend has no
    // separate duration concept); the picked date is mirrored into both.
    const singleDay = form.duration_mode === "single";
    // Phase 22.4: a logical elective-slot selection (prefixed value) sends
    // elective_slot instead of a concrete subject_id (mutually exclusive).
    const slotSelection = rule.requiresSubject ? parseSlotOption(form.subject_id) : null;
    // OCC-1 (admin occurrence mode): subject, class type and the timetable
    // reference all derive from the selected occurrence — the single source
    // of truth. Slot occurrences stay slot-wide unless narrowed to a concrete
    // member subject.
    const payload: AcademicEventPayload = adminOccurrenceMode && selectedOccurrence
      ? {
          event_type: form.event_type,
          start_date: form.start_date,
          end_date: singleDay ? form.start_date : form.end_date,
          subject_id: narrowToSubjectId || null,
          timetable_entry_id: selectedOccurrence.timetable_entry_id,
          elective_slot: null, // the backend re-derives it from the occurrence
          class_type: selectedOccurrence.class_type,
          is_working_day: null,
          substitution_schedule_override: null,
          note: form.note.trim() === "" ? null : form.note.trim(),
          active: form.active,
        }
      : {
          event_type: form.event_type,
          start_date: form.start_date,
          end_date: singleDay ? form.start_date : form.end_date,
          subject_id: rule.requiresSubject && !slotSelection ? form.subject_id : null,
          // OCC-1: cancellations carry the exact scheduled occurrence (from the
          // student's own resolved timetable read model).
          timetable_entry_id: isCancellation ? cancellationEntryId : null,
          elective_slot: slotSelection,
          class_type: rule.requiresClassType ? (form.class_type as ClassType) : null,
          // Working Saturday implies its own working-day semantics — never send a
          // contradictory explicit override.
          is_working_day: form.event_type === EventType.WORKING_SATURDAY
            ? null
            : form.is_working_day === "" ? null : form.is_working_day === "true",
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
      {/* UI-034: dvh cap (matches ShellDialog) so the form stays fully
          visible and scrollable on mobile browsers with dynamic toolbars. */}
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
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
            // 25.UX-7: the consolidated validation/server error banner is the
            // form's error summary — role="alert" announces it on failed
            // submit (it appears in response to the user's action).
            <p
              role="alert"
              className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/15 p-3 text-sm text-destructive"
            >
              <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
              {serverError || localError}
            </p>
          )}

          <div className={fieldClass}>
            <label className={labelClass} htmlFor="event-form-type">Event type</label>
            <Select
              id="event-form-type"
              value={form.event_type}
              onChange={e => handleEventTypeChange(e.target.value as EventType)}
            >
              {typeOptions.map(type => (
                <option key={type} value={type}>{humanizeEventType(type)}</option>
              ))}
            </Select>
          </div>

          {/* UI-035 / D-13: the single-day vs range choice is an
              administrative concern — student-facing types are single-day by
              definition, so students get one date picker. A student opening a
              (defensive) pre-existing multi-day event still sees both pickers
              so its stored range is never silently collapsed. */}
          <div className={fieldClass}>
            <span className={labelClass}>Date</span>
            {isAdmin && (
              // 25.UX-6: the radios get the same before:-inset hit-area
              // extension the Settings switches use — the native control
              // renders at 18px (visual change ≤2px) while the target reaches
              // the touch floor, and the 10px label gap honors the 8px
              // adjacent-target spacing.
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2.5 text-sm text-foreground">
                  <input
                    type="radio"
                    name="event-duration-mode"
                    className="relative h-4.5 w-4.5 rounded-full border-input accent-primary before:absolute before:-inset-1.5 before:content-['']"
                    checked={form.duration_mode === "single"}
                    onChange={() => handleDurationModeChange("single")}
                  />
                  Single day
                </label>
                <label className="flex items-center gap-2.5 text-sm text-foreground">
                  <input
                    type="radio"
                    name="event-duration-mode"
                    className="relative h-4.5 w-4.5 rounded-full border-input accent-primary before:absolute before:-inset-1.5 before:content-['']"
                    checked={form.duration_mode === "range"}
                    onChange={() => handleDurationModeChange("range")}
                  />
                  Date range
                </label>
              </div>
            )}
            {(!isAdmin && form.start_date !== "" && form.start_date !== form.end_date) ||
            (isAdmin && form.duration_mode === "range") ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="event-form-start">Start date</label>
                  {/* UIA-025: native date input + formatted companion. */}
                  <DateInput
                    id="event-form-start"
                    value={form.start_date}
                    onValueChange={handleStartDateChange}
                    emptyHint="Pick a date"
                  />
                </div>
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="event-form-end">End date</label>
                  <DateInput
                    id="event-form-end"
                    value={form.end_date}
                    onValueChange={handleEndDateChange}
                    emptyHint="Pick a date"
                  />
                </div>
              </div>
            ) : (
              <DateInput
                id="event-form-start"
                value={form.start_date}
                onValueChange={handleStartDateChange}
                aria-label="Event date"
                emptyHint="Pick a date"
              />
            )}
          </div>

          {adminOccurrenceMode && (
            // OCC-1: the occurrence picker replaces the subject and class-type
            // controls — the server-authoritative occurrence is the single
            // source of truth for what is being cancelled.
            <>
              {occurrenceError && (
                // Honesty rule: a FAILED request must never masquerade as an
                // empty schedule — say so and offer a retry.
                <p role="alert" className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/15 p-3 text-sm text-destructive">
                  <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
                  <span>
                    Could not load the scheduled occurrences
                    {occurrenceError instanceof Error && occurrenceError.message
                      ? `: ${occurrenceError.message}` : ""}
                    .
                    <button
                      type="button"
                      className="ml-2 underline underline-offset-2"
                      onClick={() => retryOccurrenceOptions()}
                    >
                      Retry
                    </button>
                  </span>
                </p>
              )}
              {occurrenceDayInfo && !occurrenceDayInfo.is_working_day && (
                <p className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
                  {form.start_date} is a non-working day ({occurrenceDayInfo.non_working_reason}) —
                  there are no scheduled classes to cancel.
                </p>
              )}
              <div className={fieldClass}>
                <label className={labelClass} htmlFor="event-form-occurrence">Scheduled occurrence</label>
                {storedOccurrence && storedEntryStillListed && (
                  <p className="text-2xs text-muted-foreground">
                    Currently references: {storedOccurrence.display_label}
                  </p>
                )}
                {isEdit && !storedOccurrence && (
                  <p className="text-2xs text-warning">
                    This event predates occurrence references — select the
                    scheduled occurrence it cancels before saving.
                  </p>
                )}
                <Select
                  id="event-form-occurrence"
                  value={entryId}
                  onChange={e => handleOccurrenceChange(e.target.value)}
                  disabled={occurrenceLoading || (occurrenceDayInfo != null && !occurrenceDayInfo.is_working_day)}
                >
                  <option value="">
                    {occurrenceLoading
                      ? "Loading schedule…"
                      : occurrenceError
                        ? "Schedule unavailable — load failed"
                        : (occurrenceOptions ?? []).length === 0
                          ? "No classes scheduled on this date"
                          : "Select the class to cancel"}
                  </option>
                  {(occurrenceOptions ?? []).map(o => (
                    <option key={o.timetable_entry_id} value={o.timetable_entry_id}>
                      {o.display_label}
                    </option>
                  ))}
                </Select>
                <p className="text-2xs text-muted-foreground">
                  Only classes actually scheduled on this date are listed.
                  Subject and class type derive from the occurrence.
                </p>
              </div>
              {selectedOccurrence && selectedOccurrence.elective_subjects.length > 0 && (
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="event-form-narrow">Affects</label>
                  <Select
                    id="event-form-narrow"
                    value={narrowToSubjectId}
                    onChange={e => { setNarrowTouched(true); setNarrowToSubjectId(e.target.value); }}
                  >
                    <option value="">
                      The entire {ELECTIVE_SLOT_LABELS[selectedOccurrence.elective_slot as ElectiveSlot]} slot
                      (every student in the slot)
                    </option>
                    {selectedOccurrence.elective_subjects.map(m => (
                      <option key={m.id} value={m.id}>
                        Only {m.code} — {m.name} students
                      </option>
                    ))}
                  </Select>
                  <p className="text-2xs text-muted-foreground">
                    Each student&apos;s own elective subject resolves automatically;
                    the shared anchor subject is never shown to students who
                    selected another elective.
                  </p>
                </div>
              )}
              {selectedOccurrence && (
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="event-form-derived-class">Class type (from the occurrence)</label>
                  {/* Read-only by design: the class type belongs to the
                      referenced timetable occurrence — never manually chosen. */}
                  <div
                    id="event-form-derived-class"
                    className="h-8 rounded-lg border border-input bg-input/20 px-3 text-sm text-muted-foreground flex items-center"
                  >
                    {CLASS_TYPE_LABELS[selectedOccurrence.class_type]}
                    {" · "}{selectedOccurrence.subject_code} — {selectedOccurrence.subject_name}
                  </div>
                </div>
              )}
            </>
          )}

          {rule.requiresSubject && !adminOccurrenceMode && (
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-subject">Subject</label>
              <Select
                id="event-form-subject"
                value={form.subject_id}
                onChange={e => set("subject_id", e.target.value)}
              >
                <option value="">Select a subject</option>
                {subjectsForEvent.map(subject => (
                  <option key={subject.id} value={subject.id}>
                    {subject.code} — {subject.name}
                  </option>
                ))}
                {/* Phase 22.4: ADMIN may scope a shared event to a Department
                    Elective logical slot instead of a concrete subject. Each
                    student sees the event resolved to their own selection. The
                    backend enforces ADMIN-only and rejects slots for
                    practical/lab event types. */}
                {isAdmin && !labScopedEvent && (
                  (Object.values(ElectiveSlot) as ElectiveSlot[]).map(slot => (
                    <option key={slot} value={slotOptionValue(slot)}>
                      {ELECTIVE_SLOT_LABELS[slot]}
                    </option>
                  ))
                )}
              </Select>
              {isClassCancelled && subjectsForEvent.length === 0 && form.start_date && (
                <p className="text-2xs text-muted-foreground">
                  No lectures or tutorials scheduled on {formatDateMedium(form.start_date)} for your enrolled subjects.
                </p>
              )}
              {quizScopedEvent && (
                <p className="text-2xs text-muted-foreground">
                  Only quiz-bearing (theory) subjects can host quizzes.
                </p>
              )}
            </div>
          )}

          {rule.requiresClassType && !adminOccurrenceMode && (singleClassType ? (
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-class">Class type</label>
              <div className="h-8 rounded-lg border border-input bg-input/20 px-3 text-sm text-muted-foreground flex items-center">
                {CLASS_TYPE_LABELS[singleClassType]}
              </div>
            </div>
          ) : (
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-class">Class type</label>
              <Select
                id="event-form-class"
                value={form.class_type}
                onChange={e => set("class_type", e.target.value)}
              >
                <option value="">Select a class type</option>
                {rule.allowedClassTypes.map(classType => (
                  <option key={classType} value={classType}>
                    {CLASS_TYPE_LABELS[classType]}
                  </option>
                ))}
              </Select>
            </div>
          ))}

          {(form.event_type === EventType.MID_SEM_PRACTICAL || form.event_type === EventType.LAB_CANCELLED
            || form.event_type === EventType.HOLIDAY) && (
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="event-form-note">
                {form.event_type === EventType.HOLIDAY ? "Reason / Occasion (required)" : "Reason (optional)"}
              </label>
              <Input
                id="event-form-note"
                type="text"
                className="[color-scheme:dark]"
                placeholder={form.event_type === EventType.HOLIDAY
                  ? "e.g. Republic Day, Institute Holiday, Diwali"
                  : form.event_type === EventType.LAB_CANCELLED ? "e.g. Technical issue" : "e.g. Mid-semester practical"}
                value={form.note}
                maxLength={200}
                onChange={e => set("note", e.target.value)}
              />
            </div>
          )}

          {/* UI-035 / D-13: engine-level calendar fields — hidden from
              students entirely (admin concerns). The payload defaults for
              hidden fields (is_working_day null, substitution null,
              active true) are exactly what the student form always sent. */}
          {isAdmin && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className={fieldClass}>
                <label className={labelClass} htmlFor="event-form-working">Working day state</label>
                <Select
                  id="event-form-working"
                  value={form.is_working_day}
                  onChange={e => set("is_working_day", e.target.value)}
                  disabled={rule.isClosure || form.event_type === EventType.WORKING_SATURDAY}
                >
                  <option value="">Not specified</option>
                  <option value="true">Working</option>
                  <option value="false">Non-working</option>
                </Select>
                {rule.isClosure && (
                  <p className="text-2xs text-muted-foreground">
                    Closure types are always non-working (engine rule).
                  </p>
                )}
                {form.event_type === EventType.WORKING_SATURDAY && (
                  <p className="text-2xs text-muted-foreground">
                    Working Saturday is always a working day on Saturdays (weekdays
                    inside the range keep their normal state).
                  </p>
                )}
              </div>
              <div className={fieldClass}>
                <label className={labelClass} htmlFor="event-form-substitution">Substitution schedule</label>
                <Select
                  id="event-form-substitution"
                  value={form.substitution_schedule_override}
                  onChange={e => set("substitution_schedule_override", e.target.value)}
                >
                  <option value="">None</option>
                  {SUBSTITUTION_DAYS.map(day => (
                    <option key={day} value={day}>{day[0] + day.slice(1).toLowerCase()}</option>
                  ))}
                </Select>
              </div>
            </div>
          )}

          {isAdmin && (
            // 25.UX-6: same hit-area extension as the duration radios — the
            // target reaches the touch floor without changing the visual
            // checkbox beyond 2px.
            <label className="flex items-center gap-2.5 text-sm text-foreground">
              <input
                type="checkbox"
                checked={form.active}
                onChange={e => set("active", e.target.checked)}
                className="relative h-4.5 w-4.5 rounded border-input accent-primary before:absolute before:-inset-1.5 before:content-['']"
              />
              Active (visible in calendar and event reads)
            </label>
          )}

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