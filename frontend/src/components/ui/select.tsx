import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Canonical native select (Phase 6, UI-016).
 *
 * Height vocabulary matches the control foundation: `h-10` on mobile for
 * comfortable touch targets, `sm:h-8` on desktop — the same pair used by the
 * Button and Input primitives. Styling mirrors `ui/input.tsx` so inputs and
 * selects read as one control family. The native picker/arrow is preserved
 * (no appearance-none). Local width behavior can be overridden (e.g.
 * `w-auto` next to a label).
 */
function Select({ className, children, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      data-slot="select"
      className={cn(
        "h-10 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm text-foreground transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 [color-scheme:dark] dark:bg-input/30 sm:h-8",
        className
      )}
      {...props}
    >
      {children}
    </select>
  )
}

export { Select }
