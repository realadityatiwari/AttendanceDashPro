"use client";

import { useMemo, useRef, useState } from "react";
import { useSWRConfig } from "swr";
import { useEvents, useProfile, useEventMutations, calendarMonthKey } from "@/hooks/useApi";
import { AcademicEventResponse, EventsParams, EventType } from "@/types/api";
import { PageHeader } from "@/components/shared/PageHeader";
import { EmptyState } from "@/components/shared/EmptyState";
import { ErrorState } from "@/components/shared/ErrorState";
import { DateInput } from "@/components/shared/DateInput";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EventRow } from "@/components/events/EventRow";
import { humanizeEventType } from "@/components/events/eventRules";
import { EventFormDialog } from "@/components/events/EventFormDialog";
import { canStudentMutateEventType } from "@/components/events/eventRules";
import { useToast } from "@/components/feedback/toast";
import { getLocalDateString } from "@/lib/date";
import { AlertCircle, CalendarX2, Plus } from "lucide-react";

type ActiveFilter = "active" | "inactive";

const TYPE_OPTIONS = Object.values(EventType);

/**
 * Academic Events page (Phase 6.4 read experience, frozen) + the event
 * management surface (Phase 6.5 + attendance-spec alignment).
 *
 * The backend /events endpoint is authoritative for event existence, dates,
 * types, holiday metadata, class-type metadata, and active state. Per the
 * product spec, events are student-adjustable: students may add/remove the
 * flexible subject-scoped types (extras, cancellations, surprise quizzes) for
 * their own enrolled subjects; global/closure events stay admin-only. Edit/
 * deactivate controls render only for events the current user may mutate
 * (frontend visibility is UX only; the backend enforces authorization on
 * every mutation).
 */
