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
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/feedback/ConfirmDialog";
import { useToast } from "@/components/feedback/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { formatDateMedium, formatPct1 } from "@/lib/date";
import { classTypeLabel, getSessionStatus } from "@/lib/canonicalStatus";
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
  LaboratorySummary,
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
    <div className="flex-1 py-8 w-full">
      <PageHeader
        title="Lab Experiments"
        description="Practical attendance, experiment progress, and lab activity for your lab subjects."
      />

      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <label htmlFor="lab-subject" className="text-sm font-medium text-muted-foreground">
            Subject
          </label>
          <Select
            id="lab-subject"
            value={resolvedCode}
            onChange={(e) => setSubjectCode(e.target.value)}
            className="w-auto"
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
          </Select>
        </div>

        {/* UI-033: these buttons switch in-page section content (they are
            not links and not route navigation), so the link-only aria-current
            state is replaced by aria-pressed on native buttons inside a named
            group. Section rendering and the subject selector are unchanged. */}
        <div role="group" aria-label="Laboratory sections" className="flex overflow-x-auto gap-1 rounded-md border border-border bg-muted p-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              aria-pressed={tab === id}
              className={cn(
                "flex h-10 sm:h-8 items-center gap-1.5 rounded-md px-3 text-sm font-medium transition-colors shrink-0 whitespace-nowrap outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
                tab === id
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {resolvedCode === "" ? (
        <EmptyState
          icon={<FlaskConical className="h-10 w-10 text-muted-foreground mb-4" />}
          title="No lab subjects available"
          message="No lab subjects are available for your enrollment."
        />
      ) : (
        <>
          {tab === "attendance" && (
            <PracticalAttendanceTab
              subjectCode={resolvedCode}
              onViewExperiments={() => setTab("experiments")}
            />
          )}
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

function PracticalAttendanceTab({
  subjectCode,
  onViewExperiments,
}: {
  subjectCode: string;
  onViewExperiments: () => void;
}) {
  const { summary, isLoading, isError, mutate } = useLabSummary(subjectCode);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full bg-muted/50" />
        <Skeleton className="h-24 w-full bg-muted/50" />
        <Skeleton className="h-20 w-full bg-muted/50" />
      </div>
    );
  }

  if (isError || !summary) {
    return (
      <ErrorState
        title="Failed to load laboratory summary"
        message="The laboratory summary for this subject could not be fetched. Check your connection and try again."
        onRetry={() => mutate()}
      />
    );
  }

  const pa = summary.practical_attendance;
  const ms = summary.mid_sem;
  // D-07: "Attended"/"Missed" are the backend's lab-domain data values —
  // getSessionStatus normalizes them to the canonical Present/Absent
  // vocabulary (including the not-yet-logged → Pending fallback).
  const msStatus = getSessionStatus(ms.attendance_status);

  return (
    // UIA-043: the default tab now carries the backend-provided experiment
    // progress as a third, full-width block — denser at desktop without
    // inventing a single new value or fixed height.
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="p-5">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground">Practical Attendance</h3>
          <Badge variant="primary">{pa.total} sessions</Badge>
        </div>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-2 text-center">
          <Stat label="Present" value={pa.attended} tone="text-success" />
          <Stat label="Absent" value={pa.missed} tone="text-destructive" />
          <Stat label="Pending" value={pa.pending} tone="text-warning" />
          <Stat label="Attendance" value={formatPct1(pa.current_practical_pct)} tone="text-foreground" />
        </div>
        {/* UIA-018: shared Progress primitive (size lg = former 8px bar). */}
        <Progress
          className="mt-4"
          value={Math.min(100, Math.max(0, pa.current_practical_pct))}
          variant="default"
          size="lg"
        />
        <p className="mt-2 text-xs text-muted-foreground">
          Recorded practical attendance percentage (cancelled sessions excluded, pending not counted as absent).
        </p>
      </Card>

      <Card className="p-5">
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
              <span className="font-mono text-foreground">
                {ms.session_date ? formatDateMedium(ms.session_date) : "—"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Attendance</span>
              <Badge variant={msStatus.variant}>{msStatus.label}</Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              The mid-semester practical is a real scheduled lab session; attendance against it flows through the normal attendance pipeline.
            </p>
          </div>
        )}
      </Card>

      <ExperimentProgressCard
        className="lg:col-span-2"
        progress={summary.experiment_progress}
        onViewExperiments={onViewExperiments}
      />
    </div>
  );
}

// UIA-043: backend-provided experiment progress, surfaced on the default tab
// so the lab page reads as a working page instead of a sparse card pair. No
// value is computed beyond the signed/total fill ratio for the bar.
function ExperimentProgressCard({
  progress,
  onViewExperiments,
  className,
}: {
  progress: LaboratorySummary["experiment_progress"];
  onViewExperiments: () => void;
  className?: string;
}) {
  const { catalog_available, total, signed, pending_self_tracked, advisory } = progress;
  const pct = total > 0 ? (signed / total) * 100 : 0;

  return (
    <Card className={cn("p-5", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-foreground">Experiment Progress</h3>
        {catalog_available && total > 0 && (
          <Badge variant="neutral">
            {signed} of {total} signed off
          </Badge>
        )}
      </div>

      {!catalog_available ? (
        <p className="mt-3 text-sm text-muted-foreground">
          No experiment catalog has been published for this subject yet.
          Progress appears here as soon as it is available.
        </p>
      ) : (
        <>
          <Progress
            className="mt-4"
            value={pct}
            variant={signed >= total && total > 0 ? "success" : "default"}
            size="md"
          />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>{advisory ?? `${signed} of ${total} experiments completed.`}</span>
            {pending_self_tracked > 0 && (
              <span>{pending_self_tracked} awaiting sign-off</span>
            )}
          </div>
          <Button variant="outline" size="sm" className="mt-4" onClick={onViewExperiments}>
            <FlaskConical className="size-4" aria-hidden="true" />
            View experiments
          </Button>
        </>
      )}
    </Card>
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
  // UI-015 / D-11: destructive actions confirm before mutating; this holds
  // the action awaiting confirmation (null = dialog closed).
  const [confirmAction, setConfirmAction] = useState<{
    kind: "delete" | "deactivate";
    exp: LaboratoryExperimentResponse;
  } | null>(null);
  const { toast } = useToast();

  const isLoading = summaryLoading || expLoading || recLoading;
  const catalogAvailable = summary?.experiment_progress.catalog_available ?? false;

  // Returns whether the mutation succeeded so callers can give honest
  // feedback; failures stay in the inline error banner above the list.
  const run = async (id: string, fn: () => Promise<unknown>) => {
    setBusyId(id);
    setError(null);
    try {
      await fn();
      await Promise.all([mutateExps(), mutateRecs()]);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      return false;
    } finally {
      setBusyId(null);
    }
  };

  const handleConfirmAction = async () => {
    if (!confirmAction) return;
    const { kind, exp } = confirmAction;
    if (kind === "delete") {
      const record = recordFor(exp.id);
      if (!record) return;
      const ok = await run(exp.id, () =>
        mutations.deleteRecord(subjectCode, record.id)
      );
      if (ok) toast({ variant: "success", title: "Record deleted" });
    } else {
      const ok = await run(exp.id, () =>
        mutations.deleteExperiment(subjectCode, exp.id)
      );
      if (ok) toast({ variant: "success", title: "Experiment deactivated" });
    }
  };

  const recordFor = (expId: string) =>
    (records || []).find((r) => r.experiment_id === expId) ?? null;

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-16 w-full bg-muted/50" />
        ))}
      </div>
    );
  }

  if (!catalogAvailable) {
    return (
      <EmptyState
        icon={<FlaskConical className="h-10 w-10 text-muted-foreground mb-4" />}
        title="Experiment curriculum not yet available"
        message={`No experiment catalog has been published for ${subjectCode} yet. Progress is shown as soon as the curriculum is available.`}
      />
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
        <Card className="p-3 border border-destructive/30 bg-destructive/10">
          <div className="flex items-center gap-2 text-sm text-destructive">
            <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
            {error}
          </div>
        </Card>
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
        <Card className="p-4">
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
              Add
            </Button>
          </div>
        </Card>
      )}

      <Card className="overflow-hidden">
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
              onDelete={() => setConfirmAction({ kind: "delete", exp })}
              onSign={() =>
                run(exp.id, () =>
                  mutations.updateRecord(subjectCode, recordFor(exp.id)!.id, {
                    signature_status: SignatureStatus.SIGNED,
                  })
                )
              }
              onDeactivate={() => setConfirmAction({ kind: "deactivate", exp })}
            />
          ))}
        </div>
      </Card>

      {/* UI-015 / D-11: destructive actions require explicit confirmation.
          The dialog stays open and locks its controls until the mutation
          settles; failures surface in the inline error banner above. */}
      <ConfirmDialog
        open={confirmAction !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmAction(null);
        }}
        title={
          confirmAction?.kind === "deactivate"
            ? "Deactivate this experiment?"
            : "Delete this record?"
        }
        description={
          confirmAction?.kind === "deactivate"
            ? `Experiment ${confirmAction.exp.experiment_number}${
                confirmAction.exp.title ? ` — ${confirmAction.exp.title}` : ""
              } for ${subjectCode} will be deactivated and removed from the experiment list.`
            : `Your tracking record for Experiment ${confirmAction?.exp.experiment_number ?? ""} in ${subjectCode} will be removed. You can track it again later.`
        }
        confirmLabel={confirmAction?.kind === "deactivate" ? "Deactivate" : "Delete"}
        variant="destructive"
        onConfirm={handleConfirmAction}
      />
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

  // Status colors come from the semantic tokens (success/warning), never the
  // raw palette; the text is always visible so mobile never relies on the
  // icon (color/shape) alone (25.UX-1).
  let statusIcon = <Circle className="size-4 text-muted-foreground/50" aria-hidden="true" />;
  let statusText = "Not tracked";
  let statusTone = "text-muted-foreground";

  if (record?.signature_status === SignatureStatus.SIGNED) {
    statusIcon = <CheckCircle2 className="size-4 text-success" aria-hidden="true" />;
    statusText = "Signed";
    statusTone = "text-success";
  } else if (record?.signature_status === SignatureStatus.PENDING) {
    statusIcon = <Clock className="size-4 text-warning" aria-hidden="true" />;
    statusText = "Pending";
    statusTone = "text-warning";
  }

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 hover:bg-muted/30 transition-colors">
      <div className="flex items-center gap-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded bg-muted border border-border/50 text-sm font-bold text-muted-foreground">
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
              Conducted {formatDateMedium(record.date_conducted)}
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap shrink-0 items-center gap-2 self-start sm:self-auto">
        <span className={cn("flex items-center gap-1.5 text-sm font-medium", statusTone)}>
          {statusIcon}
          <span>{statusText}</span>
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
  const { activity, isLoading, isError, mutate } = useLabActivity(subjectCode);

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-16 w-full bg-muted/50" />
        ))}
      </div>
    );
  }

  if (isError || !activity) {
    return (
      <ErrorState
        title="Failed to load laboratory activity"
        message="The laboratory activity for this subject could not be fetched. Check your connection and try again."
        onRetry={() => mutate()}
      />
    );
  }

  if (activity.items.length === 0) {
    return (
      <EmptyState
        icon={<CalendarDays className="h-10 w-10 text-muted-foreground mb-4" />}
        title="No practical sessions yet"
        message={`No practical sessions are scheduled for ${subjectCode} yet.`}
      />
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
  // Canonical 4-state session vocabulary; is_cancelled wins per the canonical
  // normalization order. D-07: "Attended"/"Missed" remain the backend data
  // values — display maps through getSessionStatus.
  const status = getSessionStatus(item.attendance_status, item.is_cancelled);
  const typeLabel = classTypeLabel(item.class_type) ?? item.class_type;
  const experiments = item.experiments || [];

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm text-foreground">
          {formatDateMedium(item.date)}
        </span>
        <Badge variant={item.class_type === ClassType.PRACTICAL ? "primary" : "outline"}>
          {typeLabel}
        </Badge>
        {item.is_extra && <Badge variant="warning">Extra</Badge>}
        <Badge variant={status.variant}>{status.label}</Badge>
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
    </Card>
  );
}

// D-09 note: date display uses the shared formatDateMedium (local calendar
// parsing); the former local en-US helper was removed with Phase 7.