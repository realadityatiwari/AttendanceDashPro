import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { OverallSection } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDelta, formatPct } from "@/lib/date";
import { RecordedPct } from "@/components/shared/RecordedPct";
import { getSubjectHealthStatus } from "@/lib/canonicalStatus";

interface OverallAttendanceCardProps {
  overall: OverallSection;
  // Backend-provided overall forecast (pending treated as attended — canonical
  // forecast semantics from GET /api/v1/analytics/overview). Optional: the
  // card renders it additively when supplied.
  forecastPct?: number | null;
}

// Canonical health variant -> progress fill variant (UIA-018). "N/A" (no
// recorded data) maps to the neutral progress treatment, never danger.
const PROGRESS_VARIANT = {
  success: "success",
  warning: "warning",
  danger: "danger",
  neutral: "neutral",
} as const;

export function OverallAttendanceCard({ overall, forecastPct }: OverallAttendanceCardProps) {
  const pct = overall.overall_pct;
  const zeroRecord = overall.recorded === 0;
  // UIA-006: one canonical health vocabulary (Healthy / At Risk / Critical /
  // N/A) — the legacy SAFE/WATCH/CRITICAL bands are normalized, not re-labeled.
  const health = getSubjectHealthStatus(overall.status);
  const progressVariant = zeroRecord
    ? PROGRESS_VARIANT.neutral
    : PROGRESS_VARIANT[health.variant as keyof typeof PROGRESS_VARIANT] ?? "default";

  return (
    // UIA-024: h-full keeps the grid row aligned; the content column centers
    // within the available height so extra space reads as intentional
    // breathing room instead of a dead void at the bottom of the card.
    // 25.UX-4: the header divider matches the other five dashboard cards —
    // within one uniform grid, five of six titles carried a border-b.
    <Card className="h-full">
      <CardHeader className="border-b">
        <div className="flex items-center justify-between gap-3">
          <CardTitle>Overall Attendance</CardTitle>
          <Badge variant={health.variant}>{health.label}</Badge>
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col justify-center">
        {zeroRecord ? (
          // UIA-014: a designed zero-record state. No fake 0%, no danger
          // color — the student simply has nothing recorded yet.
          <div>
            <RecordedPct
              value={pct}
              valueClassName="text-3xl font-bold tabular-nums tracking-tight text-foreground"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              No sessions recorded yet
              {overall.pending > 0 && ` · ${overall.pending} upcoming scheduled`}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Attendance tracking begins once your first class is marked.
            </p>
          </div>
        ) : (
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              {/* UIA-001: the headline figure carries its recorded-only basis so
                  "83%" beside "280 pending" can never read as 83% of all
                  sessions. */}
              <RecordedPct
                value={pct}
                valueClassName="text-3xl font-bold tabular-nums tracking-tight text-foreground"
                suffixClassName="text-xs font-medium text-muted-foreground"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                {`${overall.attended} attended · ${overall.recorded} recorded`}
                {overall.pending > 0 && ` · ${overall.pending} pending`}
              </p>
              {forecastPct !== null && forecastPct !== undefined && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Forecast {formatPct(forecastPct)}
                  <span className="text-muted-foreground/70"> if all pending attended</span>
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
                  <ArrowUpRight className="size-3.5" aria-hidden="true" />
                ) : (
                  <ArrowDownRight className="size-3.5" aria-hidden="true" />
                )}
                {formatDelta(overall.weekly_delta_pct)} pts vs last week
              </div>
            )}
          </div>
        )}

        <Progress
          className="mt-4"
          value={pct ?? 0}
          variant={progressVariant}
          size="md"
        />
      </CardContent>
    </Card>
  );
}

export function OverallAttendanceCardSkeleton() {
  return (
    <Card>
      <CardHeader className="border-b">
        <Skeleton className="h-5 w-44" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-9 w-28" />
        <Skeleton className="mt-3 h-2 w-full" />
      </CardContent>
    </Card>
  );
}
