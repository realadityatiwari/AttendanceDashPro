"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useAdminSessions, useAdminSemesters, useAdminSubjects, useOccurrenceOptions } from "@/hooks/useApi";
import { CreateAdminEventRequest, ClassType, ElectiveSlot, EventType, SubjectCategory } from "@/types/api";
import {
  getRule, defaultDurationMode, CLASS_TYPE_LABELS, SUBSTITUTION_DAYS,
  ELECTIVE_SLOT_LABELS, slotOptionValue, parseSlotOption, SLOT_OPTION_PREFIX,
  isOccurrenceEventType,
} from "@/components/events/eventRules";

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

// UX mirror of the backend subject-category rule (requirement 5: theory -> L/T
// events, practical/lab -> P events). The backend registry remains
// authoritative — these filters only shape the options offered per type.
function subjectCategoryForEvent(eventType: EventType): SubjectCategory | null {
  switch (eventType) {
    case EventType.EXTRA_LECTURE:
    case EventType.EXTRA_TUTORIAL:
      return SubjectCategory.THEORY;
    case EventType.EXTRA_PRACTICAL:
    case EventType.MID_SEM_PRACTICAL:
      return SubjectCategory.LAB;
    case EventType.SURPRISE_QUIZ:
    case EventType.QUIZ_DAY:
      return SubjectCategory.THEORY;
    default:
      return null;
  }
}

/**
 * Phase 24.9/24.10 — Create Event dialog (backend authoritative).
 * OCC-1: cancellation events (Class Cancelled / Lab Cancelled) are strictly
 * occurrence-driven — the admin picks the date, then one of the timetable
 * occurrences the backend reports as actually scheduled that day (in scope).
 * Subject and class type are DERIVED from the selected occurrence and are
 * never manually selectable; a shared elective-slot occurrence may be
 * narrowed to one concrete member subject (slot-wide remains the default).
 * Extra lecture/tutorial target THEORY subjects only (mirrored from the
 * backend registry). Working-day default semantics for WORKING_DAY_OVERRIDE
 * derive from the backend day resolution (weekday working; weekend/closure
 * non-working) — the backend rejects contradictory states.
 */
