"use client";

import { PageHeader } from "@/components/shared/PageHeader";
import { SubjectAttendanceGrid } from "@/components/dashboard/SubjectAttendanceGrid";
import { POOLED_ATTENDANCE_EXPLANATION } from "@/lib/formula";

export default function SubjectsPage() {
  return (
    <div className="flex-1 py-8 w-full">
      {/* UIA-004: the pooled formula is explained once here, not as body text
          on every subject card. */}
      <PageHeader 
        title="Subjects Overview" 
        description={`How your attendance is going in each enrolled subject. ${POOLED_ATTENDANCE_EXPLANATION}`}
      />
      
      <div className="mt-6">
        <SubjectAttendanceGrid />
      </div>
    </div>
  );
}
