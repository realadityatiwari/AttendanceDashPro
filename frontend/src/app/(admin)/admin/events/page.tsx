"use client";

import { useState, useMemo } from "react";
import { AlertCircle, CalendarClock, Plus, ShieldAlert } from "lucide-react";

import { useAdminMe, useAdminEvents, useAdminEventMutations } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminEventResponse, CreateAdminEventRequest, UpdateAdminEventRequest } from "@/types/api";
import { CreateEventDialog } from "./components/CreateEventDialog";
import { EditEventDialog } from "./components/EditEventDialog";

const EVENT_TYPE_LABELS: Record<string, string> = {
  EXTRA_LECTURE: "Extra Lecture",
  EXTRA_TUTORIAL: "Extra Tutorial",
  EXTRA_PRACTICAL: "Extra Practical",
  CLASS_CANCELLED: "Class Cancelled",
  CLASS_MODIFIED: "Class Modified",
  SURPRISE_QUIZ: "Surprise Quiz",
  QUIZ_DAY: "Quiz Day",
  HOLIDAY: "Holiday",
  PUBLIC_HOLIDAY: "Public Holiday",
  INSTITUTE_HOLIDAY: "Institute Holiday",
  FESTIVAL_HOLIDAY: "Festival Holiday",
  EMERGENCY_CLOSURE: "Emergency Closure",
  SEMESTER_BREAK: "Semester Break",
  MID_SEMESTER_BREAK: "Mid-Semester Break",
  WORKING_DAY_OVERRIDE: "Working Day Override",
  WORKING_SATURDAY: "Working Saturday",
  LAB_CANCELLED: "Lab Cancelled",
  MID_SEM_PRACTICAL: "Mid-Sem Practical",
};

const EVENT_COLORS: Record<string, "primary" | "neutral" | "secondary" | "outline" | "warning" | "destructive"> = {
  EXTRA_LECTURE: "secondary",
  EXTRA_TUTORIAL: "secondary",
  EXTRA_PRACTICAL: "secondary",
  CLASS_CANCELLED: "destructive",
  CLASS_MODIFIED: "warning",
  SURPRISE_QUIZ: "warning",
  QUIZ_DAY: "primary",
  HOLIDAY: "neutral",
  PUBLIC_HOLIDAY: "neutral",
  INSTITUTE_HOLIDAY: "neutral",
  FESTIVAL_HOLIDAY: "neutral",
  EMERGENCY_CLOSURE: "destructive",
  SEMESTER_BREAK: "neutral",
  MID_SEMESTER_BREAK: "neutral",
  WORKING_DAY_OVERRIDE: "outline",
  WORKING_SATURDAY: "outline",
  LAB_CANCELLED: "destructive",
  MID_SEM_PRACTICAL: "secondary",
};

