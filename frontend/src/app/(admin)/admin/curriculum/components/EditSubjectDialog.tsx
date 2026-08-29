"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  AdminSubjectSummary,
  ElectiveSlot,
  SubjectCategory,
  UpdateSubjectRequest,
} from "@/types/api";

/**
 * Phase 24.6 — Edit Subject dialog (HEAD_ADMIN only; presentation-gated by the
 * page, the backend enforces require_head_admin).
 *
 * `code` and `semester_id` are immutable — they are not editable here and the
 * backend rejects any attempt to change them with 409. Anchors (BCS-054 /
 * BCS-058) have frozen elective slots, so the slot selector is disabled for
 * them with an honest explanation.
 *
 * The parent renders this dialog only while editing (conditionally mounted per
 * subject), so state is initialized directly from `subject` and never needs an
 * effect to re-sync.
 */
export function EditSubjectDialog({
  subject,
  open,
  onOpenChange,
  onUpdate,
}: {
  subject: AdminSubjectSummary;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdate: (subjectId: string, payload: UpdateSubjectRequest) => Promise<void>;
}) {
  const [name, setName] = useState(subject.name);
  const [tag, setTag] = useState(subject.tag ?? "");
  const [category, setCategory] = useState<SubjectCategory>(subject.category);
  const [electiveSlot, setElectiveSlot] = useState<string>(subject.elective_slot ?? "");
  const [quizApplicable, setQuizApplicable] = useState(subject.quiz_applicable);
  const [attendanceApplicable, setAttendanceApplicable] = useState(subject.attendance_applicable);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await onUpdate(subject.id, {
        name: name.trim(),
        tag: tag.trim() ? tag.trim() : null,
        category,
        elective_slot: electiveSlot ? (electiveSlot as ElectiveSlot) : null,
        quiz_applicable: quizApplicable,
        attendance_applicable: attendanceApplicable,
      });
      onOpenChange(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update subject");
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectClass =
    "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit {subject.code}</DialogTitle>
          <DialogDescription>
            Update subject metadata. Code and semester are immutable after
            creation.
            {subject.is_anchor && (
              <span className="mt-1 block">
                <Badge variant="warning">Elective anchor</Badge> BCS-054 / BCS-058
                anchors have a frozen elective-slot assignment and cannot be changed.
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="space-y-2">
            <label className="text-sm font-medium">Subject name</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={200}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Tag (optional)</label>
            <Input
              placeholder="e.g. Elective-II"
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              maxLength={50}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Category</label>
              <select
                className={selectClass}
                value={category}
                onChange={(e) => setCategory(e.target.value as SubjectCategory)}
              >
                <option value={SubjectCategory.THEORY}>Theory</option>
                <option value={SubjectCategory.LAB}>Lab</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Elective slot</label>
              <select
                className={selectClass}
                value={electiveSlot}
                onChange={(e) => setElectiveSlot(e.target.value)}
                disabled={subject.is_anchor}
                title={subject.is_anchor ? "Frozen for elective anchors" : undefined}
              >
                <option value="">Common subject</option>
                <option value={ElectiveSlot.ELECTIVE_I}>Department Elective-I</option>
                <option value={ElectiveSlot.ELECTIVE_II}>Department Elective-II</option>
              </select>
            </div>
          </div>

          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={quizApplicable}
                onChange={(e) => setQuizApplicable(e.target.checked)}
              />
              Quiz applicable
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={attendanceApplicable}
                onChange={(e) => setAttendanceApplicable(e.target.checked)}
              />
              Attendance applicable
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save changes
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
