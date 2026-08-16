"use client";

import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useAnalyticsOverview } from "@/hooks/useApi";
import { OverallAnalytics, WeeklyAnalyticsItem, AnalyticsSubjectItem } from "@/types/api";
import { formatPct } from "@/lib/date";
import { cn } from "@/lib/utils";
import { TrendingUp } from "lucide-react";

/**
 * Attendance Analytics (Phase 8.3 — dedicated surface; roadmap T-3).
 *
 * This page is a PURE RENDERER of the canonical Phase 8.1 analytics read model
 * (GET /api/v1/analytics/overview). Every number — overall current/forecast,
 * weekly series, per-subject current/forecast/practical percentages, the 75%
 * must-attend/safe-skip optimizer, and the risk/health classifications — is a
 * backend field derived from the attendance engine and the canonical
 * class_sessions + attendance_records pipeline. React formats and maps colors
 * only; it never computes attendance, averages, forecasts, banding, or
 * eligibility.
 *
 * Risk-state presentation (canonical, never re-banded here):
 *   - Overall aggregate uses the frozen 3-state `overall.status`
 *     (SAFE | WATCH | CRITICAL | null) — the dashboard/analytics classification.
 *   - Each subject uses the Phase 8.2 `health` classification
 *     (HEALTHY | WATCH | AT_RISK | CRITICAL | null) — the Attendance Health
 *     taxonomy. Both are emitted by the backend; no second threshold set exists.
 */

const OVERALL_STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  SAFE: "success",
  WATCH: "warning",
  CRITICAL: "danger",
};

const HEALTH_VARIANT: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  HEALTHY: "success",
  WATCH: "warning",
  AT_RISK: "danger",
  CRITICAL: "danger",
};

const HEALTH_LABEL: Record<string, string> = {
  HEALTHY: "Healthy",
  WATCH: "Watch",
  AT_RISK: "At Risk",
  CRITICAL: "Critical",
};

