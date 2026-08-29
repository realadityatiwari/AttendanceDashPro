"use client";

import { useState, useMemo } from "react";
import { AlertCircle, CalendarDays, Clock, Copy, Plus, ShieldAlert, Square } from "lucide-react";

import {
  useAdminMe,
  useAdminTimetableEntries,
  useAdminTimetableMutations,
  useAdminSessions,
  useAdminSemesters,
  useAdminSections,
  useAdminSubjects,
} from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  TimetableEntryAdminResponse,
  CreateTimetableEntryRequest,
  UpdateTimetableEntryRequest,
  DuplicateTimetableEntryRequest,
  ClassType,
  ElectiveSlot,
} from "@/types/api";
import { CreateTimetableEntryDialog } from "./components/CreateTimetableEntryDialog";
import { EditTimetableEntryDialog } from "./components/EditTimetableEntryDialog";
import { DuplicateTimetableEntryDialog } from "./components/DuplicateTimetableEntryDialog";
import { DeactivateTimetableEntryDialog } from "./components/DeactivateTimetableEntryDialog";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const CLASS_TYPE_COLORS: Record<string, "neutral" | "primary" | "secondary" | "outline" | "warning"> = {
  [ClassType.LECTURE]: "primary",
  [ClassType.TUTORIAL]: "neutral",
  [ClassType.PRACTICAL]: "secondary",
};

/**
 * Phase 24.7-D — Admin Timetable Builder.
 *
 * Read scope is resolved SERVER-SIDE (GET /api/v1/admin/timetable): HEAD all,
 * CLASS assigned sections, SUBSECTION assigned subsections' sections,
 * ELECTIVE exact concrete subject. Write actions (create/edit/deactivate/
 * duplicate) are gated by the BACKEND to HEAD_ADMIN + CLASS_ADMIN (assigned
 * section); the buttons are hidden for others as presentation only — the
 * backend is the security boundary. Conflict detection is authoritative on
 * the server; the frontend only does lightweight UX checks (required fields,
 * end-before-start).
 */
