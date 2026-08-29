"use client";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { TimetableEntryForm, FormValues } from "./TimetableEntryForm";
import { TimetableEntryAdminResponse, UpdateTimetableEntryRequest } from "@/types/api";

/**
 * Phase 24.7-D/E — Edit timetable entry dialog.
 *
 * Pre-fills the form from the REAL persisted entry. PATCH semantics:
 * ONLY CHANGED fields are sent — omitted fields are preserved server-side,
 * so an inactive entry can be edited for non-scheduling fields (e.g. room)
 * without tripping the INACTIVE_PARENT guard, and a subsection is never
 * silently cleared. The backend ignores the row being updated during
 * conflict detection. The dialog closes only after the backend accepts the
 * update; failures (409 conflict, 422 validation, 403 scope) keep the
 * dialog open with the backend's message.
 */
export function EditTimetableEntryDialog({
  entry,
  isGlobal,
  isSubmitting,
  onUpdate,
  onOpenChange,
}: {
  entry: TimetableEntryAdminResponse;
  isGlobal: boolean;
  isSubmitting: boolean;
  onUpdate: (entryId: string, payload: UpdateTimetableEntryRequest) => Promise<void>;
  onOpenChange: (open: boolean) => void;
}) {
  const handleSubmit = async (values: FormValues) => {
    // Build a minimal PATCH payload: only fields that actually changed.
    const payload: UpdateTimetableEntryRequest = {};

    if (values.subject_id !== entry.subject_id) payload.subject_id = values.subject_id || undefined;
    if (values.day_of_week !== entry.day_of_week) payload.day_of_week = values.day_of_week;
    if (values.start_time !== entry.start_time.slice(0, 5)) payload.start_time = values.start_time;
    if (values.end_time !== entry.end_time.slice(0, 5)) payload.end_time = values.end_time;
    if (values.class_type !== entry.class_type) {
      payload.class_type = values.class_type as UpdateTimetableEntryRequest["class_type"];
    }
    if ((values.room ?? "") !== (entry.room ?? "")) payload.room = values.room || null;
    if ((values.subsection_id ?? "") !== (entry.subsection_id ?? "")) {
      payload.subsection_id = values.subsection_id || null;
    }
    if ((values.elective_slot ?? "") !== (entry.elective_slot ?? "")) {
      payload.elective_slot = values.elective_slot
        ? (values.elective_slot as UpdateTimetableEntryRequest["elective_slot"])
        : null;
    }
    if (values.is_active !== entry.is_active) payload.is_active = values.is_active;
    if ((values.sort_order ?? "") !== (entry.sort_order ? String(entry.sort_order) : "")) {
      payload.sort_order = values.sort_order ? parseInt(values.sort_order, 10) : null;
    }

    await onUpdate(entry.id, payload);
    // Success: the backend accepted the mutation and the page revalidated.
    onOpenChange(false);
  };

  return (
    <Dialog open={true} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit Timetable Entry</DialogTitle>
          <DialogDescription>
            {entry.subject_code} — {DAY_LABELS[entry.day_of_week]} {entry.start_time.slice(0, 5)}–
            {entry.end_time.slice(0, 5)}
            {!entry.is_active ? " (inactive)" : ""}. Only changed fields are sent.
          </DialogDescription>
        </DialogHeader>
        <TimetableEntryForm
          initial={{
            section_id: entry.section_id,
            subject_id: entry.subject_id,
            subsection_id: entry.subsection_id ?? "",
            day_of_week: entry.day_of_week,
            start_time: entry.start_time.slice(0, 5),
            end_time: entry.end_time.slice(0, 5),
            class_type: entry.class_type,
            room: entry.room ?? "",
            elective_slot: entry.elective_slot ?? "",
            is_active: entry.is_active,
            sort_order: entry.sort_order ? String(entry.sort_order) : "",
          }}
          isGlobal={isGlobal}
          isSubmitting={isSubmitting}
          onSubmit={handleSubmit}
          onCancel={() => onOpenChange(false)}
          submitLabel="Save changes"
        />
      </DialogContent>
    </Dialog>
  );
}

const DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];