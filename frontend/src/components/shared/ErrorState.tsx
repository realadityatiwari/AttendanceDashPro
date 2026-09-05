import { AlertCircle, RefreshCw } from "lucide-react";
import { GlassCard } from "./GlassCard";
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
    <GlassCard className="bg-red-950/20 border-red-900/50">
      <div className="flex flex-col items-center justify-center text-center p-8">
        <AlertCircle className="h-10 w-10 text-red-500 mb-4" />
        <h3 className="text-lg font-semibold text-red-400">{title}</h3>
        <p className="text-sm text-red-400/80 mt-2 max-w-md mx-auto">
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
    </GlassCard>
  );
}
