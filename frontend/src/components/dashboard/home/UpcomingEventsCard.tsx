import Link from "next/link";
import { CalendarDays } from "lucide-react";
import { UpcomingEventItem } from "@/types/api";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDayHeader } from "@/lib/date";
import { classTypeLabel, eventTypeLabel } from "./status";

interface UpcomingEventsCardProps {
  events: UpcomingEventItem[];
}

export function UpcomingEventsCard({ events }: UpcomingEventsCardProps) {
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle>Upcoming Events</CardTitle>
      </CardHeader>

      <CardContent className="p-0">
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <CalendarDays className="size-8 text-muted-foreground" />
            <h3 className="mt-3 text-sm font-medium text-foreground">
              No upcoming events
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              The academic calendar has no scheduled events yet.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-border/60">
            {events.map((event) => (
              <li key={event.id} className="flex items-center gap-3 px-4 py-3">
                <div className="flex w-12 shrink-0 flex-col items-center rounded-md border border-border bg-muted/40 py-1.5">
                  <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    {formatDayHeader(event.start_date).split(" ")[1]}
                  </span>
                  <span className="text-lg font-bold tabular-nums leading-tight text-foreground">
                    {formatDayHeader(event.start_date).split(" ")[0]}
                  </span>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">
                    {event.subject_name ?? eventTypeLabel(event.event_type)}
                  </p>
                  <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
                    <Badge variant="outline" className="h-4 px-1.5 py-0 text-[10px] uppercase tracking-wider">
                      {eventTypeLabel(event.event_type)}
                    </Badge>
                    {event.subject_code && (
                      <span className="text-xs text-muted-foreground">
                        {event.subject_code}
                        {event.class_type ? ` · ${classTypeLabel(event.class_type)}` : ""}
                      </span>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>

      <CardFooter className="justify-end">
        <Button variant="ghost" size="sm" nativeButton={false} render={<Link href="/tools/events" />}>
          View All Events
        </Button>
      </CardFooter>
    </Card>
  );
}

export function UpcomingEventsCardSkeleton() {
  return (
    <Card>
      <CardHeader className="border-b">
        <Skeleton className="h-5 w-36" />
      </CardHeader>
      <CardContent className="p-4">
        <div className="space-y-3">
          {[0, 1].map((i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}