"use client";

import { useProfile } from "@/hooks/useApi";
import { useAuth } from "@/contexts/AuthContext";
import { PageHeader } from "@/components/shared/PageHeader";
import { Card } from "@/components/ui/card";
import { ErrorState } from "@/components/shared/ErrorState";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { LogOut, User, ShieldAlert, GraduationCap } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { ShellField } from "@/components/shell/ShellDialog";
import { formatDateMedium } from "@/lib/date";

/**
 * UIA-029: this page is the single canonical Profile surface. The user-menu
 * "Profile" item links here (the near-duplicate ProfileModal was removed) and
 * the academic context that only lived in the modal now lives here, so no
 * account information or action was lost in the merge.
 *
 * UIA-007: the internal auth UUID is never rendered.
 */
export default function ProfilePage() {
  const { user, loading, logout } = useAuth();
  const { profile, isLoading, isError, mutate } = useProfile();

  if (loading) {
    return (
      <div className="flex-1 py-8 w-full max-w-4xl mx-auto space-y-6">
        <PageHeader title="Profile Settings" />
        <Skeleton className="h-[400px] w-full rounded-xl" />
      </div>
    );
  }

  const handleLogout = async () => {
    try {
      logout();
    } catch (error) {
      console.error("Error signing out", error);
    }
  };

  const displayName = profile?.display_name || user?.display_name || "Student";
  const initials = displayName.charAt(0).toUpperCase();

  if (isError) {
    return (
      <div className="flex-1 py-8 w-full max-w-4xl mx-auto">
        <PageHeader title="Profile Settings" />
        {/* 25.UX-5: retry parity with the other screens' error states. */}
        <ErrorState
          message="Could not load your student profile. Please check your connection and try again."
          onRetry={() => mutate()}
        />
        <div className="mt-8 flex justify-center">
          <Button variant="destructive" onClick={handleLogout}>
            <LogOut className="mr-2 h-4 w-4" aria-hidden="true" />
            Sign Out
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 py-8 w-full max-w-4xl mx-auto">
      <PageHeader
        title="Profile Settings"
        description="Your student identity and academic context."
      />

      <div className="grid gap-6">
        <Card>
          <div className="p-6 sm:p-8">
            <h2 className="text-lg font-medium text-foreground mb-6 flex items-center gap-2">
              <User className="h-5 w-5 text-primary" aria-hidden="true" />
              Student Identity
            </h2>

            <div className="flex flex-col sm:flex-row gap-6 items-start sm:items-center">
              <Avatar className="h-24 w-24 bg-muted border-2 border-border/50">
                <AvatarFallback className="text-3xl font-semibold">{initials}</AvatarFallback>
              </Avatar>

              <div className="space-y-4 flex-1 w-full">
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <span className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Display Name</span>
                    {isLoading ? (
                      <Skeleton className="h-6 w-48 mt-1" />
                    ) : (
                      <p className="text-base font-medium mt-1">{profile?.display_name || "—"}</p>
                    )}
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Roll Number</span>
                    {isLoading ? (
                      <Skeleton className="h-6 w-32 mt-1" />
                    ) : (
                      <p className="text-base font-medium mt-1 font-mono">{profile?.roll_number || "—"}</p>
                    )}
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Section</span>
                    {isLoading ? (
                      <Skeleton className="h-6 w-24 mt-1" />
                    ) : (
                      <p className="text-base font-medium mt-1">{profile?.section_name || "—"}</p>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-6 border-t border-border/50">
              <div className="rounded-md bg-warning/10 p-4 border border-warning/20">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <ShieldAlert className="h-5 w-5 text-warning" aria-hidden="true" />
                  </div>
                  <div className="ml-3">
                    <h3 className="text-sm font-medium text-warning">Profile editing isn&apos;t available yet</h3>
                    <div className="mt-2 text-sm text-warning/80">
                      <p>
                        This page is read-only for now.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <div className="p-6 sm:p-8">
            <h2 className="text-lg font-medium text-foreground mb-4 flex items-center gap-2">
              <GraduationCap className="h-5 w-5 text-primary" aria-hidden="true" />
              Academic Context
            </h2>
            {isLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-8 w-full" />
                ))}
              </div>
            ) : (
              <div className="divide-y divide-border/50">
                <ShellField label="Program" value={profile?.program} />
                <ShellField label="Semester" value={profile?.semester_name} />
                <ShellField label="Academic Session" value={profile?.academic_session} />
                <ShellField
                  label="Semester Start"
                  value={profile?.semester_start ? formatDateMedium(profile.semester_start) : undefined}
                />
                <ShellField
                  label="First Quiz Date"
                  value={profile?.first_quiz_date ? formatDateMedium(profile.first_quiz_date) : undefined}
                />
              </div>
            )}
          </div>
        </Card>

        <Card>
          <div className="p-6 sm:p-8">
            <h2 className="text-lg font-medium text-foreground mb-2 flex items-center gap-2">
              <LogOut className="h-5 w-5 text-primary" aria-hidden="true" />
              Account
            </h2>
            <p className="text-sm text-muted-foreground">
              Signing out ends your session on this device.
            </p>
            <Button variant="destructive" className="mt-4" onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" aria-hidden="true" />
              Sign Out
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