export function CreateEventDialog({
  open, isGlobal, isSubmitting, onCreate, onOpenChange,
}: {
  open: boolean;
  isGlobal: boolean;
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
  const [error, setError] = useState<string | null>(null);

  // OCC-1 occurrence selection + optional elective narrowing.
  const [entryId, setEntryId] = useState("");
  const [narrowToSubjectId, setNarrowToSubjectId] = useState("");

  // Working-day explicit state: only WORKING_DAY_OVERRIDE exposes it, and it
  // is prefilled from the backend day resolution (never hand-derived in
  // React) until the admin deliberately changes it.
  const [isWorkingDay, setIsWorkingDay] = useState<"" | boolean>("");
  const [workingDayTouched, setWorkingDayTouched] = useState(false);

  const rule = getRule(eventType);
  const durationMode = defaultDurationMode(eventType);
  const isOccurrence = isOccurrenceEventType(eventType);

  // Backend read model: canonical day resolution + in-scope occurrences.
  const fetchOptions = Boolean(startDate) && (isOccurrence || eventType === EventType.WORKING_DAY_OVERRIDE);
  const {
    options, dayInfo, isLoading: optionsLoading,
    isError: optionsError, mutate: retryOptions,
  } = useOccurrenceOptions(
    fetchOptions ? startDate : null,
    isOccurrence ? eventType : null,
  );

  const selectedEntry = (options ?? []).find((o) => o.timetable_entry_id === entryId) ?? null;
  if (selectedEntry === null && entryId !== "") {
    // Date changed / options reloaded: stale occurrence state can never be
    // submitted.
    setEntryId("");
    setNarrowToSubjectId("");
  }

  // Working-day default semantics from the backend day resolution: an
  // ordinary weekday is working; a weekend or an actively-closed day is not.
  // (Render-phase sync, same pattern as the class-type auto-fill.)
  if (
    eventType === EventType.WORKING_DAY_OVERRIDE
    && !workingDayTouched
    && dayInfo
    && isWorkingDay === ""
  ) {
    setIsWorkingDay(dayInfo.is_working_day);
  }

  const scopedSubjects = (subjects?.items ?? []).filter(
    (s) => !semesterId || s.semester_id === semesterId
  );
  // UX mirror of the backend subject-category metadata rule (requirement 5).
  // Anchor subjects (BCS-054 / BCS-058) are never offered as concrete
  // targets — slot-wide targets are the separate slot options.
  const requiredCategory = subjectCategoryForEvent(eventType);
  const categorySubjects = requiredCategory
    ? scopedSubjects.filter((s) => s.category === requiredCategory && !s.is_anchor)
    : scopedSubjects;

  // Event types with exactly one allowed class type never show a selector —
  // the class type IS the event type (requirement: automatic, not manually
  // selectable). Occurrence-driven cancellations derive it from the entry.
  // (Render-phase sync, same pattern as EventFormDialog's auto-fill.)
  const autoClassType =
    rule.requiresClassType && !isOccurrence && rule.allowedClassTypes.length === 1
      ? rule.allowedClassTypes[0]
      : null;
  if (autoClassType && classType !== autoClassType) setClassType(autoClassType);

  const handleEventTypeChange = (value: EventType) => {
    setEventType(value);
    setSubjectId("");
    setClassType("");
    setEntryId("");
    setNarrowToSubjectId("");
    setIsWorkingDay("");
    setWorkingDayTouched(false);
  };

  const handleEntryChange = (value: string) => {
    setEntryId(value);
    setNarrowToSubjectId("");
  };

  const handleSubmit = async () => {
    if (!startDate) { setError("Start date is required"); return; }
    const effectiveEnd = durationMode === "single" ? startDate : (endDate || startDate);
    if (effectiveEnd < startDate) { setError("End date must not be before start date"); return; }

    if (isOccurrence) {
      // Occurrence-driven: the target IS a scheduled timetable occurrence.
      if (!selectedEntry) {
        setError(
          optionsError
            ? "The scheduled occurrences could not be loaded — retry before recording the cancellation."
            : dayInfo && !dayInfo.is_working_day
              ? "The selected date is a non-working day — there is nothing to cancel."
              : "Select the scheduled occurrence to cancel."
        );
        return;
      }
    } else {
      if (rule.requiresSubject && !subjectId) { setError("This event type requires a subject or slot target"); return; }
      if (rule.requiresClassType && !classType) { setError("This event type requires a class type"); return; }
    }

    setError(null);
    // Phase 24.10: parse the target. "slot:<SLOT>" = slot-wide event
    // (HEAD-only on the backend); anything else is a concrete subject
    // (subject-specific effect for that elective/common subject).
    const slot = parseSlotOption(subjectId);
    try {
      if (isOccurrence && selectedEntry) {
        const isNarrowed = narrowToSubjectId !== "";
        await onCreate({
          event_type: eventType,
          start_date: startDate,
          end_date: effectiveEnd,
          // Slot occurrence + no narrowing -> server resolves the slot-wide
          // shape (anchor subject + elective_slot). Narrowed -> the concrete
          // member subject (subject-specific effect only).
          subject_id: isNarrowed ? narrowToSubjectId : null,
          elective_slot: null,
          class_type: selectedEntry.class_type,
          timetable_entry_id: selectedEntry.timetable_entry_id,
          substitution_schedule_override: null,
          note: null,
          is_working_day: null,
          active: true,
        });
      } else {
        await onCreate({
          event_type: eventType,
          start_date: startDate,
          end_date: effectiveEnd,
          subject_id: slot === null ? (rule.requiresSubject ? subjectId : null) : null,
          elective_slot: slot,
          class_type: rule.requiresClassType ? (classType as ClassType) : null,
          substitution_schedule_override: subDay || null,
          note: supportsNote(eventType) && note ? note : null,
          // Working-day state is only meaningful for WORKING_DAY_OVERRIDE;
          // every other type lets the canonical engine resolve the day.
          is_working_day:
            eventType === EventType.WORKING_DAY_OVERRIDE && isWorkingDay !== ""
              ? isWorkingDay
              : null,
          active: true,
        });
      }
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
            Cancellations target an exact scheduled occurrence; the backend
            validates everything.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="space-y-2">
            <label className="text-sm font-medium">Event type</label>
            <select className={selectClass} value={eventType}
              onChange={(e) => handleEventTypeChange(e.target.value as EventType)}>
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

          {isOccurrence && (
            <>
              {optionsError && (
                // Honesty rule: a FAILED request must never masquerade as an
                // empty schedule — say so and offer a retry.
                <p role="alert" className="text-sm text-destructive">
                  Could not load the scheduled occurrences
                  {optionsError instanceof Error && optionsError.message
                    ? `: ${optionsError.message}` : ""}
                  .{" "}
                  <button
                    type="button"
                    className="underline underline-offset-2"
                    onClick={() => retryOptions()}
                  >
                    Retry
                  </button>
                </p>
              )}
              {dayInfo && !dayInfo.is_working_day && (
                <div className="rounded-md border border-warning/40 bg-warning/10 p-2 text-xs text-warning">
                  {startDate} is a non-working day ({dayInfo.non_working_reason}) —
                  there are no scheduled classes to cancel.
                </div>
              )}
              {startDate && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">Scheduled occurrence</label>
                  <select
                    className={selectClass}
                    value={entryId}
                    onChange={(e) => handleEntryChange(e.target.value)}
                    disabled={optionsLoading || optionsError != null || (dayInfo != null && !dayInfo.is_working_day)}
                  >
                    <option value="">
                      {optionsLoading
                        ? "Loading schedule…"
                        : optionsError
                          ? "Schedule unavailable — load failed"
                          : (options ?? []).length === 0
                            ? "No classes scheduled on this date"
                            : "Select the class to cancel"}
                    </option>
                    {(options ?? []).map((o) => (
                      <option key={o.timetable_entry_id} value={o.timetable_entry_id}>
                        {o.display_label}
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    Only classes actually scheduled on this date are listed.
                    Subject and class type are taken from the occurrence.
                  </p>
                </div>
              )}
              {selectedEntry && selectedEntry.elective_subjects.length > 0 && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">Affects</label>
                  <select
                    className={selectClass}
                    value={narrowToSubjectId}
                    onChange={(e) => setNarrowToSubjectId(e.target.value)}
                  >
                    <option value="">
                      The entire {ELECTIVE_SLOT_LABELS[selectedEntry.elective_slot as ElectiveSlot]} slot
                      (every student in the slot)
                    </option>
                    {selectedEntry.elective_subjects.map((m) => (
                      <option key={m.id} value={m.id}>
                        Only {m.code} — {m.name} students
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-muted-foreground">
                    Each student&apos;s own elective subject resolves
                    automatically; the shared anchor subject is never shown to
                    students who selected another elective.
                  </p>
                </div>
              )}
              {selectedEntry && (
                <div className="rounded-md border border-border bg-muted/30 p-2 text-xs">
                  <span className="font-medium">Cancelling:</span>{" "}
                  {selectedEntry.subject_code} — {selectedEntry.subject_name} (
                  {CLASS_TYPE_LABELS[selectedEntry.class_type]}) ·{" "}
                  {selectedEntry.start_time.slice(0, 5)}–{selectedEntry.end_time.slice(0, 5)}
                  {selectedEntry.section_name ? ` · ${selectedEntry.section_name}` : ""}
                </div>
              )}
            </>
          )}

          {!isOccurrence && rule.requiresSubject && (
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
                <label className="text-sm font-medium">Target</label>
                <select className={selectClass} value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
                  <option value="">Select subject</option>
                  {isGlobal && (
                    <>
                      <option value={slotOptionValue(ElectiveSlot.ELECTIVE_I)}>
                        {ELECTIVE_SLOT_LABELS[ElectiveSlot.ELECTIVE_I]} (entire slot — HEAD only)
                      </option>
                      <option value={slotOptionValue(ElectiveSlot.ELECTIVE_II)}>
                        {ELECTIVE_SLOT_LABELS[ElectiveSlot.ELECTIVE_II]} (entire slot — HEAD only)
                      </option>
                    </>
                  )}
                  {categorySubjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.code} — {s.name}
                      {s.elective_slot ? ` (${ELECTIVE_SLOT_LABELS[s.elective_slot]} member — affects this subject only)` : ""}
                    </option>
                  ))}
                </select>
                {requiredCategory === SubjectCategory.THEORY && (
                  <p className="text-xs text-muted-foreground">
                    Theory subjects only — practical/lab subjects cannot host
                    this event.
                  </p>
                )}
                {subjectId.startsWith(SLOT_OPTION_PREFIX) && (
                  <p className="text-xs text-warning">
                    Slot-wide target: ONE shared event that every student in the slot resolves to
                    (existing Phase 22.4 semantics). To affect only one elective subject, pick the
                    concrete subject instead.
                  </p>
                )}
              </div>
            </>
          )}

          {isOccurrence ? null : rule.requiresClassType && !autoClassType && (
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

          {eventType === EventType.WORKING_DAY_OVERRIDE && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Working day state</label>
              <select
                className={selectClass}
                value={isWorkingDay === "" ? "" : String(isWorkingDay)}
                onChange={(e) => { setWorkingDayTouched(true); setIsWorkingDay(e.target.value === "" ? "" : e.target.value === "true"); }}
              >
                <option value="">Default (resolve from the calendar)</option>
                <option value="true">Working day</option>
                <option value="false">Non-working day</option>
              </select>
              <p className="text-xs text-muted-foreground">
                Prefilled from the calendar: ordinary weekdays are working;
                weekends and actively-closed days are not. A working weekend
                must be represented as a Working Saturday event.
              </p>
            </div>
          )}

          {!isOccurrence && rule.isGlobal && !rule.isClosure && (
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
