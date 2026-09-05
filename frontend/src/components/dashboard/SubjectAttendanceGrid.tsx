"use client";

import { useSubjects, useAnalyticsOverview } from "@/hooks/useApi";
import { SubjectAttendanceCard } from "./SubjectAttendanceCard";
import { ErrorState } from "@/components/shared/ErrorState";

export function SubjectAttendanceGrid() {
  const {
    subjects,
    isLoading: subjectsLoading,
    isError: subjectsError,
    mutate: mutateSubjects,
  } = useSubjects();
  // ONE analytics overview request supplies every subject's backend summary
  // (practical %, 75% must-attend/safe-skip, forecasts) — no per-subject N+1.
  const {
    overview,
    isLoading: overviewLoading,
    isError: overviewError,
    mutate: mutateOverview,
  } = useAnalyticsOverview();

  const isLoading = subjectsLoading || overviewLoading;
  const isError = subjectsError || overviewError;

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-40 bg-muted rounded-xl border border-border animate-pulse"></div>
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <ErrorState
        title="Failed to load subjects"
        message="Could not retrieve your enrolled subjects or their analytics. Check your connection and try again."
        onRetry={() => {
          mutateSubjects();
          mutateOverview();
        }}
      />
    );
  }

  if (!subjects || subjects.length === 0) {
    return (
      <div className="p-8 bg-card border border-border rounded-xl text-center">
        <h3 className="text-sm font-semibold text-foreground">No subjects found</h3>
        <p className="text-xs text-muted-foreground mt-1">
          You are not currently enrolled in any subjects.
        </p>
      </div>
    );
  }

  // Backend-derived summaries keyed by subject code (the analytics overview is
  // enrollment-scoped and excludes non-attendance-applicable subjects, the same
  // scope used below).
  const summaryByCode = new Map((overview?.subjects ?? []).map((s) => [s.subject_code, s]));

  const displaySubjects = subjects.filter((s) => s.attendance_applicable);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {displaySubjects.map((subject) => (
        <SubjectAttendanceCard
          key={subject.id}
          subject={subject}
          summary={summaryByCode.get(subject.code) ?? null}
        />
      ))}
    </div>
  );
}
