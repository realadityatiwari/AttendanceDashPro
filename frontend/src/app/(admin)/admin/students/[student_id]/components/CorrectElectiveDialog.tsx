import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AdminStudentDetail, ElectiveSlot } from "@/types/api";
import { useSemesterElectives, useAdminStudentMutations } from "@/hooks/useApi";
import { Loader2 } from "lucide-react";
import { mutate } from "swr";

export function CorrectElectiveDialog({
  student,
  open,
  onOpenChange,
  slot,
}: {
  student: AdminStudentDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  slot: string; // The slot label like "ELECTIVE_I"
}) {
  const { electives, isLoading } = useSemesterElectives(student.semester_id);
  const { correctElective } = useAdminStudentMutations();
  const [selected, setSelected] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const slotEnum = slot === "ELECTIVE_I" ? ElectiveSlot.ELECTIVE_I : ElectiveSlot.ELECTIVE_II;
  const filteredElectives = electives?.filter(e => e.elective_slot === slotEnum) || [];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await correctElective(student.id, { slot: slotEnum, subject_id: selected });
      mutate(`/api/v1/admin/students/${student.id}`);
      onOpenChange(false);
    } catch (err: any) {
      setError(err.message || "Failed to correct elective");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Correct {slot.replace("_", " ")}</DialogTitle>
          <DialogDescription>
            Change the assigned subject for {student.name}&apos;s {slot.replace("_", " ")}. This will immediately update their enrollments.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          {error && <p className="text-sm text-red-500">{error}</p>}
          
          <div className="space-y-2">
            <label className="text-sm font-medium">Subject</label>
            {isLoading ? (
              <div className="flex items-center text-sm text-muted-foreground"><Loader2 className="mr-2 h-4 w-4 animate-spin"/> Loading...</div>
            ) : filteredElectives.length === 0 ? (
              <p className="text-sm text-muted-foreground">No subjects available for this slot in the current semester.</p>
            ) : (
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                required
              >
                <option value="" disabled>Select a subject</option>
                {filteredElectives.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.code} - {s.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || !selected || isLoading}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save changes
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
