"use client";

import { useState } from "react";
import { useAttendanceHistory } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Search, Clock, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { AttendanceStatus, ClassType } from "@/types/api";

export default function HistoryPage() {
  const { history, isLoading, isError } = useAttendanceHistory();
  const [search, setSearch] = useState("");

  if (isError) {
    return (
      <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-5xl mx-auto w-full">
        <PageHeader title="Attendance History" />
        <ErrorState message="Could not load your attendance history. The endpoint might be unavailable or unauthenticated." />
      </div>
    );
  }

  const items = history?.items || [];
  
  // Basic client-side filtering since API doesn't support pagination/filtering parameters yet
  const filteredItems = items.filter(item => 
    item.subject_code.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-5xl mx-auto w-full">
      <PageHeader 
        title="Attendance History" 
        description="Chronological log of your marked attendance records."
      >
        <div className="relative w-full sm:w-64 mt-4 sm:mt-0">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input 
            type="search" 
            placeholder="Search subject code..." 
            className="pl-9 bg-surface border-border"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </PageHeader>

      <GlassCard className="mb-6 p-4 border border-border/50 bg-surface2/30">
        <div className="flex items-start gap-3 text-sm text-muted-foreground">
          <AlertCircle className="h-5 w-5 text-accent mt-0.5 shrink-0" />
          <p>
            Showing all {items.length} records retrieved from the backend. 
            Server-side filtering and pagination are not currently supported by the API.
          </p>
        </div>
      </GlassCard>

      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <GlassCard key={i} className="h-20 animate-pulse bg-surface/50" />
          ))}
        </div>
      ) : filteredItems.length === 0 ? (
        <EmptyState 
          title={search ? "No matches found" : "No history available"} 
          message={search ? "Try adjusting your search query." : "You haven't marked any attendance yet."}
          icon={<Clock className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      ) : (
        <div className="space-y-4">
          {filteredItems.map((item) => {
            const formattedDate = new Intl.DateTimeFormat("en-US", { 
              weekday: "short", month: "short", day: "numeric", year: "numeric" 
            }).format(new Date(item.date));
            
            const markedAt = new Intl.DateTimeFormat("en-US", { 
              hour: "numeric", minute: "2-digit" 
            }).format(new Date(item.marked_at));

            let statusColor = "text-muted-foreground";
            let statusIcon = null;

            if (item.status === AttendanceStatus.ATTENDED) {
              statusColor = "text-emerald-400";
              statusIcon = <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
            } else if (item.status === AttendanceStatus.MISSED) {
              statusColor = "text-red-400";
              statusIcon = <XCircle className="h-4 w-4 text-red-400" />;
            }

            return (
              <GlassCard key={item.id} className="p-4 hover:bg-surface/80 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className={`flex flex-col items-center justify-center w-12 h-12 rounded-full bg-surface2 border border-border/50 shrink-0 ${statusColor}`}>
                    {statusIcon}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-foreground">{item.subject_code}</h4>
                      <Badge variant="outline" className="text-[10px] uppercase tracking-wider py-0 h-4">
                        {item.class_type === ClassType.LECTURE ? "Lecture" : 
                         item.class_type === ClassType.TUTORIAL ? "Tutorial" : "Practical"}
                      </Badge>
                    </div>
                    <div className="text-sm text-muted-foreground mt-0.5 flex items-center gap-1.5">
                      <Clock className="h-3 w-3" />
                      {formattedDate}
                    </div>
                  </div>
                </div>
                <div className="text-right sm:border-l sm:border-border/50 sm:pl-4">
                  <div className={`font-semibold ${statusColor} capitalize`}>
                    {item.status.toLowerCase()}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    Logged at {markedAt}
                  </div>
                </div>
              </GlassCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
