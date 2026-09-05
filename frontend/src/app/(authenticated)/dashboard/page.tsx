"use client";

import { useDashboardSummary, useAnalyticsOverview } from "@/hooks/useApi";
import { ErrorState } from "@/components/shared/ErrorState";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";
import { GreetingHeader } from "@/components/dashboard/home/GreetingHeader";
import { TodayAttendanceCard, TodayAttendanceCardSkeleton } from "@/components/dashboard/home/TodayAttendanceCard";
import { OverallAttendanceCard, OverallAttendanceCardSkeleton } from "@/components/dashboard/home/OverallAttendanceCard";
import { WeeklyAttendanceCard, WeeklyAttendanceCardSkeleton } from "@/components/dashboard/home/WeeklyAttendanceCard";
import { QuizSnapshotCard, QuizSnapshotCardSkeleton } from "@/components/dashboard/home/QuizSnapshotCard";
import { AttentionRequiredCard, AttentionRequiredCardSkeleton } from "@/components/dashboard/home/AttentionRequiredCard";
import { UpcomingEventsCard, UpcomingEventsCardSkeleton } from "@/components/dashboard/home/UpcomingEventsCard";

export default function DashboardPage() {
  const { summary, isLoading, isError, mutate } = useDashboardSummary();
  // Phase 8.1 analytics read model: supplies the overall forecast and the
  // authoritative weekly series that the cards render (backend-derived only).
  // Optional by design (UI-022): its failure must never blank the dashboard —
  // it surfaces as a dismissible-free, non-blocking note with a targeted retry.
  const {
    overview,
    isError: analyticsError,
    mutate: mutateAnalytics,
  } = useAnalyticsOverview();

  if (isError) {
    return (
      <div className="w-full">
        <GreetingHeader />
        <ErrorState
          title="Failed to load dashboard"
          message="The dashboard could not be loaded. Check your connection and try again."
          onRetry={() => mutate()}
        />
      </div>
    );
  }

  return (
    <div className="w-full">
      <GreetingHeader />

      {analyticsError && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5">
          <p className="flex items-center gap-2 text-sm text-warning">
            <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
            Some analytics couldn&apos;t be loaded — forecast and weekly trends
            may be missing.
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => mutateAnalytics()}
          >
            Try again
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {isLoading || !summary ? (
          <>
            <TodayAttendanceCardSkeleton />
            <OverallAttendanceCardSkeleton />
            <WeeklyAttendanceCardSkeleton />
            <QuizSnapshotCardSkeleton />
            <AttentionRequiredCardSkeleton />
            <UpcomingEventsCardSkeleton />
          </>
        ) : (
          <>
            <TodayAttendanceCard today={summary.today} />
            <OverallAttendanceCard overall={summary.overall} forecastPct={overview?.overall.forecast_pct ?? null} />
            <WeeklyAttendanceCard weekly={summary.weekly} series={overview?.weekly ?? null} />
            <QuizSnapshotCard quiz={summary.quiz_snapshot} />
            <AttentionRequiredCard items={summary.attention_required} />
            <UpcomingEventsCard events={summary.upcoming_events} />
          </>
        )}
      </div>
    </div>
  );
}