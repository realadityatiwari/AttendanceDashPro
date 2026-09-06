import { useProfile } from "@/hooks/useApi";
import { formatLongDate, getGreeting } from "@/lib/date";
import { Skeleton } from "@/components/ui/skeleton";

export function GreetingHeader() {
  const { profile, isLoading } = useProfile();

  // UI-031: when the profile request fails (or carries no display name) the
  // greeting falls back to the bare time-aware greeting — never an empty name
  // after the comma. No identity is fabricated; profile errors stay visible
  // through the dashboard's own error/retry states.
  const firstName = profile?.display_name ? profile.display_name.split(" ")[0] : "";

  return (
    <header className="mb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {isLoading ? (
            <Skeleton className="h-8 w-56" />
          ) : firstName ? (
            `${getGreeting()}, ${firstName}`
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