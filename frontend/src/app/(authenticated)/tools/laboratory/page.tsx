"use client";

import { useState } from "react";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { useDailySessions, useMutateAttendance, useDashboardSummary, useProfile } from "@/hooks/useApi";
import { getLocalDateString, formatLongDate, addDays, isToday, formatShortDate, parseLocalDate } from "@/lib/date";
import { AttendanceStatus, AttendanceMutationRequest } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { TrackSessionCard } from "@/components/dashboard/TrackSessionCard";
import { ChevronLeft, ChevronRight, Loader2, Calendar, AlertTriangle } from "lucide-react";

export default function TrackAttendancePage() {
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [isMarkingAll, setIsMarkingAll] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const dateStr = getLocalDateString(selectedDate);
  // Future academic dates are VIEW-ONLY: the schedule stays visible (Upcoming),
  // but no attendance mutation controls are offered (the backend rejects
  // future-date mutations too). Canonical local-date string comparison.
  const isFutureDate = dateStr > getLocalDateString();

  const { profile } = useProfile();
  const semesterStart = profile?.semester_start ?? null;
  const semesterEnd = profile?.semester_end ?? null;

  const { dailySessions, isLoading, isError, mutate } = useDailySessions(dateStr);
  const { mutateAttendance } = useMutateAttendance();
  const { mutate: mutateDashboard } = useDashboardSummary();

  const atSemesterStart = semesterStart ? dateStr <= semesterStart : false;
  const atSemesterEnd = semesterEnd ? dateStr >= semesterEnd : false;

  const clampToSemester = (d: Date) => {
    if (semesterStart) {
      const start = parseLocalDate(semesterStart);
      if (getLocalDateString(d) < semesterStart) return start;
    }
    if (semesterEnd) {
      const end = parseLocalDate(semesterEnd);
      if (getLocalDateString(d) > semesterEnd) return end;
    }
    return d;
  };

  const handlePreviousDay = () => {
    if (atSemesterStart) return;
    setMutationError(null);
    setSelectedDate(prev => clampToSemester(addDays(prev, -1)));
  };
  const handleNextDay = () => {
    if (atSemesterEnd) return;
    setMutationError(null);
    setSelectedDate(prev => clampToSemester(addDays(prev, 1)));
  };
  const handleToday = () => {
    setMutationError(null);
    setSelectedDate(clampToSemester(new Date()));
  };
  const handleDatePick = (value: string) => {
    if (!value) return;
    setMutationError(null);
    setSelectedDate(clampToSemester(parseLocalDate(value)));
  };

  const handleMutate = async (request: AttendanceMutationRequest) => {
    try {
      await mutateAttendance(request);
      setMutationError(null);
      await mutate();
      mutateDashboard(); // invalidate dashboard cache silently
    } catch (err) {
      console.error("Failed to mutate attendance", err);
      setMutationError(err instanceof Error ? err.message : "Failed to update attendance");
    }
  };

  const handleMarkAllPresent = async () => {
    if (!dailySessions || isMarkingAll) return;
    setIsMarkingAll(true);
    setMutationError(null);
    try {
      const pendingSessions = dailySessions.sessions.filter(
        s => !s.is_cancelled && s.status === AttendanceStatus.PENDING
      );

      const results = await Promise.allSettled(
        pendingSessions.map(s =>
          mutateAttendance({ class_session_id: s.id, status: AttendanceStatus.ATTENDED })
        )
      );

      const failed = results.filter(r => r.status === "rejected").length;
      if (failed > 0) {
        setMutationError(`${failed} session${failed > 1 ? "s" : ""} could not be marked.`);
      }

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
        <p className="text-sm text-muted-foreground">
          {formatLongDate(selectedDate)}
          {atSemesterStart && <span className="text-primary"> · Semester start</span>}
        </p>
      </div>

      {/* Date Navigation — Phase 12B: the center column becomes fluid so the
          date input stretches between the arrows on narrow screens (input and
          Today are 40px tall on mobile via the 12A button foundation; the
          `sm:h-8` restore keeps the desktop size byte-identical). */}
      <div className="flex items-center justify-between w-full gap-2">
        <Button variant="outline" size="icon" onClick={handlePreviousDay} disabled={atSemesterStart} aria-label="Previous day">
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <div className="flex flex-1 min-w-0 flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:justify-center">
          <Input
            type="date"
            aria-label="Jump to date"
            value={dateStr}
            min={semesterStart ?? undefined}
            max={semesterEnd ?? undefined}
            onChange={e => handleDatePick(e.target.value)}
            className="h-10 w-full [color-scheme:dark] text-xs sm:h-8 sm:w-40"
          />
          <Button
            variant={isToday(selectedDate) ? "secondary" : "outline"}
            size="sm"
            className="text-xs uppercase tracking-wider sm:h-8"
            onClick={handleToday}
          >
            Today
          </Button>
        </div>
        <Button variant="outline" size="icon" onClick={handleNextDay} disabled={atSemesterEnd} aria-label="Next day">
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
      <div className="text-center -mt-2">
        <span className="text-xs text-muted-foreground">{formatShortDate(selectedDate)}</span>
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
          {mutationError && (
            <div className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{mutationError}</span>
            </div>
          )}

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

            {isFutureDate ? (
              <p className="text-xs text-muted-foreground">
                View-only — attendance unlocks on {dateStr}.
              </p>
            ) : (
              pending > 0 && (
                <Button
                  onClick={handleMarkAllPresent}
                  disabled={isMarkingAll}
                  className="w-full bg-success hover:bg-success/90 text-success-foreground"
                >
                  {isMarkingAll ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Mark all present
                </Button>
              )
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
