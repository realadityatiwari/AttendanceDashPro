"use client";

import { useState } from "react";
import { RefreshCw, X } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Update-available banner (UI-023).
 *
 * Rendered by ServiceWorkerRegistration when the service worker reports a
 * newly installed waiting version. Offers an explicit user-triggered reload
 * (the installed worker activates on reload by design — no skipWaiting) and
 * can be dismissed for the session. Never reloads on its own. Sits above the
 * mobile bottom navigation; uses popover/card tokens; no animation.
 */
export function UpdateBanner() {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div
      role="status"
      className="fixed inset-x-4 bottom-24 z-50 flex items-center justify-between gap-3 rounded-lg border border-border bg-popover p-3 shadow-lg sm:inset-x-auto sm:bottom-6 sm:right-6 sm:max-w-sm"
    >
      <p className="text-sm font-medium text-foreground">
        A new version is available.
      </p>
      <div className="flex shrink-0 items-center gap-1">
        <Button size="sm" onClick={() => window.location.reload()}>
          <RefreshCw className="size-3.5" aria-hidden="true" />
          Refresh
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Dismiss update message"
          onClick={() => setDismissed(true)}
        >
          <X className="size-3.5" aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}