export default function EventsPage() {
  const todayStr = getLocalDateString();
  const { profile } = useProfile();
  const isAdmin = profile?.role === "ADMIN";

  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("active");
  const [typeFilter, setTypeFilter] = useState<EventType | "">("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [formOpen, setFormOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<AcademicEventResponse | null>(null);

  // Revalidate the current calendar month after an event mutation so the
  // calendar reflects the change without a separate event cache.
  // Perf batch 1: revalidate by KEY (same cache key the calendar page uses)
  // instead of mounting useCalendarMonth() just for its mutate handle — the
  // mounted hook fetched the full month read model on every Events visit even
  // though this page never renders it.
  const now = new Date();
  const { mutate: globalMutate } = useSWRConfig();
  const mutateCalendar = () => globalMutate(calendarMonthKey(now.getFullYear(), now.getMonth() + 1));

  // Guard against an inverted server-side range (which the API rejects with
  // 422) — show a hint instead of letting the request fail.
  const datesValid = !dateFrom || !dateTo || dateFrom <= dateTo;

  const params: EventsParams = useMemo(
    () => ({
      active: activeFilter === "active" ? true : false,
      date_from: datesValid ? dateFrom || undefined : undefined,
      date_to: datesValid ? dateTo || undefined : undefined,
    }),
    [activeFilter, dateFrom, dateTo, datesValid]
  );

  const { events, isLoading, isError, mutate } = useEvents(params);
  const { deactivateEvent } = useEventMutations();
  const { toast } = useToast();
  // UI-009: in-flight guard so a rapid double-click on the inline Confirm can
  // never submit the deactivation twice. The inline Confirm/Cancel interaction
  // is retained per D-11 (structurally sound).
  const deactivatingRef = useRef(false);

  const handleSaved = () => {
    setFormOpen(false);
    setEditingEvent(null);
    mutate();
    mutateCalendar();
    toast({ variant: "success", title: "Event saved" });
  };

  const openCreate = () => {
    setEditingEvent(null);
    setFormOpen(true);
  };

  const openEdit = (event: AcademicEventResponse) => {
    setEditingEvent(event);
    setFormOpen(true);
  };

  const handleDeactivate = async (event: AcademicEventResponse) => {
    if (deactivatingRef.current) return;
    deactivatingRef.current = true;
    try {
      await deactivateEvent(event.id);
      mutate();
      mutateCalendar();
      toast({ variant: "success", title: "Event deactivated" });
    } catch (err: unknown) {
      // apiFetch translates network-level failures ("Failed to fetch") into an
      // actionable message; HTTP errors keep their backend-provided detail.
      // UI-009: error feedback via the application toast layer — the native
      // browser alert is gone; confirmation semantics are unchanged (Phase 3).
      const message = err instanceof Error ? err.message : "Unable to deactivate the event.";
      toast({
        variant: "error",
        title: "Couldn't deactivate the event",
        description: `${message} Please try again.`,
      });
    } finally {
      deactivatingRef.current = false;
    }
  };

  const hasFilters = activeFilter !== "active" || Boolean(typeFilter || dateFrom || dateTo);

  const resetFilters = () => {
    setActiveFilter("active");
    setTypeFilter("");
    setDateFrom("");
    setDateTo("");
  };

  // Event-type filter is presentation-only over the single server-fetched set.
  const filtered = useMemo(() => {
    const base = events ?? [];
    if (!typeFilter) return base;
    return base.filter(e => e.event_type === typeFilter);
  }, [events, typeFilter]);

  // Presentation grouping using local dates and the backend-provided ranges:
  // today inside [start, end] -> TODAY; end after today -> UPCOMING; else PAST.
  const groups = useMemo(() => {
    const today: AcademicEventResponse[] = [];
    const upcoming: AcademicEventResponse[] = [];
    const past: AcademicEventResponse[] = [];
    for (const event of filtered) {
      if (event.start_date <= todayStr && todayStr <= event.end_date) today.push(event);
      else if (event.end_date > todayStr) upcoming.push(event);
      else past.push(event);
    }
    const byStartAsc = (a: AcademicEventResponse, b: AcademicEventResponse) =>
      a.start_date.localeCompare(b.start_date) || a.end_date.localeCompare(b.end_date);
    const byStartDesc = (a: AcademicEventResponse, b: AcademicEventResponse) =>
      b.start_date.localeCompare(a.start_date) || b.end_date.localeCompare(a.end_date);
    today.sort(byStartAsc);
    upcoming.sort(byStartAsc);
    past.sort(byStartDesc);
    return { today, upcoming, past };
  }, [filtered, todayStr]);

  return (
    <div className="flex w-full flex-1 flex-col gap-6 py-6">
      <PageHeader
        title="Academic Events"
        description="Upcoming, current, and past academic events for your program."
      />

      <Card className="border-warning/30 bg-warning/10 p-4">
        <p className="flex items-start gap-2 text-sm text-warning">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {isAdmin
            ? "Admin view: you can add, edit, and deactivate any academic event. Deactivation is safe — the event can be re-enabled later."
            : "Events are flexible: record what actually happened by adding extra classes, cancellations, or surprise quizzes for your enrolled subjects. Holidays and global events are managed by administrators."}
        </p>
      </Card>

      {/* Event management surface (Phase 6.5 + attendance-spec alignment).
          Admins manage every event type; students add/remove the flexible
          subject-scoped types. The dialog exposes only the types the current
          role may create, and the backend enforces authorization.
          UIA-033: the banner above already explains what can be added and who
          manages what, so this card is the action itself — heading + button,
          no third restatement of the same explanation. */}
      <Card className="flex items-center justify-between gap-3 border-border p-4">
        <h2 className="text-sm font-semibold text-foreground">Manage events</h2>
        <Button size="sm" onClick={openCreate} className="shrink-0">
          <Plus className="size-3.5" aria-hidden />
          Add Event
        </Button>
      </Card>

      {/* Filters */}
      <Card className="flex flex-col gap-3 border-border p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Filters</span>
          {/* UIA-030: the per-component sm:h-7 override is removed — the
              shared button size enforces the 40px touch / 32px pointer
              floor. */}
          {hasFilters && (
            <Button variant="ghost" size="sm" className="text-xs" onClick={resetFilters}>
              Reset
            </Button>
          )}
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1">
            <label className="text-2xs uppercase tracking-wider text-muted-foreground" htmlFor="events-type">
              Event type
            </label>
            <Select
              id="events-type"
              value={typeFilter}
              onChange={e => setTypeFilter(e.target.value as EventType | "")}
            >
              <option value="">All types</option>
              {TYPE_OPTIONS.map(type => (
                <option key={type} value={type}>{humanizeEventType(type)}</option>
              ))}
            </Select>
          </div>
          <div className="flex flex-col gap-1">              <label className="text-2xs uppercase tracking-wider text-muted-foreground" htmlFor="events-active">
              Status
            </label>
            <Select
              id="events-active"
              value={activeFilter}
              onChange={e => setActiveFilter(e.target.value as ActiveFilter)}
            >
              <option value="active">Active events</option>
              <option value="inactive">Inactive events</option>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-2xs uppercase tracking-wider text-muted-foreground" htmlFor="events-from">
              From
            </label>
            {/* UIA-025: native date input + formatted companion. */}
            <DateInput
              id="events-from"
              value={dateFrom}
              onValueChange={setDateFrom}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-2xs uppercase tracking-wider text-muted-foreground" htmlFor="events-to">
              To
            </label>
            <DateInput
              id="events-to"
              value={dateTo}
              onValueChange={setDateTo}
            />
          </div>
        </div>
        {!datesValid && (
          <p className="text-xs text-destructive">From date must be on or before the To date.</p>
        )}
      </Card>

      {/* Error — shared ErrorState (25.UX-1); the former ad-hoc red card is
          gone, retry semantics unchanged. */}
      {isError ? (
        <ErrorState
          title="Unable to load events"
          message="Academic events could not be fetched from the server. Check your connection and try again."
          onRetry={() => mutate()}
        />
      ) : // Loading — never flash a fake empty state.
      isLoading || !events ? (
        <div className="flex flex-col gap-6">
          {[0, 1, 2].map(section => (
            <div key={section} className="flex flex-col gap-3">
              <Skeleton className="h-4 w-32" />
              {Array.from({ length: 2 }).map((_, i) => (
                <Skeleton key={i} className="h-20 rounded-xl" />
              ))}
            </div>
          ))}
        </div>
      ) : // Empty — differentiate "no events at all" from "no events match the filters".
      filtered.length === 0 ? (
        <EmptyState
          title={hasFilters ? "No events match the selected filters" : "No events scheduled"}
          message={
            hasFilters
              ? "Try adjusting the event type, status, or date range."
              : "There are no academic events in the calendar right now."
          }
          icon={<CalendarX2 className="mb-4 size-10 text-muted-foreground" aria-hidden />}
        />
      ) : (
        <div className="flex flex-col gap-8">
          <EventSection
            id="events-upcoming"
            title="Upcoming"
            count={groups.upcoming.length}
            events={groups.upcoming}
            emptyLabel="No upcoming events."
            canEdit={isAdmin}
            isAdmin={isAdmin}
            onEdit={openEdit}
            onDeactivate={handleDeactivate}
          />
          <EventSection
            id="events-today"
            title="Today"
            count={groups.today.length}
            events={groups.today}
            emptyLabel="No events happening today."
            isTodaySection
            canEdit={isAdmin}
            isAdmin={isAdmin}
            onEdit={openEdit}
            onDeactivate={handleDeactivate}
          />
          <EventSection
            id="events-past"
            title="Past"
            count={groups.past.length}
            events={groups.past}
            emptyLabel="No past events."
            canEdit={isAdmin}
            isAdmin={isAdmin}
            onEdit={openEdit}
            onDeactivate={handleDeactivate}
          />
        </div>
      )}

      <EventFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        event={editingEvent}
        onSaved={handleSaved}
        isAdmin={isAdmin}
      />
    </div>
  );
}

function EventSection({
  id,
  title,
  count,
  events,
  emptyLabel,
  isTodaySection = false,
  canEdit,
  isAdmin,
  onEdit,
  onDeactivate,
}: {
  id: string;
  title: string;
  count: number;
  events: AcademicEventResponse[];
  emptyLabel: string;
  isTodaySection?: boolean;
  /** Admins may edit every event; students only the flexible subject-scoped
      types they are allowed to mutate (backend remains authoritative). */
  canEdit: boolean;
  isAdmin: boolean;
  onEdit?: (event: AcademicEventResponse) => void;
  onDeactivate?: (event: AcademicEventResponse) => void;
}) {
  return (
    <section aria-labelledby={id}>
      <div className="mb-3 flex items-center gap-2">
        <h2 id={id} className="text-sm font-semibold uppercase tracking-wider text-foreground">
          {title}
        </h2>
        <Badge variant="neutral" size="xs" className="px-1.5">{count}</Badge>
      </div>
      {events.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyLabel}</p>
      ) : (
        <div className="flex flex-col gap-3">
          {events.map(event => {
            const mutable = canEdit || (!isAdmin && canStudentMutateEventType(event.event_type));
            return (
              <EventRow
                key={event.id}
                event={event}
                isToday={isTodaySection}
                onEdit={mutable ? onEdit : undefined}
                onDeactivate={mutable ? onDeactivate : undefined}
              />
            );
          })}
        </div>
      )}
    </section>
  );
}
