"use client";

import { useState } from "react";
import { useSubjects, useCurrentQuizCycle } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { GlassCard } from "@/components/shared/GlassCard";
import { QuizEligibilityCard } from "@/components/quiz/QuizEligibilityCard";
import { cn } from "@/lib/utils";
import { Calendar, Info } from "lucide-react";

const CYCLES = [
  { number: 1, label: "Quiz I" },
  { number: 2, label: "Quiz II" },
  { number: 3, label: "Quiz III" },
];

export default function QuizEligibilityPage() {
  const { subjects, isLoading, isError } = useSubjects();
  // Date-aware default tab (Phase 7.2): the backend picks the canonical
  // currently-relevant cycle from the authoritative quiz schedule. Manual tab
  // selection always overrides; tab state never mutates backend state.
  const { currentCycle } = useCurrentQuizCycle();
  const [cycle, setCycle] = useState<number | null>(null);
  const activeCycle = cycle ?? currentCycle?.quiz_cycle ?? 1;

  if (isError) {
    return (
      <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-4xl mx-auto w-full">
        <PageHeader title="Quiz Eligibility" />
        <ErrorState message="Could not load subjects to determine quiz eligibility." />
      </div>
    );
  }

  const quizApplicableSubjects = subjects?.filter((s) => s.quiz_applicable) || [];

  return (
    <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-4xl mx-auto w-full">
      <PageHeader
        title="Quiz Eligibility"
        description="Eligibility per the institutional attendance criteria — evaluated by the backend from your actual attendance."
      />

      <GlassCard className="mb-6 p-4 border border-border/50 bg-surface2/30">
        <div className="flex items-start gap-3 text-sm text-muted-foreground">
          <Info className="h-5 w-5 text-accent mt-0.5 shrink-0" />
          <p>
            A subject is eligible when <span className="font-medium text-foreground">Criterion I (Lecture %) OR Criterion II (Combined average)</span>{" "}
            meets the required percentage — 70% for Quiz I, 75% for Quiz II and Quiz III. Only theory subjects with a confirmed quiz schedule appear here.
          </p>
        </div>
      </GlassCard>

      <div className="flex flex-wrap items-center gap-2 mb-6" role="tablist" aria-label="Quiz cycle">
        {CYCLES.map((c) => (
          <button
            key={c.number}
            role="tab"
            aria-selected={activeCycle === c.number}
            onClick={() => setCycle(c.number)}
            className={cn(
              "h-8 px-4 rounded-lg text-sm font-medium transition-colors",
              activeCycle === c.number
                ? "bg-primary text-primary-foreground"
                : "bg-surface2/50 border border-border/50 text-muted-foreground hover:bg-surface2 hover:text-foreground"
            )}
          >
            {c.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-6">
          {[1, 2].map((i) => (
            <GlassCard key={i} className="h-44 animate-pulse bg-surface/50" />
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
          {quizApplicableSubjects.map((subject) => (
            <QuizEligibilityCard
              key={`${subject.code}-${activeCycle}`}
              subjectCode={subject.code}
              cycle={activeCycle}
              cycleLabel={CYCLES.find((c) => c.number === activeCycle)?.label ?? `Quiz ${activeCycle}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}