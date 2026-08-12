import { useSubjects } from "@/hooks/useApi";
import { SubjectAttendanceCard } from "./SubjectAttendanceCard";
import { AlertCircle } from "lucide-react";
import { SubjectCategory } from "@/types/api";

export function SubjectAttendanceGrid() {
  const { subjects, isLoading, isError } = useSubjects();

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-40 bg-surface rounded-xl border border-border animate-pulse"></div>
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6 bg-red-950/20 border border-red-900/50 rounded-xl text-center">
        <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-2" />
        <h3 className="text-sm font-semibold text-red-400">Failed to load subjects</h3>
        <p className="text-xs text-red-400/80 mt-1">
          Could not retrieve your enrolled subjects from the server.
        </p>
      </div>
    );
  }

  if (!subjects || subjects.length === 0) {
    return (
      <div className="p-8 bg-surface border border-border rounded-xl text-center">
        <h3 className="text-sm font-semibold text-foreground">No subjects found</h3>
        <p className="text-xs text-muted-foreground mt-1">
          You are not currently enrolled in any subjects.
        </p>
      </div>
    );
  }

  // Filter out LAB category or group them if needed. 
  // Based on legacy, labs have a separate tool, but we can show them if attendance_applicable is true.
  const displaySubjects = subjects.filter(s => s.attendance_applicable);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {displaySubjects.map((subject) => (
        <SubjectAttendanceCard key={subject.id} subject={subject} />
      ))}
    </div>
  );
}
