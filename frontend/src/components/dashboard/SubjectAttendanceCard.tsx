import { useSubjectSummary, useQuizEligibility } from "@/hooks/useApi";
import { SubjectResponse } from "@/types/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, Target, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

interface SubjectAttendanceCardProps {
  subject: SubjectResponse;
}

export function SubjectAttendanceCard({ subject }: SubjectAttendanceCardProps) {
  // Hardcode cycle 1 for now, or this could come from a context/prop
  const cycle = 1;
  const { summary, isLoading: sumLoading, isError: sumError } = useSubjectSummary(subject.code);
  const { eligibility, isLoading: eligLoading, isError: eligError } = useQuizEligibility(subject.quiz_applicable ? subject.code : null, cycle);

  const isLoading = sumLoading || eligLoading;
  
  if (isLoading) {
    return (
      <Card className="bg-surface border-border overflow-hidden opacity-70">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex justify-between items-center">
            <span className="font-semibold">{subject.code}</span>
            <div className="w-12 h-4 bg-surface2 rounded animate-pulse"></div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="h-2 w-full bg-surface2 rounded-full animate-pulse"></div>
            <div className="flex justify-between">
              <div className="w-16 h-4 bg-surface2 rounded animate-pulse"></div>
              <div className="w-16 h-4 bg-surface2 rounded animate-pulse"></div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (sumError) {
    return (
      <Card className="bg-surface border-border overflow-hidden">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold">{subject.code}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-xs text-red-400 flex items-center gap-1.5">
            <AlertCircle size={14} />
            Failed to load stats
          </div>
        </CardContent>
      </Card>
    );
  }

  // Determine status color based on avg percentage or quiz eligibility
  const avgPct = summary?.current_avg_pct ?? 0;
  
  let statusColor = "text-foreground";
  let badgeColor = "bg-surface2 text-text border-border";
  let statusIcon = null;

  if (subject.quiz_applicable && eligibility) {
    if (eligibility.is_eligible) {
      statusColor = "text-emerald-400";
      badgeColor = "bg-emerald-500/15 text-emerald-400 border-emerald-500/20";
      statusIcon = <CheckCircle2 size={14} className="text-emerald-400" />;
    } else {
      statusColor = "text-red-400";
      badgeColor = "bg-red-500/15 text-red-400 border-red-500/20";
      statusIcon = <XCircle size={14} className="text-red-400" />;
    }
  } else {
    // Basic threshold if no quiz
    if (avgPct >= 75) {
      statusColor = "text-emerald-400";
    } else if (avgPct >= 65) {
      statusColor = "text-amber-400";
    } else {
      statusColor = "text-red-400";
    }
  }

  return (
    <Card className="bg-surface border-border overflow-hidden hover:border-border/80 transition-colors">
      <CardHeader className="pb-2 pt-4 px-4 bg-surface/50 border-b border-border/30">
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-base font-bold text-foreground">
              {subject.code}
            </CardTitle>
            <div className="text-xs text-muted-foreground truncate max-w-[150px]" title={subject.name}>
              {subject.name}
            </div>
          </div>
          {subject.quiz_applicable && eligibility && (
             <Badge className={`uppercase text-[10px] tracking-wider px-2 py-0 h-5 flex items-center gap-1 ${badgeColor}`}>
               {statusIcon}
               {eligibility.is_eligible ? "Eligible" : "Defaulter"}
             </Badge>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="p-4">
        {/* Main Stats */}
        <div className="flex items-end justify-between mb-4">
          <div>
            <div className={`text-2xl font-bold tracking-tight ${statusColor}`}>
              {summary?.current_avg_pct !== null ? `${summary?.current_avg_pct?.toFixed(1)}%` : "N/A"}
            </div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wide mt-0.5">Overall Avg</div>
          </div>
          
          <div className="text-right">
            <div className="text-sm font-semibold text-foreground">
              {summary?.lecture.attended} / {summary?.lecture.total}
            </div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wide mt-0.5">Lec Attended</div>
          </div>
        </div>

        {/* Progress Bar (Visual representation) */}
        <div className="h-1.5 w-full bg-surface2 rounded-full overflow-hidden mb-4">
          <div 
            className="h-full bg-emerald-500 rounded-full" 
            style={{ 
              width: `${Math.min(100, Math.max(0, avgPct))}%`,
              backgroundColor: avgPct >= 75 ? 'var(--emerald-500)' : avgPct >= 65 ? 'var(--amber-500)' : 'var(--red-500)'
            }}
          />
        </div>

        {/* Details Grid */}
        <div className="grid grid-cols-2 gap-2 text-xs border-t border-border/30 pt-3">
          <div className="flex flex-col">
            <span className="text-muted-foreground">Lec: <span className="font-medium text-foreground">{summary?.current_lecture_pct !== null ? `${summary?.current_lecture_pct?.toFixed(0)}%` : "—"}</span></span>
            {subject.quiz_applicable && eligibility?.optimization && (
              <span className="text-[10px] mt-0.5 text-text2 flex items-center gap-1">
                <Target size={10} /> Safe Skips: {eligibility.optimization.safe_skip_lecture}
              </span>
            )}
          </div>
          
          <div className="flex flex-col text-right">
            <span className="text-muted-foreground">Tut: <span className="font-medium text-foreground">{summary?.current_tutorial_pct !== null ? `${summary?.current_tutorial_pct?.toFixed(0)}%` : "—"}</span></span>
            {subject.quiz_applicable && eligibility?.optimization && (
              <span className="text-[10px] mt-0.5 text-text2 flex items-center justify-end gap-1">
                <Target size={10} /> Safe Skips: {eligibility.optimization.safe_skip_tutorial}
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