export default function EventsPage() {
  const { identity } = useAdminMe();
  const isGlobal = identity?.is_global ?? false;

  const [typeFilter, setTypeFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");

  const params = useMemo(() => {
    const p: Record<string, string> = {};
    if (typeFilter) p.event_type = typeFilter;
    if (activeFilter === "active") p.active = "true";
    if (activeFilter === "inactive") p.active = "false";
    return p;
  }, [typeFilter, activeFilter]);

  const { events, isLoading, isError, mutate } = useAdminEvents(params);
  const mutations = useAdminEventMutations();
  const status = (isError as Error & { status?: number } | null)?.status;

  const [mutationLoading, setMutationLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<AdminEventResponse | null>(null);

  const runMutation = async (fn: () => Promise<unknown>) => {
    setMutationLoading(true);
    try { await fn(); await mutate(); } finally { setMutationLoading(false); }
  };

  const selectClass =
    "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <div>
      <PageHeader
        title="Events"
        description="Manage academic events (holidays, extras, cancellations, quizzes). The canonical event architecture is authoritative. QUIZ_DAY events backed by the Quiz Schedule Manager must be edited through /admin/quizzes."
      >
        {isGlobal && (
          <Button size="sm" className="gap-2" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Add Event
          </Button>
        )}
      </PageHeader>

      <div className="mb-6 flex flex-wrap gap-3">
        <div className="w-48">
          <label className="mb-1 block text-xs text-muted-foreground" htmlFor="ev-type">Event type</label>
          <select id="ev-type" className={selectClass} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="">All types</option>
            {Object.entries(EVENT_TYPE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
        <div className="w-40">
          <label className="mb-1 block text-xs text-muted-foreground" htmlFor="ev-state">State</label>
          <select id="ev-state" className={selectClass} value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)}>
            <option value="">All</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
        </div>
      </div>

      {isLoading && !events ? (
        <EventsSkeleton />
      ) : isError ? (
        status === 403 ? (
          <ForbiddenState />
        ) : (
          <ErrorState message={(isError as Error).message} onRetry={() => mutate()} />
        )
      ) : !events || events.length === 0 ? (
        <EmptyState
          title="No events in your scope"
          message="No events match your current filters or administrative scope."
          icon={<CalendarClock className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      ) : (
        <GlassCard className="overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Target</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">State</th>
                <th className="px-4 py-3">Managed</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr key={ev.id} className="border-b border-border/60 last:border-0">
                  <td className="px-4 py-3">
                    <Badge variant={EVENT_COLORS[ev.event_type] ?? "neutral"}>
                      {EVENT_TYPE_LABELS[ev.event_type] ?? ev.event_type}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm">{ev.target_summary}</span>
                    {ev.subject_code && <span className="ml-1 text-xs text-muted-foreground">({ev.subject_code})</span>}
                  </td>
                  <td className="px-4 py-3">
                    {ev.start_date === ev.end_date ? ev.start_date : `${ev.start_date} \u2013 ${ev.end_date}`}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={ev.active ? "primary" : "outline"}>{ev.active ? "Active" : "Inactive"}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    {ev.quiz_schedule_managed ? (
                      <Badge variant="warning">Quiz-managed</Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground">\u2014</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {isGlobal && !ev.quiz_schedule_managed && (
                      <Button variant="outline" size="sm" onClick={() => setEditing(ev)}>Edit</Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>
      )}

      {isGlobal && (
        <CreateEventDialog
          key={createOpen ? "open" : "closed"}
          open={createOpen}
          isSubmitting={mutationLoading}
          onOpenChange={setCreateOpen}
          onCreate={(payload: CreateAdminEventRequest) =>
            runMutation(() => mutations.createEvent(payload))
          }
        />
      )}

      {editing && isGlobal && (
        <EditEventDialog
          key={editing.id}
          event={editing}
          isSubmitting={mutationLoading}
          onOpenChange={(open) => !open && setEditing(null)}
          onUpdate={(eid: string, payload: UpdateAdminEventRequest) =>
            runMutation(() => mutations.updateEvent(eid, payload))
          }
          onDeactivate={(eid: string) =>
            runMutation(async () => { await mutations.deactivateEvent(eid); setEditing(null); })
          }
        />
      )}
    </div>
  );
}

function EventsSkeleton() {
  return <div className="space-y-3">{[0,1,2,3,4,5].map((i) => <Skeleton key={i} className="h-14 w-full rounded-xl" />)}</div>;
}

function ForbiddenState() {
  return (
    <GlassCard className="max-w-2xl">
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <ShieldAlert className="mb-4 h-10 w-10 text-warning" />
        <h1 className="text-lg font-semibold text-foreground">Administrative access required</h1>
        <p className="mt-2 max-w-md text-sm text-muted-foreground">Events are available to authorized administrators only.</p>
      </div>
    </GlassCard>
  );
}

function ErrorState({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <GlassCard className="max-w-2xl border-red-900/50 bg-red-950/20">
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <AlertCircle className="mb-4 h-10 w-10 text-red-500" />
        <h1 className="text-lg font-semibold text-red-400">Could not load events</h1>
        {message && <p className="mt-2 max-w-md text-sm text-red-400/80">{message}</p>}
        <Button variant="outline" size="sm" className="mt-6" onClick={onRetry}>Retry</Button>
      </div>
    </GlassCard>
  );
}