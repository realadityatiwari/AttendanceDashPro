import { format } from "date-fns";
import { useCalendarDay, useTimetable } from "@/hooks/useApi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar, AlertCircle } from "lucide-react";
import { ClassType } from "@/types/api";

export function TodayClassesCard() {
  const todayDate = format(new Date(), "yyyy-MM-dd");
  
  const { calendarDay, isLoading: calLoading, isError: calError } = useCalendarDay(todayDate);
  const { timetable, isLoading: ttLoading, isError: ttError } = useTimetable();

  const isLoading = calLoading || ttLoading;
  const isError = calError || ttError;

  if (isLoading) {
    return (
      <Card className="mb-6 bg-surface border-border">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            Today's Classes
            <Badge variant="outline" className="text-muted-foreground animate-pulse">Loading...</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-24 flex items-center justify-center text-muted-foreground">
            Loading timetable...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="mb-6 bg-red-950/20 border-red-900/50">
        <CardContent className="pt-6">
          <div className="flex flex-col items-center justify-center text-center p-4">
            <AlertCircle className="h-8 w-8 text-red-500 mb-2" />
            <h3 className="text-sm font-semibold text-red-400">Failed to load classes</h3>
            <p className="text-xs text-red-400/80 mt-1">
              Could not retrieve the timetable or calendar data.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Filter timetable for today based on calendarDay.original_day_of_week
  // Note: timetable day_of_week is 0-indexed (Monday=0).
  const dayNameMap: Record<string, number> = {
    "MONDAY": 0, "TUESDAY": 1, "WEDNESDAY": 2, "THURSDAY": 3, "FRIDAY": 4, "SATURDAY": 5, "SUNDAY": 6
  };
  
  const effectiveDayName = calendarDay?.substitution_schedule_override || calendarDay?.original_day_of_week;
  const targetDayIdx = effectiveDayName ? dayNameMap[effectiveDayName] : -1;

  const todaysClasses = timetable?.filter(t => t.day_of_week === targetDayIdx) || [];

  return (
    <Card className="mb-6 bg-surface border-border overflow-hidden">
      <CardHeader className="pb-3 border-b border-border/50 bg-surface/50">
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-lg flex items-center gap-2 text-foreground">
              Today's Classes
              {calendarDay?.is_working_day && (
                <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/20 hover:bg-emerald-500/25">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse"></span>
                  LIVE
                </Badge>
              )}
            </CardTitle>
            <div className="text-sm text-muted-foreground mt-1 flex items-center gap-1.5">
              <Calendar className="h-3.5 w-3.5" />
              {format(new Date(), "EEEE, MMM d, yyyy")}
              {calendarDay?.substitution_schedule_override && (
                <span className="text-amber-400 ml-1">
                  (Following {calendarDay.substitution_schedule_override.toLowerCase()} schedule)
                </span>
              )}
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {!calendarDay?.is_working_day ? (
          <div className="p-8 text-center">
            <h3 className="text-base font-medium text-foreground mb-1">No Classes Today</h3>
            <p className="text-sm text-muted-foreground">
              {calendarDay?.events?.find(e => e.is_holiday)?.title || "It's a non-working day"}
            </p>
          </div>
        ) : todaysClasses.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            No classes scheduled for today.
          </div>
        ) : (
          <div className="divide-y divide-border/50">
            {todaysClasses.map((cls) => (
              <div key={cls.id} className="p-4 flex items-center justify-between hover:bg-surface2/50 transition-colors">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-semibold text-foreground text-sm">{cls.subject.code}</h4>
                    <Badge variant="outline" className="text-[10px] uppercase tracking-wider py-0 h-4 border-border/60">
                      {cls.class_type === ClassType.LECTURE ? "Lecture" : 
                       cls.class_type === ClassType.TUTORIAL ? "Tutorial" : "Practical"}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground truncate max-w-[200px] sm:max-w-md">
                    {cls.subject.name}
                  </p>
                </div>
                {/* Mutation deferred as per constraint, just showing read-only visual for now */}
                <div className="text-xs text-muted-foreground italic">
                  Attendance pending
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
