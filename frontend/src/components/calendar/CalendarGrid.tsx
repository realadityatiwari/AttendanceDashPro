"use client";

import { CalendarDayItem } from "@/types/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatLongDate, getLocalDateString, parseLocalDate } from "@/lib/date";

// Alignment follows the backend convention: JS getDay() indices, Sunday first
// (matches DEFAULT_WEEKENDS in the Python calendar engine). Weekday headers are
// pure layout; whether a day is working comes only from the API read model.
const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const MONTH_NAME_FORMATTER = new Intl.DateTimeFormat("en-US", { month: "long" });

interface CalendarGridProps {
  year: number;
  month: number;
  days: CalendarDayItem[];
  selectedDate: string | null;
  onSelect: (date: string) => void;
}

/**
 * Monthly calendar grid. Renders only the backend-provided CalendarDayItems,
 * placed on the real calendar month (local time). Leading/trailing cells that
 * are not in the API's effective range are plain layout placeholders — never
 * academic days.
 */
export function CalendarGrid({ year, month, days, selectedDate, onSelect }: CalendarGridProps) {
  const todayStr = getLocalDateString();
  const dayMap = new Map(days.map(d => [d.date, d]));
  const firstOfMonth = new Date(year, month - 1, 1);
  const leadingBlanks = firstOfMonth.getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const monthLabel = `${MONTH_NAME_FORMATTER.format(firstOfMonth)} ${year}`;

  const cells: React.ReactNode[] = [];
  for (let i = 0; i < leadingBlanks; i++) {
    cells.push(<div key={`placeholder-leading-${i}`} className="aspect-square rounded-lg" aria-hidden />);
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
        <div key={dateStr} className="aspect-square rounded-lg" aria-hidden />
      )
    );
  }

  return (
    <div aria-label={`${monthLabel} academic calendar`}>
      <div className="grid grid-cols-7 gap-1 sm:gap-1.5">
        {WEEKDAY_LABELS.map(label => (
          <div
            key={label}
            className="text-center text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
          >
            {label}
          </div>
        ))}
      </div>
      <div className="mt-1.5 grid grid-cols-7 gap-1 sm:gap-1.5">{cells}</div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="size-1.5 rounded-full bg-accent" aria-hidden />
          Event
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-accent/10 ring-1 ring-accent" aria-hidden />
          Selected
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-muted/40" aria-hidden />
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
        "flex aspect-square h-auto w-full flex-col items-stretch justify-between rounded-lg p-1.5",
        working ? "bg-card hover:bg-muted/70" : "bg-muted/25 text-muted-foreground hover:bg-muted/40",
        isSelected && "bg-accent/10 ring-2 ring-accent hover:bg-accent/15",
        isToday && !isSelected && "ring-1 ring-primary/50"
      )}
    >
      <span className="flex items-center justify-between">
        <span
          className={cn(
            "text-sm leading-none font-semibold",
            isToday ? "text-primary" : working ? "text-foreground" : "text-muted-foreground"
          )}
        >
          {parseLocalDate(item.date).getDate()}
        </span>
        {eventCount > 0 && (
          <span className="flex items-center gap-0.5" title={`${eventCount} ${eventCount === 1 ? "event" : "events"}`}>
            <span className="size-1.5 rounded-full bg-accent" aria-hidden />
            {eventCount > 1 && <span className="text-[9px] leading-none font-bold text-accent">{eventCount}</span>}
          </span>
        )}
      </span>
      <span className="mt-auto min-h-0">
        {working ? (
          item.session_count > 0 && (
            <span className="block truncate text-[10px] leading-tight font-medium text-success/90">{classLabel}</span>
          )
        ) : (
          item.non_working_reason && (
            <span
              className="block truncate text-[10px] leading-tight text-muted-foreground/80"
              title={item.non_working_reason}
            >
              {item.non_working_reason}
            </span>
          )
        )}
      </span>
    </Button>
  );
}
