"use client";

import { useState } from "react";
import { useQuizEligibility } from "@/hooks/useApi";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { EligibilityState, type CriterionResult } from "@/types/api";
import { formatDateMedium, formatPct1 } from "@/lib/date";
import { getQuizEligibilityStatus } from "@/lib/canonicalStatus";
import { AlertCircle, Calendar, ChevronDown, ChevronUp, Calculator, Check, X, Info } from "lucide-react";
import { cn } from "@/lib/utils";

// D-10 (as corrected): every quiz percentage on this card represents actual
// calculated attendance/eligibility, so all rows — including the detailed
// calculation — use the shared one-decimal formatter.
function fmtPct(value: number | null): string {
  return formatPct1(value);
}

// Presentation-only criterion titles: both criteria use the SAME pooled
// L+T count-level average — (Lecture Present + Tutorial Present) /
// (Lecture Conducted + Tutorial Conducted) × 100 — and differ only in the
// counting window, so both render as "Attendance Average". The backend-emitted
// name remains the fallback for any unrecognized title. No values or math are
// touched.
const CRITERION_TITLES: Record<string, string> = {
  "Criterion I — Lecture + Tutorial Average": "Criterion I — Attendance Average",
  "Criterion II — Lecture + Tutorial Average": "Criterion II — Attendance Average",
};

function criterionTitle(name: string | null | undefined): string {
  if (!name) return "—";
  return CRITERION_TITLES[name] ?? name;
}

