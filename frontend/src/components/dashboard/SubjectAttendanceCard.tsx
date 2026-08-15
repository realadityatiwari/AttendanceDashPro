"use client";

import { useState } from "react";
import { useQuizEligibility, useCurrentQuizCycle } from "@/hooks/useApi";
import { SubjectResponse, AnalyticsSubjectItem } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { CheckCircle2, ChevronDown, ChevronUp, XCircle, Calculator, Target } from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_BADGE: Record<string, { label: string; variant: "success" | "warning" | "danger" } | null> = {
  SAFE: { label: "Safe", variant: "success" },
  WATCH: { label: "Watch", variant: "warning" },
  CRITICAL: { label: "Critical", variant: "danger" },
};

function fmtPct(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}%`;
}

function fmtInt(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(0)}%`;
}

/**
 * Attendance subject card (reference UI — attendance spec).
 *
 * Every number is a backend field from the Phase 8.1 analytics read model:
 *   - primary %: combined average (Lecture + Tutorial) / 2 for theory subjects,
 *     practical % for lab-only subjects;
 *   - lecture/tutorial: current % · attended/total · required · must-attend
 *     (optimization.*_deficit) · safe-skip (optimization.safe_skip_*);
 *   - status: the canonical SAFE/WATCH/CRITICAL band emitted by the backend.
 * React only formats and expands/collapses — no attendance mathematics here.
 */
