import { useProfile } from "@/hooks/useApi";
import { formatLongDate, getGreeting } from "@/lib/date";
import { Skeleton } from "@/components/ui/skeleton";

export function GreetingHeader() {
  const { profile, isLoading } = useProfile();

  const firstName = profile?.display_name ? profile.display_name.split(" ")[0] : "";

  return (
    <header className="mb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          {isLoading ? (
            <Skeleton className="h-8 w-56" />
          ) : (
            `${getGreeting()}, ${firstName}`
          )}
        </h1>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        {formatLongDate(new Date())}
      </p>
    </header>
  );
}