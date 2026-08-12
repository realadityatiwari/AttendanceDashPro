"use client";

import { useProfile } from "@/hooks/useApi";
import { useAuth } from "@/contexts/AuthContext";
import { auth } from "@/lib/firebase";
import { signOut } from "firebase/auth";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { ErrorState } from "@/components/shared/ErrorState";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { LogOut, User, Mail, ShieldAlert, Key } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProfilePage() {
  const { user } = useAuth();
  const { profile, isLoading, isError } = useProfile();

  const handleLogout = async () => {
    try {
      await signOut(auth);
    } catch (error) {
      console.error("Error signing out", error);
    }
  };

  const displayName = profile?.display_name || user?.displayName || "Student";
  const initials = displayName.charAt(0).toUpperCase();

  if (isError) {
    return (
      <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-4xl mx-auto w-full">
        <PageHeader title="Profile Settings" />
        <ErrorState message="Could not load your student profile. Firebase identity is active, but the PostgreSQL profile linkage endpoint may not be fully implemented yet (501)." />
        <div className="mt-8 flex justify-center">
          <Button variant="destructive" onClick={handleLogout}>
            <LogOut className="mr-2 h-4 w-4" />
            Sign Out of Firebase
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-4xl mx-auto w-full">
      <PageHeader title="Profile Settings" description="Manage your account identity and settings." />
      
      <div className="grid gap-6">
        <GlassCard>
          <div className="p-6 sm:p-8">
            <h3 className="text-lg font-medium text-foreground mb-6 flex items-center gap-2">
              <User className="h-5 w-5 text-accent" />
              Student Identity (PostgreSQL)
            </h3>
            
            <div className="flex flex-col sm:flex-row gap-6 items-start sm:items-center">
              <Avatar className="h-24 w-24 bg-surface2 border-2 border-border/50">
                <AvatarImage src={user?.photoURL || undefined} alt={displayName} />
                <AvatarFallback className="text-3xl font-semibold">{initials}</AvatarFallback>
              </Avatar>
              
              <div className="space-y-4 flex-1 w-full">
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Display Name</label>
                    {isLoading ? (
                      <Skeleton className="h-6 w-48 mt-1" />
                    ) : (
                      <p className="text-base font-medium mt-1">{profile?.display_name || "—"}</p>
                    )}
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Roll Number</label>
                    {isLoading ? (
                      <Skeleton className="h-6 w-32 mt-1" />
                    ) : (
                      <p className="text-base font-medium mt-1 font-mono">{profile?.roll_number || "—"}</p>
                    )}
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Section</label>
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
              <div className="rounded-md bg-amber-500/10 p-4 border border-amber-500/20">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <ShieldAlert className="h-5 w-5 text-amber-400" aria-hidden="true" />
                  </div>
                  <div className="ml-3">
                    <h3 className="text-sm font-medium text-amber-400">Profile Editing Deferred</h3>
                    <div className="mt-2 text-sm text-amber-400/80">
                      <p>
                        The backend API currently does not expose an endpoint to modify student profile data. This is a read-only view.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </GlassCard>

        <GlassCard>
          <div className="p-6 sm:p-8">
            <h3 className="text-lg font-medium text-foreground mb-6 flex items-center gap-2">
              <Key className="h-5 w-5 text-accent" />
              Authentication (Firebase)
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="text-xs text-muted-foreground uppercase tracking-wider font-semibold flex items-center gap-1.5">
                  <Mail className="h-3.5 w-3.5" /> Email Address
                </label>
                <p className="text-base font-medium mt-1">{user?.email}</p>
              </div>
              
              <div>
                <label className="text-xs text-muted-foreground uppercase tracking-wider font-semibold">Firebase UID</label>
                <p className="text-sm font-mono text-muted-foreground mt-1 break-all">{user?.uid}</p>
              </div>
              
              <div className="pt-4">
                <Button variant="destructive" onClick={handleLogout}>
                  <LogOut className="mr-2 h-4 w-4" />
                  Sign Out
                </Button>
              </div>
            </div>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
