"use client";

import { useMemo, useState } from "react";
import { useEvents, useProfile, useCalendarMonth, useEventMutations } from "@/hooks/useApi";
import { AcademicEventResponse, EventsParams, EventType } from "@/types/api";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { EventRow, humanizeEventType } from "@/components/events/EventRow";
import { EventFormDialog } from "@/components/events/EventFormDialog";
import { canStudentMutateEventType } from "@/components/events/eventRules";
import { getLocalDateString } from "@/lib/date";
import { AlertCircle, CalendarX2, Plus, RefreshCw } from "lucide-react";

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
  const now = new Date();
  const { mutate: mutateCalendar } = useCalendarMonth(now.getFullYear(), now.getMonth() + 1);

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

  const handleSaved = () => {
    setFormOpen(false);
    setEditingEvent(null);
    mutate();
    mutateCalendar();
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
    try {
      await deactivateEvent(event.id);
      mutate();
      mutateCalendar();
    } catch (err: unknown) {
      // apiFetch translates network-level failures ("Failed to fetch") into an
      // actionable message; HTTP errors keep their backend-provided detail.
      const message = err instanceof Error ? err.message : "Unable to deactivate the event.";
      window.alert(message);
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

  const selectClass =
    "h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30 [color-scheme:dark]";
  const dateInputClass = selectClass;

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <PageHeader
        title="Academic Events"
        description="Upcoming, current, and past academic events for your program."
      />

      <GlassCard className="border-amber-500/20 bg-amber-500/10 p-4">
        <p className="flex items-start gap-2 text-sm text-amber-400">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {isAdmin
            ? "Admin view: you can add, edit, and deactivate any academic event. Deactivation is safe — the event can be re-enabled later."
            : "Events are flexible: record what actually happened by adding extra classes, cancellations, or surprise quizzes for your enrolled subjects. Holidays and global events are managed by administrators."}
        </p>
      </GlassCard>

      {/* Event management surface (Phase 6.5 + attendance-spec alignment).
          Admins manage every event type; students add/remove the flexible
          subject-scoped types. The dialog exposes only the types the current
          role may create, and the backend enforces authorization. */}
      <Card className="flex items-center justify-between gap-3 border-border p-4">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">Manage events</h2>
          <p className="text-xs text-muted-foreground">
            {isAdmin
              ? "Create subject-scoped or global events. Validation rules are enforced by the server."
              : "Add extras, cancellations, or surprise quizzes for your subjects. The server enforces enrollment and event rules."}
          </p>
        </div>
        <Button size="sm" onClick={openCreate} className="shrink-0">
          <Plus className="size-3.5" aria-hidden />
          Add Event
        </Button>
      </Card>

      {/* Filters */}
      <Card className="flex flex-col gap-3 border-border p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Filters</span>
          {hasFilters && (
            <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={resetFilters}>
              Reset
            </Button>
          )}
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground" htmlFor="events-type">
              Event type
            </label>
            <select
              id="events-type"
              className={selectClass}
              value={typeFilter}
              onChange={e => setTypeFilter(e.target.value as EventType | "")}
            >
              <option value="">All types</option>
              {TYPE_OPTIONS.map(type => (
                <option key={type} value={type}>{humanizeEventType(type)}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground" htmlFor="events-active">
              State
            </label>
            <select
              id="events-active"
              className={selectClass}
              value={activeFilter}
              onChange={e => setActiveFilter(e.target.value as ActiveFilter)}
            >
              <option value="active">Active events</option>
              <option value="inactive">Inactive events</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground" htmlFor="events-from">
              From
            </label>
            <Input
              id="events-from"
              type="date"
              className={dateInputClass}
              value={dateFrom}
              onChange={e => setDateFrom(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[10px] uppercase tracking-wider text-muted-foreground" htmlFor="events-to">
              To
            </label>
            <Input
              id="events-to"
              type="date"
              className={dateInputClass}
              value={dateTo}
              onChange={e => setDateTo(e.target.value)}
            />
          </div>
        </div>
        {!datesValid && (
          <p className="text-xs text-destructive">From date must be on or before the To date.</p>
        )}
      </Card>

      {/* Error */}
      {isError ? (
        <GlassCard className="border-red-900/50 bg-red-950/20">
          <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
            <AlertCircle className="size-10 text-red-500" aria-hidden />
            <h3 className="text-lg font-semibold text-red-400">Unable to load events</h3>
            <p className="max-w-md text-sm text-red-400/80">
              Academic events could not be fetched from the server. Check your connection and try again.
            </p>
            <Button variant="outline" size="sm" onClick={() => mutate()}>
              <RefreshCw className="size-3.5" aria-hidden />
              Try again
            </Button>
          </div>
        </GlassCard>
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
              ? "Try adjusting the event type, state, or date range."
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
        <Badge variant="neutral" className="h-4 px-1.5 text-[10px]">{count}</Badge>
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
