import { ArrowDownRight, ArrowUpRight, CalendarRange } from "lucide-react";
import { WeeklySection, WeeklyAnalyticsItem } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatShortDate, formatDelta, formatPct } from "@/lib/date";
import { WEEKLY_BAR_SAFE_PCT, WEEKLY_BAR_WATCH_PCT } from "@/lib/statusLabels";

interface WeeklyAttendanceCardProps {
  weekly: WeeklySection;
  // Backend weekly read-model series from GET /api/v1/analytics/overview
  // (Monday-start weeks, recorded-only current_pct, null = gap week). The
  // frontend renders these values and never re-derives percentages.
  series?: WeeklyAnalyticsItem[] | null;
}

// Presentation-only: cap the rendered series to the most recent weeks so the
// card stays compact. No data is invented — the backend series is shown as-is.
const MAX_WEEKS = 6;

export function WeeklyAttendanceCard({ weekly, series }: WeeklyAttendanceCardProps) {
  const delta = weekly.delta_pct;
  const weeks = (series ?? []).slice(-MAX_WEEKS);

  return (
    <Card>
      <CardHeader className="border-b">
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle>This Week</CardTitle>
            <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
              <CalendarRange className="size-3.5" />
              {weekly.week_start} → {weekly.week_end}
            </p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold tabular-nums tracking-tight text-foreground">
              {formatPct(weekly.weekly_pct)}
            </div>
            {delta !== null && (
              <div
                className={`mt-0.5 flex items-center justify-end gap-1 text-xs font-medium tabular-nums ${
                  delta >= 0 ? "text-success" : "text-destructive"
                }`}
              >
                {delta >= 0 ? (
                  <ArrowUpRight className="size-3.5" />
                ) : (
                  <ArrowDownRight className="size-3.5" />
                )}
                {formatDelta(delta)} pts
              </div>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-4">
        {weeks.length === 0 ? (
          <div className="py-6 text-center">
            <p className="text-xs text-muted-foreground">
              No weekly attendance data yet.
            </p>
          </div>
        ) : (
          <ul className="space-y-2.5">
            {weeks.map((week) => {
              const pct = week.current_pct; // backend-provided; null = gap week
              const isCurrentWeek = week.week_start === weekly.week_start;
              return (
                <li
                  key={week.week_start}
                  className={`flex items-center gap-2 rounded-md px-2 py-1.5 sm:gap-3 ${
                    isCurrentWeek ? "bg-muted/60 ring-1 ring-border" : ""
                  }`}
                >
                  <span className="w-16 shrink-0 text-xs font-medium text-foreground">
                    {formatShortDate(week.week_start)}
                  </span>
                  <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full rounded-full ${
                        pct === null
                          ? "bg-muted"
                          : pct >= WEEKLY_BAR_SAFE_PCT
                            ? "bg-success"
                            : pct >= WEEKLY_BAR_WATCH_PCT
                              ? "bg-warning"
                              : "bg-destructive"
                      }`}
                      style={{ width: pct === null ? "0%" : `${Math.min(100, pct)}%` }}
                    />
                  </div>
                  <span className="w-14 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                    {pct !== null ? `${Math.round(pct)}%` : "—"}
                  </span>
                  <span className="w-24 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                    {week.attended}/{week.recorded}
                    {week.pending > 0 ? ` · ${week.pending} pending` : ""}
                  </span>
                </li>
              );
            })}
          </ul>
        )}

        <div className="mt-4 space-y-1.5 border-t border-border/60 pt-3 text-xs">
          {weekly.best_subject && (
            <p className="flex items-center justify-between gap-2 text-muted-foreground">
              <span>Best this week</span>
              <span className="text-foreground">
                <span className="font-medium">{weekly.best_subject.subject_code}</span>
                <span className="ml-1.5 tabular-nums text-success">
                  {formatPct(weekly.best_subject.pct)}
                </span>
              </span>
            </p>
          )}
          {weekly.needs_attention_subject && (
            <p className="flex items-center justify-between gap-2 text-muted-foreground">
              <span>Needs attention</span>
              <span className="text-foreground">
                <span className="font-medium">
                  {weekly.needs_attention_subject.subject_code}
                </span>
                <span className="ml-1.5 tabular-nums text-destructive">
                  {formatPct(weekly.needs_attention_subject.pct)}
                </span>
              </span>
            </p>
          )}
          {!weekly.best_subject && !weekly.needs_attention_subject && (
            <p className="text-muted-foreground">
              <Badge variant="neutral">No subjects with recorded attendance</Badge>
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function WeeklyAttendanceCardSkeleton() {
  return (
    <Card>
      <CardHeader className="border-b">
        <Skeleton className="h-5 w-28" />
      </CardHeader>
      <CardContent className="p-4">
        <div className="space-y-3">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-5 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}