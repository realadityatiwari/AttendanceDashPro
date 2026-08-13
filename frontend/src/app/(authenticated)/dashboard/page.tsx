"use client";

import { useDashboardSummary } from "@/hooks/useApi";
import { ErrorState } from "@/components/shared/ErrorState";
import { GreetingHeader } from "@/components/dashboard/home/GreetingHeader";
import { TodayAttendanceCard, TodayAttendanceCardSkeleton } from "@/components/dashboard/home/TodayAttendanceCard";
import { OverallAttendanceCard, OverallAttendanceCardSkeleton } from "@/components/dashboard/home/OverallAttendanceCard";
import { WeeklyAttendanceCard, WeeklyAttendanceCardSkeleton } from "@/components/dashboard/home/WeeklyAttendanceCard";
import { QuizSnapshotCard, QuizSnapshotCardSkeleton } from "@/components/dashboard/home/QuizSnapshotCard";
import { AttentionRequiredCard, AttentionRequiredCardSkeleton } from "@/components/dashboard/home/AttentionRequiredCard";
import { UpcomingEventsCard, UpcomingEventsCardSkeleton } from "@/components/dashboard/home/UpcomingEventsCard";

export default function DashboardPage() {
  const { summary, isLoading, isError } = useDashboardSummary();

  if (isError) {
    return (
      <div className="w-full">
        <GreetingHeader />
        <ErrorState
          title="Failed to load dashboard"
          message="The dashboard summary could not be retrieved from the server."
        />
      </div>
    );
  }

  return (
    <div className="w-full">
      <GreetingHeader />

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
            <OverallAttendanceCard overall={summary.overall} />
            <WeeklyAttendanceCard weekly={summary.weekly} />
            <QuizSnapshotCard quiz={summary.quiz_snapshot} />
            <AttentionRequiredCard items={summary.attention_required} />
            <UpcomingEventsCard events={summary.upcoming_events} />
          </>
        )}
      </div>
    </div>
  );
}