"use client";

import { useSubjects } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { SubjectLaboratoryView } from "@/components/dashboard/SubjectLaboratoryView";
import { SubjectCategory } from "@/types/api";
import { Beaker } from "lucide-react";

export default function LaboratoryPage() {
  const { subjects, isLoading, isError } = useSubjects();

  if (isError) {
    return (
      <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-4xl mx-auto w-full">
        <PageHeader title="Laboratory Manager" />
        <ErrorState message="Could not load enrolled subjects to identify your laboratories." />
      </div>
    );
  }

  // Find subjects that are considered LAB category
  const labSubjects = subjects?.filter(s => s.category === SubjectCategory.LAB) || [];

  return (
    <div className="flex-1 px-4 py-8 sm:px-6 lg:px-8 max-w-4xl mx-auto w-full">
      <PageHeader 
        title="Laboratory Manager" 
        description="Track your experiment signatures, rework status, and lab progress."
      />

      {isLoading ? (
        <div className="space-y-6">
          <div className="h-64 animate-pulse bg-surface/50 rounded-xl border border-border" />
        </div>
      ) : labSubjects.length === 0 ? (
        <EmptyState 
          title="No laboratory subjects" 
          message="You are not enrolled in any laboratory subjects this semester."
          icon={<Beaker className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      ) : (
        <div className="space-y-6">
          {labSubjects.map(subject => (
            <SubjectLaboratoryView key={subject.id} subjectCode={subject.code} />
          ))}
        </div>
      )}
    </div>
  );
}
