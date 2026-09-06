"use client";

import { useState } from "react";
import Link from "next/link";
import { useDashboardSummary, useAnalyticsOverview } from "@/hooks/useApi";
import { ErrorState } from "@/components/shared/ErrorState";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { AlertTriangle, Sparkles, X } from "lucide-react";
import { GreetingHeader } from "@/components/dashboard/home/GreetingHeader";
import { TodayAttendanceCard, TodayAttendanceCardSkeleton } from "@/components/dashboard/home/TodayAttendanceCard";
import { OverallAttendanceCard, OverallAttendanceCardSkeleton } from "@/components/dashboard/home/OverallAttendanceCard";
import { WeeklyAttendanceCard, WeeklyAttendanceCardSkeleton } from "@/components/dashboard/home/WeeklyAttendanceCard";
import { QuizSnapshotCard, QuizSnapshotCardSkeleton } from "@/components/dashboard/home/QuizSnapshotCard";
import { AttentionRequiredCard, AttentionRequiredCardSkeleton } from "@/components/dashboard/home/AttentionRequiredCard";
import { UpcomingEventsCard, UpcomingEventsCardSkeleton } from "@/components/dashboard/home/UpcomingEventsCard";

// UI-027: first-use hint. There is no backend onboarding state — dismissal is
// frontend-only (localStorage), so no schema, auth, or session change. The
// hint renders only while the account has zero recorded sessions; any recorded
// attendance (or dismissal) removes it for good. Privacy mode degrades to a
// per-visit hint rather than breaking.
const GETTING_STARTED_DISMISS_KEY = "adp_getting_started_dismissed";

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
  const [gettingStartedDismissed, setGettingStartedDismissed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try {
      return window.localStorage.getItem(GETTING_STARTED_DISMISS_KEY) === "1";
    } catch {
      return false;
    }
  });

  const dismissGettingStarted = () => {
    setGettingStartedDismissed(true);
    try {
      window.localStorage.setItem(GETTING_STARTED_DISMISS_KEY, "1");
    } catch {
      // Storage unavailable (privacy mode) — the hint returns next visit.
    }
  };

  const showGettingStarted =
    !isLoading && !!summary && summary.overall.recorded === 0 && !gettingStartedDismissed;

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

      {/* UI-027: single first-use hint — shown only for accounts with no
          recorded sessions yet, non-blocking, and dismissible for good. */}
      {showGettingStarted && (
        <Card className="mb-6 flex items-start justify-between gap-3 border-primary/30 p-4">
          <div className="flex min-w-0 items-start gap-3">
            <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
            <div className="min-w-0 text-sm">
              <p className="font-medium text-foreground">Getting started</p>
              <p className="mt-0.5 text-muted-foreground">
                Mark today&apos;s classes under{" "}
                <Link href="/tools/laboratory" className="font-medium text-primary hover:underline">
                  Mark Attendance
                </Link>
                , record extra classes, cancellations, or surprise quizzes under{" "}
                <Link href="/tools/events" className="font-medium text-primary hover:underline">
                  Events
                </Link>
                , and watch{" "}
                <Link href="/tools/quiz-schedule" className="font-medium text-primary hover:underline">
                  Quiz Eligibility
                </Link>{" "}
                as quizzes approach.
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Dismiss getting started hint"
            onClick={dismissGettingStarted}
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </Card>
      )}

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