"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";

/**
 * Route-level error boundary (UI-007). Catches render/data errors below the
 * root layout and replaces the default framework error page. Offers retry
 * (framework reset) and a way back to the dashboard. Never surfaces stack
 * traces or raw error text to the user; details go to the console only.
 */
export default function GlobalRouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-8 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-destructive/10">
          <AlertTriangle
            className="size-6 text-destructive"
            aria-hidden="true"
          />
        </div>
        <h1 className="mt-4 text-xl font-bold tracking-tight text-foreground">
          Something went wrong
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          An unexpected error occurred while showing this page. Please try
          again.
        </p>
        <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
          <button
            type="button"
            onClick={reset}
            className="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors outline-none hover:bg-primary/80 focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            <RefreshCw className="mr-2 size-4" aria-hidden="true" />
            Try again
          </button>
          <Link
            href="/dashboard"
            className="inline-flex h-10 items-center justify-center rounded-lg border border-border bg-background px-4 text-sm font-medium text-foreground transition-colors outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            <Home className="mr-2 size-4" aria-hidden="true" />
            Go to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
