import { CalendarDays } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shared/EmptyState";
import { EventsOverview } from "@/types/api";
import { formatShortDate } from "@/lib/date";

interface AdminEventsCardProps {
  events: EventsOverview;
}

function eventTypeLabel(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/**
 * Events + quizzes overview for the HEAD_ADMIN dashboard (Phase 24.2).
 * Upcoming events are the active QUIZ_DAY/closure/override events ending at
 * or after today (authoritative academic_events rows). Presentation only.
 */
export function AdminEventsCard({ events }: AdminEventsCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarDays className="size-4 text-muted-foreground" aria-hidden="true" />
          Events &amp; quizzes
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="divide-y divide-border/60">
          <div className="flex items-center justify-between gap-3 py-2">
            <dt className="text-sm text-muted-foreground">Active events</dt>
            <dd className="text-sm font-semibold tabular-nums text-foreground">
              {events.total_active}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3 py-2">
            <dt className="text-sm text-muted-foreground">
              Upcoming (active, ending today or later)
            </dt>
            <dd className="text-sm font-semibold tabular-nums text-foreground">
              {events.upcoming_active}
            </dd>
          </div>
        </dl>

        <div className="mt-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Next events
          </p>
          {events.upcoming.length === 0 ? (
            <EmptyState
              title="No upcoming events"
              message="No active academic events are scheduled from today onward."
            />
          ) : (
            <ul className="mt-2 divide-y divide-border/60 rounded-lg border border-border">
              {events.upcoming.map((event) => (
                <li
                  key={event.id}
                  className="flex flex-col gap-1 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <Badge variant="secondary">
                      {eventTypeLabel(event.event_type)}
                    </Badge>
                    {event.subject_code ? (
                      <span className="truncate font-mono text-xs text-foreground">
                        {event.subject_code}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        Global
                      </span>
                    )}
                    {event.elective_slot && (
                      <Badge variant="neutral">{event.elective_slot}</Badge>
                    )}
                  </div>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                    {formatShortDate(event.start_date)}
                    {event.end_date !== event.start_date
                      ? ` – ${formatShortDate(event.end_date)}`
                      : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  );
}