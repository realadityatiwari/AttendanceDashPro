"use client";

import { useSubjects, useAnalyticsOverview } from "@/hooks/useApi";
import { SubjectAttendanceCard } from "./SubjectAttendanceCard";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";

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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" aria-hidden="true">
        {/* 25.UX-4: h-64 tracks the real subject card height (~300px with
            header, headline, breakdown blocks, and details CTA) so the
            loading state no longer collapses to half the loaded height. */}
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-64 rounded-xl border border-border" />
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
      <EmptyState
        title="No subjects found"
        message="You are not currently enrolled in any subjects."
      />
    );
  }

  // Backend-derived summaries keyed by subject code (the analytics overview is
  // enrollment-scoped and excludes non-attendance-applicable subjects, the same
  // scope used below).
  const summaryByCode = new Map((overview?.subjects ?? []).map((s) => [s.subject_code, s]));

  const displaySubjects = subjects.filter((s) => s.attendance_applicable);

  // 25.UX-4: an enrollment can exist while carrying no attendance-applicable
  // subject — without this guard the grid rendered as a silent blank area.
  if (displaySubjects.length === 0) {
    return (
      <EmptyState
        title="No attendance to track"
        message="None of your enrolled subjects are attendance-applicable this semester."
      />
    );
  }

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