function CriterionRow({
  criterion,
  passed,
  noData,
}: {
  criterion: CriterionResult | null;
  passed: boolean;
  noData: boolean;
}) {
  const opt = criterion?.optimization;
  const hasOpt =
    !!opt &&
    (opt.lecture_deficit > 0 ||
      opt.tutorial_deficit > 0 ||
      opt.safe_skip_lecture > 0 ||
      opt.safe_skip_tutorial > 0);
  // D1: only a reachable route is actionable guidance. An unreachable
  // criterion still shows its counts, percentages, threshold and explanation
  // above — only the "Must attend / Safe skip" line is withheld.
  const showGuidance = !noData && hasOpt && opt.is_reachable === true;
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">{criterionTitle(criterion?.name)}</p>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
          <span className="text-muted-foreground">
            Average: <span className="font-bold tabular-nums text-foreground">{fmtPct(criterion?.value ?? null)}</span>
          </span>
          <span className="text-muted-foreground">
            Required:{" "}
            <span className="font-bold tabular-nums text-foreground">
              {criterion?.threshold != null ? `${criterion.threshold.toFixed(0)}%` : "—"}
            </span>
          </span>
        </div>
        <p className="text-xs text-muted-foreground mt-1">{criterion?.explanation ?? "—"}</p>
        {showGuidance && (
          <p className="text-xs text-muted-foreground mt-1">
            Must attend:{" "}
            <span className="font-bold tabular-nums">
              {opt.lecture_deficit} lecture{opt.lecture_deficit === 1 ? "" : "s"}
            </span>
            {opt.tutorial_deficit > 0 && (
              <span className="font-bold tabular-nums">
                {" "}
                · {opt.tutorial_deficit} tutorial{opt.tutorial_deficit === 1 ? "" : "s"}
              </span>
            )}{" "}
            · Safe skip:{" "}
            <span className="font-bold tabular-nums">
              {opt.safe_skip_lecture} lecture{opt.safe_skip_lecture === 1 ? "" : "s"}
            </span>
            {opt.safe_skip_tutorial > 0 && (
              <span className="font-bold tabular-nums">
                {" "}
                · {opt.safe_skip_tutorial} tutorial{opt.safe_skip_tutorial === 1 ? "" : "s"}
              </span>
            )}
          </p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {noData ? (
          <Badge variant="neutral">NO DATA</Badge>
        ) : passed ? (
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

/**
 * UIA-012: one direct, always-visible action statement instead of parallel
 * criteria math the student has to reconcile. Purely a presentation layer
 * over the backend optimization object — no value is recomputed.
 */
function GuidanceCallout({
  state,
  noData,
  lectureDeficit,
  tutorialDeficit,
  safeSkipLecture,
  safeSkipTutorial,
  reachable,
  criterion,
}: {
  state: EligibilityState;
  noData: boolean;
  lectureDeficit: number;
  tutorialDeficit: number;
  safeSkipLecture: number;
  safeSkipTutorial: number;
  reachable: boolean;
  criterion: string | null | undefined;
}) {
  const route = criterion || "best route";
  const lectureWord = (n: number) => `lecture${n === 1 ? "" : "s"}`;
  const tutorialWord = (n: number) => `tutorial${n === 1 ? "" : "s"}`;

  let tone: "success" | "warning" | "danger" | "neutral";
  let message: string;

  if (noData) {
    tone = "neutral";
    message = "Attendance needs to be recorded before eligibility can be determined.";
  } else if (state === EligibilityState.ELIGIBLE && (safeSkipLecture > 0 || safeSkipTutorial > 0)) {
    tone = "success";
    const parts: string[] = [];
    if (safeSkipLecture > 0) parts.push(`${safeSkipLecture} ${lectureWord(safeSkipLecture)}`);
    if (safeSkipTutorial > 0) parts.push(`${safeSkipTutorial} ${tutorialWord(safeSkipTutorial)}`);
    message = `You can safely miss up to ${parts.join(" and ")} (${route}).`;
  } else if (state === EligibilityState.RECOVERABLE && reachable) {
    tone = "warning";
    const parts: string[] = [];
    if (lectureDeficit > 0) parts.push(`${lectureDeficit} ${lectureWord(lectureDeficit)}`);
    if (tutorialDeficit > 0) parts.push(`${tutorialDeficit} ${tutorialWord(tutorialDeficit)}`);
    message =
      parts.length > 0
        ? `You need to attend the next ${parts.join(" and ")} to qualify (${route}).`
        : `You can still reach the requirement (${route}).`;
  } else if (state === EligibilityState.NOT_ELIGIBLE) {
    tone = "danger";
    message = "The attendance requirement cannot be met within the remaining attendance window.";
  } else {
    return null;
  }

  const toneClasses: Record<typeof tone, string> = {
    success: "border-success/30 bg-success/10 text-success",
    warning: "border-warning/30 bg-warning/10 text-warning",
    danger: "border-destructive/30 bg-destructive/10 text-destructive",
    neutral: "border-border bg-muted/40 text-muted-foreground",
  };

  return (
    <p className={cn("flex items-start gap-2 rounded-lg border px-3 py-2 text-xs font-medium", toneClasses[tone])}>
      <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      {message}
    </p>
  );
}

export function QuizEligibilityCard({ subjectCode, cycle, cycleLabel }: { subjectCode: string; cycle: number; cycleLabel: string }) {
  const [showCalculation, setShowCalculation] = useState(false);
  const { eligibility, isLoading, isError, mutate } = useQuizEligibility(subjectCode, cycle);

  if (isLoading) {
    return <Card className="h-44 animate-pulse bg-muted/50" />;
  }

  if (isError || !eligibility) {
    // UIA-017: the error treatment uses semantic destructive tokens instead of
    // a raw red palette, so it can never drift from the token set.
    return (
      <Card className="border-destructive/40 bg-destructive/10 p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span className="text-sm font-medium">Could not load eligibility for {subjectCode}</span>
          </div>
          <Button variant="outline" size="sm" onClick={() => mutate()}>Retry</Button>
        </div>
      </Card>
    );
  }

  // UIA-028: zero recorded sessions is a "no data yet" state, never a FAIL —
  // the thresholds cannot be evaluated before any class is marked. This is a
  // presentation guard only; eligibility values and math stay untouched.
  const totalRecorded =
    (eligibility.lecture?.attended ?? 0) +
    (eligibility.lecture?.missed ?? 0) +
    (eligibility.tutorial?.attended ?? 0) +
    (eligibility.tutorial?.missed ?? 0);
  const noData =
    eligibility.state !== EligibilityState.UNRESOLVED && totalRecorded === 0;

  const status = getQuizEligibilityStatus(eligibility.state, noData);
  const hasTutorials = (eligibility.tutorial?.total ?? 0) > 0;
  const required = eligibility.required_percentage ?? eligibility.lecture_threshold ?? 75;

  const lectureVariant = noData
    ? "neutral"
    : eligibility.lecture_pct !== null && eligibility.lecture_pct >= required
      ? "success"
      : "warning";
  const tutorialVariant = noData
    ? "neutral"
    : eligibility.tutorial_pct !== null && eligibility.tutorial_pct >= required
      ? "success"
      : "warning";
  const averageVariant = noData
    ? "neutral"
    : eligibility.average_pct !== null && eligibility.average_pct >= required
      ? "success"
      : "warning";

  return (
    <Card className="overflow-hidden">
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
                {cycleLabel} · Quiz on {eligibility.quiz_date ? formatDateMedium(eligibility.quiz_date) : "TBD"}
              </span>
              {eligibility.state !== EligibilityState.UNRESOLVED && (
                <span className="inline-flex items-center gap-1">
                  <span className="h-1 w-1 rounded-full bg-border inline-block" />
                  Criterion I window: {eligibility.window_start ? formatDateMedium(eligibility.window_start) : "TBD"} – {eligibility.window_end ? formatDateMedium(eligibility.window_end) : "TBD"}
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
            <p className="text-xs text-warning mt-2">{eligibility.policy_ambiguity_notes}</p>
          )}
        </div>
      ) : (
        <div className="p-4 space-y-4">
          <div className="space-y-3">
            <p className="text-xs font-medium text-muted-foreground">
              Criterion I window counts
            </p>
            <div>
              <div className="flex items-baseline justify-between gap-3 text-sm mb-1.5">
                <span className="font-medium text-foreground min-w-0">
                  Lecture <span className="text-muted-foreground font-normal">· {eligibility.lecture.attended}/{eligibility.lecture.total} attended</span>
                  {eligibility.lecture.pending > 0 && (
                    <span className="text-muted-foreground font-normal"> · {eligibility.lecture.pending} pending</span>
                  )}
                </span>
                <span className="tabular-nums text-muted-foreground">{formatPct1(eligibility.lecture_pct)}</span>
              </div>
              <Progress value={eligibility.lecture_pct ?? 0} variant={lectureVariant} size="md" />
            </div>
            {hasTutorials && (
              <div>
                <div className="flex items-baseline justify-between gap-3 text-sm mb-1.5">
                  <span className="font-medium text-foreground min-w-0">
                    Tutorial <span className="text-muted-foreground font-normal">· {eligibility.tutorial.attended}/{eligibility.tutorial.total} attended</span>
                    {eligibility.tutorial.pending > 0 && (
                      <span className="text-muted-foreground font-normal"> · {eligibility.tutorial.pending} pending</span>
                    )}
                  </span>
                  <span className="tabular-nums text-muted-foreground">{formatPct1(eligibility.tutorial_pct)}</span>
                </div>
                <Progress value={eligibility.tutorial_pct ?? 0} variant={tutorialVariant} size="md" />
              </div>
            )}
            <div>
              <div className="flex items-baseline justify-between gap-3 text-sm mb-1.5">
                <span className="font-medium text-foreground min-w-0">
                  Average <span className="text-muted-foreground font-normal">· required {required.toFixed(0)}%</span>
                </span>
                <span className={cn("tabular-nums font-medium", noData ? "text-muted-foreground" : eligibility.average_pct !== null && eligibility.average_pct >= required ? "text-success" : "text-warning")}>
                  {formatPct1(eligibility.average_pct)}
                </span>
              </div>
              <Progress value={eligibility.average_pct ?? 0} variant={averageVariant} size="md" />
            </div>
          </div>

          <GuidanceCallout
            state={eligibility.state}
            noData={noData}
            lectureDeficit={eligibility.optimization?.lecture_deficit ?? 0}
            tutorialDeficit={eligibility.optimization?.tutorial_deficit ?? 0}
            safeSkipLecture={eligibility.optimization?.safe_skip_lecture ?? 0}
            safeSkipTutorial={eligibility.optimization?.safe_skip_tutorial ?? 0}
            reachable={eligibility.optimization?.is_reachable === true}
            criterion={eligibility.must_attend_criterion ?? eligibility.safe_skip_criterion}
          />

          <Button variant="outline" size="sm" onClick={() => setShowCalculation((v) => !v)} className="w-full justify-between">
            <span className="inline-flex items-center gap-1.5">
              <Calculator className="size-3.5" />
              View Calculation
            </span>
            {showCalculation ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
          </Button>

          {showCalculation && (
            <div className="rounded-lg border border-border/50 bg-muted/30 p-4 space-y-4">
              <CriterionRow criterion={eligibility.criterion_i} passed={eligibility.criterion_i?.passed ?? false} noData={noData} />
              <CriterionRow criterion={eligibility.criterion_ii} passed={eligibility.criterion_ii?.passed ?? false} noData={noData} />
              <div className="flex items-start justify-between gap-3 border-t border-border/50 pt-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground">Final Result</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{eligibility.final_criterion?.combination ?? "—"}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {noData
                      ? "No attendance recorded yet for this quiz window."
                      : eligibility.final_criterion?.explanation ?? "—"}
                  </p>
                </div>
                <Badge variant={noData ? "neutral" : eligibility.final_criterion?.passed ? "success" : "danger"}>
                  {noData ? "NO DATA YET" : eligibility.final_criterion?.passed ? "ELIGIBLE" : "NOT ELIGIBLE"}
                </Badge>
              </div>
              {!noData && eligibility.optimization && eligibility.optimization.is_reachable === true && (
                <div className="grid grid-cols-2 gap-2 border-t border-border/50 pt-3 text-xs">
                  <div className="rounded bg-muted/50 border border-border/50 px-3 py-2">
                    <p className="font-semibold text-muted-foreground text-[11px] tracking-wider uppercase mb-1">
                      Must Attend{eligibility.must_attend_criterion ? ` — ${eligibility.must_attend_criterion}` : " (best route)"}
                    </p>
                    <p className="text-foreground">Lecture: <span className="font-bold tabular-nums">{eligibility.optimization.lecture_deficit}</span></p>
                    {hasTutorials && (
                      <p className="text-foreground">Tutorial: <span className="font-bold tabular-nums">{eligibility.optimization.tutorial_deficit}</span></p>
                    )}
                  </div>
                  {eligibility.safe_skip_optimization && (
                    <div className="rounded bg-muted/50 border border-border/50 px-3 py-2">
                      <p className="font-semibold text-muted-foreground text-[11px] tracking-wider uppercase mb-1">
                        Safe Skip{eligibility.safe_skip_criterion ? ` — ${eligibility.safe_skip_criterion}` : " (best route)"}
                      </p>
                      <p className="text-foreground">Lecture: <span className="font-bold tabular-nums">{eligibility.safe_skip_optimization.safe_skip_lecture}</span></p>
                      {eligibility.safe_skip_optimization.safe_skip_tutorial > 0 && (
                        <p className="text-foreground">Tutorial: <span className="font-bold tabular-nums">{eligibility.safe_skip_optimization.safe_skip_tutorial}</span></p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {eligibility.explanation && (
            <p className="text-xs text-muted-foreground">{eligibility.explanation}</p>
          )}
        </div>
      )}
    </Card>
  );
}
