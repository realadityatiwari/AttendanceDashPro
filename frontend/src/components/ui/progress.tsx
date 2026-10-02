"use client"

import { Progress as ProgressPrimitive } from "@base-ui/react/progress"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * UIA-018 — the single progress primitive for the app.
 *
 * Sizes (track height), chosen from what the screens actually need:
 *  - sm (default): 4px — compact/inline meters
 *  - md:           6px — per-subject and per-criterion bars
 *  - lg:           8px — page-level summary bars (Mark Attendance, Lab)
 *
 * Variants (indicator fill) map 1:1 to the semantic token set:
 * default / success / warning / danger, plus neutral for the zero-record
 * "N/A" state (UIA-014).
 *
 * The track uses `bg-muted-foreground/20` rather than `bg-muted`: `--muted`
 * equals `--card` in this token set, so a muted track is invisible on cards
 * (UIA-014/UIA-018). The neutral indicator is intentionally a step stronger
 * (`/30`) so an N/A bar reads as a track with a faint fill, never as an
 * error-colored bar.
 */
const progressIndicatorVariants = cva(
  "h-full transition-all",
  {
    variants: {
      variant: {
        default: "bg-primary",
        success: "bg-success",
        warning: "bg-warning",
        danger: "bg-destructive",
        neutral: "bg-muted-foreground/30",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

const progressTrackVariants = cva(
  "relative flex w-full items-center overflow-x-hidden rounded-full bg-muted-foreground/20",
  {
    variants: {
      size: {
        sm: "h-1",
        md: "h-1.5",
        lg: "h-2",
      },
    },
    defaultVariants: {
      size: "sm",
    },
  }
)

interface ProgressProps
  extends ProgressPrimitive.Root.Props,
    VariantProps<typeof progressIndicatorVariants>,
    Pick<VariantProps<typeof progressTrackVariants>, "size"> {}

function Progress({
  className,
  children,
  value,
  variant,
  size,
  ...props
}: ProgressProps) {
  return (
    <ProgressPrimitive.Root
      value={value}
      data-slot="progress"
      className={cn("flex flex-wrap gap-3", className)}
      {...props}
    >
      {children}
      <ProgressTrack size={size}>
        <ProgressIndicator variant={variant} />
      </ProgressTrack>
    </ProgressPrimitive.Root>
  )
}

function ProgressTrack({
  className,
  size,
  ...props
}: ProgressPrimitive.Track.Props &
  Pick<VariantProps<typeof progressTrackVariants>, "size">) {
  return (
    <ProgressPrimitive.Track
      className={cn(progressTrackVariants({ size }), className)}
      data-slot="progress-track"
      {...props}
    />
  )
}

function ProgressIndicator({
  className,
  variant,
  ...props
}: ProgressPrimitive.Indicator.Props &
  VariantProps<typeof progressIndicatorVariants>) {
  return (
    <ProgressPrimitive.Indicator
      data-slot="progress-indicator"
      className={cn(progressIndicatorVariants({ variant }), className)}
      {...props}
    />
  )
}

function ProgressLabel({ className, ...props }: ProgressPrimitive.Label.Props) {
  return (
    <ProgressPrimitive.Label
      className={cn("text-sm font-medium", className)}
      data-slot="progress-label"
      {...props}
    />
  )
}

function ProgressValue({ className, ...props }: ProgressPrimitive.Value.Props) {
  return (
    <ProgressPrimitive.Value
      className={cn(
        "ml-auto text-sm text-muted-foreground tabular-nums",
        className
      )}
      data-slot="progress-value"
      {...props}
    />
  )
}

export {
  Progress,
  ProgressTrack,
  ProgressIndicator,
  ProgressLabel,
  ProgressValue,
}
