"use client";

import { PageHeader } from "@/components/shared/PageHeader";
import { SubjectAttendanceGrid } from "@/components/dashboard/SubjectAttendanceGrid";

export default function SubjectsPage() {
  return (
    <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full">
      <PageHeader 
        title="Subjects Overview" 
        description="Detailed attendance and quiz eligibility across all enrolled subjects."
      />
      
      <div className="mt-6">
        <SubjectAttendanceGrid />
      </div>
    </div>
  );
}
