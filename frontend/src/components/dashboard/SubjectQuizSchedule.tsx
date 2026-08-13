import { useQuizEligibility } from "@/hooks/useApi";
import { GlassCard } from "@/components/shared/GlassCard";
import { Badge } from "@/components/ui/badge";
import { Calendar, AlertCircle } from "lucide-react";

export function SubjectQuizSchedule({ subjectCode }: { subjectCode: string }) {
  const q1 = useQuizEligibility(subjectCode, 1);
  const q2 = useQuizEligibility(subjectCode, 2);
  const q3 = useQuizEligibility(subjectCode, 3);

  const isLoading = q1.isLoading || q2.isLoading || q3.isLoading;
  const isError = q1.isError || q2.isError || q3.isError;

  if (isLoading) {
    return <GlassCard className="h-32 animate-pulse bg-surface/50" />;
  }

  if (isError) {
    return (
      <GlassCard className="p-4 border border-red-900/50 bg-red-950/20">
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="h-4 w-4" />
          <span className="text-sm font-medium">Failed to load quiz schedule for {subjectCode}</span>
        </div>
      </GlassCard>
    );
  }

  const cycles = [
    { label: "Quiz I", data: q1.eligibility },
    { label: "Quiz II", data: q2.eligibility },
    { label: "Quiz III", data: q3.eligibility },
  ];

  return (
    <GlassCard className="overflow-hidden">
      <div className="bg-surface2/50 px-4 py-3 border-b border-border/50">
        <h3 className="font-bold text-foreground text-base">{subjectCode}</h3>
      </div>
      <div className="divide-y divide-border/50">
        {cycles.map((cycle, idx) => {
          if (!cycle.data) return null;
          
          let dateRange = "Unresolved / TBD";
          if (cycle.data.window_start && cycle.data.window_end) {
            const start = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(cycle.data.window_start));
            const end = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(new Date(cycle.data.window_end));
            dateRange = `${start} - ${end}`;
          }

          const threshold = cycle.data.combined_threshold || cycle.data.lecture_threshold || 75;

          return (
            <div key={idx} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-surface2/30 transition-colors">
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="font-semibold text-sm text-foreground">{cycle.label}</h4>
                  <Badge variant="outline" className="text-[10px] tracking-wider py-0 h-4">
                    Req: {threshold}%
                  </Badge>
                </div>
                {cycle.data.policy_ambiguity_notes && (
                  <p className="text-xs text-amber-400 mt-1">
                    {cycle.data.policy_ambiguity_notes}
                  </p>
                )}
                {cycle.data.optimization && (
                  <div className="mt-2 grid grid-cols-2 gap-2 max-w-xs text-xs">
                    <div className="rounded bg-surface2/50 border border-border/50 px-3 py-2">
                      <p className="font-semibold text-muted-foreground text-[10px] tracking-wider uppercase">Must Attend</p>
                      <p className="text-foreground">Lecture: <span className="font-bold">{cycle.data.optimization.lecture_deficit}</span></p>
                      <p className="text-foreground">Tutorial: <span className="font-bold">{cycle.data.optimization.tutorial_deficit}</span></p>
                    </div>
                    <div className="rounded bg-surface2/50 border border-border/50 px-3 py-2">
                      <p className="font-semibold text-muted-foreground text-[10px] tracking-wider uppercase">Safe Skip</p>
                      <p className="text-foreground">Lecture: <span className="font-bold">{cycle.data.optimization.safe_skip_lecture}</span></p>
                      <p className="text-foreground">Tutorial: <span className="font-bold">{cycle.data.optimization.safe_skip_tutorial}</span></p>
                    </div>
                  </div>
                )}
              </div>
              <div className="text-sm font-medium text-accent flex items-center gap-2">
                <Calendar className="h-4 w-4" />
                {dateRange}
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
