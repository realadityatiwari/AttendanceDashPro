"use client";

import Link from "next/link";
import { AlertCircle, BarChart3, CalendarClock } from "lucide-react";

import { useAdminAttendanceSections, useAdminAttendanceSubjects } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { AdminSectionAttendanceSummary, AdminSubjectAttendanceSummary } from "@/types/api";

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${v.toFixed(1)}%`;
}

function SectionTable({ items, range }: { items: AdminSectionAttendanceSummary[]; range?: string | null }) {
  return (
    <GlassCard className="overflow-hidden">
      <div className="flex items-center justify-between px-4 pt-4">
        <h2 className="text-sm font-semibold text-foreground">Section attendance</h2>
        {range && <span className="text-xs text-muted-foreground">through {range}</span>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-3">Section</th>
              <th className="px-4 py-3 text-right">Students</th>
              <th className="px-4 py-3 text-right">Scheduled</th>
              <th className="px-4 py-3 text-right">Cancelled</th>
              <th className="px-4 py-3 text-right">Extra</th>
              <th className="px-4 py-3 text-right">Attended</th>
              <th className="px-4 py-3 text-right">Missed</th>
              <th className="px-4 py-3 text-right">Pending</th>
              <th className="px-4 py-3 text-right">Current %</th>
              <th className="px-4 py-3 text-right">Forecast %</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.section_id} className="border-b border-border/60 last:border-0">
                <td className="px-4 py-3 font-medium">{s.section_name}</td>
                <td className="px-4 py-3 text-right">{s.students}</td>
                <td className="px-4 py-3 text-right">{s.scheduled}</td>
                <td className="px-4 py-3 text-right text-muted-foreground">{s.cancelled}</td>
                <td className="px-4 py-3 text-right text-muted-foreground">{s.extra}</td>
                <td className="px-4 py-3 text-right text-green-600">{s.attended}</td>
                <td className="px-4 py-3 text-right text-red-600">{s.missed}</td>
                <td className="px-4 py-3 text-right text-muted-foreground">{s.pending}</td>
                <td className="px-4 py-3 text-right font-medium">{pct(s.current_pct)}</td>
                <td className="px-4 py-3 text-right">{pct(s.forecast_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
}

function SubjectTable({ items, range }: { items: AdminSubjectAttendanceSummary[]; range?: string | null }) {
  return (
    <GlassCard className="overflow-hidden">
      <div className="flex items-center justify-between px-4 pt-4">
        <h2 className="text-sm font-semibold text-foreground">Subject attendance (roster)</h2>
        {range && <span className="text-xs text-muted-foreground">through {range}</span>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="px-4 py-3">Subject</th>
              <th className="px-4 py-3 text-right">Roster</th>
              <th className="px-4 py-3 text-right">Scheduled</th>
              <th className="px-4 py-3 text-right">Cancelled</th>
              <th className="px-4 py-3 text-right">Extra</th>
              <th className="px-4 py-3 text-right">Attended</th>
              <th className="px-4 py-3 text-right">Missed</th>
              <th className="px-4 py-3 text-right">Pending</th>
              <th className="px-4 py-3 text-right">Current %</th>
              <th className="px-4 py-3 text-right">Forecast %</th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.subject_id} className="border-b border-border/60 last:border-0">
                <td className="px-4 py-3 font-medium">
                  <span className="font-mono text-xs text-muted-foreground mr-2">{s.code}</span>
                  {s.name}
                </td>
                <td className="px-4 py-3 text-right">{s.roster}</td>
                <td className="px-4 py-3 text-right">{s.scheduled}</td>
                <td className="px-4 py-3 text-right text-muted-foreground">{s.cancelled}</td>
                <td className="px-4 py-3 text-right text-muted-foreground">{s.extra}</td>
                <td className="px-4 py-3 text-right text-green-600">{s.attended}</td>
                <td className="px-4 py-3 text-right text-red-600">{s.missed}</td>
                <td className="px-4 py-3 text-right text-muted-foreground">{s.pending}</td>
                <td className="px-4 py-3 text-right font-medium">{pct(s.current_pct)}</td>
                <td className="px-4 py-3 text-right">{pct(s.forecast_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  );
}

function ErrorState({ message, onRetry }: { message?: string; onRetry: () => void }) {
  return (
    <GlassCard className="max-w-2xl border-red-900/50 bg-red-950/20">
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <AlertCircle className="mb-4 h-10 w-10 text-red-500" />
        <h1 className="text-lg font-semibold text-red-400">Could not load attendance analytics</h1>
        {message && <p className="mt-2 max-w-md text-sm text-red-400/80">{message}</p>}
        <Button variant="outline" size="sm" className="mt-6" onClick={onRetry}>Retry</Button>
      </div>
    </GlassCard>
  );
}

export default function AdminAttendancePage() {
  const sections = useAdminAttendanceSections();
  const subjects = useAdminAttendanceSubjects();

  const loading = (sections.isLoading || subjects.isLoading) && !sections.data && !subjects.data;
  const error = sections.isError || subjects.isError;

  return (
    <div>
      <PageHeader
        title="Attendance"
        description="Read-only attendance analytics over the canonical session/attendance pipeline. Scope follows the viewer: global admin sees all sections and subjects; class admin sees their own section; elective admin sees their assigned subject's roster."
      />
      <div className="mb-4 flex flex-wrap gap-2">
        <Badge variant="neutral">Read-only — no attendance correction</Badge>
        <Badge variant="neutral">Cancelled sessions counted separately</Badge>
        <Badge variant="neutral">Pending never counted absent</Badge>
      </div>

      {loading ? (
        <div className="space-y-3">{[0, 1].map((i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}</div>
      ) : error ? (
        <ErrorState message={(error as Error).message} onRetry={() => { sections.mutate(); subjects.mutate(); }} />
      ) : (
        <div className="space-y-6">
          {(sections.data?.items.length ?? 0) > 0 && (
            <SectionTable items={sections.data!.items} range={sections.data!.range_end} />
          )}
          {(subjects.data?.items.length ?? 0) > 0 && (
            <SubjectTable items={subjects.data!.items} range={subjects.data!.range_end} />
          )}
          {(sections.data?.items.length ?? 0) === 0 && (subjects.data?.items.length ?? 0) === 0 && (
            <GlassCard>
              <div className="flex flex-col items-center justify-center p-8 text-center">
                <BarChart3 className="mb-4 h-10 w-10 text-muted-foreground" />
                <h2 className="text-base font-semibold text-foreground">No attendance data in scope</h2>
                <p className="mt-1 max-w-md text-sm text-muted-foreground">
                  No sections or subjects are within the current admin scope for the active academic session.
                </p>
              </div>
            </GlassCard>
          )}
        </div>
      )}

      <div className="mt-8">
        <GlassCard className="p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <CalendarClock className="size-4 text-muted-foreground" aria-hidden="true" />
              <div>
                <p className="text-sm font-medium text-foreground">Per-student attendance</p>
                <p className="text-xs text-muted-foreground">
                  Open a student to view their canonical attendance overview (scope-checked).
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="self-start sm:self-auto"
              nativeButton={false}
              render={<Link href="/admin/students" />}
            >
              Browse students
            </Button>
          </div>
        </GlassCard>
      </div>
    </div>
  );
}