import { useLabExperiments, useLabRecords } from "@/hooks/useApi";
import { GlassCard } from "@/components/shared/GlassCard";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Circle, AlertCircle, Clock } from "lucide-react";
import { SignatureStatus } from "@/types/api";

export function SubjectLaboratoryView({ subjectCode }: { subjectCode: string }) {
  const { experiments, isLoading: expLoading, isError: expError } = useLabExperiments(subjectCode);
  const { records, isLoading: recLoading, isError: recError } = useLabRecords(subjectCode);

  const isLoading = expLoading || recLoading;
  const isError = expError || recError;

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <GlassCard key={i} className="h-16 animate-pulse bg-surface/50" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <GlassCard className="p-4 border border-red-900/50 bg-red-950/20">
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="h-4 w-4" />
          <span className="text-sm font-medium">Failed to load laboratory data for {subjectCode}</span>
        </div>
      </GlassCard>
    );
  }

  const expList = experiments || [];
  const recList = records || [];

  if (expList.length === 0) {
    return (
      <GlassCard className="p-8 text-center text-muted-foreground">
        No experiments defined for {subjectCode}.
      </GlassCard>
    );
  }

  return (
    <GlassCard className="overflow-hidden">
      <div className="bg-surface2/50 px-4 py-3 border-b border-border/50 flex justify-between items-center">
        <h3 className="font-bold text-foreground text-base">{subjectCode} Experiments</h3>
        <Badge variant="outline" className="bg-surface border-border">
          {recList.filter(r => r.signature_status === SignatureStatus.DONE).length} / {expList.length} Completed
        </Badge>
      </div>
      <div className="divide-y divide-border/50">
        {expList.map((exp) => {
          const record = recList.find(r => r.experiment_id === exp.id);
          const status = record?.signature_status || SignatureStatus.NONE;
          
          let statusIcon = <Circle className="h-5 w-5 text-muted-foreground/50" />;
          let statusText = "Not Started";
          let statusColor = "text-muted-foreground";

          if (status === SignatureStatus.DONE) {
            statusIcon = <CheckCircle2 className="h-5 w-5 text-emerald-400" />;
            statusText = "Signed";
            statusColor = "text-emerald-400";
          } else if (status === SignatureStatus.PENDING_REWORK) {
            statusIcon = <Clock className="h-5 w-5 text-amber-400" />;
            statusText = "Rework";
            statusColor = "text-amber-400";
          }

          return (
            <div key={exp.id} className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-surface2/30 transition-colors">
              <div className="flex items-center gap-4">
                <div className="flex flex-col items-center justify-center w-8 h-8 rounded bg-surface2 border border-border/50 shrink-0 text-sm font-bold text-muted-foreground">
                  {exp.experiment_number}
                </div>
                <div>
                  <h4 className="font-semibold text-sm text-foreground">{exp.title}</h4>
                  {record?.date_conducted && (
                    <div className="text-xs text-muted-foreground mt-0.5">
                      Conducted: {new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(record.date_conducted))}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-4 sm:justify-end">
                {record?.marks !== null && record?.marks !== undefined && (
                  <Badge variant="outline" className="bg-surface2 border-border text-foreground font-mono">
                    {record.marks} pts
                  </Badge>
                )}
                <div className={`flex items-center gap-1.5 text-sm font-medium ${statusColor}`}>
                  {statusIcon}
                  <span className="hidden sm:inline">{statusText}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </GlassCard>
  );
}
