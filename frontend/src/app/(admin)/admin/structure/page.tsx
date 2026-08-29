"use client";

import { useState } from "react";
import Link from "next/link";
import { format } from "date-fns";
import {
  FolderTree,
  Plus,
  Loader2,
  AlertTriangle,
  AlertCircle,
  ShieldAlert,
  Play,
  Square,
  ChevronRight,
} from "lucide-react";

import { useAdminSessions, useAdminStructureMutations } from "@/hooks/useApi";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/shared/GlassCard";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

export default function StructurePage() {
  const { sessions, isLoading, isError, mutate } = useAdminSessions();
  const mutations = useAdminStructureMutations();

  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createStart, setCreateStart] = useState("");
  const [createEnd, setCreateEnd] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const status = (isError as Error & { status?: number } | null)?.status;

  const handleCreateSubmit = async () => {
    try {
      setError("");
      setIsSubmitting(true);
      if (!createName || !createStart || !createEnd) {
        throw new Error("All fields are required");
      }
      await mutations.createSession({
        name: createName,
        start_date: createStart,
        end_date: createEnd,
      });
      setCreateOpen(false);
      setCreateName("");
      setCreateStart("");
      setCreateEnd("");
      await mutate();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create session");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleActive = async (session: { id: string; is_active: boolean }) => {
    try {
      if (session.is_active) {
        await mutations.deactivateSession(session.id);
      } else {
        await mutations.activateSession(session.id);
      }
      await mutate();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to toggle activation");
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <FolderTree className="h-6 w-6 text-primary" />
            Academic Structure
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage academic sessions, semesters, sections, and subsections.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          Create Session
        </Button>
      </div>

      {isLoading && !sessions ? (
        <SessionsSkeleton />
      ) : isError ? (
        status === 403 ? (
          <ForbiddenState />
        ) : (
          <ErrorState message={(isError as Error).message} onRetry={() => mutate()} />
        )
      ) : !sessions || sessions.length === 0 ? (
        <GlassCard className="p-10 text-center text-muted-foreground">
          <FolderTree className="h-10 w-10 mx-auto mb-3 opacity-20" />
          <p>No academic sessions found.</p>
        </GlassCard>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sessions.map((session) => (
            <GlassCard key={session.id} className="flex flex-col">
              <div className="p-5 flex-1 space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold text-lg">{session.name}</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      {format(new Date(session.start_date), "MMM d, yyyy")} - {format(new Date(session.end_date), "MMM d, yyyy")}
                    </p>
                  </div>
                  {session.is_active ? (
                    <Badge variant="default" className="bg-green-500/10 text-green-500 hover:bg-green-500/20">Active</Badge>
                  ) : (
                    <Badge variant="outline" className="text-muted-foreground">Inactive</Badge>
                  )}
                </div>

                <div className="pt-2">
                  <div className="flex gap-2">
                    <Button
                      variant={session.is_active ? "outline" : "default"}
                      size="sm"
                      className="flex-1"
                      onClick={() => handleToggleActive(session)}
                    >
                      {session.is_active ? (
                        <><Square className="h-3 w-3 mr-2" /> Deactivate</>
                      ) : (
                        <><Play className="h-3 w-3 mr-2" /> Activate</>
                      )}
                    </Button>
                  </div>
                </div>
              </div>
              <div className="border-t border-border p-3 bg-muted/30">
                <Link href={`/admin/structure/${session.id}`} className="block">
                  <Button variant="ghost" className="w-full justify-between group">
                    <span>Manage Hierarchy</span>
                    <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
                  </Button>
                </Link>
              </div>
            </GlassCard>
          ))}
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Academic Session</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Session Name</label>
              <Input
                placeholder="e.g. Academic Year 2026-2027"
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Start Date</label>
                <Input type="date" value={createStart} onChange={(e) => setCreateStart(e.target.value)} />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">End Date</label>
                <Input type="date" value={createEnd} onChange={(e) => setCreateEnd(e.target.value)} />
              </div>
            </div>
            {error && (
              <div className="p-3 bg-destructive/10 text-destructive text-sm rounded-md flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                <p>{error}</p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={isSubmitting}>Cancel</Button>
            <Button onClick={handleCreateSubmit} disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ForbiddenState() {
  return (
    <GlassCard className="max-w-2xl">
      <div className="flex flex-col items-center justify-center text-center p-8">
        <ShieldAlert className="h-10 w-10 text-warning mb-4" />
        <h1 className="text-lg font-semibold text-foreground">
          Global administrator required
        </h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-md">
          Academic structure management is available to global administrators
          (HEAD_ADMIN) only. Your account does not hold that authority.
        </p>
      </div>
    </GlassCard>
  );
}

function ErrorState({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <GlassCard className="max-w-2xl border-red-900/50 bg-red-950/20">
      <div className="flex flex-col items-center justify-center text-center p-8">
        <AlertCircle className="h-10 w-10 text-red-500 mb-4" />
        <h1 className="text-lg font-semibold text-red-400">
          Could not load academic structure
        </h1>
        {message && <p className="text-sm text-red-400/80 mt-2 max-w-md">{message}</p>}
        <Button variant="outline" size="sm" className="mt-6" onClick={onRetry}>
          Retry
        </Button>
      </div>
    </GlassCard>
  );
}

function SessionsSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {[0, 1, 2].map((i) => (
        <Skeleton key={i} className="h-48 w-full rounded-xl" />
      ))}
    </div>
  );
}
