"use client";

import { useState } from "react";
import {
  FlaskConical,
  CheckCircle2,
  Clock,
  Circle,
  AlertCircle,
  CalendarDays,
  ClipboardList,
  Activity as ActivityIcon,
  Plus,
  Trash2,
  PenLine,
} from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
  useSubjects,
  useProfile,
  useLabSummary,
  useLabExperiments,
  useLabRecords,
  useLabActivity,
  useLabMutations,
} from "@/hooks/useApi";
import {
  SubjectCategory,
  SignatureStatus,
  LaboratoryExperimentResponse,
  LaboratoryRecordResponse,
  LaboratoryActivityItem,
  ClassType,
} from "@/types/api";

type Tab = "attendance" | "experiments" | "activity";

const TABS: { id: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "attendance", label: "Practical Attendance", icon: ClipboardList },
  { id: "experiments", label: "Experiments", icon: FlaskConical },
  { id: "activity", label: "Activity", icon: ActivityIcon },
];

export default function LaboratoryPage() {
  const { subjects, isLoading: subjectsLoading } = useSubjects();
  const { profile } = useProfile();
  const [subjectCode, setSubjectCode] = useState<string>("");
  const [tab, setTab] = useState<Tab>("attendance");

  const labSubjects = (subjects || []).filter(
    (s) => s.category === SubjectCategory.LAB
  );

  const resolvedCode = subjectCode || labSubjects[0]?.code || "";

  return (
    <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full">
      <PageHeader
        title="Laboratory"
        description="Practical attendance, experiment progress, and lab activity — all values are backend-derived from the canonical attendance pipeline."
      />

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <label htmlFor="lab-subject" className="text-sm font-medium text-muted-foreground">
            Subject
          </label>
          <select
            id="lab-subject"
            value={resolvedCode}
            onChange={(e) => setSubjectCode(e.target.value)}
            className="h-9 rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            {(labSubjects.length > 0 || subjectsLoading) && (
              <option value="" disabled>
                {subjectsLoading ? "Loading…" : "Select a lab subject"}
              </option>
            )}
            {labSubjects.map((s) => (
              <option key={s.id} value={s.code}>
                {s.code} — {s.name}
              </option>
            ))}
          </select>
        </div>

        <nav aria-label="Laboratory sections" className="flex overflow-x-auto gap-1 rounded-md border border-border bg-surface p-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              aria-current={tab === id ? "page" : undefined}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors shrink-0 whitespace-nowrap",
                tab === id
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </nav>
      </div>

      {resolvedCode === "" ? (
        <GlassCard className="p-8 text-center text-muted-foreground">
          No lab subjects available for your enrollment.
        </GlassCard>
      ) : (
        <>
          {tab === "attendance" && <PracticalAttendanceTab subjectCode={resolvedCode} />}
          {tab === "experiments" && (
            <ExperimentsTab subjectCode={resolvedCode} isAdmin={profile?.role === "ADMIN"} />
          )}
          {tab === "activity" && <ActivityTab subjectCode={resolvedCode} />}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 1 — Practical Attendance (canonical summary + mid-sem status)
// ---------------------------------------------------------------------------

function PracticalAttendanceTab({ subjectCode }: { subjectCode: string }) {
  const { summary, isLoading, isError } = useLabSummary(subjectCode);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full bg-surface/50" />
        <Skeleton className="h-24 w-full bg-surface/50" />
      </div>
    );
  }

  if (isError || !summary) {
    return (
      <GlassCard className="p-4 border border-red-900/50 bg-red-950/20">
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="h-4 w-4" />
          <span className="text-sm font-medium">Failed to load laboratory summary.</span>
        </div>
      </GlassCard>
    );
  }

  const pa = summary.practical_attendance;
  const ms = summary.mid_sem;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <GlassCard className="p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground">Practical Attendance</h3>
          <Badge variant="primary">{pa.total} sessions</Badge>
        </div>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-2 text-center">
          <Stat label="Attended" value={pa.attended} tone="text-emerald-400" />
          <Stat label="Missed" value={pa.missed} tone="text-red-400" />
          <Stat label="Pending" value={pa.pending} tone="text-amber-400" />
          <Stat label="Attendance" value={`${pa.current_practical_pct.toFixed(1)}%`} tone="text-foreground" />
        </div>
        <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-surface2">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${Math.min(pa.current_practical_pct, 100)}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Recorded practical attendance percentage (cancelled sessions excluded, pending not counted as absent).
        </p>
      </GlassCard>

      <GlassCard className="p-5">
        <h3 className="text-sm font-bold text-foreground">Mid-Semester Practical</h3>
        {!ms.designated ? (
          <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
            <Circle className="size-4 text-muted-foreground/50" />
            Not yet designated. An administrator marks the mid-semester practical on an actual scheduled lab session.
          </div>
        ) : (
          <div className="mt-4 space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Session</span>
              <span className="font-mono text-foreground">{ms.session_date ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Attendance</span>
              <Badge variant={ms.attendance_status === "Attended" ? "success" : ms.attendance_status === "Missed" ? "danger" : "neutral"}>
                {ms.attendance_status ?? "Not logged"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              The mid-semester practical is a real scheduled lab session; attendance against it flows through the normal attendance pipeline.
            </p>
          </div>
        )}
      </GlassCard>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number | string; tone: string }) {
  return (
    <div>
      <div className={cn("text-xl font-bold", tone)}>{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 2 — Experiments (catalog + self-tracked progress)
// ---------------------------------------------------------------------------

function ExperimentsTab({ subjectCode, isAdmin }: { subjectCode: string; isAdmin: boolean }) {
  const { summary, isLoading: summaryLoading } = useLabSummary(subjectCode);
  const { experiments, isLoading: expLoading, mutate: mutateExps } = useLabExperiments(subjectCode);
  const { records, isLoading: recLoading, mutate: mutateRecs } = useLabRecords(subjectCode);
  const mutations = useLabMutations();
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [num, setNum] = useState("");
  const [title, setTitle] = useState("");
  const [showIngest, setShowIngest] = useState(false);

  const isLoading = summaryLoading || expLoading || recLoading;
  const catalogAvailable = summary?.experiment_progress.catalog_available ?? false;

  const run = async (id: string, fn: () => Promise<unknown>) => {
    setBusyId(id);
    setError(null);
    try {
      await fn();
      await Promise.all([mutateExps(), mutateRecs()]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusyId(null);
    }
  };

  const recordFor = (expId: string) =>
    (records || []).find((r) => r.experiment_id === expId) ?? null;

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-16 w-full bg-surface/50" />
        ))}
      </div>
    );
  }

  if (!catalogAvailable) {
    return (
      <GlassCard className="p-8 text-center">
        <FlaskConical className="mx-auto size-8 text-muted-foreground/50" aria-hidden="true" />
        <h3 className="mt-3 font-bold text-foreground">Experiment curriculum not yet available</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          No experiment catalog has been published for {subjectCode} yet. Progress is shown as soon as the curriculum is available.
        </p>
      </GlassCard>
    );
  }

  const handleIngest = async () => {
    const n = parseInt(num, 10);
    if (!Number.isFinite(n) || n < 1) return;
    await run(`ingest-${n}`, () =>
      mutations.createExperiment(subjectCode, { experiment_number: n, title: title.trim() || null })
    );
    setNum("");
    setTitle("");
    setShowIngest(false);
  };

  return (
    <div className="space-y-4">
      {error && (
        <GlassCard className="p-3 border border-red-900/50 bg-red-950/20">
          <div className="flex items-center gap-2 text-sm text-red-400">
            <AlertCircle className="size-4" />
            {error}
          </div>
        </GlassCard>
      )}

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {summary?.experiment_progress.advisory}
        </p>
        {isAdmin && (
          <Button variant="outline" size="sm" onClick={() => setShowIngest((v) => !v)}>
            <Plus className="size-4" aria-hidden="true" /> Add experiment
          </Button>
        )}
      </div>

      {isAdmin && showIngest && (
        <GlassCard className="p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <div className="flex-1">
              <label htmlFor="exp-num" className="text-xs text-muted-foreground">
                Experiment number
              </label>
              <Input
                id="exp-num"
                type="number"
                min={1}
                value={num}
                onChange={(e) => setNum(e.target.value)}
                placeholder="1"
                className="mt-1"
              />
            </div>
            <div className="flex-1">
              <label htmlFor="exp-title" className="text-xs text-muted-foreground">
                Title
              </label>
              <Input
                id="exp-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Optional title"
                className="mt-1"
              />
            </div>
            <Button onClick={handleIngest} disabled={busyId !== null || num.trim() === ""}>
              Ingest
            </Button>
          </div>
        </GlassCard>
      )}

      <GlassCard className="overflow-hidden">
        <div className="divide-y divide-border/50">
          {(experiments || []).map((exp) => (
            <ExperimentRow
              key={exp.id}
              exp={exp}
              record={recordFor(exp.id)}
              isAdmin={isAdmin}
              busyId={busyId}
              onTrack={() =>
                run(exp.id, () =>
                  mutations.createRecord(subjectCode, { experiment_id: exp.id })
                )
              }
              onDelete={() => run(exp.id, () => mutations.deleteRecord(subjectCode, recordFor(exp.id)!.id))}
              onSign={() =>
                run(exp.id, () =>
                  mutations.updateRecord(subjectCode, recordFor(exp.id)!.id, {
                    signature_status: SignatureStatus.SIGNED,
                  })
                )
              }
              onDeactivate={() => run(exp.id, () => mutations.deleteExperiment(subjectCode, exp.id))}
            />
          ))}
        </div>
      </GlassCard>
    </div>
  );
}

