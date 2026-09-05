import { CalendarDays, CheckCircle2 } from "lucide-react";
import { TodaySection, DashboardClassStatus } from "@/types/api";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatLongDate } from "@/lib/date";
import { classStatusLabel, classStatusVariant, classTypeLabel } from "./status";

interface TodayAttendanceCardProps {
  today: TodaySection;
}

export function TodayAttendanceCard({ today }: TodayAttendanceCardProps) {
  const { classes } = today;
  const pendingCount = classes.filter(
    (c) => c.status === DashboardClassStatus.PENDING
  ).length;

  return (
    <Card className="h-full">
      <CardHeader className="border-b">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>Today&apos;s Attendance</CardTitle>
            <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
              <CalendarDays className="size-3.5" />
              {formatLongDate(today.date)}
            </p>
          </div>
          {today.is_teaching_day && (
            <Badge variant="success">
              <span className="size-1.5 rounded-full bg-current" />
              {today.is_working_day ? "LIVE" : "TEACHING DAY"}
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-0">
        {classes.length === 0 ? (
          <div className="p-8 text-center">
            <h3 className="text-base font-medium text-foreground">No Classes Today</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {today.is_working_day
                ? "Nothing scheduled for today."
                : "It's a non-working day."}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-border/60">
            {classes.map((cls) => (
              <li key={cls.session_id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">
                      {cls.subject_code}
                    </span>
                    <Badge variant="outline" className="h-4 px-1.5 py-0 leading-none text-[11px] uppercase tracking-wider">
                      {classTypeLabel(cls.class_type)}
                    </Badge>
                    {cls.is_extra && (
                      <Badge variant="neutral" className="h-4 px-1.5 py-0 leading-none text-[11px] uppercase tracking-wider">
                        Extra
                      </Badge>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">
                    {cls.subject_name}
                  </p>
                </div>
                <Badge variant={classStatusVariant(cls.status)} className="shrink-0 capitalize">
                  {cls.status === DashboardClassStatus.ATTENDED && (
                    <CheckCircle2 className="size-3" />
                  )}
                  {classStatusLabel(cls.status)}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      <CardFooter className="justify-between">
        <span className="text-xs text-muted-foreground">
          {today.attended} of {today.total} classes attended
        </span>
        {pendingCount > 0 && (
          <span className="text-xs text-muted-foreground">
            {pendingCount} pending
          </span>
        )}
      </CardFooter>
    </Card>
  );
}

export function TodayAttendanceCardSkeleton() {
  return (
    <Card>
      <CardHeader className="border-b">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="mt-1 h-3 w-48" />
      </CardHeader>
      <CardContent className="p-4">
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}