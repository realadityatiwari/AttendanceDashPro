"use client";

import Link from "next/link";
import { useState } from "react";
import { AcademicEventResponse, ClassType, EventType } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { parseLocalDate } from "@/lib/date";
import { CalendarDays, CalendarRange, Info, Pencil, Power } from "lucide-react";
import { cn } from "@/lib/utils";

const EVENT_DATE_FORMATTER = new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short", year: "numeric" });

export function formatEventDate(value: string): string {
  return EVENT_DATE_FORMATTER.format(parseLocalDate(value));
}

// Humanizes any event type string — including types unknown to the current
// enum — so an unknown/future type renders a readable label instead of crashing.
export function humanizeEventType(type: string): string {
  return type.toLowerCase().replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

export function classTypeLabel(type: ClassType | null): string | null {
  if (type === ClassType.LECTURE) return "Lecture";
  if (type === ClassType.TUTORIAL) return "Tutorial";
  if (type === ClassType.PRACTICAL || type === ClassType.PRACTICAL2) return "Practical";
  return null;
}

const HOLIDAY_TYPES = new Set([EventType.PUBLIC_HOLIDAY, EventType.INSTITUTE_HOLIDAY, EventType.FESTIVAL_HOLIDAY]);

interface EventRowProps {
  event: AcademicEventResponse;
  isToday?: boolean;
  /** Admin controls (Phase 6.5) — rendered only when provided by the page. */
  onEdit?: (event: AcademicEventResponse) => void;
  onDeactivate?: (event: AcademicEventResponse) => void;
}

/**
 * Compact read-only event row. Every label is derived directly from the
 * backend AcademicEventResponse — no holiday/working-day/session semantics are
 * computed here. Admin actions are optional props; the page decides whether
 * they are shown (backend role), and the backend remains authoritative.
 */
export function EventRow({ event, isToday = false, onEdit, onDeactivate }: EventRowProps) {
  const [confirming, setConfirming] = useState(false);
  const isAdmin = onEdit !== undefined || onDeactivate !== undefined;
  const title = humanizeEventType(event.event_type);
  const isHoliday = HOLIDAY_TYPES.has(event.event_type);
  const isExtra = event.event_type.startsWith("EXTRA_");
  // Phase 9.1: LAB_CANCELLED renders the same Cancelled treatment as
  // CLASS_CANCELLED (it is the practical-scoped cancellation event).
  const isCancelled = event.event_type === EventType.CLASS_CANCELLED
    || event.event_type === EventType.LAB_CANCELLED;
  const classLabel = classTypeLabel(event.class_type);

  const dateRange =
    event.start_date === event.end_date
      ? formatEventDate(event.start_date)
      : `${formatEventDate(event.start_date)} – ${formatEventDate(event.end_date)}`;

  return (
    <Card
      className={cn(
        "p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3",
        !event.active && "opacity-60 grayscale"
      )}
    >
      <div className="flex items-center gap-4 min-w-0">
        <div className="flex w-12 shrink-0 flex-col items-center justify-center rounded-full border border-border bg-muted py-1.5">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {formatEventDate(event.start_date).split(" ")[1]}
          </span>
          <span className="text-sm font-bold leading-none text-foreground">
            {formatEventDate(event.start_date).split(" ")[0]}
          </span>
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-foreground">{title}</h3>
            {isToday && <Badge variant="primary" className="h-4 py-0 text-[10px]">Today</Badge>}
            {isHoliday && <Badge variant="success" className="h-4 py-0 text-[10px]">Holiday</Badge>}
            {isExtra && <Badge variant="warning" className="h-4 py-0 text-[10px]">Extra</Badge>}
            {isCancelled && <Badge variant="neutral" className="h-4 py-0 text-[10px]">Cancelled</Badge>}
            {classLabel && (
              <Badge variant="outline" className="h-4 py-0 text-[10px] uppercase tracking-wider">{classLabel}</Badge>
            )}
            {!event.active && <Badge variant="neutral" className="h-4 py-0 text-[10px]">Inactive</Badge>}
          </div>
          <p className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
            <CalendarDays className="size-3.5 shrink-0" aria-hidden />
            {dateRange}
          </p>
          {event.substitution_schedule_override && (
            <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
              <Info className="size-3 shrink-0" aria-hidden />
              Follows {event.substitution_schedule_override.toLowerCase()} schedule
            </p>
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        {isAdmin && (
          <>
            {onEdit && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 gap-1 px-2 text-xs"
                onClick={() => onEdit(event)}
              >
                <Pencil className="size-3.5" aria-hidden />
                Edit
              </Button>
            )}
            {onDeactivate && event.active && (
              confirming ? (
                <>
                  <Button
                    variant="destructive"
                    size="sm"
                    className="h-7 gap-1 px-2 text-xs"
                    onClick={() => { setConfirming(false); onDeactivate(event); }}
                  >
                    Confirm
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setConfirming(false)}
                  >
                    Cancel
                  </Button>
                </>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1 px-2 text-xs text-muted-foreground hover:text-destructive"
                  onClick={() => setConfirming(true)}
                  title="Deactivate this event (safe deactivation, reversible via edit)"
                >
                  <Power className="size-3.5" aria-hidden />
                  Deactivate
                </Button>
              )
            )}
          </>
        )}
        <Link
          href="/calendar"
          aria-label="Open the calendar"
          title="View in calendar"
          className="flex items-center gap-1 rounded-md text-xs font-medium text-accent underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
        >
          <CalendarRange className="size-3.5" aria-hidden />
          Calendar
        </Link>
      </div>
    </Card>
  );
}
