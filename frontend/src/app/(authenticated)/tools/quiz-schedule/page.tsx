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

const QUIZ_ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];

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
      <div className="flex-1 py-8 w-full max-w-4xl mx-auto">
        <PageHeader title="Quiz Eligibility" />
        <ErrorState message="Could not load subjects to determine quiz eligibility." />
      </div>
    );
  }

  const quizApplicableSubjects = subjects?.filter((s) => s.quiz_applicable) || [];

  return (
    <div className="flex-1 py-8 w-full max-w-4xl mx-auto">
      <PageHeader
        title="Quiz Eligibility"
        description="Eligibility per the institutional attendance criteria — evaluated by the backend from your actual attendance."
      />

      <GlassCard className="mb-6 p-4 border border-border/50 bg-muted/30">
        <div className="flex items-start gap-3 text-sm text-muted-foreground">
          <Info className="h-5 w-5 text-primary mt-0.5 shrink-0" />
          <div className="space-y-1">
            <p>
              A subject is eligible when{" "}
              <span className="font-medium text-foreground">Criterion I or Criterion II</span> reaches the required
              percentage: <span className="font-medium text-foreground">70%</span> for Quiz I,{" "}
              <span className="font-medium text-foreground">75%</span> for Quiz II and III.
            </p>
            <p>
              Both criteria use the same{" "}
              <span className="font-medium text-foreground">(Lecture % + Tutorial %) / 2</span> average and differ only
              in the counting window — Criterion I counts from the previous quiz, Criterion II from the semester start.
            </p>
            <p>Only theory subjects with confirmed quiz dates appear here.</p>
          </div>
        </div>
      </GlassCard>

      {/* UI-020: these buttons filter the card list below (including loading
          and empty states) — they are not a tab interface, so the false
          tablist/tab semantics are replaced by native buttons exposing the
          active cycle via aria-pressed inside a named group. Selection stays
          client-side only; cycle values and data fetching are unchanged. */}
      <div className="flex flex-wrap items-center gap-2 mb-6" role="group" aria-label="Quiz cycle">
        {CYCLES.map((c) => (
          <button
            key={c.number}
            type="button"
            aria-pressed={activeCycle === c.number}
            onClick={() => setCycle(c.number)}
            className={cn(
              "h-10 px-4 rounded-lg text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/60 sm:h-8",
              activeCycle === c.number
                ? "bg-primary text-primary-foreground"
                : "bg-muted/50 border border-border/50 text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            {c.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-6">
          {[1, 2].map((i) => (
            <GlassCard key={i} className="h-44 animate-pulse bg-muted/50" />
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
              cycleLabel={CYCLES.find((c) => c.number === activeCycle)?.label ?? `Quiz ${QUIZ_ROMAN[activeCycle] ?? activeCycle}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}