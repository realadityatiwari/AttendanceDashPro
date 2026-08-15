"use client";

import { useQuizEligibility, useCurrentQuizCycle } from "@/hooks/useApi";
import { SubjectResponse, AnalyticsSubjectItem } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, XCircle, Target } from "lucide-react";

interface SubjectAttendanceCardProps {
  subject: SubjectResponse;
  // Backend-derived analytics (Phase 8.1 read model, delivered via the
  // analytics overview). The card renders these values and never recomputes
  // percentages, must-attend, or safe-skip client-side.
  summary: AnalyticsSubjectItem | null;
}

export function SubjectAttendanceCard({ subject, summary }: SubjectAttendanceCardProps) {
  // Canonical date-aware quiz cycle (Phase 7.2): the backend answers which
  // cycle is currently relevant — no hardcoded cycle=1, no client-side
  // schedule logic. While it loads, the eligibility query stays disabled.
  const { currentCycle } = useCurrentQuizCycle();
  const cycle = currentCycle?.quiz_cycle ?? null;
  const { eligibility, isError: eligError } = useQuizEligibility(
    subject.quiz_applicable ? subject.code : null,
    cycle
  );

  const avgPct = summary?.current_avg_pct ?? null;
  const optimization = summary?.optimization ?? null;
  const hasPractical = (summary?.practical.total ?? 0) > 0;

  const isEligible = subject.quiz_applicable && eligibility?.is_eligible === true;

  return (
    <Card className="bg-surface border-border overflow-hidden hover:border-border/80 transition-colors">
      <CardHeader className="pb-2 pt-4 px-4 bg-surface/50 border-b border-border/30">
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-base font-bold text-foreground">
              {subject.code}
            </CardTitle>
            <div className="text-xs text-muted-foreground truncate max-w-[150px]" title={subject.name}>
              {subject.name}
            </div>
          </div>
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
      </CardHeader>

      <CardContent className="p-4">
        {/* Main stats (backend values) */}
        <div className="flex items-end justify-between mb-4">
          <div>
            <div className="text-2xl font-bold tracking-tight text-foreground">
              {avgPct !== null ? `${avgPct.toFixed(1)}%` : "N/A"}
            </div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wide mt-0.5">Overall Avg</div>
          </div>

          <div className="text-right">
            <div className="text-sm font-semibold text-foreground">
              {summary?.lecture.attended ?? 0} / {summary?.lecture.total ?? 0}
            </div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wide mt-0.5">Lec Attended</div>
          </div>
        </div>

        {/* Progress bar — single accent; no client-side SAFE/WATCH/CRITICAL
            banding (the backend does not emit a per-subject status, so none is
            invented here). */}
        <div className="h-1.5 w-full bg-surface2 rounded-full overflow-hidden mb-4">
          <div
            className="h-full bg-accent rounded-full"
            style={{ width: `${avgPct !== null ? Math.min(100, Math.max(0, avgPct)) : 0}%` }}
          />
        </div>

        {/* Lecture / Tutorial with backend 75% optimization */}
        <div className="grid grid-cols-2 gap-2 text-xs border-t border-border/30 pt-3">
          <div className="flex flex-col">
            <span className="text-muted-foreground">
              Lec:{" "}
              <span className="font-medium text-foreground">
                {summary?.current_lecture_pct !== null && summary?.current_lecture_pct !== undefined
                  ? `${summary.current_lecture_pct.toFixed(0)}%`
                  : "—"}
              </span>
            </span>
            {optimization && (
              <span className="text-[10px] mt-0.5 text-text2 flex items-center gap-1">
                <Target size={10} />
                Must attend: {optimization.lecture_deficit} · Safe skip: {optimization.safe_skip_lecture}
              </span>
            )}
          </div>

          <div className="flex flex-col text-right">
            <span className="text-muted-foreground">
              Tut:{" "}
              <span className="font-medium text-foreground">
                {summary?.current_tutorial_pct !== null && summary?.current_tutorial_pct !== undefined
                  ? `${summary.current_tutorial_pct.toFixed(0)}%`
                  : "—"}
              </span>
            </span>
            {optimization && (
              <span className="text-[10px] mt-0.5 text-text2 flex items-center justify-end gap-1">
                <Target size={10} />
                Must attend: {optimization.tutorial_deficit} · Safe skip: {optimization.safe_skip_tutorial}
              </span>
            )}
          </div>
        </div>

        {/* Practical analytics (backend canonical fields; shown only when the
            subject actually has practical sessions) */}
        {hasPractical && (
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs border-t border-border/30 pt-3">
            <div className="flex flex-col">
              <span className="text-muted-foreground">
                Prac:{" "}
                <span className="font-medium text-foreground">
                  {summary?.current_practical_pct !== null && summary?.current_practical_pct !== undefined
                    ? `${summary.current_practical_pct.toFixed(0)}%`
                    : "—"}
                </span>
              </span>
              <span className="text-[10px] mt-0.5 text-text2">
                {summary?.practical.attended ?? 0} / {summary?.practical.total ?? 0} attended
                {summary && summary.practical.pending > 0 ? ` · ${summary.practical.pending} pending` : ""}
              </span>
            </div>
            <div className="flex flex-col text-right">
              <span className="text-muted-foreground">
                Forecast:{" "}
                <span className="font-medium text-foreground">
                  {summary?.forecast_practical_pct !== null && summary?.forecast_practical_pct !== undefined
                    ? `${summary.forecast_practical_pct.toFixed(0)}%`
                    : "—"}
                </span>
              </span>
              <span className="text-[10px] mt-0.5 text-text2">if pending attended</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
