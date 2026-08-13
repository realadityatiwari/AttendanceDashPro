"use client";

import { useState } from "react";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { useDailySessions, useMutateAttendance, useDashboardSummary } from "@/hooks/useApi";
import { getLocalDateString, formatLongDate, addDays, isToday, formatShortDate } from "@/lib/date";
import { AttendanceStatus, ClassType, AttendanceMutationRequest } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { TrackSessionCard } from "@/components/dashboard/TrackSessionCard";
import { ChevronLeft, ChevronRight, Loader2, Calendar } from "lucide-react";

export default function TrackAttendancePage() {
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [isMarkingAll, setIsMarkingAll] = useState(false);
  const dateStr = getLocalDateString(selectedDate);
  
  const { dailySessions, isLoading, isError, mutate } = useDailySessions(dateStr);
  const { mutateAttendance } = useMutateAttendance();
  const { mutate: mutateDashboard } = useDashboardSummary();

  const handlePreviousDay = () => setSelectedDate(addDays(selectedDate, -1));
  const handleNextDay = () => setSelectedDate(addDays(selectedDate, 1));
  const handleToday = () => setSelectedDate(new Date());

  const handleMutate = async (request: AttendanceMutationRequest) => {
    try {
      await mutateAttendance(request);
      await mutate();
      mutateDashboard(); // invalidate dashboard cache silently
    } catch (err) {
      console.error("Failed to mutate attendance", err);
    }
  };

  const handleMarkAllPresent = async () => {
    if (!dailySessions || isMarkingAll) return;
    setIsMarkingAll(true);
    try {
      const pendingSessions = dailySessions.sessions.filter(
        s => !s.is_cancelled && s.status === AttendanceStatus.PENDING
      );
      
      const promises = pendingSessions.map(s => 
        mutateAttendance({ class_session_id: s.id, status: AttendanceStatus.ATTENDED })
      );
      
      await Promise.allSettled(promises);
      await mutate();
      mutateDashboard();
    } finally {
      setIsMarkingAll(false);
    }
  };

  if (isError) {
    return (
      <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-2xl mx-auto w-full">
        <PageHeader title="Track Attendance" />
        <ErrorState message="Could not load daily scheduled sessions." />
      </div>
    );
  }

  const sessions = dailySessions?.sessions || [];
  const validSessions = sessions.filter(s => !s.is_cancelled);
  
  const total = validSessions.length;
  const present = validSessions.filter(s => s.status === AttendanceStatus.ATTENDED).length;
  const absent = validSessions.filter(s => s.status === AttendanceStatus.MISSED).length;
  const recorded = present + absent;
  const pending = total - recorded;
  
  const progressValue = total > 0 ? (recorded / total) * 100 : 0;

  return (
    <div className="flex-1 px-4 py-6 sm:px-6 lg:px-8 max-w-2xl mx-auto w-full flex flex-col gap-6">
      
      {/* Header */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">Track Attendance</h1>
        <p className="text-sm text-muted-foreground">{formatLongDate(selectedDate)}</p>
      </div>

      {/* Date Navigation */}
      <div className="flex items-center justify-between w-full">
        <Button variant="outline" size="icon" onClick={handlePreviousDay}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium w-28 text-center">{formatShortDate(selectedDate)}</span>
          <Button 
            variant={isToday(selectedDate) ? "secondary" : "outline"}
            size="sm" 
            className="text-xs uppercase tracking-wider h-8"
            onClick={handleToday}
          >
            Today
          </Button>
        </div>
        <Button variant="outline" size="icon" onClick={handleNextDay}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          <div className="h-32 animate-pulse bg-muted rounded-xl border border-border" />
          <div className="h-40 animate-pulse bg-muted rounded-xl border border-border" />
        </div>
      ) : sessions.length === 0 ? (
        <EmptyState 
          title="No classes scheduled" 
          message="Enjoy your free day! There are no classes in the timetable."
          icon={<Calendar className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      ) : (
        <>
          {/* Top Summary Card */}
          <Card className="p-4 bg-muted border-border flex flex-col gap-4">
            <div className="flex justify-between items-end">
              <div className="flex flex-col gap-1">
                <span className="text-sm font-medium text-foreground">{total} classes {isToday(selectedDate) ? "today" : ""}</span>
                {pending > 0 && <span className="text-xs text-muted-foreground">{pending} remaining</span>}
              </div>
              <span className="text-sm font-bold">{recorded}/{total}</span>
            </div>
            <Progress value={progressValue} variant="default" className="h-2" />
            
            {pending > 0 && (
              <Button 
                onClick={handleMarkAllPresent}
                disabled={isMarkingAll}
                className="w-full bg-success hover:bg-success/90 text-success-foreground"
              >
                {isMarkingAll ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Mark all present
              </Button>
            )}
          </Card>

          {/* Session Cards */}
          <div className="flex flex-col gap-4">
            {sessions.map(session => (
              <TrackSessionCard key={session.id} session={session} onMutate={handleMutate} />
            ))}
          </div>

          {/* Bottom Summary */}
          <Card className="p-4 bg-card border-border mt-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">
              {isToday(selectedDate) ? "Today's Attendance" : "Daily Attendance"}
            </h3>
            <div className="grid grid-cols-3 divide-x divide-border">
              <div className="flex flex-col items-center">
                <span className="text-2xl font-bold tracking-tight text-success">{present}</span>
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">Present</span>
              </div>
              <div className="flex flex-col items-center">
                <span className="text-2xl font-bold tracking-tight text-destructive">{absent}</span>
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">Absent</span>
              </div>
              <div className="flex flex-col items-center">
                <span className="text-2xl font-bold tracking-tight text-foreground">{pending}</span>
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">Pending</span>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
