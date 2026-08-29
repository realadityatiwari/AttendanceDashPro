import { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";

interface MetricCardProps {
  label: string;
  value: number | string;
  icon: LucideIcon;
  hint?: string;
}

/**
 * Compact key-metric card for the HEAD_ADMIN dashboard (Phase 24.2).
 * Values come from the backend read model — presentation only.
 */
export function MetricCard({ label, value, icon: Icon, hint }: MetricCardProps) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums text-foreground">
            {value}
          </p>
          {hint && (
            <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
              {hint}
            </p>
          )}
        </div>
        <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Icon className="size-4" aria-hidden="true" />
        </span>
      </div>
    </Card>
  );
}
