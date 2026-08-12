"use client";

import { useSubjects } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { GlassCard } from "@/components/shared/GlassCard";
import { SubjectQuizSchedule } from "@/components/dashboard/SubjectQuizSchedule";
import { AlertCircle, Calendar } from "lucide-react";

export default function QuizSchedulePage() {
  const { subjects, isLoading, isError } = useSubjects();

  if (isError) {
    return (
      <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-4xl mx-auto w-full">
        <PageHeader title="Quiz Schedule" />
        <ErrorState message="Could not load subjects to determine quiz schedules." />
      </div>
    );
  }

  const quizApplicableSubjects = subjects?.filter(s => s.quiz_applicable) || [];

  return (
    <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-4xl mx-auto w-full">
      <PageHeader 
        title="Quiz Schedule" 
        description="Eligibility requirements and dates for your enrolled subjects."
      />

      <GlassCard className="mb-6 p-4 border border-border/50 bg-surface2/30">
        <div className="flex items-start gap-3 text-sm text-muted-foreground">
          <AlertCircle className="h-5 w-5 text-accent mt-0.5 shrink-0" />
          <p>
            The backend API evaluates quiz eligibility individually per subject and cycle. 
            Dates labeled &quot;Unresolved / TBD&quot; (such as BCS-054 Quiz III) have no confirmed dates in the academic database.
          </p>
        </div>
      </GlassCard>

      {isLoading ? (
        <div className="space-y-6">
          {[1, 2].map((i) => (
            <GlassCard key={i} className="h-48 animate-pulse bg-surface/50" />
          ))}
        </div>
      ) : quizApplicableSubjects.length === 0 ? (
        <EmptyState 
          title="No quizzes scheduled" 
          message="None of your enrolled subjects have applicable quizzes."
          icon={<Calendar className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      ) : (
        <div className="space-y-6">
          {quizApplicableSubjects.map(subject => (
            <SubjectQuizSchedule key={subject.id} subjectCode={subject.code} />
          ))}
        </div>
      )}
    </div>
  );
}
