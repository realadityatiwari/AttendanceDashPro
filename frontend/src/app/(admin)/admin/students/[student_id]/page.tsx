"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, ArrowLeft, ShieldAlert, Users } from "lucide-react";
import { useAdminStudentDetail } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminStudentDetail } from "@/types/api";
import { formatShortDate } from "@/lib/date";

/**
 * Phase 24.3 scoped student detail (read-only academic context).
 *
 * Data comes from GET /api/v1/admin/students/{id} — the authoritative
 * StudentContextService composition (placement, enrollments with
 * COMPULSORY/ELECTIVE types, elective choices, inconsistencies). Out-of-scope
 * and nonexistent students return 404 and are shown as a not-found state (no
 * existence leak). No attendance mathematics here — that is the Phase 24.13
 * attendance-admin domain.
 */
export default function AdminStudentDetailPage() {
  const params = useParams<{ student_id: string }>();
  const { student, isLoading, isError, mutate } = useAdminStudentDetail(
    params?.student_id ?? null
  );

  const status = (isError as Error & { status?: number } | null)?.status;

  return (
    <div>
      <Button
        variant="ghost"
        size="sm"
        className="mb-4"
        nativeButton={false}
        render={<Link href="/admin/students" />}
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        Back to students
      </Button>

      {isLoading && !student ? (
        <DetailSkeleton />
      ) : isError ? (
        status === 404 ? (
          <EmptyState
            title="Student not found"
            message="This student does not exist or is outside your administrative scope."
            icon={<Users className="h-10 w-10 text-muted-foreground mb-4" />}
          />
        ) : status === 403 ? (
          <GlassCard className="max-w-2xl">
            <div className="flex flex-col items-center justify-center text-center p-8">
              <ShieldAlert className="h-10 w-10 text-warning mb-4" />
              <h1 className="text-lg font-semibold text-foreground">
                Administrative access required
              </h1>
              <p className="text-sm text-muted-foreground mt-2 max-w-md">
                This authenticated account does not hold an administrative
                role. Student details are available to authorized
                administrators only.
              </p>
            </div>
          </GlassCard>
        ) : (
          <ErrorState message={(isError as Error).message} onRetry={() => mutate()} />
        )
      ) : !student ? (
        <DetailSkeleton />
      ) : (
        <DetailContent student={student} />
      )}
    </div>
  );
}

function DetailContent({ student }: { student: AdminStudentDetail }) {
  return (
    <div className="space-y-4">
      <PageHeader title={student.name} description={student.roll_number}>
        <div className="flex items-center gap-2">
          {student.is_placed && student.section_name ? (
            <Badge variant="secondary">{student.section_name}</Badge>
          ) : (
            <Badge variant="warning">Unplaced</Badge>
          )}
          {student.program && <Badge variant="neutral">{student.program}</Badge>}
        </div>
      </PageHeader>

      {student.inconsistencies.length > 0 && (
        <GlassCard className="border-warning/40">
          <div className="p-4">
            <h2 className="text-sm font-semibold text-warning">
              Data-quality warnings
            </h2>
            <ul className="mt-2 space-y-1">
              {student.inconsistencies.map((inc, i) => (
                <li key={i} className="text-sm text-muted-foreground">
                  {inc}
                </li>
              ))}
            </ul>
          </div>
        </GlassCard>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <PlacementCard student={student} />
        <ElectiveCard student={student} />
        <EnrollmentsCard
          title="Compulsory subjects"
          subjects={student.compulsory_subjects}
        />
        <EnrollmentsCard
          title="Elective subjects"
          subjects={student.elective_subjects}
        />
      </div>
    </div>
  );
}

function PlacementCard({ student }: { student: AdminStudentDetail }) {
  const rows: { label: string; value: string }[] = [
    { label: "Academic session", value: student.academic_session_name ?? "None" },
    { label: "Semester", value: student.semester_name ?? "None" },
    { label: "Section", value: student.section_name ?? "Unplaced" },
    { label: "Subsection", value: student.subsection_name ?? "Unassigned" },
    { label: "Program", value: student.program ?? "—" },
    {
      label: "Semester dates",
      value:
        student.semester_start && student.semester_end
          ? `${formatShortDate(student.semester_start)} – ${formatShortDate(student.semester_end)}`
          : "—",
    },
  ];
  return (
    <GlassCard>
      <div className="p-4">
        <h2 className="text-sm font-semibold text-foreground">Placement</h2>
        <dl className="mt-2 divide-y divide-border/60">
          {rows.map((r) => (
            <div
              key={r.label}
              className="flex items-center justify-between gap-3 py-2"
            >
              <dt className="text-sm text-muted-foreground">{r.label}</dt>
              <dd className="text-sm font-medium text-foreground">{r.value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </GlassCard>
  );
}

function ElectiveCard({ student }: { student: AdminStudentDetail }) {
  const entries = Object.entries(student.elective_choices);
  return (
    <GlassCard>
      <div className="p-4">
        <h2 className="text-sm font-semibold text-foreground">
          Department electives
        </h2>
        {entries.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            No elective selection recorded.
          </p>
        ) : (
          <dl className="mt-2 divide-y divide-border/60">
            {entries.map(([slot, code]) => (
              <div
                key={slot}
                className="flex items-center justify-between gap-3 py-2"
              >
                <dt className="text-sm text-muted-foreground">{slot}</dt>
                <dd className="text-sm font-medium text-foreground">{code}</dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </GlassCard>
  );
}

function EnrollmentsCard({
  title,
  subjects,
}: {
  title: string;
  subjects: AdminStudentDetail["compulsory_subjects"];
}) {
  return (
    <GlassCard>
      <div className="p-4">
        <h2 className="text-sm font-semibold text-foreground">{title}</h2>
        {subjects.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">
            No subjects in this category.
          </p>
        ) : (
          <ul className="mt-2 space-y-1.5">
            {subjects.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between gap-3"
              >
                <span className="text-sm font-medium text-foreground">
                  {s.code}
                </span>
                <span className="truncate text-sm text-muted-foreground">
                  {s.name}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </GlassCard>
  );
}

function ErrorState({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <GlassCard className="max-w-2xl border-red-900/50 bg-red-950/20">
      <div className="flex flex-col items-center justify-center text-center p-8">
        <AlertCircle className="h-10 w-10 text-red-500 mb-4" />
        <h1 className="text-lg font-semibold text-red-400">
          Could not load the student
        </h1>
        {message && <p className="text-sm text-red-400/80 mt-2 max-w-md">{message}</p>}
        <Button variant="outline" size="sm" className="mt-6" onClick={onRetry}>
          Retry
        </Button>
      </div>
    </GlassCard>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-64" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    </div>
  );
}