function ExperimentRow({
  exp,
  record,
  isAdmin,
  busyId,
  onTrack,
  onDelete,
  onSign,
  onDeactivate,
}: {
  exp: LaboratoryExperimentResponse;
  record: LaboratoryRecordResponse | null;
  isAdmin: boolean;
  busyId: string | null;
  onTrack: () => void;
  onDelete: () => void;
  onSign: () => void;
  onDeactivate: () => void;
}) {
  const busy = busyId === exp.id;

  let statusIcon = <Circle className="size-4 text-muted-foreground/50" />;
  let statusText = "Not tracked";
  let statusTone = "text-muted-foreground";

  if (record?.signature_status === SignatureStatus.SIGNED) {
    statusIcon = <CheckCircle2 className="size-4 text-emerald-400" />;
    statusText = "Signed";
    statusTone = "text-emerald-400";
  } else if (record?.signature_status === SignatureStatus.PENDING) {
    statusIcon = <Clock className="size-4 text-amber-400" />;
    statusText = "Pending";
    statusTone = "text-amber-400";
  }

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 hover:bg-surface2/30 transition-colors">
      <div className="flex items-center gap-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded bg-surface2 border border-border/50 text-sm font-bold text-muted-foreground">
          {exp.experiment_number}
        </div>
        <div className="min-w-0">
          <h4 className="truncate text-sm font-semibold text-foreground">
            {exp.title ?? `Experiment ${exp.experiment_number}`}
          </h4>
          {exp.description && (
            <p className="truncate text-xs text-muted-foreground">{exp.description}</p>
          )}
          {record?.date_conducted && (
            <p className="text-xs text-muted-foreground">
              Conducted {formatDate(record.date_conducted)}
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap shrink-0 items-center gap-2 self-start sm:self-auto">
        <span className={cn("flex items-center gap-1.5 text-sm font-medium", statusTone)}>
          {statusIcon}
          <span className="hidden sm:inline">{statusText}</span>
        </span>
        {busy ? (
          <span className="text-xs text-muted-foreground">…</span>
        ) : !record ? (
          <Button size="sm" variant="outline" onClick={onTrack}>
            Track
          </Button>
        ) : record.signature_status === SignatureStatus.PENDING ? (
          <div className="flex items-center gap-1">
            {isAdmin && (
              <Button size="sm" variant="outline" onClick={onSign}>
                <PenLine className="size-3.5" aria-hidden="true" /> Sign
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={onDelete} aria-label="Delete record">
              <Trash2 className="size-4 text-muted-foreground" />
            </Button>
          </div>
        ) : (
          isAdmin && (
            <Button size="sm" variant="ghost" onClick={onDeactivate} aria-label="Deactivate experiment">
              <Trash2 className="size-4 text-muted-foreground" />
            </Button>
          )
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab 3 — Activity (truthful chronological lab sessions)
// ---------------------------------------------------------------------------

function ActivityTab({ subjectCode }: { subjectCode: string }) {
  const { activity, isLoading, isError } = useLabActivity(subjectCode);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-16 w-full bg-surface/50" />
        ))}
      </div>
    );
  }

  if (isError || !activity) {
    return (
      <GlassCard className="p-4 border border-red-900/50 bg-red-950/20">
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="h-4 w-4" />
          <span className="text-sm font-medium">Failed to load laboratory activity.</span>
        </div>
      </GlassCard>
    );
  }

  if (activity.items.length === 0) {
    return (
      <GlassCard className="p-8 text-center text-muted-foreground">
        <CalendarDays className="mx-auto size-8 text-muted-foreground/50" aria-hidden="true" />
        <p className="mt-2 text-sm">No practical sessions scheduled yet for {subjectCode}.</p>
      </GlassCard>
    );
  }

  return (
    <div className="space-y-2">
      {activity.items.map((item) => (
        <ActivityRow key={item.id} item={item} />
      ))}
    </div>
  );
}

function ActivityRow({ item }: { item: LaboratoryActivityItem }) {
  const status = item.attendance_status;
  const experiments = item.experiments || [];

  return (
    <GlassCard className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm text-foreground">{item.date}</span>
        <Badge variant={item.class_type === ClassType.PRACTICAL ? "primary" : "outline"}>
          {item.class_type === ClassType.PRACTICAL ? "Practical" : item.class_type}
        </Badge>
        {item.is_extra && <Badge variant="warning">Extra</Badge>}
        {item.is_cancelled ? (
          <Badge variant="danger">Cancelled</Badge>
        ) : status ? (
          <Badge
            variant={status === "Attended" ? "success" : status === "Missed" ? "danger" : "neutral"}
          >
            {status}
          </Badge>
        ) : (
          <Badge variant="neutral">Not logged</Badge>
        )}
        {item.designation === "MID_SEM_PRACTICAL" && <Badge variant="primary">Mid-Sem</Badge>}
      </div>

      {experiments.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {experiments.map((rec) => (
            <Badge
              key={rec.id}
              variant={rec.signature_status === SignatureStatus.SIGNED ? "success" : "warning"}
            >
              Experiment record —{" "}
              {rec.signature_status === SignatureStatus.SIGNED ? "Signed" : "Pending"}
            </Badge>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">
          Practical session — no experiment recorded.
        </p>
      )}
    </GlassCard>
  );
}

function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}