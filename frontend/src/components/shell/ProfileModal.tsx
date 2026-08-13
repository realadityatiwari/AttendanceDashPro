"use client";

import { ShellDialog, ShellField } from "@/components/shell/ShellDialog";
import { useProfile } from "@/hooks/useApi";
import { useAuth } from "@/contexts/AuthContext";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";

function formatDate(iso?: string | null): string | undefined {
  if (!iso) return undefined;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return undefined;
  return date.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

interface ProfileModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ProfileModal({ open, onOpenChange }: ProfileModalProps) {
  const { user } = useAuth();
  const { profile, isLoading } = useProfile();

  const displayName = profile?.display_name || user?.display_name || "Student";
  const initials = displayName.trim().charAt(0).toUpperCase() || "?";
  const rollNumber = profile?.roll_number || user?.roll_number || null;

  return (
    <ShellDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Profile"
      description="Your student identity and academic context"
      width="md"
    >
      <div className="flex items-center gap-4">
        <Avatar size="lg" className="bg-surface2 border border-border">
          <AvatarFallback className="text-base font-semibold">
            {initials}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <p className="truncate text-base font-semibold text-foreground">
            {displayName}
          </p>
          <p className="mt-0.5 font-mono text-xs text-muted-foreground">
            {rollNumber || "—"}
          </p>
        </div>
      </div>

      <div className="mt-4 divide-y divide-border border-t border-b border-border">
        {isLoading ? (
          <>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between gap-4 py-2">
                <Skeleton className="h-3 w-24" />
                <Skeleton className="h-4 w-32" />
              </div>
            ))}
          </>
        ) : (
          <>
            <ShellField label="University Roll Number" value={rollNumber} mono />
            <ShellField
              label="Program"
              unavailable
            />
            <ShellField label="Semester" value={profile?.semester_name} />
            <ShellField label="Academic Session" value={profile?.academic_session} />
            <ShellField
              label="Semester Start"
              value={formatDate(profile?.semester_start)}
            />
            <ShellField
              label="First Quiz Date"
              value={formatDate(profile?.first_quiz_date)}
            />
          </>
        )}
      </div>

      <p className="mt-4 text-xs text-muted-foreground">
        Program data is not stored in the backend model yet; the remaining
        fields are resolved from your section, semester and quiz schedules.
      </p>
    </ShellDialog>
  );
}