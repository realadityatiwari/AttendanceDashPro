"use client";

import { useState } from "react";
import { useQuizEligibility } from "@/hooks/useApi";
import { GlassCard } from "@/components/shared/GlassCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { EligibilityState, type CriterionResult } from "@/types/api";
import { AlertCircle, Calendar, ChevronDown, ChevronUp, Calculator, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";

const STATE_BADGE: Record<EligibilityState, { label: string; variant: "success" | "warning" | "danger" | "neutral" }> = {
  [EligibilityState.ELIGIBLE]: { label: "Eligible", variant: "success" },
  [EligibilityState.RECOVERABLE]: { label: "Recoverable", variant: "warning" },
  [EligibilityState.NOT_ELIGIBLE]: { label: "Not Eligible", variant: "danger" },
  [EligibilityState.UNRESOLVED]: { label: "Unresolved", variant: "neutral" },
};

function fmtPct(value: number | null): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)}%`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "TBD";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(`${iso}T00:00:00`));
}

function CriterionRow({ criterion, passed }: { criterion: CriterionResult | null; passed: boolean }) {
  const opt = criterion?.optimization;
  const hasOpt = !!opt && (opt.lecture_deficit > 0 || opt.tutorial_deficit > 0 || opt.safe_skip_lecture > 0 || opt.safe_skip_tutorial > 0);
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">{criterion?.name ?? "—"}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
          <span className="text-muted-foreground">
            Average: <span className="font-bold tabular-nums text-foreground">{fmtPct(criterion?.value ?? null)}</span>
          </span>
          <span className="text-muted-foreground">
            Required: <span className="font-bold tabular-nums text-foreground">
              {criterion?.threshold != null ? `${criterion.threshold.toFixed(0)}%` : "—"}
            </span>
          </span>
          <span className="text-muted-foreground">
            Formula: <span className="text-foreground">(Lecture % + Tutorial %) / 2</span>
          </span>
        </div>
        <p className="text-xs text-muted-foreground mt-1">{criterion?.explanation ?? "—"}</p>
        {hasOpt && (
          <p className="text-xs text-muted-foreground mt-1">
            Must attend: <span className="font-bold tabular-nums">{opt.lecture_deficit} lecture{opt.lecture_deficit === 1 ? "" : "s"}</span>
            {opt.tutorial_deficit > 0 && <span className="font-bold tabular-nums"> · {opt.tutorial_deficit} tutorial{opt.tutorial_deficit === 1 ? "" : "s"}</span>}
            {" "}· Safe skip: <span className="font-bold tabular-nums">{opt.safe_skip_lecture} lecture{opt.safe_skip_lecture === 1 ? "" : "s"}</span>
            {opt.safe_skip_tutorial > 0 && <span className="font-bold tabular-nums"> · {opt.safe_skip_tutorial} tutorial{opt.safe_skip_tutorial === 1 ? "" : "s"}</span>}
          </p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {passed ? (
          <Badge variant="success">
            <Check className="size-3" /> PASS
          </Badge>
        ) : (
          <Badge variant="danger">
            <X className="size-3" /> FAIL
          </Badge>
        )}
      </div>
    </div>
  );
}

export function QuizEligibilityCard({ subjectCode, cycle, cycleLabel }: { subjectCode: string; cycle: number; cycleLabel: string }) {
  const [showCalculation, setShowCalculation] = useState(false);
  const { eligibility, isLoading, isError, mutate } = useQuizEligibility(subjectCode, cycle);

  if (isLoading) {
    return <GlassCard className="h-44 animate-pulse bg-surface/50" />;
  }

  if (isError || !eligibility) {
    return (
      <GlassCard className="p-4 border border-red-900/50 bg-red-950/20">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="text-sm font-medium">Could not load eligibility for {subjectCode}</span>
          </div>
          <Button variant="outline" size="xs" onClick={() => mutate()}>Retry</Button>
        </div>
      </GlassCard>
    );
  }

  const status = STATE_BADGE[eligibility.state];
  const hasTutorials = (eligibility.tutorial?.total ?? 0) > 0;
  const required = eligibility.required_percentage ?? eligibility.lecture_threshold ?? 75;

  const lectureVariant = eligibility.lecture_pct !== null && eligibility.lecture_pct >= required ? "success" : "warning";
  const tutorialVariant = eligibility.tutorial_pct !== null && eligibility.tutorial_pct >= required ? "success" : "warning";
  const averageVariant = eligibility.average_pct !== null && eligibility.average_pct >= required ? "success" : "warning";

  return (
    <GlassCard className="overflow-hidden">
      <div className="p-4 border-b border-border/50">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-bold text-foreground font-mono text-sm tracking-tight">{eligibility.subject_code}</h3>
              <Badge variant="primary">THEORY</Badge>
              {eligibility.subject_name && <span className="text-sm text-muted-foreground truncate">{eligibility.subject_name}</span>}
            </div>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5" />
                {cycleLabel} · Quiz on {fmtDate(eligibility.quiz_date)}
              </span>
              {eligibility.state !== EligibilityState.UNRESOLVED && (
                <span className="inline-flex items-center gap-1">
                  <span className="h-1 w-1 rounded-full bg-border inline-block" />
                  Criterion I window: {fmtDate(eligibility.window_start)} – {fmtDate(eligibility.window_end)}
                </span>
              )}
            </div>
          </div>
          <Badge variant={status.variant}>{status.label}</Badge>
        </div>
      </div>

      {eligibility.state === EligibilityState.UNRESOLVED ? (
        <div className="p-4">
          <p className="text-sm text-muted-foreground">{eligibility.explanation ?? "No confirmed schedule for this cycle yet."}</p>
          {eligibility.policy_ambiguity_notes && (
            <p className="text-xs text-amber-400 mt-2">{eligibility.policy_ambiguity_notes}</p>
          )}
        </div>
      ) : (
        <>
          <div className="p-4 space-y-4">
            <div className="space-y-3">
              <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                Criterion I window counts · Average = (Lecture % + Tutorial %) / 2
              </p>
              <div>
                <div className="flex items-baseline justify-between text-sm mb-1.5">
                  <span className="font-medium text-foreground">
                    Lecture <span className="text-muted-foreground font-normal">· {eligibility.lecture.attended}/{eligibility.lecture.total} attended</span>
                    {eligibility.lecture.pending > 0 && (
                      <span className="text-muted-foreground font-normal"> · {eligibility.lecture.pending} pending</span>
                    )}
                  </span>
                  <span className="tabular-nums text-muted-foreground">{fmtPct(eligibility.lecture_pct)}</span>
                </div>
                <Progress value={eligibility.lecture_pct ?? 0} variant={lectureVariant} className="[&_[data-slot=progress-track]]:h-1.5" />
              </div>
              {hasTutorials && (
                <div>
                  <div className="flex items-baseline justify-between text-sm mb-1.5">
                    <span className="font-medium text-foreground">
                      Tutorial <span className="text-muted-foreground font-normal">· {eligibility.tutorial.attended}/{eligibility.tutorial.total} attended</span>
                      {eligibility.tutorial.pending > 0 && (
                        <span className="text-muted-foreground font-normal"> · {eligibility.tutorial.pending} pending</span>
                      )}
                    </span>
                    <span className="tabular-nums text-muted-foreground">{fmtPct(eligibility.tutorial_pct)}</span>
                  </div>
                  <Progress value={eligibility.tutorial_pct ?? 0} variant={tutorialVariant} className="[&_[data-slot=progress-track]]:h-1.5" />
                </div>
              )}
              <div>
                <div className="flex items-baseline justify-between text-sm mb-1.5">
                  <span className="font-medium text-foreground">
                    Average <span className="text-muted-foreground font-normal">· required {required.toFixed(0)}%</span>
                  </span>
                  <span className={cn("tabular-nums font-medium", eligibility.average_pct !== null && eligibility.average_pct >= required ? "text-success" : "text-warning")}>
                    {fmtPct(eligibility.average_pct)}
                  </span>
                </div>
                <Progress value={eligibility.average_pct ?? 0} variant={averageVariant} className="[&_[data-slot=progress-track]]:h-1.5" />
              </div>
            </div>

            <Button variant="outline" size="sm" onClick={() => setShowCalculation((v) => !v)} className="w-full justify-between">
              <span className="inline-flex items-center gap-1.5">
                <Calculator className="size-3.5" />
                View Calculation
              </span>
              {showCalculation ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            </Button>

            {showCalculation && (
              <div className="rounded-lg border border-border/50 bg-surface2/30 p-4 space-y-4">
                <CriterionRow criterion={eligibility.criterion_i} passed={eligibility.criterion_i?.passed ?? false} />
                <CriterionRow criterion={eligibility.criterion_ii} passed={eligibility.criterion_ii?.passed ?? false} />
                <div className="flex items-start justify-between gap-3 border-t border-border/50 pt-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground">Final Result</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{eligibility.final_criterion?.combination ?? "—"}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{eligibility.final_criterion?.explanation ?? "—"}</p>
                  </div>
                  <Badge variant={eligibility.final_criterion?.passed ? "success" : "danger"}>
                    {eligibility.final_criterion?.passed ? "ELIGIBLE" : "NOT ELIGIBLE"}
                  </Badge>
                </div>
                {eligibility.optimization && (
                  <div className="grid grid-cols-2 gap-2 border-t border-border/50 pt-3 text-xs">
                    <div className="rounded bg-surface2/50 border border-border/50 px-3 py-2">
                      <p className="font-semibold text-muted-foreground text-[10px] tracking-wider uppercase mb-1">Must Attend <span className="font-normal normal-case tracking-normal">(best route)</span></p>
                      <p className="text-foreground">Lecture: <span className="font-bold tabular-nums">{eligibility.optimization.lecture_deficit}</span></p>
                      {hasTutorials && (
                        <p className="text-foreground">Tutorial: <span className="font-bold tabular-nums">{eligibility.optimization.tutorial_deficit}</span></p>
                      )}
                    </div>
                    <div className="rounded bg-surface2/50 border border-border/50 px-3 py-2">
                      <p className="font-semibold text-muted-foreground text-[10px] tracking-wider uppercase mb-1">Safe Skip <span className="font-normal normal-case tracking-normal">(best route)</span></p>
                      <p className="text-foreground">Lecture: <span className="font-bold tabular-nums">{eligibility.optimization.safe_skip_lecture}</span></p>
                      {hasTutorials && (
                        <p className="text-foreground">Tutorial: <span className="font-bold tabular-nums">{eligibility.optimization.safe_skip_tutorial}</span></p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {eligibility.explanation && (
              <p className="text-xs text-muted-foreground">{eligibility.explanation}</p>
            )}
          </div>
        </>
      )}
    </GlassCard>
  );
}