"use client";

import { useState, useMemo } from "react";
import { AlertCircle, ClipboardList, Plus, ShieldAlert } from "lucide-react";

import {
  useAdminMe,
  useAdminQuizSchedules,
  useAdminQuizCycles,
  useAdminQuizMutations,
  useAdminSessions,
  useAdminSemesters,
} from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AdminQuizScheduleResponse,
  CreateQuizScheduleRequest,
  UpdateQuizScheduleRequest,
  ScheduleStatus,
} from "@/types/api";
import { CreateQuizScheduleDialog } from "./components/CreateQuizScheduleDialog";
import { EditQuizScheduleDialog } from "./components/EditQuizScheduleDialog";

const STATUS_VARIANTS: Record<string, "primary" | "outline" | "destructive" | "warning" | "neutral"> = {
  [ScheduleStatus.SCHEDULED]: "primary",
  [ScheduleStatus.UNRESOLVED]: "warning",
  [ScheduleStatus.CANCELLED]: "destructive",
};

/**
 * Phase 24.8 — Admin Quiz Schedule Manager.
 *
 * Read scope is resolved SERVER-SIDE (GET /api/v1/admin/quizzes): HEAD all,
 * CLASS assigned section's semester, ELECTIVE exact subject, SUBSECTION
 * inert. Writes are HEAD_ADMIN only — the backend is the security boundary.
 * The runtime quiz-date authority remains the active QUIZ_DAY AcademicEvents
 * (synchronized atomically by the backend); `has_active_event` here reflects
 * that derivation state honestly.
 */