function fmtPct(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}%`;
}

function fmtWeek(value: string): string {
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export default function AnalyticsPage() {
  const { overview, isLoading, isError } = useAnalyticsOverview();

  if (isError) {
    return (
      <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full">
        <PageHeader
          title="Attendance Analytics"
          description="Your overall, weekly, and subject-level attendance intelligence."
        />
        <ErrorState
          title="Failed to load analytics"
          message="The analytics read model could not be retrieved from the server."
        />
      </div>
    );
  }

  return (
    <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full">
      <PageHeader
        title="Attendance Analytics"
        description="A read-only view of your attendance intelligence — overall standing, the semester trend, and a subject-by-subject breakdown. All values are computed by the backend from your actual recorded attendance."
      />

      {isLoading || !overview ? (
        <AnalyticsSkeleton />
      ) : (
        <div className="space-y-6">
          <OverallCard overall={overview.overall} />
          <TrendCard weekly={overview.weekly} />
          <SubjectsCard subjects={overview.subjects} />
        </div>
      )}
    </div>
  );
}

function OverallCard({ overall }: { overall: OverallAnalytics }) {
  const statusVariant = overall.status ? OVERALL_STATUS_VARIANT[overall.status] ?? "neutral" : "neutral";
  const progressVariant =
    overall.status === "SAFE" ? "success" : overall.status === "WATCH" ? "warning" : "danger";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>Overall Attendance</CardTitle>
          <Badge variant={statusVariant}>{overall.status ?? "N/A"}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="text-3xl font-bold tabular-nums tracking-tight text-foreground">
              {formatPct(overall.current_pct)}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {overall.attended} attended · {overall.recorded} recorded
              {overall.pending > 0 && ` · ${overall.pending} pending`}
              {overall.cancelled > 0 && ` · ${overall.cancelled} cancelled`}
            </p>
            {overall.forecast_pct !== null && (
              <p className="mt-1 text-xs text-muted-foreground">
                Forecast {formatPct(overall.forecast_pct)}
                <span className="text-text2"> if all pending attended</span>
              </p>
            )}
          </div>
        </div>
        <div className="mt-4 h-1.5 w-full rounded-full bg-muted overflow-hidden">
          <div
            className={cn(
              "h-full rounded-full",
              progressVariant === "success" && "bg-success",
              progressVariant === "warning" && "bg-warning",
              progressVariant === "danger" && "bg-destructive"
            )}
            style={{ width: `${overall.current_pct !== null ? Math.min(100, Math.max(0, overall.current_pct)) : 0}%` }}
          />
        </div>
        <p className="mt-3 text-[11px] text-muted-foreground">
          Current percentage is recorded-only — pending sessions are never treated as absent. Overall
          status uses the canonical SAFE / WATCH / CRITICAL classification.
        </p>
      </CardContent>
    </Card>
  );
}

function TrendCard({ weekly }: { weekly: WeeklyAnalyticsItem[] }) {
  const recordedWeeks = weekly.filter((w) => w.recorded > 0);
  const hasAny = recordedWeeks.length > 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <TrendingUp className="size-4 text-muted-foreground" aria-hidden="true" />
          <CardTitle>Semester Trend</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {!hasAny ? (
          <div className="py-6 text-center">
            <p className="text-xs text-muted-foreground">
              No recorded attendance yet — the trend appears once classes are marked.
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {weekly.map((week) => {
              const pct = week.current_pct;
              const isGap = pct === null;
              return (
                <li key={week.week_start} className="flex items-center gap-3">
                  <span className="w-20 shrink-0 text-xs font-medium text-foreground tabular-nums">
                    {fmtWeek(week.week_start)}
                  </span>
                  <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-full rounded-full",
                        isGap
                          ? "bg-muted"
                          : pct >= 80
                            ? "bg-success"
                            : pct >= 60
                              ? "bg-warning"
                              : "bg-destructive"
                      )}
                      style={{ width: isGap ? "0%" : `${Math.min(100, pct as number)}%` }}
                    />
                  </div>
                  <span className="w-12 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                    {isGap ? "—" : `${Math.round(pct as number)}%`}
                  </span>
                  <span className="w-16 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                    {week.attended}/{week.recorded}
                    {week.pending > 0 ? ` · ${week.pending}p` : ""}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <p className="mt-4 border-t border-border/60 pt-3 text-[11px] text-muted-foreground">
          Monday-start weeks of the semester. A dash means nothing was recorded that week — it is a
          gap, never 0%. Values are backend-derived from the weekly read model.
        </p>
      </CardContent>
    </Card>
  );
}

function SubjectsCard({ subjects }: { subjects: AnalyticsSubjectItem[] }) {
  if (subjects.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Subject-wise Attendance</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="py-6 text-center">
            <p className="text-xs text-muted-foreground">
              No attendance-applicable subjects found for your enrollment.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Subject-wise Attendance</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {subjects.map((subject) => (
            <SubjectRow key={subject.subject_code} subject={subject} />
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function SubjectRow({ subject }: { subject: AnalyticsSubjectItem }) {
  // Lab-only subjects have practical sessions and no lecture/tutorial counts
  // (data-driven from the canonical summary counts, matching the Attendance
  // page's LAB badge semantics).
  const isLabOnly =
    subject.lecture.total === 0 && subject.tutorial.total === 0 && subject.practical.total > 0;
  const primaryPct = isLabOnly ? subject.current_practical_pct : subject.current_avg_pct;
  const health = subject.health;
  const healthVariant = health ? HEALTH_VARIANT[health] ?? "neutral" : "neutral";

  const optimization = subject.optimization;
  const mustAttend =
    optimization && optimization.is_reachable
      ? optimization.lecture_deficit + optimization.tutorial_deficit
      : null;
  const safeSkip =
    optimization && optimization.is_reachable
      ? optimization.safe_skip_lecture + optimization.safe_skip_tutorial
      : null;
  const unreachable = optimization ? !optimization.is_reachable : null;

  return (
    <li className="rounded-lg border border-border/40 bg-muted/30 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-sm font-bold tracking-tight text-foreground">
              {subject.subject_code}
            </span>
            <Badge variant={isLabOnly ? "neutral" : "primary"} className="uppercase text-[10px] tracking-wider px-2 py-0 h-5">
              {isLabOnly ? "LAB" : "THEORY"}
            </Badge>
            {health && (
              <Badge variant={healthVariant} className="uppercase text-[10px] tracking-wider px-2 py-0 h-5">
                {HEALTH_LABEL[health] ?? health}
              </Badge>
            )}
          </div>
          <div className="mt-1 text-xs text-muted-foreground truncate max-w-md" title={subject.subject_name ?? undefined}>
            {subject.subject_name ?? subject.subject_code}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-xl font-bold tabular-nums tracking-tight text-foreground leading-none">
            {fmtPct(primaryPct)}
          </div>
          <div className="mt-1 text-[10px] uppercase tracking-wide text-muted-foreground">
            {isLabOnly ? "Practical" : "Overall"}
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
        {!isLabOnly && (
          <MiniStat
            label="Lecture"
            pct={subject.current_lecture_pct}
            counts={subject.lecture}
          />
        )}
        {!isLabOnly && subject.tutorial.total > 0 && (
          <MiniStat
            label="Tutorial"
            pct={subject.current_tutorial_pct}
            counts={subject.tutorial}
          />
        )}
        {subject.practical.total > 0 && (
          <MiniStat
            label="Practical"
            pct={subject.current_practical_pct}
            counts={subject.practical}
          />
        )}
        {!isLabOnly && subject.tutorial.total === 0 && (
          <p className="flex items-center rounded-md border border-border/40 bg-muted/40 px-2.5 py-1.5 text-[11px] text-muted-foreground sm:col-span-2">
            No tutorials — subject average equals Lecture %
          </p>
        )}
      </div>

      {/* Subject-level 75% optimizer (backend `optimization` fields only). */}
      <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        {unreachable ? (
          <span>
            <span className="text-destructive">Not reachable</span> — 75% cannot be met from remaining
            pending sessions.
          </span>
        ) : (
          <>
            {mustAttend !== null && mustAttend > 0 && (
              <span>
                Must attend <span className="font-medium text-foreground tabular-nums">{mustAttend}</span> more
                {optimization && optimization.tutorial_deficit > 0
                  ? " (incl. tutorials)"
                  : ""} to reach 75%
              </span>
            )}
            {mustAttend !== null && mustAttend === 0 && (
              <span className="text-success">Already at or above 75%</span>
            )}
            {safeSkip !== null && safeSkip > 0 && (
              <span>
                Can safely skip <span className="font-medium text-foreground tabular-nums">{safeSkip}</span>{" "}
                more session{safeSkip === 1 ? "" : "s"}
              </span>
            )}
          </>
        )}
      </div>
    </li>
  );
}

function MiniStat({
  label,
  pct,
  counts,
}: {
  label: string;
  pct: number | null;
  counts: { total: number; attended: number } | undefined;
}) {
  return (
    <div className="rounded-md border border-border/40 bg-muted/40 px-2.5 py-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">{label}</span>
        <span className="tabular-nums font-semibold text-foreground text-sm leading-none">{fmtPct(pct)}</span>
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground tabular-nums">
        {counts?.attended ?? 0}/{counts?.total ?? 0} attended
      </p>
    </div>
  );
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-44" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-9 w-28" />
          <Skeleton className="mt-3 h-2 w-full" />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-36" />
        </CardHeader>
        <CardContent>
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="mb-2 h-5 w-full" />
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-44" />
        </CardHeader>
        <CardContent>
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="mb-2 h-16 w-full" />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
