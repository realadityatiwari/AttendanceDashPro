"use client";

import { useState } from "react";
import { AlertCircle, ShieldCheck, Users, Plus } from "lucide-react";

import { useAdminUsers, useAdminUserDetail, useAdminScopeMutations } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminUserSummary, AdminRole } from "@/types/api";
import { AssignScopeDialog } from "./components/AssignScopeDialog";

const ROLE_LABELS: Record<string, string> = {
  [AdminRole.HEAD_ADMIN]: "Global Admin",
  [AdminRole.CLASS_ADMIN]: "Class Admin",
  [AdminRole.SUBSECTION_ADMIN]: "Subsection Admin",
  [AdminRole.ELECTIVE_ADMIN]: "Elective Admin",
};

export default function AdminsPage() {
  const { admins, isLoading, isError, mutate } = useAdminUsers();
  const [selected, setSelected] = useState<AdminUserSummary | null>(null);
  const [assignFor, setAssignFor] = useState<AdminUserSummary | null>(null);

  return (
    <div>
      <PageHeader
        title="Admins"
        description="Administrative accounts and their scopes. Scope assignment, revocation (deactivation), and reactivation are HEAD_ADMIN only. Account creation and password bootstrap are operator-script-managed."
      />

      {isLoading && !admins ? (
        <div className="space-y-3">{[0,1,2].map((i) => <Skeleton key={i} className="h-14 w-full rounded-xl" />)}</div>
      ) : isError ? (
        <ErrorState message={(isError as Error).message} onRetry={() => mutate()} />
      ) : !admins || admins.length === 0 ? (
        <EmptyState
          title="No admin users"
          message="No users hold administrative authority."
          icon={<Users className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      ) : (
        <GlassCard className="overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Roll</th>
                <th className="px-4 py-3">Effective roles</th>
                <th className="px-4 py-3">Active scopes</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {admins.map((a) => (
                <tr key={a.id} className="border-b border-border/60 last:border-0">
                  <td className="px-4 py-3 font-medium">{a.display_name}</td>
                  <td className="px-4 py-3 text-muted-foreground">{a.roll_number ?? "—"}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {a.roles.map((r) => (
                        <Badge key={r} variant={r === AdminRole.HEAD_ADMIN ? "primary" : "neutral"}>
                          {ROLE_LABELS[r] ?? r}
                        </Badge>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">{a.active_scope_count}</td>
                  <td className="px-4 py-3 text-right">
                    <Button variant="outline" size="sm" onClick={() => setSelected(a)}>View scopes</Button>
                    <Button variant="outline" size="sm" className="ml-1" onClick={() => setAssignFor(a)}>
                      <Plus className="h-3 w-3 mr-1" />Assign
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>
      )}

      {selected && (
        <AdminDetailDialog
          userId={selected.id}
          onClose={() => { setSelected(null); mutate(); }}
        />
      )}

      {assignFor && (
        <AssignScopeDialog
          user={assignFor}
          onClose={() => { setAssignFor(null); mutate(); }}
        />
      )}
    </div>
  );
}

function AdminDetailDialog({ userId, onClose }: { userId: string; onClose: () => void }) {
  const { admin, isLoading } = useAdminUserDetail(userId);
  const { setScopeActive } = useAdminScopeMutations();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggle = async (scopeId: string, active: boolean) => {
    setBusy(true); setError(null);
    try { await setScopeActive(userId, scopeId, active); } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update scope");
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onClose}>
      <div className="max-w-xl w-full rounded-lg bg-background p-6 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            {admin?.display_name ?? "Admin"}
          </h2>
          <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">Roll: {admin?.roll_number ?? "—"}</p>
        {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
        <div className="mt-4 space-y-2">
          {isLoading ? (
            <Skeleton className="h-20 w-full rounded-lg" />
          ) : !admin || admin.scopes.length === 0 ? (
            <p className="text-sm text-muted-foreground">No scope rows (global authority comes from the legacy admin role).</p>
          ) : (
            admin.scopes.map((s) => (
              <div key={s.id} className="flex items-center justify-between rounded-lg border border-border p-3">
                <div>
                  <Badge variant={s.role === AdminRole.HEAD_ADMIN ? "primary" : "neutral"}>
                    {ROLE_LABELS[s.role] ?? s.role}
                  </Badge>
                  <span className="ml-2 text-sm">
                    {s.section_name ?? s.subsection_name ?? s.subject_code ?? "global"}
                  </span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {s.active ? "active" : "inactive"}
                  </span>
                </div>
                <Button variant="outline" size="sm" disabled={busy}
                  onClick={() => toggle(s.id, !s.active)}>
                  {s.active ? "Revoke" : "Reactivate"}
                </Button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <GlassCard className="max-w-2xl border-red-900/50 bg-red-950/20">
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <AlertCircle className="mb-4 h-10 w-10 text-red-500" />
        <h1 className="text-lg font-semibold text-red-400">Could not load admins</h1>
        {message && <p className="mt-2 max-w-md text-sm text-red-400/80">{message}</p>}
        <Button variant="outline" size="sm" className="mt-6" onClick={onRetry}>Retry</Button>
      </div>
    </GlassCard>
  );
}