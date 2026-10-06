import Link from "next/link";
import { ClipboardList } from "lucide-react";
import { QuizSnapshotSection } from "@/types/api";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPct, formatShortDate } from "@/lib/date";
import { quizCycleLabel } from "@/lib/canonicalStatus";

interface QuizSnapshotCardProps {
  quiz: QuizSnapshotSection;
}

export function QuizSnapshotCard({ quiz }: QuizSnapshotCardProps) {
  return (
    // UI-040: h-full keeps both cards in a grid row visually aligned, with
    // the footer CTA pinned to the card's bottom edge.
    <Card className="h-full">
      <CardHeader className="border-b">
        <div className="flex items-center justify-between gap-3">
          <CardTitle>Quiz Snapshot</CardTitle>
          {quiz.has_snapshot && quiz.quiz_label && (
            // 25.UX-1/3: cycle labels flow from the canonical quiz-cycle
            // vocabulary (handles backend shapes like "Quiz1").
            <Badge variant="primary">{quizCycleLabel(quiz.quiz_label)}</Badge>
          )}
        </div>
      </CardHeader>

      {/* UIA-024: the content column centers within the shared row height so
          a sparse snapshot never strands a large void above the footer. */}
      <CardContent className="flex flex-1 flex-col justify-center p-4">
        {!quiz.has_snapshot ? (
          <div className="flex flex-col items-center justify-center py-6 text-center">
            <ClipboardList className="size-8 text-muted-foreground" />
            <h3 className="mt-3 text-sm font-medium text-foreground">
              No upcoming quizzes scheduled
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              Check the quiz schedule for the semester.
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs uppercase tracking-wide text-muted-foreground">
                  Next quiz
                </div>
                <div className="mt-0.5 text-lg font-semibold tabular-nums text-foreground">
                  {quiz.quiz_date ? formatShortDate(quiz.quiz_date) : "—"}
                </div>
              </div>
              {quiz.threshold !== null && (
                <div className="text-right">
                  <div className="text-xs uppercase tracking-wide text-muted-foreground">
                    Eligibility
                  </div>
                  <div className="mt-0.5 text-lg font-semibold tabular-nums text-foreground">
                    {/* 25.UX-3: thresholds render through the canonical
                        whole-number formatter. */}
                    ≥ {formatPct(quiz.threshold)}
                  </div>
                </div>
              )}
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border/60 pt-4 text-center">
              <div>
                <div className="text-xl font-bold tabular-nums text-success">
                  {quiz.eligible}
                </div>
                <div className="mt-0.5 text-2xs uppercase tracking-wide text-muted-foreground">
                  Eligible
                </div>
              </div>
              <div>
                <div className="text-xl font-bold tabular-nums text-warning">
                  {quiz.attention}
                </div>
                {/* 25.UX-3: the middle bucket IS the canonical Recoverable
                    state — the backend counts subjects whose optimization is
                    reachable (dashboard_service), so the label matches the
                    Quiz Eligibility vocabulary instead of a second name. */}
                <div className="mt-0.5 text-2xs uppercase tracking-wide text-muted-foreground">
                  Recoverable
                </div>
              </div>
              <div>
                <div className="text-xl font-bold tabular-nums text-destructive">
                  {quiz.not_eligible}
                </div>
                <div className="mt-0.5 text-2xs uppercase tracking-wide text-muted-foreground">
                  Not eligible
                </div>
              </div>
            </div>
          </>
        )}
      </CardContent>

      <CardFooter className="mt-auto justify-end">
        <Button variant="ghost" size="sm" nativeButton={false} render={<Link href="/tools/quiz-schedule" />}>
          View Quiz Eligibility
        </Button>
      </CardFooter>
    </Card>
  );
}

export function QuizSnapshotCardSkeleton() {
  return (
    <Card>
      <CardHeader className="border-b">
        <Skeleton className="h-5 w-32" />
      </CardHeader>
      <CardContent className="p-4">
        <Skeleton className="h-8 w-24" />
        <Skeleton className="mt-4 h-12 w-full" />
      </CardContent>
    </Card>
  );
}