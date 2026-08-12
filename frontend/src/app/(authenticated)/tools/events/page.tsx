"use client";

import { useEvents } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Calendar, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function EventsPage() {
  const { events, isLoading, isError } = useEvents();

  if (isError) {
    return (
      <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-5xl mx-auto w-full">
        <PageHeader title="Academic Events" />
        <ErrorState message="Could not load academic events." />
      </div>
    );
  }

  const activeEvents = events || [];

  return (
    <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-5xl mx-auto w-full">
      <PageHeader 
        title="Academic Events" 
        description="Upcoming holidays, extra classes, and institute events."
      />

      <GlassCard className="mb-6 p-4 border border-amber-500/20 bg-amber-500/10">
        <div className="flex items-start gap-3 text-sm text-amber-400">
          <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
          <p>
            Event creation is currently restricted to administrators. This is a read-only view of scheduled events.
          </p>
        </div>
      </GlassCard>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <GlassCard key={i} className="h-24 animate-pulse bg-surface/50" />
          ))}
        </div>
      ) : activeEvents.length === 0 ? (
        <EmptyState 
          title="No events scheduled" 
          message="There are no upcoming academic events in the calendar."
          icon={<Calendar className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      ) : (
        <div className="space-y-4">
          {activeEvents.map((event) => {
            const startDate = new Intl.DateTimeFormat("en-US", { 
              weekday: "short", month: "long", day: "numeric" 
            }).format(new Date(event.start_date));
            
            const endDate = event.end_date !== event.start_date 
              ? new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric" }).format(new Date(event.end_date))
              : null;

            return (
              <GlassCard key={event.id} className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-l-4 border-l-accent">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-bold text-foreground text-lg">{event.title}</h3>
                    {event.is_holiday && (
                      <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/25">
                        Holiday
                      </Badge>
                    )}
                  </div>
                  {event.description && (
                    <p className="text-sm text-muted-foreground mb-2">{event.description}</p>
                  )}
                  <div className="text-sm font-medium text-accent flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    {startDate} {endDate ? `- ${endDate}` : ""}
                  </div>
                </div>
                <div className="sm:text-right">
                  <Badge variant="outline" className="uppercase text-[10px] tracking-wider border-border/60">
                    {event.event_type.replace("_", " ")}
                  </Badge>
                </div>
              </GlassCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
