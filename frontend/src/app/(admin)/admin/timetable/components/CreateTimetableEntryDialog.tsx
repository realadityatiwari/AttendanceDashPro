"use client";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { TimetableEntryForm, FormValues } from "./TimetableEntryForm";
import { CreateTimetableEntryRequest } from "@/types/api";

/**
 * Phase 24.7-D/E — Create timetable entry dialog.
 * Closes on success; stays open with the backend error message on failure.
 * The page re-renders this dialog with a fresh key on open so form state
 * is always clean (no stale UX from a previous cancelled creation).
 */
export function CreateTimetableEntryDialog({
  open,
  isGlobal,
  scopedSections = [],
  isSubmitting,
  onCreate,
  onOpenChange,
}: {
  open: boolean;
  isGlobal: boolean;
  scopedSections?: { id: string; name: string }[];
  isSubmitting: boolean;
  onCreate: (payload: CreateTimetableEntryRequest) => Promise<void>;
  onOpenChange: (open: boolean) => void;
}) {
  const handleSubmit = async (values: FormValues) => {
    await onCreate({
      section_id: values.section_id,
      subject_id: values.subject_id,
      day_of_week: values.day_of_week,
      start_time: values.start_time,
      end_time: values.end_time,
      class_type: values.class_type,
      room: values.room || null,
      subsection_id: values.subsection_id || null,
      elective_slot: values.elective_slot ? (values.elective_slot as CreateTimetableEntryRequest["elective_slot"]) : null,
      is_active: values.is_active,
      sort_order: values.sort_order ? parseInt(values.sort_order, 10) : null,
    });
    // Success: the backend accepted the mutation and the page revalidated.
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add Timetable Entry</DialogTitle>
          <DialogDescription>
            Create an expected-schedule entry. Conflicts and validation are
            enforced by the backend.
          </DialogDescription>
        </DialogHeader>
        <TimetableEntryForm
          isGlobal={isGlobal}
          scopedSections={scopedSections}
          isSubmitting={isSubmitting}
          onSubmit={handleSubmit}
          onCancel={() => onOpenChange(false)}
          submitLabel="Create entry"
        />
      </DialogContent>
    </Dialog>
  );
}