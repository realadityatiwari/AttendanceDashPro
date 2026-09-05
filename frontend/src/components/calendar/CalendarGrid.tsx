"use client";

import { CalendarDayItem } from "@/types/api";
import type { WeekStart } from "@/types/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatLongDate, getLocalDateString, parseLocalDate } from "@/lib/date";

// Weekday headers are pure layout; whether a day is working comes only from
// the API read model. Column order rotates with the user's week-start
// preference (Phase 9, D-05) — the backend default is MONDAY.
const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const WEEKDAY_SHORT = ["S", "M", "T", "W", "T", "F", "S"];

const MONTH_NAME_FORMATTER = new Intl.DateTimeFormat("en-US", { month: "long" });

interface CalendarGridProps {
  year: number;
  month: number;
  days: CalendarDayItem[];
  selectedDate: string | null;
  onSelect: (date: string) => void;
  /** D-05: visual week-start preference. Affects only column order and the
   * leading blank count — dates, selection, today, and indicators are
   * unchanged and stay attached to their real calendar dates. */
  weekStartsOn?: WeekStart;
}

/**
 * Monthly calendar grid. Renders only the backend-provided CalendarDayItems,
 * placed on the real calendar month (local time). Leading/trailing cells that
 * are not in the API's effective range are plain layout placeholders — never
 * academic days.
 */
export function CalendarGrid({
  year,
  month,
  days,
  selectedDate,
  onSelect,
  weekStartsOn = "MONDAY",
}: CalendarGridProps) {
  const todayStr = getLocalDateString();
  const dayMap = new Map(days.map(d => [d.date, d]));
  const firstOfMonth = new Date(year, month - 1, 1);
  const mondayStart = weekStartsOn === "MONDAY";
  // JS getDay(): 0 = Sunday. Monday-start rotates the header columns and
  // shifts the leading blanks so the first lands under its weekday column.
  const weekdayLabels = mondayStart
    ? [...WEEKDAY_LABELS.slice(1), WEEKDAY_LABELS[0]]
    : WEEKDAY_LABELS;
  const weekdayShort = mondayStart
    ? [...WEEKDAY_SHORT.slice(1), WEEKDAY_SHORT[0]]
    : WEEKDAY_SHORT;
  const leadingBlanks = mondayStart
    ? (firstOfMonth.getDay() + 6) % 7
    : firstOfMonth.getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const monthLabel = `${MONTH_NAME_FORMATTER.format(firstOfMonth)} ${year}`;

  const cells: React.ReactNode[] = [];
  for (let i = 0; i < leadingBlanks; i++) {
    cells.push(<div key={`placeholder-leading-${i}`} className="min-h-12 rounded-lg sm:min-h-16" aria-hidden />);
  }
  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const item = dayMap.get(dateStr);
    cells.push(
      item ? (
        <DayCell
          key={dateStr}
          item={item}
          isToday={dateStr === todayStr}
          isSelected={selectedDate === dateStr}
          onSelect={onSelect}
        />
      ) : (
        <div key={dateStr} className="min-h-12 rounded-lg sm:min-h-16" aria-hidden />
      )
    );
  }

  return (
    <div aria-label={`${monthLabel} academic calendar`}>
      <div className="grid grid-cols-7 gap-1 sm:gap-1.5">
        {weekdayLabels.map((label, i) => (
          <div
            key={label}
            className="pb-1 text-center text-[11px] font-semibold uppercase tracking-wider text-muted-foreground sm:text-xs"
          >
            <span className="sm:hidden">{weekdayShort[i]}</span>
            <span className="hidden sm:inline">{label}</span>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1 sm:gap-1.5">{cells}</div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full bg-primary" aria-hidden />
          Event
        </span>
        <span className="flex items-center gap-1.5">
          <span className="flex size-4 items-center justify-center rounded-full bg-primary text-[9px] leading-none font-bold text-primary-foreground" aria-hidden>
            {parseLocalDate(todayStr).getDate()}
          </span>
          Today
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-3 rounded-sm bg-primary/15 ring-1 ring-primary" aria-hidden />
          Selected
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-3 rounded-sm bg-muted/30" aria-hidden />
          Non-working
        </span>
      </div>
    </div>
  );
}

function DayCell({
  item,
  isToday,
  isSelected,
  onSelect,
}: {
  item: CalendarDayItem;
  isToday: boolean;
  isSelected: boolean;
  onSelect: (date: string) => void;
}) {
  const working = item.is_working_day;
  const eventCount = item.events.length;
  const classLabel = `${item.session_count} ${item.session_count === 1 ? "class" : "classes"}`;
  const ariaLabel = [
    formatLongDate(item.date),
    working ? "working day" : `non-working day${item.non_working_reason ? ` (${item.non_working_reason})` : ""}`,
    item.session_count > 0 ? classLabel : "no classes",
    eventCount > 0 ? `${eventCount} ${eventCount === 1 ? "event" : "events"}` : "no events",
    isSelected ? "selected" : null,
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <Button
      variant="ghost"
      aria-pressed={isSelected}
      aria-label={ariaLabel}
      onClick={() => onSelect(item.date)}
      className={cn(
        "flex min-h-12 w-full flex-col items-stretch justify-between gap-0.5 rounded-lg p-1.5 sm:min-h-16 sm:p-2",
        working ? "bg-card hover:bg-muted/70" : "bg-muted/25 text-muted-foreground hover:bg-muted/40",
        isSelected && "bg-primary/10 ring-2 ring-primary hover:bg-primary/15",
        isToday && !isSelected && "ring-1 ring-primary/50"
      )}
    >
      <span className="flex items-center justify-between gap-1">
        <span
          className={cn(
            "flex size-5 items-center justify-center rounded-full text-xs leading-none font-semibold sm:size-6 sm:text-sm",
            isToday ? "bg-primary text-primary-foreground" : working ? "text-foreground" : "text-muted-foreground"
          )}
        >
          {parseLocalDate(item.date).getDate()}
        </span>
        {eventCount > 0 && (
          <span className="flex items-center gap-0.5" title={`${eventCount} ${eventCount === 1 ? "event" : "events"}`}>
            <span className="size-1.5 rounded-full bg-primary" aria-hidden />
            {eventCount > 1 && <span className="text-[9px] leading-none font-bold text-primary">{eventCount}</span>}
          </span>
        )}
      </span>
      <span className="min-h-0">
        {working ? (
          item.session_count > 0 && (
            <span className="block truncate text-[11px] leading-tight font-medium text-success/90">{classLabel}</span>
          )
        ) : (
          item.non_working_reason && (
            <>
              {/* Small cells: compact dot only — the full reason stays in the
                  aria-label and in the DayDetail card, never crammed into the
                  cell. Larger screens show the truncated reason text. */}
              <span
                className="block size-1.5 rounded-full bg-muted-foreground/50 sm:hidden"
                aria-hidden
              />
              <span
                className="hidden truncate text-[11px] leading-tight text-muted-foreground/80 sm:block"
                title={item.non_working_reason}
              >
                {item.non_working_reason}
              </span>
            </>
          )
        )}
      </span>
    </Button>
  );
}