export function SubjectAttendanceCard({ subject, summary }: SubjectAttendanceCardProps) {
  // Canonical date-aware quiz cycle (Phase 7.2): the backend answers which
  // cycle is currently relevant — no hardcoded cycle, no client-side schedule
  // logic. While it loads, the eligibility query stays disabled.
  const { currentCycle } = useCurrentQuizCycle();
  const cycle = currentCycle?.quiz_cycle ?? null;
  const { eligibility, isError: eligError } = useQuizEligibility(
    subject.quiz_applicable ? subject.code : null,
    cycle
  );
  const [showDetails, setShowDetails] = useState(false);

  const isLabOnly = !subject.quiz_applicable;
  const hasTutorials = (summary?.tutorial.total ?? 0) > 0;
  const hasPractical = (summary?.practical.total ?? 0) > 0;

  // PRIMARY: theory subjects headline the combined average (the spec's subject
  // formula); lab-only subjects headline the practical percentage.
  const primaryPct = isLabOnly ? summary?.current_practical_pct ?? null : summary?.current_avg_pct ?? null;
  const primaryCounts = isLabOnly ? summary?.practical : summary?.lecture;

  const status = summary?.status ?? null;
  const statusBadge = status ? STATUS_BADGE[status] : null;
  const required = summary?.required_pct ?? 75;
  const optimization = summary?.optimization ?? null;
  const isEligible = subject.quiz_applicable && eligibility?.is_eligible === true;

  const progressVariant =
    status === "SAFE" ? "success" : status === "WATCH" ? "warning" : status === "CRITICAL" ? "danger" : "default";

  return (
    <Card className="bg-surface border-border overflow-hidden hover:border-border/80 transition-colors flex flex-col">
      {/* Header: code · type · name · current status */}
      <CardHeader className="pb-2 pt-4 px-4 bg-surface/50 border-b border-border/30">
        <div className="flex justify-between items-start gap-2">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="font-mono text-sm font-bold tracking-tight text-foreground">
                {subject.code}
              </CardTitle>
              <Badge variant={isLabOnly ? "neutral" : "primary"} className="uppercase text-[10px] tracking-wider px-2 py-0 h-5">
                {isLabOnly ? "LAB" : "THEORY"}
              </Badge>
              {subject.quiz_applicable && eligibility && !eligError && (
                <Badge
                  className={`uppercase text-[10px] tracking-wider px-2 py-0 h-5 flex items-center gap-1 ${
                    isEligible
                      ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/20"
                      : "bg-red-500/15 text-red-400 border-red-500/20"
                  }`}
                >
                  {isEligible ? (
                    <CheckCircle2 size={14} className="text-emerald-400" />
                  ) : (
                    <XCircle size={14} className="text-red-400" />
                  )}
                  {isEligible ? "Eligible" : "Defaulter"}
                </Badge>
              )}
            </div>
            <div className="text-xs text-muted-foreground truncate mt-1" title={subject.name}>
              {subject.name}
            </div>
          </div>
          {statusBadge && <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>}
        </div>
      </CardHeader>

      <CardContent className="p-4 flex-1 flex flex-col gap-4">
        {/* Primary attendance */}
        <div>
          <div className="flex items-end justify-between">
            <div>
              <div className="text-3xl font-bold tracking-tight text-foreground tabular-nums">
                {fmtPct(primaryPct)}
              </div>
              <div className="text-[10px] text-muted-foreground uppercase tracking-wide mt-0.5">
                {isLabOnly ? "Practical Attendance" : "Average Attendance"}
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-semibold text-foreground tabular-nums">
                {primaryCounts?.attended ?? 0} / {primaryCounts?.total ?? 0}
              </div>
              <div className="text-[10px] text-muted-foreground uppercase tracking-wide mt-0.5">
                {isLabOnly ? "Prac Attended" : "Lecture Attended"}
              </div>
            </div>
          </div>
          <div className="h-1.5 w-full bg-surface2 rounded-full overflow-hidden mt-3">
            <div
              className={cn(
                "h-full rounded-full",
                progressVariant === "success" && "bg-success",
                progressVariant === "warning" && "bg-warning",
                progressVariant === "danger" && "bg-destructive",
                progressVariant === "default" && "bg-accent"
              )}
              style={{ width: `${primaryPct !== null ? Math.min(100, Math.max(0, primaryPct)) : 0}%` }}
            />
          </div>
        </div>

        {/* Theory: lecture / tutorial / combined sections (backend values) */}
        {!isLabOnly && (
          <>
            <Section
              label="Lecture"
              pct={summary?.current_lecture_pct ?? null}
              counts={summary?.lecture}
              required={required}
              optimization={optimization ? { deficit: optimization.lecture_deficit, safeSkip: optimization.safe_skip_lecture } : null}
              align="left"
            />
            {hasTutorials && (
              <Section
                label="Tutorial"
                pct={summary?.current_tutorial_pct ?? null}
                counts={summary?.tutorial}
                required={required}
                optimization={optimization ? { deficit: optimization.tutorial_deficit, safeSkip: optimization.safe_skip_tutorial } : null}
                align="right"
              />
            )}
            <div className="border-t border-border/30 pt-3">
              <div className="flex items-baseline justify-between text-sm">
                <span className="font-medium text-foreground">Combined Average</span>
                <span className="tabular-nums font-semibold text-foreground">{fmtPct(summary?.current_avg_pct ?? null)}</span>
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">
                {hasTutorials
                  ? "Average = (Lecture % + Tutorial %) / 2"
                  : "No tutorials — subject average equals Lecture %"}
              </p>
            </div>
          </>
        )}

        {/* Lab / practical-only: practical section in the same dense language */}
        {isLabOnly && hasPractical && (
          <div className="border-t border-border/30 pt-3">
            <div className="flex items-baseline justify-between text-sm">
              <span className="font-medium text-foreground">
                Practical{" "}
                <span className="text-muted-foreground font-normal">
                  · {summary?.practical.attended ?? 0}/{summary?.practical.total ?? 0} attended
                  {summary && summary.practical.pending > 0 ? ` · ${summary.practical.pending} pending` : ""}
                </span>
              </span>
              <span className="tabular-nums text-muted-foreground">{fmtPct(summary?.current_practical_pct ?? null)}</span>
            </div>
            <Progress value={summary?.current_practical_pct ?? 0} variant={progressVariant} className="mt-2 [&_[data-slot=progress-track]]:h-1.5" />
          </div>
        )}

        {/* Expandable calculation / forecast details — real backend values only */}
        <Button variant="outline" size="sm" onClick={() => setShowDetails(v => !v)} className="w-full justify-between mt-auto">
          <span className="inline-flex items-center gap-1.5">
            <Calculator className="size-3.5" />
            View Details
          </span>
          {showDetails ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
        </Button>

        {showDetails && (
          <div className="rounded-lg border border-border/50 bg-surface2/30 p-4 space-y-4 text-xs">
            {/* Current vs forecast per class type */}
            <div className="space-y-2">
              <p className="font-semibold text-muted-foreground text-[10px] tracking-wider uppercase">Current vs Forecast</p>
              <DetailRow label="Lecture" current={summary?.current_lecture_pct ?? null} forecast={summary?.forecast_lecture_pct ?? null} counts={summary?.lecture} />
              {hasTutorials && (
                <DetailRow label="Tutorial" current={summary?.current_tutorial_pct ?? null} forecast={summary?.forecast_tutorial_pct ?? null} counts={summary?.tutorial} />
              )}
              {hasPractical && (
                <DetailRow label="Practical" current={summary?.current_practical_pct ?? null} forecast={summary?.forecast_practical_pct ?? null} counts={summary?.practical} />
              )}
              {!isLabOnly && (
                <DetailRow label="Average" current={summary?.current_avg_pct ?? null} forecast={summary?.forecast_avg_pct ?? null} counts={null} />
              )}
            </div>

            {/* Optimizer: must-attend / safe-skip (backend optimization result) */}
            {optimization && !isLabOnly && (
              <div className="grid grid-cols-2 gap-2 border-t border-border/50 pt-3">
                <div className="rounded bg-surface2/50 border border-border/50 px-3 py-2">
                  <p className="font-semibold text-muted-foreground text-[10px] tracking-wider uppercase mb-1">Must Attend</p>
                  <p className="text-foreground">Lecture: <span className="font-bold tabular-nums">{optimization.lecture_deficit}</span></p>
                  {hasTutorials && (
                    <p className="text-foreground">Tutorial: <span className="font-bold tabular-nums">{optimization.tutorial_deficit}</span></p>
                  )}
                  {!optimization.is_reachable && <p className="text-[10px] text-warning mt-1">Target unreachable</p>}
                </div>
                <div className="rounded bg-surface2/50 border border-border/50 px-3 py-2">
                  <p className="font-semibold text-muted-foreground text-[10px] tracking-wider uppercase mb-1">Safe Skip</p>
                  <p className="text-foreground">Lecture: <span className="font-bold tabular-nums">{optimization.safe_skip_lecture}</span></p>
                  {hasTutorials && (
                    <p className="text-foreground">Tutorial: <span className="font-bold tabular-nums">{optimization.safe_skip_tutorial}</span></p>
                  )}
                </div>
              </div>
            )}

            {/* Formula / pending note */}
            <p className="border-t border-border/50 pt-3 text-muted-foreground">
              {isLabOnly
                ? "Current % is recorded-only (pending never treated as absent); forecast assumes pending classes are attended."
                : `Current % is recorded-only (pending never treated as absent); forecast assumes pending classes are attended. Required attendance for the optimizer is ${required.toFixed(0)}%.`}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface SubjectAttendanceCardProps {
  subject: SubjectResponse;
  // Backend-derived analytics (Phase 8.1 read model, delivered via the
  // analytics overview). The card renders these values and never recomputes
  // percentages, must-attend, or safe-skip client-side.
  summary: AnalyticsSubjectItem | null;
}

function Section({
  label,
  pct,
  counts,
  required,
  optimization,
  align,
}: {
  label: string;
  pct: number | null;
  counts: { total: number; attended: number; pending: number } | undefined;
  required: number;
  optimization: { deficit: number; safeSkip: number } | null;
  align: "left" | "right";
}) {
  return (
    <div className={cn("flex flex-col", align === "right" && "text-right")}>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-medium text-foreground">{label}</span>
        <span className="tabular-nums font-semibold text-foreground">{fmtInt(pct)}</span>
      </div>
      <p className="text-[11px] text-muted-foreground mt-0.5">
        {counts?.attended ?? 0}/{counts?.total ?? 0} attended
        {counts && counts.pending > 0 ? ` · ${counts.pending} pending` : ""} · Current {fmtInt(pct)} · Required{" "}
        {required.toFixed(0)}%
      </p>
      {optimization && (
        <p className={cn("text-[11px] mt-1 text-text2 flex items-center gap-1", align === "right" && "justify-end")}>
          <Target size={10} className="shrink-0" />
          <span>
            Must attend <span className="font-bold tabular-nums">{optimization.deficit}</span> · Safe skip{" "}
            <span className="font-bold tabular-nums">{optimization.safeSkip}</span>
          </span>
        </p>
      )}
    </div>
  );
}

function DetailRow({
  label,
  current,
  forecast,
  counts,
}: {
  label: string;
  current: number | null;
  forecast: number | null;
  counts: { total: number; attended: number; pending: number } | null | undefined;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-foreground">
        {label}
        {counts && (
          <span className="text-muted-foreground">
            {" "}
            · {counts.attended}/{counts.total} attended{counts.pending > 0 ? ` · ${counts.pending} pending` : ""}
          </span>
        )}
      </span>
      <span className="tabular-nums text-muted-foreground shrink-0">
        {fmtPct(current)} → {fmtPct(forecast)}
      </span>
    </div>
  );
}
