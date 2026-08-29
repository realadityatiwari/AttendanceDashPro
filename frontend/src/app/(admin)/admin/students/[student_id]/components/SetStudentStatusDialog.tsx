import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AdminStudentDetail } from "@/types/api";
import { useAdminStudentMutations } from "@/hooks/useApi";
import { Loader2, AlertTriangle } from "lucide-react";
import { mutate } from "swr";

export function SetStudentStatusDialog({
  student,
  open,
  onOpenChange,
}: {
  student: AdminStudentDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { setStudentStatus } = useAdminStudentMutations();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isActive = student.is_active;
  const newStatus = !isActive;

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      await setStudentStatus(student.id, { is_active: newStatus });
      mutate(`/api/v1/admin/students/${student.id}`);
      onOpenChange(false);
    } catch (err: any) {
      setError(err.message || "Failed to update student status");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{newStatus ? "Activate" : "Deactivate"} Account</DialogTitle>
          <DialogDescription>
            {newStatus 
              ? `Are you sure you want to reactivate ${student.name}'s account? They will be able to log in again.`
              : `Are you sure you want to deactivate ${student.name}'s account? They will lose access to the system immediately.`
            }
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-4">
          {error && <p className="text-sm text-red-500">{error}</p>}
          
          {!newStatus && (
            <div className="flex items-center gap-2 p-3 text-sm text-warning-foreground bg-warning/10 border border-warning/20 rounded-md">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <p>Deactivating this account will prevent the student from logging in, but their academic records and attendance history will be preserved.</p>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button 
              type="button" 
              variant={newStatus ? "default" : "destructive"} 
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {newStatus ? "Activate Account" : "Deactivate Account"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
