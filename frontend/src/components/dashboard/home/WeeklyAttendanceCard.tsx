import { ArrowDownRight, ArrowUpRight, CalendarRange } from "lucide-react";
import { WeeklySection } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDelta, formatPct } from "@/lib/date";

interface WeeklyAttendanceCardProps {
  weekly: WeeklySection;
}

export function WeeklyAttendanceCard({ weekly }: WeeklyAttendanceCardProps) {
  const delta = weekly.delta_pct;

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
        <ul className="space-y-2.5">
          {weekly.days.map((day) => {
            const pct = day.recorded > 0 ? (day.attended / day.recorded) * 100 : null;
            return (
              <li
                key={day.date}
                className={`flex items-center gap-3 rounded-md px-2 py-1.5 ${
                  day.is_today ? "bg-muted/60 ring-1 ring-border" : ""
                }`}
              >
                <span className="w-16 shrink-0 text-xs font-medium text-foreground">
                  {day.day_label.slice(0, 3)}
                </span>
                <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full ${
                      pct === null
                        ? "bg-muted"
                        : pct >= 80
                          ? "bg-success"
                          : pct >= 60
                            ? "bg-warning"
                            : "bg-destructive"
                    }`}
                    style={{ width: pct === null ? "0%" : `${Math.min(100, pct)}%` }}
                  />
                </div>
                <span className="w-14 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                  {day.is_future ? "—" : pct !== null ? `${Math.round(pct)}%` : "—"}
                </span>
                <span className="w-14 shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                  {day.attended}/{day.recorded || day.classes}
                </span>
              </li>
            );
          })}
        </ul>

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