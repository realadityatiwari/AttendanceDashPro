import { AlertCircle, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface ErrorStateProps {
  title?: string;
  message?: string;
  /** When provided, renders a Retry action that re-triggers the failed request. */
  onRetry?: () => void;
  retryLabel?: string;
  /** Optional secondary action (e.g. a link) rendered beside Retry. */
  action?: React.ReactNode;
}

export function ErrorState({
  title = "Failed to load data",
  message = "An error occurred while fetching data from the server. The server may be temporarily unavailable.",
  onRetry,
  retryLabel = "Try again",
  action,
}: ErrorStateProps) {
  return (
    // 25.UX-1: semantic destructive tokens — the same recipe as the app's
    // other inline error surfaces (border-destructive/30 bg-destructive/10),
    // so the shared error state can never drift from the token set.
    <Card className="border-destructive/30 bg-destructive/10">
      <div className="flex flex-col items-center justify-center text-center p-8">
        <AlertCircle className="h-10 w-10 text-destructive mb-4" aria-hidden="true" />
        <h3 className="text-lg font-semibold text-destructive">{title}</h3>
        <p className="text-sm text-destructive/90 mt-2 max-w-md mx-auto">
          {message}
        </p>
        {(onRetry || action) && (
          <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
            {onRetry && (
              <Button variant="outline" size="sm" onClick={onRetry}>
                <RefreshCw className="size-3.5" aria-hidden="true" />
                {retryLabel}
              </Button>
            )}
            {action}
          </div>
        )}
      </div>
    </Card>
  );
}