export default function QuizSchedulesPage() {
  const { identity } = useAdminMe();
  const isGlobal = identity?.is_global ?? false;

  const { sessions } = useAdminSessions();
  const [sessionId, setSessionId] = useState("");
  const { semesters } = useAdminSemesters(sessionId || null);
  const [semesterId, setSemesterId] = useState("");

  const [cycleFilter, setCycleFilter] = useState("");
  const { schedules, isLoading, isError, mutate } = useAdminQuizSchedules(
    useMemo(() => {
      const p: Record<string, string> = {};
      if (cycleFilter) p.cycle_number = cycleFilter;
      if (semesterId) p.semester_id = semesterId;
      if (sessionId) p.session_id = sessionId;
      return p;
    }, [cycleFilter, semesterId, sessionId])
  );
  const { cycles } = useAdminQuizCycles();
  const mutations = useAdminQuizMutations();
  const status = (isError as Error & { status?: number } | null)?.status;

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<AdminQuizScheduleResponse | null>(null);
  const [mutationLoading, setMutationLoading] = useState(false);

  const runMutation = async (fn: () => Promise<unknown>) => {
    setMutationLoading(true);
    try {
      await fn();
      await mutate();
    } finally {
      setMutationLoading(false);
    }
  };

  const selectClass =
    "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <div>
      <PageHeader
        title="Quiz Schedules"
        description="Configure quiz cycles, dates, and targets. Quiz dates remain authoritative from the synchronized QUIZ_DAY events consumed by eligibility."
      >
        {isGlobal && (
          <Button size="sm" className="gap-2" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Create Schedule
          </Button>
        )}
      </PageHeader>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap gap-3">
        {isGlobal && (
          <>
            <div className="w-48">
              <label className="mb-1 block text-xs text-muted-foreground" htmlFor="qz-session">Session</label>
              <select id="qz-session" className={selectClass} value={sessionId} onChange={(e) => { setSessionId(e.target.value); setSemesterId(""); }}>
                <option value="">All sessions</option>
                {(sessions ?? []).map((s) => (
                  <option key={s.id} value={s.id}>{s.name}{s.is_active ? " (active)" : ""}</option>
                ))}
              </select>
            </div>
            <div className="w-48">
              <label className="mb-1 block text-xs text-muted-foreground" htmlFor="qz-semester">Semester</label>
              <select id="qz-semester" className={selectClass} value={semesterId} onChange={(e) => setSemesterId(e.target.value)} disabled={!sessionId}>
                <option value="">All semesters</option>
                {(semesters ?? []).map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
          </>
        )}
        <div className="w-40">
          <label className="mb-1 block text-xs text-muted-foreground" htmlFor="qz-cycle">Cycle</label>
          <select id="qz-cycle" className={selectClass} value={cycleFilter} onChange={(e) => setCycleFilter(e.target.value)}>
            <option value="">All cycles</option>
            {(cycles ?? []).map((c) => (
              <option key={c.id} value={c.cycle_number}>{c.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Content */}
      {isLoading && !schedules ? (
        <QuizSkeleton />
      ) : isError ? (
        status === 403 ? (
          <ForbiddenState />
        ) : (
          <ErrorState message={(isError as Error).message} onRetry={() => mutate()} />
        )
      ) : !schedules || schedules.length === 0 ? (
        <EmptyState
          title="No quiz schedules in your scope"
          message="No quiz schedules match your current filters or administrative scope."
          icon={<ClipboardList className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      ) : (
        <GlassCard className="overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-3">Cycle</th>
                <th className="px-4 py-3">Subject</th>
                <th className="px-4 py-3">Target</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">QUIZ_DAY</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((s) => (
                <tr key={s.id} className="border-b border-border/60 last:border-0">
                  <td className="px-4 py-3">{s.cycle_label}</td>
                  <td className="px-4 py-3">
                    <span className="font-medium">{s.subject_code}</span>
                    <span className="ml-2 text-muted-foreground">{s.subject_name}</span>
                  </td>
                  <td className="px-4 py-3">
                    {s.is_elective ? (
                      <Badge variant="primary">{s.elective_slot === "ELECTIVE_I" ? "Dept. Elective-I" : "Dept. Elective-II"}</Badge>
                    ) : (
                      <Badge variant="neutral">Common subject</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3">{s.date ?? "—"}</td>
                  <td className="px-4 py-3">
                    <Badge variant={STATUS_VARIANTS[s.schedule_status] ?? "neutral"}>{s.schedule_status}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    {s.has_active_event ? (
                      <Badge variant="primary">Active event</Badge>
                    ) : (
                      <Badge variant="outline" className="text-muted-foreground">None</Badge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {isGlobal && (
                      <Button variant="outline" size="sm" onClick={() => setEditing(s)}>
                        Edit
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>
      )}

      {isGlobal && (
        <CreateQuizScheduleDialog
          key={createOpen ? "create-open" : "create-closed"}
          open={createOpen}
          isSubmitting={mutationLoading}
          onOpenChange={setCreateOpen}
          onCreate={(payload: CreateQuizScheduleRequest) =>
            runMutation(() => mutations.createSchedule(payload))
          }
        />
      )}

      {editing && isGlobal && (
        <EditQuizScheduleDialog
          key={editing.id}
          schedule={editing}
          isSubmitting={mutationLoading}
          onOpenChange={(open) => !open && setEditing(null)}
          onUpdate={(scheduleId: string, payload: UpdateQuizScheduleRequest) =>
            runMutation(() => mutations.updateSchedule(scheduleId, payload))
          }
        />
      )}
    </div>
  );
}

function ForbiddenState() {
  return (
    <GlassCard className="max-w-2xl">
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <ShieldAlert className="mb-4 h-10 w-10 text-warning" />
        <h1 className="text-lg font-semibold text-foreground">Administrative access required</h1>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">
          Quiz schedules are available to authorized administrators only.
        </p>
      </div>
    </GlassCard>
  );
}

function ErrorState({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <GlassCard className="max-w-2xl border-red-900/50 bg-red-950/20">
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <AlertCircle className="mb-4 h-10 w-10 text-red-500" />
        <h1 className="text-lg font-semibold text-red-400">Could not load quiz schedules</h1>
        {message && <p className="mt-2 max-w-md text-sm text-red-400/80">{message}</p>}
        <Button variant="outline" size="sm" className="mt-6" onClick={onRetry}>Retry</Button>
      </div>
    </GlassCard>
  );
}

function QuizSkeleton() {
  return (
    <div className="space-y-3">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <Skeleton key={i} className="h-14 w-full rounded-xl" />
      ))}
    </div>
  );
}