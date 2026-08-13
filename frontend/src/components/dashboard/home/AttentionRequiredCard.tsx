import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { AttentionItem } from "@/types/api";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPct } from "@/lib/date";
import { attendanceStatusVariant } from "./status";

interface AttentionRequiredCardProps {
  items: AttentionItem[];
}

export function AttentionRequiredCard({ items }: AttentionRequiredCardProps) {
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle>Attention Required</CardTitle>
      </CardHeader>

      <CardContent className="p-0">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <div className="flex size-9 items-center justify-center rounded-full bg-success/15">
              <AlertTriangle className="size-4 text-success" />
            </div>
            <h3 className="mt-3 text-sm font-medium text-foreground">
              All subjects on track
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              No subject is below the attendance target right now.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-border/60">
            {items.map((item) => (
              <li key={item.subject_code} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">
                      {item.subject_code}
                    </span>
                    <Badge variant={attendanceStatusVariant(item.status)}>
                      {item.status}
                    </Badge>
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">
                    {item.subject_name}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <div className="text-sm font-semibold tabular-nums text-foreground">
                    {formatPct(item.current_pct)}
                  </div>
                  {item.forecast_pct !== null && (
                    <div className="text-[10px] tabular-nums text-muted-foreground">
                      forecast {formatPct(item.forecast_pct)}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      <CardFooter className="justify-end">
        <Button variant="ghost" size="sm" render={<Link href="/tools/laboratory" />}>
          View Strategy
        </Button>
      </CardFooter>
    </Card>
  );
}

export function AttentionRequiredCardSkeleton() {
  return (
    <Card>
      <CardHeader className="border-b">
        <Skeleton className="h-5 w-40" />
      </CardHeader>
      <CardContent className="p-4">
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}