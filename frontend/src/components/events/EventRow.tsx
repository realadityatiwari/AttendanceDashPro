"use client";

import Link from "next/link";
import { useState } from "react";
import { AcademicEventResponse, EventType } from "@/types/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatDateParts, formatDateMedium } from "@/lib/date";
import { classTypeLabel, humanizeEventType, isHolidayEventType } from "@/components/events/eventRules";
import { CalendarDays, CalendarRange, Info, Pencil, Power } from "lucide-react";
import { cn } from "@/lib/utils";

// D-09: deterministic English dates — medium for ranges, short for chips.
function formatEventDate(value: string): string {
  return formatDateMedium(value);
}

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
  const isHoliday = isHolidayEventType(event.event_type);
  const isExtra = event.event_type.startsWith("EXTRA_");
  // Phase 9.1: LAB_CANCELLED renders the same Cancelled treatment as
  // CLASS_CANCELLED (it is the practical-scoped cancellation event).
  const isCancelled = event.event_type === EventType.CLASS_CANCELLED
    || event.event_type === EventType.LAB_CANCELLED;
  const classLabel = classTypeLabel(event.class_type);

  // UIA-032: the round date tile already carries the start date for a
  // single-day event — the full date text is only rendered for ranges, where
  // the tile alone cannot express the end date. No information is lost.
  const isRange = event.start_date !== event.end_date;
  const dateRange = isRange
    ? `${formatEventDate(event.start_date)} – ${formatEventDate(event.end_date)}`
    : null;

  return (
    <Card
      className={cn(
        "p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3",
        !event.active && "opacity-60 grayscale"
      )}
    >
      <div className="flex items-center gap-4 min-w-0">
        <div className="flex w-12 shrink-0 flex-col items-center justify-center rounded-full border border-border bg-muted py-1.5">
          <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
            {formatDateParts(event.start_date).month}
          </span>
          <span className="text-sm font-bold leading-none text-foreground">
            {formatDateParts(event.start_date).day}
          </span>
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold text-foreground">{title}</h3>
            {isToday && <Badge variant="primary" className="h-4 py-0 leading-none text-[11px]">Today</Badge>}
            {isHoliday && <Badge variant="success" className="h-4 py-0 leading-none text-[11px]">Holiday</Badge>}
            {isExtra && <Badge variant="warning" className="h-4 py-0 leading-none text-[11px]">Extra</Badge>}
            {isCancelled && <Badge variant="neutral" className="h-4 py-0 leading-none text-[11px]">Cancelled</Badge>}
            {classLabel && (
              <Badge variant="outline" className="h-4 py-0 leading-none text-[11px] uppercase tracking-wider">{classLabel}</Badge>
            )}
            {!event.active && <Badge variant="neutral" className="h-4 py-0 leading-none text-[11px]">Inactive</Badge>}
          </div>
          {dateRange && (
            <p className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
              <CalendarDays className="size-3.5 shrink-0" aria-hidden />
              {dateRange}
            </p>
          )}
          {/* Phase 22.4: the effective subject of the event as resolved for
              the authenticated student (their selected elective for
              Departmental Elective slot events; null for global events). */}
          {event.resolved_subject_code && (
            <p className="mt-1 flex items-center gap-1.5 text-xs font-medium text-foreground/80">
              <span className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[11px] tracking-wide">
                {event.resolved_subject_code}
              </span>
              {event.resolved_subject_name}
            </p>
          )}
          {event.substitution_schedule_override && (
            <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
              <Info className="size-3 shrink-0" aria-hidden />
              Follows {event.substitution_schedule_override.toLowerCase()} schedule
            </p>
          )}
          {event.note && (
            <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
              <Info className="size-3 shrink-0" aria-hidden />
              {event.note}
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap shrink-0 items-center gap-1.5 self-start sm:self-auto">
        {/* 25.UX-1: the former per-button h-7 override is removed — the size
            primitive enforces the 40px touch / 32px pointer floor (UIA-030),
            matching the identical override removal in TrackSessionCard. */}
        {isAdmin && (
          <>
            {onEdit && (
              <Button
                variant="ghost"
                size="sm"
                className="gap-1 px-2 text-xs"
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
                    className="gap-1 px-2 text-xs"
                    onClick={() => { setConfirming(false); onDeactivate(event); }}
                  >
                    Confirm
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="px-2 text-xs"
                    onClick={() => setConfirming(false)}
                  >
                    Cancel
                  </Button>
                </>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1 px-2 text-xs text-muted-foreground hover:text-destructive"
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
          className="flex items-center gap-1 rounded-md text-xs font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
        >
          <CalendarRange className="size-3.5" aria-hidden />
          Calendar
        </Link>
      </div>
    </Card>
  );
}
