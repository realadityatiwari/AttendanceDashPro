import { AlertTriangle, Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AdminDashboardWarning } from "@/types/api";

interface AdminWarningsCardProps {
  warnings: AdminDashboardWarning[];
}

/**
 * Operational data-quality warnings for the HEAD_ADMIN dashboard
 * (Phase 24.2). All warnings are factual — no defaults fabricated, no
 * repairs suggested. Each warning encodes a severity (info / warning)
 * and a message describing the objectively detectable condition.
 */
export function AdminWarningsCard({ warnings }: AdminWarningsCardProps) {
  if (warnings.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="size-4 text-warning" aria-hidden="true" />
          Operational status
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {warnings.map((w) => {
          const isWarning = w.severity === "warning";
          return (
            <div
              key={w.code}
              className="flex items-start gap-3 rounded-lg border border-border p-3"
            >
              <span className="mt-0.5 shrink-0">
                {isWarning ? (
                  <AlertTriangle className="size-4 text-warning" aria-hidden="true" />
                ) : (
                  <Info className="size-4 text-muted-foreground" aria-hidden="true" />
                )}
              </span>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <Badge variant={isWarning ? "warning" : "neutral"}>
                    {w.code}
                  </Badge>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">
                  {w.message}
                </p>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}