export default function TimetablePage() {
  const { identity } = useAdminMe();
  const isGlobal = identity?.is_global ?? false;
  const roles = identity?.roles ?? [];
  const canWrite = isGlobal || roles.includes("CLASS_ADMIN");

  // Academic hierarchy selectors (HEAD only — structure hooks are HEAD-gated).
  const { sessions } = useAdminSessions();
  const [sessionId, setSessionId] = useState("");
  const { semesters } = useAdminSemesters(sessionId || null);
  const [semesterId, setSemesterId] = useState("");
  const { sections } = useAdminSections(semesterId || null);
  const [sectionId, setSectionId] = useState("");
  const { subjects } = useAdminSubjects();

  const [dayFilter, setDayFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [subjectFilter, setSubjectFilter] = useState("");
  const [elecFilter, setElecFilter] = useState("");

  const params = useMemo(() => {
    const p: Record<string, string> = {};
    if (sectionId) p.section_id = sectionId;
    if (dayFilter) p.day_of_week = dayFilter;
    if (activeFilter === "active") p.is_active = "true";
    if (activeFilter === "inactive") p.is_active = "false";
    if (subjectFilter) p.subject_id = subjectFilter;
    if (elecFilter) p.elective_slot = elecFilter;
    return p;
  }, [sectionId, dayFilter, activeFilter, subjectFilter, elecFilter]);

  const { entries, isLoading, isError, mutate } = useAdminTimetableEntries(params);
  const mutations = useAdminTimetableMutations();
  const status = (isError as Error & { status?: number } | null)?.status;

  // Dialog state
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<TimetableEntryAdminResponse | null>(null);
  const [duplicating, setDuplicating] = useState<TimetableEntryAdminResponse | null>(null);
  const [deactivating, setDeactivating] = useState<TimetableEntryAdminResponse | null>(null);
  const [mutationLoading, setMutationLoading] = useState(false);

  const byDay = useMemo(() => {
    if (!entries) return [];
    const groups: { day: number; label: string; entries: TimetableEntryAdminResponse[] }[] = [];
    for (let d = 0; d <= 6; d++) {
      const e = entries
        .filter((x) => x.day_of_week === d)
        .sort((a, b) => (a.start_time > b.start_time ? 1 : -1));
      if (e.length > 0) {
        groups.push({ day: d, label: DAY_LABELS[d], entries: e });
      }
    }
    return groups;
  }, [entries]);

  // Server-derived sections visible to the acting admin (from the scoped
  // timetable list) — used to populate the create form for scoped admins who
  // cannot call the HEAD-gated structure endpoints.
  const scopedSections = useMemo(() => {
    if (!entries) return [];
    const seen = new Map<string, string>();
    for (const e of entries) {
      if (!seen.has(e.section_id)) seen.set(e.section_id, e.section_name);
    }
    return Array.from(seen.entries()).map(([id, name]) => ({ id, name }));
  }, [entries]);

  const runMutation = async (fn: () => Promise<unknown>) => {
    setMutationLoading(true);
    try {
      await fn();
      // Revalidate the authoritative query AFTER a successful backend accept;
      // never invent the resulting row and never keep stale optimistic state
      // from a failed mutation.
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
        title="Timetable"
        description="Weekly academic schedule. The timetable is the EXPECTED schedule (per Section, optionally per Subsection), distinct from actual class-session occurrences. Conflicts are detected and rejected by the backend."
      >
        {canWrite && (
          <Button size="sm" className="gap-2" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            Add Entry
          </Button>
        )}
      </PageHeader>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap gap-3">
        {isGlobal && (
          <>
            <div className="w-48">
              <label className="mb-1 block text-xs text-muted-foreground" htmlFor="tt-session">Session</label>
              <select id="tt-session" className={selectClass} value={sessionId} onChange={(e) => { setSessionId(e.target.value); setSemesterId(""); setSectionId(""); }}>
                <option value="">All sessions</option>
                {(sessions ?? []).map((s) => (
                  <option key={s.id} value={s.id}>{s.name}{s.is_active ? " (active)" : ""}</option>
                ))}
              </select>
            </div>
            <div className="w-48">
              <label className="mb-1 block text-xs text-muted-foreground" htmlFor="tt-semester">Semester</label>
              <select id="tt-semester" className={selectClass} value={semesterId} onChange={(e) => { setSemesterId(e.target.value); setSectionId(""); }} disabled={!sessionId}>
                <option value="">All semesters</option>
                {(semesters ?? []).map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
            <div className="w-48">
              <label className="mb-1 block text-xs text-muted-foreground" htmlFor="tt-section">Section</label>
              <select id="tt-section" className={selectClass} value={sectionId} onChange={(e) => setSectionId(e.target.value)} disabled={!semesterId}>
                <option value="">All sections</option>
                {(sections ?? []).map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
          </>
        )}
        <div className="w-40">
          <label className="mb-1 block text-xs text-muted-foreground" htmlFor="tt-day">Day</label>
          <select id="tt-day" className={selectClass} value={dayFilter} onChange={(e) => setDayFilter(e.target.value)}>
            <option value="">All days</option>
            {DAY_LABELS.map((l, i) => (
              <option key={i} value={i}>{l}</option>
            ))}
          </select>
        </div>
        <div className="w-40">
          <label className="mb-1 block text-xs text-muted-foreground" htmlFor="tt-state">State</label>
          <select id="tt-state" className={selectClass} value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)}>
            <option value="">Active entries</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
        </div>
        <div className="w-48">
          <label className="mb-1 block text-xs text-muted-foreground" htmlFor="tt-subject">Subject</label>
          <select id="tt-subject" className={selectClass} value={subjectFilter} onChange={(e) => setSubjectFilter(e.target.value)}>
            <option value="">All subjects</option>
            {(subjects?.items ?? []).map((s) => (
              <option key={s.id} value={s.id}>{s.code}</option>
            ))}
          </select>
        </div>
        <div className="w-40">
          <label className="mb-1 block text-xs text-muted-foreground" htmlFor="tt-elec">Elective slot</label>
          <select id="tt-elec" className={selectClass} value={elecFilter} onChange={(e) => setElecFilter(e.target.value)}>
            <option value="">All</option>
            <option value="ELECTIVE_I">Elective-I</option>
            <option value="ELECTIVE_II">Elective-II</option>
          </select>
        </div>
      </div>

      {/* Content */}
      {isLoading && !entries ? (
        <TimetableSkeleton />
      ) : isError ? (
        status === 403 ? (
          <ForbiddenState />
        ) : (
          <ErrorState message={(isError as Error).message} onRetry={() => mutate()} />
        )
      ) : !entries || entries.length === 0 ? (
        <EmptyState
          title="No timetable entries in your scope"
          message="No timetable entries match your current filters or administrative scope."
          icon={<CalendarDays className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
          {byDay.map((group) => (
            <div key={group.day}>
              <h3 className="mb-2 text-sm font-semibold text-foreground">{group.label}</h3>
              <div className="space-y-2">
                {group.entries.map((entry) => (
                  <EntryCard
                    key={entry.id}
                    entry={entry}
                    canWrite={canWrite}
                    onEdit={() => setEditing(entry)}
                    onDeactivate={() => setDeactivating(entry)}
                    onDuplicate={() => setDuplicating(entry)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Dialogs — presentation only; the backend is the security boundary */}
      {canWrite && (
        <CreateTimetableEntryDialog
          key={createOpen ? 'create-open' : 'create-closed'}
          open={createOpen}
          isGlobal={isGlobal}
          scopedSections={scopedSections}
          isSubmitting={mutationLoading}
          onOpenChange={setCreateOpen}
          onCreate={(payload: CreateTimetableEntryRequest) =>
            runMutation(() => mutations.createEntry(payload))
          }
        />
      )}

      {editing && canWrite && (
        <EditTimetableEntryDialog
          key={editing.id}
          entry={editing}
          isGlobal={isGlobal}
          isSubmitting={mutationLoading}
          onOpenChange={(open) => !open && setEditing(null)}
          onUpdate={(entryId: string, payload: UpdateTimetableEntryRequest) =>
            runMutation(() => mutations.updateEntry(entryId, payload))
          }
        />
      )}

      {duplicating && canWrite && (
        <DuplicateTimetableEntryDialog
          key={duplicating.id}
          entry={duplicating}
          isSubmitting={mutationLoading}
          onOpenChange={(open) => !open && setDuplicating(null)}
          onDuplicate={(entryId: string, payload: DuplicateTimetableEntryRequest) =>
            runMutation(async () => {
              await mutations.duplicateEntry(entryId, payload);
              setDuplicating(null);
            })
          }
        />
      )}

      {deactivating && canWrite && (
        <DeactivateTimetableEntryDialog
          key={deactivating.id}
          entry={deactivating}
          isSubmitting={mutationLoading}
          onOpenChange={(open) => !open && setDeactivating(null)}
          onDeactivate={(entryId: string) =>
            runMutation(async () => {
              await mutations.deactivateEntry(entryId);
              setDeactivating(null);
            })
          }
        />
      )}
    </div>
  );
}

function EntryCard({
  entry,
  canWrite,
  onEdit,
  onDeactivate,
  onDuplicate,
}: {
  entry: TimetableEntryAdminResponse;
  canWrite: boolean;
  onEdit: () => void;
  onDeactivate: () => void;
  onDuplicate: () => void;
}) {
  const slotLabel =
    entry.elective_slot === ElectiveSlot.ELECTIVE_I ? "EI"
    : entry.elective_slot === ElectiveSlot.ELECTIVE_II ? "EII"
    : null;
  const ctColor = CLASS_TYPE_COLORS[entry.class_type] ?? "outline";

  // Time bar: approximate position within an 08:00–18:00 window (10 h = 600 min).
  const dayStart = 8 * 60; // 08:00 in minutes
  const dayEnd = 18 * 60; // 18:00 in minutes
  const daySpan = dayEnd - dayStart;
  const parseMin = (t: string) => {
    const p = t.split(":").map(Number);
    return p[0] * 60 + (p[1] ?? 0);
  };
  const startMin = parseMin(entry.start_time) - dayStart;
  const endMin = parseMin(entry.end_time) - dayStart;
  const topPct = Math.max(0, (startMin / daySpan) * 100);
  const heightPct = Math.max(3, ((endMin - startMin) / daySpan) * 100);

  return (
    <div className="relative pl-3">
      {/* Time bar — visual indicator of the entry's time position within the
          08:00–18:00 day window. Overlapping entries are immediately visible
          because their bars occupy the same vertical region. */}
      <div
        className="absolute left-0 top-0 w-1.5 rounded-full bg-primary/30"
        style={{ top: `${topPct}%`, height: `${heightPct}%`, minHeight: "6px" }}
        aria-hidden="true"
      />
      <GlassCard className="p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span>{entry.start_time.slice(0, 5)}–{entry.end_time.slice(0, 5)}</span>
          </div>
          <p className="mt-1 truncate text-sm font-medium leading-tight text-foreground" title={`${entry.subject_code} — ${entry.subject_name}`}>
            {entry.subject_code}
          </p>
          <p className="truncate text-xs text-muted-foreground">{entry.subject_name}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            <Badge variant={ctColor} className="px-1.5 py-0 text-[10px]">
              {entry.class_type === ClassType.LECTURE ? "L" : entry.class_type === ClassType.TUTORIAL ? "T" : "P"}
            </Badge>
            {slotLabel && <Badge variant="primary" className="px-1.5 py-0 text-[10px]">{slotLabel}</Badge>}
            {entry.room && <span className="text-[10px] text-muted-foreground">@{entry.room}</span>}
          </div>
          {entry.subsection_name && (
            <p className="mt-1 text-[10px] text-muted-foreground">Sub: {entry.subsection_name}</p>
          )}
        </div>
        {!entry.is_active && (
          <Badge variant="outline" className="shrink-0 text-[10px]">Inactive</Badge>
        )}
      </div>
      {canWrite && (
        <div className="mt-2 flex gap-2 border-t border-border pt-2">
          <button
            type="button"
            onClick={onEdit}
            className="text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            Edit
          </button>
          <button
            type="button"
            onClick={onDuplicate}
            className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <Copy className="h-3 w-3" />
            Duplicate
          </button>
          <button
            type="button"
            onClick={onDeactivate}
            className="ml-auto flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-destructive"
          >
            <Square className="h-3 w-3" />
            Deactivate
          </button>
        </div>
      )}
    </GlassCard>
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
          The timetable is available to authorized administrators only.
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
        <h1 className="text-lg font-semibold text-red-400">Could not load the timetable</h1>
        {message && <p className="mt-2 max-w-md text-sm text-red-400/80">{message}</p>}
        <Button variant="outline" size="sm" className="mt-6" onClick={onRetry}>Retry</Button>
      </div>
    </GlassCard>
  );
}

function TimetableSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
      {[0, 1, 2, 3, 4].map((d) => (
        <div key={d}>
          <Skeleton className="mb-2 h-5 w-16 rounded-md" />
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-28 w-full rounded-xl" />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}