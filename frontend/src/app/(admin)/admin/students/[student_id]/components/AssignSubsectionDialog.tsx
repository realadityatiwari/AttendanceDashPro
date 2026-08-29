import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AdminStudentDetail } from "@/types/api";
import { useSectionSubsections, useAdminStudentMutations } from "@/hooks/useApi";
import { Loader2 } from "lucide-react";
import { mutate } from "swr";

export function AssignSubsectionDialog({
  student,
  open,
  onOpenChange,
}: {
  student: AdminStudentDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { subsections, isLoading } = useSectionSubsections(student.section_id);
  const { assignSubsection } = useAdminStudentMutations();
  const [selected, setSelected] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await assignSubsection(student.id, { subsection_id: selected });
      mutate(`/api/v1/admin/students/${student.id}`);
      onOpenChange(false);
    } catch (err: any) {
      setError(err.message || "Failed to assign subsection");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Assign Subsection</DialogTitle>
          <DialogDescription>
            Move {student.name} to a different subsection within {student.section_name}.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          {error && <p className="text-sm text-red-500">{error}</p>}
          
          <div className="space-y-2">
            <label className="text-sm font-medium">Subsection</label>
            {isLoading ? (
              <div className="flex items-center text-sm text-muted-foreground"><Loader2 className="mr-2 h-4 w-4 animate-spin"/> Loading...</div>
            ) : !subsections || subsections.length === 0 ? (
              <p className="text-sm text-muted-foreground">No subsections available in this section.</p>
            ) : (
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                required
              >
                <option value="" disabled>Select a subsection</option>
                {subsections.map((s) => (
                  <option key={s.id} value={s.id} disabled={s.max_strength !== null && s.current_strength !== null && s.current_strength >= s.max_strength && s.id !== student.subsection_id}>
                    {s.name} {s.max_strength ? `(${s.current_strength || 0}/${s.max_strength})` : ""}
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
