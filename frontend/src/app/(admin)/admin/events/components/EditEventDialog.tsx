"use client";

import { useState } from "react";
import { Loader2, Power } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useOccurrenceOptions } from "@/hooks/useApi";
import { AdminEventResponse, UpdateAdminEventRequest, ClassType, ElectiveSlot } from "@/types/api";
import { getRule, CLASS_TYPE_LABELS, SUBSTITUTION_DAYS, isOccurrenceEventType } from "@/components/events/eventRules";

const selectClass =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

/**
 * Phase 24.9 — Edit/Deactivate Event dialog (HEAD_ADMIN only; backend
 * authoritative). Quiz-schedule-managed QUIZ_DAY events are read-only here
 * (their date/subject/active state is owned by the Quiz Schedule Manager).
 * Deactivation is safe/reversible (no physical deletion).
 *
 * OCC-1: occurrence-driven cancellation events show the exact referenced
 * occurrence; the class type is never independently editable (it belongs to
 * the occurrence). Changing the date re-resolves the occurrences scheduled
 * for that new date — if the stored occurrence is no longer scheduled (or the
 * event predates occurrence references), a new one must be selected and the
 * subject/class-type/entry state is re-derived, never left stale.
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
  const isOccurrence = isOccurrenceEventType(event.event_type);

  const [startDate, setStartDate] = useState(event.start_date);
  const [endDate, setEndDate] = useState(event.end_date);
  const [classType, setClassType] = useState<ClassType | "">(event.class_type ?? "");
  const [subDay, setSubDay] = useState(event.substitution_schedule_override ?? "");
  const [note, setNote] = useState(event.note ?? "");
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // OCC-1 occurrence state. Selection falls back to the event's stored entry
  // (kept when the date still resolves to it); a date change resets the
  // fallback so a stale entry can never be silently submitted.
  const [entryId, setEntryId] = useState(event.timetable_entry_id ?? "");
  const [narrowToSubjectId, setNarrowToSubjectId] = useState("");
  const [narrowTouched, setNarrowTouched] = useState(false);
  const { options, dayInfo, isLoading: optionsLoading } = useOccurrenceOptions(
    isOccurrence ? startDate : null,
    isOccurrence ? event.event_type : null,
  );

  const selectedEntry = (options ?? []).find((o) => o.timetable_entry_id === entryId) ?? null;
  const storedEntryStillListed = Boolean(
    event.timetable_entry_id && (options ?? []).some((o) => o.timetable_entry_id === event.timetable_entry_id)
  );

  // Narrowing derivation: whenever the selected entry identity changes,
  // reset any touched narrowing; prefill from the event's own subject when
  // it is a concrete member of the entry's slot (a narrowed event edits as
  // narrowed), else slot-wide.
  const [lastEntryKey, setLastEntryKey] = useState<string | null>(event.timetable_entry_id);
  const entryKey = selectedEntry?.timetable_entry_id ?? null;
  if (entryKey !== lastEntryKey) {
    setLastEntryKey(entryKey);
    setNarrowTouched(false);
    setNarrowToSubjectId("");
  }
  const prefilledNarrow =
    selectedEntry && event.subject_id
      && selectedEntry.elective_subjects.some((m) => m.id === event.subject_id)
      ? event.subject_id
      : "";
  if (selectedEntry && !narrowTouched && narrowToSubjectId !== prefilledNarrow) {
    setNarrowToSubjectId(prefilledNarrow);
  }

  const occurrenceNeedsSelection =
    isOccurrence && selectedEntry === null && (dayInfo?.is_working_day ?? true);

  const handleStartDateChange = (value: string) => {
    setStartDate(value);
    if (rule.singleDayOnly) {
      setEndDate(value);
    }
    // Re-resolve: fall back to the stored entry (kept only if still
    // scheduled on the new date); narrowing re-derives from the entry.
    setEntryId(event.timetable_entry_id ?? "");
  };

  const handleSubmit = async () => {
    if (readOnly) { setError("This event is managed by the Quiz Schedule Manager and cannot be edited here."); return; }
    const effectiveEndDate = rule.singleDayOnly ? startDate : endDate;
    if (effectiveEndDate < startDate) { setError("End date must not be before start date"); return; }
    if (occurrenceNeedsSelection) {
      setError(
        "Select the scheduled occurrence for this date — a cancellation must reference a real timetable occurrence."
      );
      return;
    }
    setError(null);
    try {
      const payload: UpdateAdminEventRequest = {};
      if (startDate !== event.start_date) payload.start_date = startDate;
      if (effectiveEndDate !== event.end_date) payload.end_date = effectiveEndDate;
      if (isOccurrence && selectedEntry) {
        const entryChanged = selectedEntry.timetable_entry_id !== event.timetable_entry_id;
        const narrowingChanged = narrowTouched && narrowToSubjectId !== prefilledNarrow;
        if (entryChanged || narrowingChanged) {
          payload.timetable_entry_id = selectedEntry.timetable_entry_id;
          payload.subject_id = narrowToSubjectId || (selectedEntry.elective_slot ? null : selectedEntry.subject_id);
          payload.elective_slot = null; // server re-derives from the occurrence
          payload.class_type = selectedEntry.class_type;
        }
      }
      if (!isOccurrence && rule.requiresClassType && classType !== (event.class_type ?? "")) {
        payload.class_type = classType as ClassType;
      }
      if (subDay !== (event.substitution_schedule_override ?? "")) {
        payload.substitution_schedule_override = subDay || null;
      }
      if (event.event_type === "HOLIDAY" && note !== (event.note ?? "")) payload.note = note || null;
      if (Object.keys(payload).length === 0) { onOpenChange(false); return; }
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

          <div className={rule.singleDayOnly ? "space-y-2" : "grid grid-cols-2 gap-4"}>
            <div className="space-y-2">
              <label className="text-sm font-medium">{rule.singleDayOnly ? "Date" : "Start date"}</label>
              <Input type="date" value={startDate} onChange={(e) => handleStartDateChange(e.target.value)} disabled={readOnly} />
            </div>
            {!rule.singleDayOnly && (
              <div className="space-y-2">
                <label className="text-sm font-medium">End date</label>
                <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} disabled={readOnly} />
              </div>
            )}
          </div>

          {isOccurrence && (
            <>
              <div className="space-y-2">
                <label className="text-sm font-medium">Scheduled occurrence</label>
                {event.occurrence_label && storedEntryStillListed && (
                  <p className="text-xs text-muted-foreground">
                    Currently references: {event.occurrence_label}
                  </p>
                )}
                {!event.occurrence_label && (
                  <p className="text-xs text-warning">
                    This event predates occurrence references — select the
                    scheduled occurrence it cancels before saving.
                  </p>
                )}
                <select
                  className={selectClass}
                  value={entryId}
                  onChange={(e) => setEntryId(e.target.value)}
                  disabled={readOnly || optionsLoading || (dayInfo != null && !dayInfo.is_working_day)}
                >
                  <option value="">
                    {optionsLoading
                      ? "Loading schedule…"
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
                {dayInfo && !dayInfo.is_working_day && (
                  <p className="text-xs text-warning">
                    {startDate} is a non-working day ({dayInfo.non_working_reason}) —
                    there are no scheduled classes to cancel.
                  </p>
                )}
              </div>
              {selectedEntry && selectedEntry.elective_subjects.length > 0 && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">Affects</label>
                  <select
                    className={selectClass}
                    value={narrowToSubjectId}
                    onChange={(e) => { setNarrowTouched(true); setNarrowToSubjectId(e.target.value); }}
                    disabled={readOnly}
                  >
                    <option value="">
                      The entire {ELECTIVE_SLOT_LABEL(selectedEntry.elective_slot)} slot
                      (every student in the slot)
                    </option>
                    {selectedEntry.elective_subjects.map((m) => (
                      <option key={m.id} value={m.id}>
                        Only {m.code} — {m.name} students
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {selectedEntry && (
                <p className="text-xs text-muted-foreground">
                  Subject and class type follow the occurrence —{" "}
                  {selectedEntry.subject_code} ({CLASS_TYPE_LABELS[selectedEntry.class_type]}).
                </p>
              )}
            </>
          )}

          {rule.requiresClassType && (
            <div className="space-y-2">
              <label className="text-sm font-medium">Class type</label>
              {isOccurrence ? (
                // OCC-1: the class type belongs to the referenced occurrence —
                // never independently changeable.
                <p className="text-sm text-muted-foreground">
                  {event.class_type ? CLASS_TYPE_LABELS[event.class_type] : "—"}{" "}
                  <span className="text-xs">(derived from the occurrence)</span>
                </p>
              ) : (
                <select className={selectClass} value={classType} onChange={(e) => setClassType(e.target.value as ClassType)} disabled={readOnly}>
                  <option value="">Select class type</option>
                  {rule.allowedClassTypes.map((ct) => (
                    <option key={ct} value={ct}>{CLASS_TYPE_LABELS[ct]}</option>
                  ))}
                </select>
              )}
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

// Canonical elective-slot label (mirrors the create dialog's register).
function ELECTIVE_SLOT_LABEL(slot: ElectiveSlot | null): string {
  if (slot === "ELECTIVE_I") return "Department Elective-I";
  if (slot === "ELECTIVE_II") return "Department Elective-II";
  return slot ?? "";
}
