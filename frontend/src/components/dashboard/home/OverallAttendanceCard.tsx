import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { OverallSection } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDelta, formatPct } from "@/lib/date";
import { attendanceStatusVariant } from "./status";

interface OverallAttendanceCardProps {
  overall: OverallSection;
  // Backend-provided overall forecast (pending treated as attended — canonical
  // forecast semantics from GET /api/v1/analytics/overview). Optional: the
  // card renders it additively when supplied.
  forecastPct?: number | null;
}

export function OverallAttendanceCard({ overall, forecastPct }: OverallAttendanceCardProps) {
  const pct = overall.overall_pct;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>Overall Attendance</CardTitle>
          <Badge variant={attendanceStatusVariant(overall.status)}>
            {overall.status ?? "N/A"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-3xl font-bold tabular-nums tracking-tight text-foreground">
              {formatPct(pct)}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {overall.attended} attended · {overall.recorded} recorded
              {overall.pending > 0 && ` · ${overall.pending} pending`}
            </p>
            {forecastPct !== null && forecastPct !== undefined && (
              <p className="mt-1 text-xs text-muted-foreground">
                Forecast {formatPct(forecastPct)}
                <span className="text-text2"> if all pending attended</span>
              </p>
            )}
          </div>
          {overall.weekly_delta_pct !== null && (
            <div
              className={`flex items-center gap-1 text-xs font-medium tabular-nums ${
                overall.weekly_delta_pct >= 0 ? "text-success" : "text-destructive"
              }`}
            >
              {overall.weekly_delta_pct >= 0 ? (
                <ArrowUpRight className="size-3.5" />
              ) : (
                <ArrowDownRight className="size-3.5" />
              )}
              {formatDelta(overall.weekly_delta_pct)} pts vs last week
            </div>
          )}
        </div>

        <Progress
          className="mt-4"
          value={pct ?? 0}
          variant={
            overall.status === "SAFE"
              ? "success"
              : overall.status === "WATCH"
                ? "warning"
                : "danger"
          }
        />
      </CardContent>
    </Card>
  );
}

export function OverallAttendanceCardSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton className="h-5 w-44" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-9 w-28" />
        <Skeleton className="mt-3 h-2 w-full" />
      </CardContent>
    </Card>
  );
}