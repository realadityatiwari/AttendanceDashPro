"use client";

import type { ComponentType } from "react";
import { cn } from "@/lib/utils";

export interface SegmentedOption<T extends string | number> {
  value: T;
  label: string;
  icon?: ComponentType<{ className?: string }>;
}

type SegmentedVariant = "solid" | "track" | "tint";

const VARIANT_CLASSES: Record<
  SegmentedVariant,
  { container: string; button: string; active: string; inactive: string }
> = {
  // Solid primary fill (quiz-cycle selector language).
  solid: {
    container: "",
    button: "rounded-lg px-4",
    active: "bg-primary text-primary-foreground",
    inactive:
      "bg-muted/50 border border-border/50 text-muted-foreground hover:bg-muted hover:text-foreground",
  },
  // Recessed track with slides (laboratory section-switcher language).
  track: {
    container:
      "flex overflow-x-auto gap-1 rounded-md border border-border bg-muted p-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden",
    button: "rounded-md px-3 shrink-0 whitespace-nowrap",
    active: "bg-secondary text-foreground",
    inactive: "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
  },
  // Outlined chips with a primary tint (feedback-type language).
  tint: {
    container: "",
    button: "rounded-lg border px-3",
    active: "border-primary/50 bg-primary/10 text-primary",
    inactive:
      "border-border bg-background text-muted-foreground hover:text-foreground",
  },
};

interface SegmentedControlProps<T extends string | number> {
  value: T | null;
  onValueChange: (value: T) => void;
  options: readonly SegmentedOption<T>[];
  /** Visual language; preserves each adopting surface's established look. */
  variant?: SegmentedVariant;
  className?: string;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  /** 25.UX-7: association hook for an inline validation message (the
   *  container carries it; the error text gets a stable id). */
  "aria-describedby"?: string;
}

/**
 * Controlled segmented control (25.UX-2): one implementation of the
 * toggle-button group previously duplicated on the quiz-eligibility cycle
 * selector, the laboratory section switcher, and the feedback type chips.
 *
 * Interaction model (shared by all three former implementations):
 *  - `role="group"` container named via aria-label/aria-labelledby;
 *  - one native button per option exposing the selection via `aria-pressed`
 *    (UI-020/UIA-033: these are toggles, not a tablist — no tab semantics);
 *  - the UIA-030 touch floor (40px touch / 32px pointer) on every option;
 *  - visible focus ring on the shared ring token.
 *
 * The variant only reproduces each surface's established visual language —
 * it carries no state, layout, or domain logic. Layout extras (wrap, grid,
 * margins) compose through `className`.
 */
export function SegmentedControl<T extends string | number>({
  value,
  onValueChange,
  options,
  variant = "solid",
  className,
  ...labelProps
}: SegmentedControlProps<T>) {
  const classes = VARIANT_CLASSES[variant];
  return (
    <div
      role="group"
      className={cn(classes.container, className)}
      {...labelProps}
    >
      {options.map(({ value: optionValue, label, icon: Icon }) => {
        const selected = value === optionValue;
        return (
          <button
            key={String(optionValue)}
            type="button"
            aria-pressed={selected}
            onClick={() => onValueChange(optionValue)}
            className={cn(
              "flex h-10 sm:h-8 items-center justify-center gap-1.5 text-sm font-medium transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
              classes.button,
              selected ? classes.active : classes.inactive
            )}
          >
            {Icon && <Icon className="size-4 shrink-0" aria-hidden="true" />}
            {label}
          </button>
        );
      })}
    </div>
  );
}
