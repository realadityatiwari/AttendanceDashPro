import { useProfile } from "@/hooks/useApi";
import { formatLongDate, getGreeting } from "@/lib/date";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * UIA-009: the greeting uses the student's full display name, trimmed and
 * whitespace-normalized — never truncated to the first token. Returns an
 * empty string when no usable name exists so the caller can render the bare
 * time-aware greeting (no fabricated identity).
 */
export function formatGreetingName(fullName: string | null | undefined): string {
  if (!fullName) return "";
  return fullName.trim().replace(/\s+/g, " ");
}

export function GreetingHeader() {
  const { profile, isLoading } = useProfile();

  // UI-031: when the profile request fails (or carries no display name) the
  // greeting falls back to the bare time-aware greeting — never an empty name
  // after the comma. No identity is fabricated; profile errors stay visible
  // through the dashboard's own error/retry states.
  const displayName = formatGreetingName(profile?.display_name);

  return (
    <header className="mb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        {/* UIA-009: break-words keeps an unusually long name from overflowing
            on 375px mobile. */}
        <h1 className="break-words max-w-full text-2xl font-bold tracking-tight text-foreground">
          {isLoading ? (
            <Skeleton className="h-8 w-56" />
          ) : displayName ? (
            `${getGreeting()}, ${displayName}`
          ) : (
            getGreeting()
          )}
        </h1>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        {formatLongDate(new Date())}
      </p>
    </header>
  );
}