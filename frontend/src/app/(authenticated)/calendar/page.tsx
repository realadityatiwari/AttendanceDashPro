"use client";

import { useState } from "react";
import { useCalendarMonth, usePreferences } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { CalendarGrid } from "@/components/calendar/CalendarGrid";
import { DayDetail } from "@/components/calendar/DayDetail";
import { formatLongDate, getLocalDateString } from "@/lib/date";
import { AlertCircle, CalendarX2, ChevronLeft, ChevronRight, Loader2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";

const MONTH_LABEL_FORMATTER = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" });

interface DaySelection {
  monthKey: string;
  date: string | null;
}

export default function CalendarPage() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [selection, setSelection] = useState<DaySelection>({ monthKey: "", date: null });

  const monthKey = `${year}-${month}`;
  const { calendarMonth: data, isLoading, isError, mutate } = useCalendarMonth(year, month);
  // Phase 9 (D-05): the saved week-start preference drives the grid's visual
  // column order. Same SWR key as Settings (deduped); backend default MONDAY.
  const { preferences } = usePreferences();

  // The displayed month always comes from the backend read model (SWR's
  // keepPreviousData retains the previous month during a switch). The requested
  // month is only used for navigation and fetching.
  const gridYear = data?.year ?? year;
  const gridMonth = data?.month ?? month;
  const gridMonthKey = data ? `${data.year}-${data.month}` : monthKey;
  const switching = isLoading && Boolean(data);

  const semesterStart = data?.semester_start ?? null;
  const semesterEnd = data?.semester_end ?? null;

  // Effective selected day: the user's choice while the month is unchanged;
  // otherwise today when the backend returned it, else the first effective day,
  // else nothing. Pure derivation from the read model — no effects, no
  // invented dates, and manual selections survive revalidations.
  const selectedDate = (() => {
    if (!data) return selection.date;
    if (selection.monthKey === gridMonthKey && selection.date !== null) return selection.date;
    const todayStr = getLocalDateString();
    if (data.days.some(d => d.date === todayStr)) return todayStr;
    return data.days.length > 0 ? data.days[0].date : null;
  })();

  const selectedDay = data?.days.find(d => d.date === selectedDate) ?? null;

  // Month navigation is gated by the backend-provided semester bounds when
  // known: never let the user navigate to a month that cannot contain a single
  // academic day. No hardcoded dates, no invented bounds.
  const canGoPrev = semesterStart
    ? getLocalDateString(new Date(year, month - 1, 0)) >= semesterStart
    : true;
  const canGoNext = semesterEnd
    ? getLocalDateString(new Date(year, month, 1)) <= semesterEnd
    : true;

  const isCurrentMonth = year === today.getFullYear() && month === today.getMonth() + 1;

  const shiftMonth = (delta: number) => {
    const next = month + delta;
    if (next < 1) {
      setYear(year - 1);
      setMonth(12);
    } else if (next > 12) {
      setYear(year + 1);
      setMonth(1);
    } else {
      setMonth(next);
    }
  };

  const goToToday = () => {
    setYear(today.getFullYear());
    setMonth(today.getMonth() + 1);
  };

  const handleSelect = (date: string) => {
    // Track the month the selected day actually belongs to so a retained grid
    // shown during a month switch can never leak its selection forward.
    setSelection({ monthKey: gridMonthKey, date });
  };

  const semesterRange =
    semesterStart && semesterEnd
      ? `Semester ${formatLongDate(semesterStart).replace(" · ", " ")} – ${formatLongDate(semesterEnd).replace(" · ", " ")}`
      : null;

  const monthLabel = MONTH_LABEL_FORMATTER.format(new Date(year, month - 1, 1));

  // Phase 12B: the row wraps (never clips) and the month label shrinks
  // responsively so Previous / Next / Today all fit at 320px; desktop keeps
  // the fixed w-36 label.
  const navControls = (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        variant="outline"
        size="icon-sm"
        aria-label="Previous month"
        onClick={() => shiftMonth(-1)}
        disabled={!canGoPrev}
      >
        <ChevronLeft aria-hidden />
      </Button>
      <span className="min-w-0 w-28 text-center text-sm font-semibold text-foreground sm:w-36">{monthLabel}</span>
      <Button
        variant="outline"
        size="icon-sm"
        aria-label="Next month"
        onClick={() => shiftMonth(1)}
        disabled={!canGoNext}
      >
        <ChevronRight aria-hidden />
      </Button>
      <Button variant="outline" size="sm" onClick={goToToday} disabled={isCurrentMonth}>
        Today
      </Button>
    </div>
  );

  if (isError && (!data || data.year !== year || data.month !== month)) {
    return (
      <div className="flex w-full flex-1 flex-col gap-6 py-6">
        <PageHeader title="Calendar" description="Monthly view of your academic calendar">
          {navControls}
        </PageHeader>
        <GlassCard className="border-red-900/50 bg-red-950/20">
          <div className="flex flex-col items-center justify-center gap-3 p-10 text-center">
            <AlertCircle className="size-10 text-red-500" aria-hidden />
            <h3 className="text-lg font-semibold text-red-400">Unable to load calendar</h3>
            <p className="max-w-md text-sm text-red-400/80">
              The calendar could not be fetched from the server. Check your connection and try again.
            </p>
            <Button variant="outline" size="sm" onClick={() => mutate()}>
              <RefreshCw className="size-3.5" aria-hidden />
              Try again
            </Button>
          </div>
        </GlassCard>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex w-full flex-1 flex-col gap-6 py-6">
        <PageHeader title="Calendar" description="Monthly view of your academic calendar">
          {navControls}
        </PageHeader>
        <GridSkeleton />
      </div>
    );
  }

  const isEmpty = data.days.length === 0;

  return (
    <div className="flex w-full flex-1 flex-col gap-6 py-6">
      <PageHeader title="Calendar" description={semesterRange ?? "Monthly view of your academic calendar"}>
        {navControls}
      </PageHeader>

      {isEmpty ? (
        <EmptyState
          title="No academic days in this period"
          message={
            semesterRange
              ? `This month falls outside your semester (${semesterRange}). Use the month controls to explore your academic calendar.`
              : "This month has no effective academic days for your enrolled program."
          }
          icon={<CalendarX2 className="mb-4 size-10 text-muted-foreground" aria-hidden />}
        />
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
          <GlassCard className={cn("p-2 sm:p-4", switching && "pointer-events-none opacity-70")}>
            {switching && (
              <div className="mb-2 flex items-center justify-end gap-1.5 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
                Loading {monthLabel}
              </div>
            )}
            <CalendarGrid
              year={gridYear}
              month={gridMonth}
              days={data.days}
              selectedDate={selectedDate}
              onSelect={handleSelect}
              weekStartsOn={preferences?.week_starts_on ?? "MONDAY"}
            />
          </GlassCard>
          <div className="lg:sticky lg:top-4 lg:max-h-[calc(100dvh-2rem)] lg:overflow-y-auto">
            {selectedDay ? (
              <DayDetail day={selectedDay} />
            ) : (
              <GlassCard className="p-5">
                <p className="text-sm text-muted-foreground">Select a day to see its details.</p>
              </GlassCard>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function GridSkeleton() {
  return (
    <>
      <GlassCard className="p-2 sm:p-4">
        <div className="mb-1.5 grid grid-cols-7 gap-1 sm:gap-1.5">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-3" />
          ))}
        </div>
        <div className="grid grid-cols-7 gap-1 sm:gap-1.5">
          {Array.from({ length: 35 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square rounded-lg" />
          ))}
        </div>
      </GlassCard>
      <Skeleton className="h-72 rounded-xl" />
    </>
  );
}
