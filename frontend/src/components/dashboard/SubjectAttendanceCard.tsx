"use client";

import { useState } from "react";
import { SubjectResponse, AnalyticsSubjectItem } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatDateMedium, formatPct, formatPct1 } from "@/lib/date";
import { ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";

// Attendance Health (Phase 8.2) — the backend emits the classification
// (`summary.health`); React only maps it to existing semantic tokens:
//   HEALTHY  -> success (green)
//   WATCH    -> warning (amber)
//   AT_RISK  -> danger (soft red)
//   CRITICAL -> danger (solid red)
// No new color system is invented; banding never happens in React.
const HEALTH_BADGE: Record<string, { label: string; variant: "success" | "warning" | "danger"; solid?: boolean }> = {
  HEALTHY: { label: "Healthy", variant: "success" },
  WATCH: { label: "Watch", variant: "warning" },
  AT_RISK: { label: "At Risk", variant: "danger" },
  CRITICAL: { label: "Critical", variant: "danger", solid: true },
};

const HEALTH_PROGRESS: Record<string, "success" | "warning" | "danger" | "default"> = {
  HEALTHY: "success",
  WATCH: "warning",
  AT_RISK: "danger",
  CRITICAL: "danger",
};

// D-10 (as corrected): calculated attendance keeps one decimal (72.2%).
// Whole-number contexts use the shared formatPct. No local helpers remain.

/**
 * Attendance subject card (Phase 8.2 — attendance monitoring only).
 *
 * This card answers "how is my attendance going in this subject?" and nothing
 * else. Quiz strategy (must-attend, safe-skip, forecast, current-vs-forecast,
 * quiz-window denominators, required 75%, eligibility badge) is deliberately
 * absent — those concepts belong to the Quiz Eligibility surface and stay in
 * its engine/API.
 *
 * Every number is a backend field from the canonical attendance pipeline
 * (analytics read model / subject summary). React formats, expands/collapses,
 * and maps backend health to tokens — it never computes attendance, averages,
 * banding, or mid-sem state.
 */
export function SubjectAttendanceCard({ subject, summary }: SubjectAttendanceCardProps) {
  const [showDetails, setShowDetails] = useState(false);

  // Theory subjects headline the combined average (the spec formula);
  // lab-only subjects headline practical attendance.
  const isLabOnly = !subject.quiz_applicable;
  const hasTutorials = (summary?.tutorial.total ?? 0) > 0;

  const primaryPct = isLabOnly ? summary?.current_practical_pct ?? null : summary?.current_avg_pct ?? null;
  const health = summary?.health ?? null;
  const healthBadge = health ? HEALTH_BADGE[health] : null;
  const progressVariant = health ? HEALTH_PROGRESS[health] : "default";

  return (
    <Card className="bg-card border-border overflow-hidden hover:border-border/80 transition-colors flex flex-col">
      {/* Header: code · type · name + Attendance Health */}
      <CardHeader className="pb-2 pt-3.5 px-4 flex flex-row items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle className="font-mono text-sm font-bold tracking-tight text-foreground">
              {subject.code}
            </CardTitle>
            <Badge variant={isLabOnly ? "neutral" : "primary"} className="uppercase text-[11px] tracking-wider px-2 py-0 h-5">
              {isLabOnly ? "LAB" : "THEORY"}
            </Badge>
          </div>
          <div className="text-xs text-muted-foreground truncate mt-1 max-w-56 sm:max-w-none" title={subject.name}>
            {subject.name}
          </div>
        </div>
        {healthBadge && (
          <Badge
            variant={healthBadge.variant}
            className={cn("uppercase text-[11px] tracking-wider px-2 py-0 h-5 shrink-0", healthBadge.solid && "bg-destructive text-destructive-foreground border-destructive")}
          >
            {healthBadge.label}
          </Badge>
        )}
      </CardHeader>

      <CardContent className="p-4 pt-1 flex-1 flex flex-col gap-3">
        {/* Main: large overall percentage */}
        <div>
            <div className="flex items-end justify-between gap-3">
              <div className="text-3xl font-bold tracking-tight text-foreground tabular-nums leading-none">
                {formatPct1(primaryPct)}
              </div>
            <div className="text-right pb-0.5">
              <div className="text-[11px] text-muted-foreground uppercase tracking-wide leading-tight">
                {isLabOnly ? "Practical" : "Overall"}
              </div>
              <div className="text-[11px] text-muted-foreground uppercase tracking-wide leading-tight">
                Attendance
              </div>
            </div>
          </div>
          <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden mt-2.5">
            <div
              className={cn(
                "h-full rounded-full",
                progressVariant === "success" && "bg-success",
                progressVariant === "warning" && "bg-warning",
                progressVariant === "danger" && "bg-destructive",
                progressVariant === "default" && "bg-primary"
              )}
              style={{ width: `${primaryPct !== null ? Math.min(100, Math.max(0, primaryPct)) : 0}%` }}
            />
          </div>
        </div>

        {!isLabOnly ? (
          <>
            {/* Breakdown: two balanced blocks, Lecture / Tutorial */}
            <div className="grid grid-cols-2 gap-2 sm:gap-3 mt-0.5">
              <Block
                label="Lecture"
                pct={summary?.current_lecture_pct ?? null}
                counts={summary?.lecture}
              />
              {hasTutorials ? (
                <Block
                  label="Tutorial"
                  pct={summary?.current_tutorial_pct ?? null}
                  counts={summary?.tutorial}
                />
              ) : (
                <div className="rounded-lg border border-border/40 bg-muted/30 px-3 py-2.5 flex items-center justify-center text-[11px] text-muted-foreground">
                  No tutorials
                </div>
              )}
            </div>

            {/* Formula caption (presentation only — the backend computes) */}
            <p className="text-[11px] text-muted-foreground">
              {hasTutorials
                ? "Average = (Lecture % + Tutorial %) / 2"
                : "No tutorials — subject average equals Lecture %"}
            </p>
          </>
        ) : (
          /* Lab / practical-only: practical attendance + mid-sem state (backend-backed) */
          <div className="space-y-2 mt-0.5">
            <div className="flex items-baseline justify-between rounded-lg border border-border/40 bg-muted/30 px-3 py-2.5">
              <span className="text-xs font-medium text-foreground">Practical sessions attended</span>
              <span className="tabular-nums font-semibold text-foreground text-sm">
                {summary?.practical.attended ?? 0} / {summary?.practical.total ?? 0}
              </span>
            </div>
            {/* Mid-sem state comes only from the backend designation (actual
                scheduled session); nothing is fabricated when unset. */}
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Mid-Sem Practical</span>
              <span className="font-medium text-foreground tabular-nums">
                {summary?.mid_sem_session_date ? formatDateMedium(summary.mid_sem_session_date) : "Not scheduled"}
              </span>
            </div>
          </div>
        )}

        {/* Details: real backend values only — no forecast, no optimizer */}
        <Button variant="outline" size="sm" onClick={() => setShowDetails(v => !v)} className="w-full justify-between mt-auto">
          <span>View Details</span>
          {showDetails ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
        </Button>

        {showDetails && (
          <div className="rounded-lg border border-border/50 bg-muted/30 p-3.5 space-y-2.5 text-xs">
            {!isLabOnly && (
              <>
                <DetailRow label="Lecture" counts={summary?.lecture} pct={summary?.current_lecture_pct ?? null} />
                {hasTutorials && <DetailRow label="Tutorial" counts={summary?.tutorial} pct={summary?.current_tutorial_pct ?? null} />}
                <DetailRow label="Overall" counts={null} pct={summary?.current_avg_pct ?? null} />
              </>
            )}
            {isLabOnly && (
              <DetailRow label="Practical" counts={summary?.practical} pct={summary?.current_practical_pct ?? null} />
            )}
            <p className="text-[11px] text-muted-foreground pt-1 border-t border-border/40">
              Percentages are current and recorded-only — pending sessions are never treated as absent.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface SubjectAttendanceCardProps {
  subject: SubjectResponse;
  // Backend-derived analytics (canonical attendance pipeline via the analytics
  // overview). The card renders these values and never recomputes percentages,
  // banding, or mid-sem state client-side.
  summary: AnalyticsSubjectItem | null;
}

function Block({
  label,
  pct,
  counts,
}: {
  label: string;
  pct: number | null;
  counts: { total: number; attended: number } | undefined;
}) {
  return (
    <div className="rounded-lg border border-border/40 bg-muted/30 px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">{label}</span>
        <span className="tabular-nums font-semibold text-foreground text-sm leading-none">{formatPct(pct)}</span>
      </div>
      <p className="text-[11px] text-muted-foreground mt-1.5 tabular-nums">
        {counts?.attended ?? 0}/{counts?.total ?? 0} attended
      </p>
    </div>
  );
}

function DetailRow({
  label,
  counts,
  pct,
}: {
  label: string;
  counts: { total: number; attended: number; missed: number; pending: number } | null | undefined;
  pct: number | null;
}) {
  return (
    <div className="flex items-start sm:items-center justify-between gap-3">
      <span className="text-foreground">
        {label}
        {counts && (
          <span className="text-muted-foreground">
            {" "}
            · {counts.attended}/{counts.total} attended
            {counts.missed > 0 ? ` · ${counts.missed} missed` : ""}
            {counts.pending > 0 ? ` · ${counts.pending} pending` : ""}
          </span>
        )}
      </span>
      <span className="tabular-nums text-muted-foreground shrink-0">{formatPct1(pct)}</span>
    </div>
  );
}
