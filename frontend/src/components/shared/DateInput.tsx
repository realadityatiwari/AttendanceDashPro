"use client";

import { Input } from "@/components/ui/input";
import { formatDateMedium } from "@/lib/date";
import { cn } from "@/lib/utils";

interface DateInputProps
  extends Omit<React.ComponentProps<"input">, "type" | "value" | "onChange"> {
  /** ISO `YYYY-MM-DD` value — the native input keeps its machine-readable
   * value; this component never rewrites it. */
  value: string;
  onValueChange: (value: string) => void;
  /** Companion text shown while no date is chosen (keeps the row height
   * stable and explains that the filter is open). */
  emptyHint?: string;
  /** Classes for the input itself (the companion text is fixed). */
  className?: string;
}

/**
 * UIA-025 — one consistent date-input strategy.
 *
 * The native `<input type="date">` is preserved (keyboard entry, mobile
 * pickers, screen-reader value) and paired with a visible formatted companion
 * ("5 Oct 2026") in the app's canonical date format, so students are not
 * forced to decode the browser's mm/dd/yyyy rendering. The companion is
 * aria-hidden because the input already exposes the value to assistive
 * technology.
 */
export function DateInput({
  value,
  onValueChange,
  emptyHint = "Any date",
  className,
  ...props
}: DateInputProps) {
  return (
    <div className="flex flex-col gap-0.5">
      <Input
        type="date"
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        className={cn("[color-scheme:dark]", className)}
        {...props}
      />
      <span aria-hidden="true" className="text-[11px] text-muted-foreground">
        {value ? formatDateMedium(value) : emptyHint}
      </span>
    </div>
  );
}
