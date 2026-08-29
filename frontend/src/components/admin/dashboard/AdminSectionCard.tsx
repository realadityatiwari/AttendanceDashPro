import { LucideIcon } from "lucide-react";
import { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export interface StatRow {
  label: string;
  value: string | number;
}

interface AdminSectionCardProps {
  title: string;
  icon: LucideIcon;
  description?: string;
  rows: StatRow[];
  children?: ReactNode;
}

/**
 * Generic titled statistics card for the HEAD_ADMIN dashboard (Phase 24.2).
 * Renders label/value rows (backend-derived; presentation only) plus any
 * optional extra content below the rows.
 */
export function AdminSectionCard({
  title,
  icon: Icon,
  description,
  rows,
  children,
}: AdminSectionCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
          {title}
        </CardTitle>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </CardHeader>
      <CardContent>
        <dl className="divide-y divide-border/60">
          {rows.map((row) => (
            <div
              key={row.label}
              className="flex items-center justify-between gap-3 py-2"
            >
              <dt className="text-sm text-muted-foreground">{row.label}</dt>
              <dd className="text-sm font-semibold tabular-nums text-foreground">
                {row.value}
              </dd>
            </div>
          ))}
        </dl>
        {children}
      </CardContent>
    </Card>
  );
}