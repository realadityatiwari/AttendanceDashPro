"use client";

import Link from "next/link";
import { AcademicEventResponse, CalendarDayItem, ClassType, EventType } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/shared/GlassCard";
import { formatLongDate, parseLocalDate } from "@/lib/date";
import { CalendarDays, CalendarRange, Info } from "lucide-react";

const EVENT_DATE_FORMATTER = new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short", year: "numeric" });

function formatEventDate(value: string): string {
  return EVENT_DATE_FORMATTER.format(parseLocalDate(value));
}

function humanizeEventType(type: string): string {
  return type.toLowerCase().replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function classTypeLabel(type: ClassType | null): string | null {
  if (type === ClassType.LECTURE) return "Lecture";
  if (type === ClassType.TUTORIAL) return "Tutorial";
  if (type === ClassType.PRACTICAL || type === ClassType.PRACTICAL2) return "Practical";
  return null;
}

const HOLIDAY_TYPES = new Set([EventType.PUBLIC_HOLIDAY, EventType.INSTITUTE_HOLIDAY, EventType.FESTIVAL_HOLIDAY]);

/**
 * Detail card for the selected calendar day. Every value is rendered directly
 * from the backend read model — no weekday, holiday, or session calculations.
 */
export function DayDetail({ day }: { day: CalendarDayItem }) {
  const sessionLabel =
    day.session_count === 0
      ? "No classes"
      : `${day.session_count} ${day.session_count === 1 ? "class" : "classes"}`;

  return (
    <GlassCard className="flex h-full flex-col p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-base font-semibold text-foreground">{formatLongDate(day.date)}</h3>
        <div className="flex flex-wrap gap-1.5">
          {day.is_working_day ? (
            <Badge variant="success">Working day</Badge>
          ) : (
            <Badge variant="neutral">Non-working day</Badge>
          )}
          {day.is_teaching_day && <Badge variant="primary">Teaching day</Badge>}
        </div>
      </div>

      {day.substitution_schedule_override && (
        <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-accent">
          <CalendarRange className="size-3.5 shrink-0" aria-hidden />
          Follows {day.substitution_schedule_override.toLowerCase()} schedule
        </p>
      )}

      {!day.is_working_day && day.non_working_reason && (
        <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          <Info className="size-3.5 shrink-0" aria-hidden />
          {day.non_working_reason}
        </p>
      )}

      <div className="mt-4 flex items-center justify-between rounded-lg border border-border bg-muted/40 px-3 py-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Scheduled classes
        </span>
        <span className="text-sm font-bold text-foreground">{sessionLabel}</span>
      </div>

      <div className="mt-4 flex min-h-0 flex-1 flex-col">
        <div className="mb-2 flex items-center justify-between">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Events</h4>
          <Link
            href="/tools/events"
            className="rounded-sm text-xs font-medium text-accent underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            View all
          </Link>
        </div>
        {day.events.length === 0 ? (
          <p className="text-sm text-muted-foreground">No academic events on this day.</p>
        ) : (
          <ul className="space-y-2">
            {day.events.map(event => (
              <EventRow key={event.id} event={event} />
            ))}
          </ul>
        )}
      </div>
    </GlassCard>
  );
}

function EventRow({ event }: { event: AcademicEventResponse }) {
  const isHoliday = HOLIDAY_TYPES.has(event.event_type);
  const range =
    event.start_date === event.end_date
      ? formatEventDate(event.start_date)
      : `${formatEventDate(event.start_date)} – ${formatEventDate(event.end_date)}`;
  const classLabel = classTypeLabel(event.class_type);

  return (
    <li className="rounded-lg border-l-2 border-accent bg-muted/30 px-3 py-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-sm font-medium text-foreground">{humanizeEventType(event.event_type)}</span>
        {isHoliday && <Badge variant="success" className="h-4 py-0 text-[10px]">Holiday</Badge>}
        {classLabel && (
          <Badge variant="outline" className="h-4 py-0 text-[10px] uppercase tracking-wider">{classLabel}</Badge>
        )}
      </div>
      <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
        <CalendarDays className="size-3 shrink-0" aria-hidden />
        {range}
      </p>
    </li>
  );
}
