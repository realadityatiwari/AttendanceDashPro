"use client";

import { useState } from "react";
import { DailySessionResponse, AttendanceStatus, AttendanceMutationRequest, ClassType } from "@/types/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CheckCircle2, XCircle, Loader2, Clock } from "lucide-react";
import { cn } from "@/lib/utils";
import { getLocalDateString } from "@/lib/date";

interface TrackSessionCardProps {
  session: DailySessionResponse;
  onMutate: (request: AttendanceMutationRequest) => Promise<void>;
}

export function TrackSessionCard({ session, onMutate }: TrackSessionCardProps) {
  const [isMutating, setIsMutating] = useState(false);

  // Future academic dates are VIEW-ONLY (canonical local date; ISO string
  // comparison — the same utility the Track page uses for navigation).
  // Scheduled and event-created sessions stay visible as Upcoming, but
  // Present/Absent cannot be recorded before the date (backend enforces this
  // too — this is the UI layer of the same rule).
  const isFuture = session.date > getLocalDateString();

  const handleMutate = async (status: AttendanceStatus) => {
    if (isMutating) return;
    setIsMutating(true);
    try {
      await onMutate({ class_session_id: session.id, status });
    } finally {
      setIsMutating(false);
    }
  };

  const getStatusDisplay = () => {
    if (session.is_cancelled) {
      return (
        <div className="flex items-center gap-2">
          <Badge variant="neutral" className="pointer-events-none">Cancelled</Badge>
        </div>
      );
    }

    // Future dates: no attendance mutation controls at all (view-only).
    if (isFuture && session.status === AttendanceStatus.PENDING) {
      return (
        <div className="flex items-center gap-2">
          <Badge variant="neutral" className="pointer-events-none">
            <Clock className="h-3 w-3 mr-1" /> Upcoming
          </Badge>
        </div>
      );
    }

    if (session.status === AttendanceStatus.ATTENDED) {
      return (
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2 text-success font-medium text-sm">
            <CheckCircle2 className="h-5 w-5" />
            <span>Present</span>
          </div>
          {!isFuture && (
            <Button 
              variant="ghost" 
              size="sm" 
              className="text-xs h-7 px-2 text-muted-foreground hover:text-foreground"
              onClick={() => handleMutate(AttendanceStatus.MISSED)}
              disabled={isMutating}
            >
              {isMutating ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
              Change
            </Button>
          )}
        </div>
      );
    }

    if (session.status === AttendanceStatus.MISSED) {
      return (
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2 text-destructive font-medium text-sm">
            <XCircle className="h-5 w-5" />
            <span>Absent</span>
          </div>
          {!isFuture && (
            <Button 
              variant="ghost" 
              size="sm" 
              className="text-xs h-7 px-2 text-muted-foreground hover:text-foreground"
              onClick={() => handleMutate(AttendanceStatus.ATTENDED)}
              disabled={isMutating}
            >
              {isMutating ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : null}
              Change
            </Button>
          )}
        </div>
      );
    }

    // PENDING (past/today)
    return (
      <div className="grid grid-cols-2 gap-3 w-full">
        <Button 
          variant="outline" 
          className={cn("w-full border-success/30 text-success hover:bg-success/15 hover:text-success", isMutating && "opacity-50")}
          onClick={() => handleMutate(AttendanceStatus.ATTENDED)}
          disabled={isMutating}
        >
          {isMutating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : "Present"}
        </Button>
        <Button 
          variant="outline" 
          className={cn("w-full border-border hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30", isMutating && "opacity-50")}
          onClick={() => handleMutate(AttendanceStatus.MISSED)}
          disabled={isMutating}
        >
          {isMutating ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : "Absent"}
        </Button>
      </div>
    );
  };

  // Phase 9.1: a session designated as the mid-semester practical is labeled
  // as such in Track (from the backend session field — never computed here);
  // everything else keeps its canonical class type.
  //
  // Option A (separate quiz-day occurrence): the backend flags ONLY the
  // materialized quiz-day session (LECTURE, is_extra=false, no timetable
  // time) — normal timetable lectures on the same quiz date are independent
  // occurrences and are NOT flagged. The flagged session gets its own card
  // labeled "Quiz Day"/"QUIZ DAY" instead of "TBD", and stays a fully
  // independent attendance occurrence (single Present/Absent, single record).
  const isQuizDaySession =
    session.is_quiz_day &&
    session.class_type === ClassType.LECTURE &&
    !session.is_extra &&
    !session.start_time;

  const displayType = session.designation === "MID_SEM_PRACTICAL" ? "MID-SEM PRACTICAL" :
                      isQuizDaySession ? "QUIZ DAY" :
                      session.class_type === ClassType.LECTURE ? "LECTURE" :
                      session.class_type === ClassType.TUTORIAL ? "TUTORIAL" : "PRACTICAL";

  return (
    <Card className={cn("p-4", session.is_cancelled && "opacity-50 grayscale")}>
      <div className="flex flex-col gap-3">
        {/* Header: Time, Subject Code, Class Type */}
        <div className="flex justify-between items-start">
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-foreground">
              {isQuizDaySession
                ? "Quiz Day"
                : session.start_time || (session.is_extra ? "Extra Class" : "TBD")}
              {!isQuizDaySession && session.end_time ? ` – ${session.end_time}` : ""}
            </span>
            <span className="text-xs text-muted-foreground font-mono mt-0.5">{session.subject_code}</span>
          </div>
          <div className="flex items-center gap-1.5">
            {/* Option A: the backend flags only the actual quiz-day
                ClassSession (shape: LECTURE, is_extra=false, no timetable
                time). Normal lectures on the same date stay unflagged. */}
            {session.is_quiz_day && (
              <Badge variant="primary" className="text-[10px] tracking-wider py-0 h-5">
                Quiz Day
              </Badge>
            )}
            <Badge variant="outline" className="text-[10px] tracking-wider py-0 h-5">
              {displayType}
            </Badge>
          </div>
        </div>

        {/* Subject Name */}
        <div className="text-sm text-foreground line-clamp-2 leading-snug">
          {session.subject_name}
        </div>

        {/* Actions / Status */}
        <div className="mt-1 flex items-center h-9">
          {getStatusDisplay()}
        </div>
      </div>
    </Card>
  );
}
