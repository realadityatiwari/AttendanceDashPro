"use client";

import { PageHeader } from "@/components/shared/PageHeader";
import { SubjectAttendanceGrid } from "@/components/dashboard/SubjectAttendanceGrid";

export default function SubjectsPage() {
  return (
    <div className="flex-1 py-8 w-full">
      <PageHeader 
        title="Subjects Overview" 
        description="How your attendance is going in each enrolled subject — current to today's scheduled classes."
      />
      
      <div className="mt-6">
        <SubjectAttendanceGrid />
      </div>
    </div>
  );
}
