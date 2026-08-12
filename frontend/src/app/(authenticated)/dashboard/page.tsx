"use client";

import { FormulaCard } from "@/components/dashboard/FormulaCard";
import { TodayClassesCard } from "@/components/dashboard/TodayClassesCard";
import { SubjectAttendanceGrid } from "@/components/dashboard/SubjectAttendanceGrid";

export default function DashboardPage() {
  return (
    <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-foreground">Overview</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Track your attendance and quiz eligibility across all subjects.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Today's Classes & Formula */}
        <div className="lg:col-span-1 space-y-6">
          <TodayClassesCard />
          <FormulaCard />
        </div>

        {/* Right Column - Subject Grid */}
        <div className="lg:col-span-2">
          <SubjectAttendanceGrid />
        </div>
      </div>
    </div>
  );
}
