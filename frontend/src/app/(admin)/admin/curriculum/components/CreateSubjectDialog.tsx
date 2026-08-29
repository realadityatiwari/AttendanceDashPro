"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAdminSessions, useAdminSemesters } from "@/hooks/useApi";
import { CreateSubjectRequest, ElectiveSlot, SubjectCategory } from "@/types/api";

/**
 * Phase 24.6 — Create Subject dialog (HEAD_ADMIN only; the page gates this
 * dialog to global admins as presentation, the backend enforces require_head_admin).
 */
export function CreateSubjectDialog({
  open,
  onOpenChange,
  onCreate,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (payload: CreateSubjectRequest) => Promise<void>;
}) {
  const { sessions } = useAdminSessions();
  const [sessionId, setSessionId] = useState<string>("");
  const { semesters } = useAdminSemesters(sessionId || null);

  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [tag, setTag] = useState("");
  const [semesterId, setSemesterId] = useState("");
  const [category, setCategory] = useState<SubjectCategory>(SubjectCategory.THEORY);
  const [electiveSlot, setElectiveSlot] = useState<string>("");
  const [quizApplicable, setQuizApplicable] = useState(true);
  const [attendanceApplicable, setAttendanceApplicable] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setCode("");
    setName("");
    setTag("");
    setSemesterId("");
    setCategory(SubjectCategory.THEORY);
    setElectiveSlot("");
    setQuizApplicable(true);
    setAttendanceApplicable(true);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim() || !name.trim() || !semesterId) {
      setError("Code, name, and semester are required");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      await onCreate({
        code: code.trim(),
        name: name.trim(),
        tag: tag.trim() ? tag.trim() : null,
        elective_slot: electiveSlot ? (electiveSlot as ElectiveSlot) : null,
        category,
        quiz_applicable: quizApplicable,
        attendance_applicable: attendanceApplicable,
        semester_id: semesterId,
      });
      reset();
      onOpenChange(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create subject");
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectClass =
    "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) reset();
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Subject</DialogTitle>
          <DialogDescription>
            Create a new subject in a semester. Subject code and semester are
            immutable after creation.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="space-y-2">
            <label className="text-sm font-medium">Academic session</label>
            <select
              className={selectClass}
              value={sessionId}
              onChange={(e) => {
                setSessionId(e.target.value);
                setSemesterId("");
              }}
            >
              <option value="">Select a session</option>
              {(sessions ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.is_active ? " (active)" : ""}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Semester</label>
            <select
              className={selectClass}
              value={semesterId}
              onChange={(e) => setSemesterId(e.target.value)}
              disabled={!sessionId || !semesters}
            >
              <option value="">Select a semester</option>
              {(semesters ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Subject code</label>
              <Input
                placeholder="e.g. BCS-099"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={20}
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
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Subject name</label>
            <Input
              placeholder="e.g. Cloud Computing"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={200}
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
              Create subject
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
