"use client";

import Link from "next/link";
import {
  AlertCircle,
  BarChart3,
  BookOpen,
  CalendarClock,
  CalendarDays,
  ClipboardList,
  GraduationCap,
  LayoutGrid,
  MessageSquareText,
  ShieldAlert,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useAdminMe, useAdminDashboard } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { MetricCard } from "@/components/admin/dashboard/MetricCard";
import { AdminSectionCard, StatRow } from "@/components/admin/dashboard/AdminSectionCard";
import { AdminWarningsCard } from "@/components/admin/dashboard/AdminWarningsCard";
import { AdminEventsCard } from "@/components/admin/dashboard/AdminEventsCard";
import { formatPct, formatShortDate } from "@/lib/date";
import { AdminDashboardResponse } from "@/types/api";

// Planned portal areas (Phase 24.0 sequence). PRESENTATION ONLY — these are
// NOT implemented and no route exists; the phase hint is the discovery
// sequence, never a claim of availability.
// NOTE: Phase 24.5 (Academic Structure), Phase 24.6 (Curriculum), Phase
// 24.7 (Timetable), Phase 24.8 (Quiz Schedules), Phase 24.9 (Events),
// Phase 24.10 (Subject-Specific Elective Events), Phase 24.11 (Admin &
// Scope Management) and Phase 24.12 (Attendance Admin & Analytics) are NOW
// implemented and have been removed from this list and added to the
// "Available now" section.
const FUTURE_AREAS: { label: string; phase: string }[] = [
  { label: "Integration & Hardening", phase: "Phase 24.13" },
] as const;

/**
 * HEAD_ADMIN operational dashboard (Phase 24.2) — replaces the Phase 24.1
 * placeholder overview on /admin. All numbers come from the backend read
 * model (GET /api/v1/admin/dashboard, require_head_admin). Scoped admins
 * receive the backend 403 and are shown an honest HEAD-only state — never
 * elevated to a fake global dashboard.
 */
export default function AdminDashboardPage() {
  const { identity } = useAdminMe();
  const { dashboard, isLoading, isError, mutate } = useAdminDashboard();

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Current academic and operational state of AttendanceDash Pro."
      >
        {identity && (
          <div className="flex items-center gap-2">
            {identity.is_global ? (
              <Badge variant="primary">Global authority</Badge>
            ) : (
              <Badge variant="neutral">Scoped authority</Badge>
            )}
            <span className="hidden text-sm text-muted-foreground sm:block">
              {identity.display_name}
            </span>
          </div>
        )}
      </PageHeader>

      {isLoading || !dashboard ? (
        <DashboardSkeleton />
      ) : isError ? (
        <DashboardErrorState status={(isError as Error & { status?: number }).status} onRetry={() => mutate()} />
      ) : (
        <DashboardContent dashboard={dashboard} />
      )}
    </div>
  );
}

function DashboardContent({ dashboard }: { dashboard: AdminDashboardResponse }) {
  const { academic, curriculum, students, schedule, events, quizzes, attendance, warnings } = dashboard;

  const academicRows: StatRow[] = [
    { label: "Active session", value: academic.active_session ?? "None" },
    { label: "Semesters in session", value: academic.semester_count },
    ...(academic.semester_name ? [{ label: "Semester", value: academic.semester_name }] : []),
    { label: "Sections", value: academic.section_count },
    { label: "Programs", value: academic.program_count },
    { label: "Subjects", value: academic.subject_count },
    { label: "Students", value: academic.student_count },
  ];

  const curriculumRows: StatRow[] = [
    { label: "Theory subjects", value: curriculum.theory_subjects },
    { label: "Lab subjects", value: curriculum.lab_subjects },
    { label: "Elective-I catalog", value: curriculum.elective_i_subjects },
    { label: "Elective-II catalog", value: curriculum.elective_ii_subjects },
    { label: "Compulsory enrollments", value: curriculum.compulsory_enrollments },
    { label: "Elective enrollments", value: curriculum.elective_enrollments },
  ];

  const studentRows: StatRow[] = [
    { label: "Total students", value: students.total },
    { label: "Placed (section assigned)", value: students.placed },
    { label: "Unplaced", value: students.unplaced },
    { label: "Subsection assigned", value: students.subsection_assigned },
    { label: "Subsection unassigned", value: students.subsection_unassigned },
    { label: "Students with elective choices", value: students.elective_choice_holders },
    { label: "Elective choice rows", value: students.elective_choices_total },
  ];

  const scheduleRows: StatRow[] = [
    { label: "Timetable entries", value: schedule.timetable_entry_count },
    { label: "Class sessions (total)", value: schedule.class_session_total },
    { label: "Cancelled (anchor)", value: schedule.class_sessions_cancelled },
    { label: "Extra", value: schedule.class_sessions_extra },
    { label: "Sessions today", value: schedule.sessions_today },
    { label: "Upcoming sessions", value: schedule.upcoming_sessions },
    { label: "Occurrence outcomes", value: schedule.occurrence_outcomes },
  ];

  const quizRows: StatRow[] = [
    { label: "Quiz cycles", value: quizzes.cycle_count },
    { label: "Schedules (total)", value: quizzes.schedule_total },
    { label: "Scheduled with date", value: quizzes.scheduled_dated },
    { label: "Unresolved", value: quizzes.unresolved },
    { label: "Cancelled", value: quizzes.cancelled },
    {
      label: "Next quiz date",
      value: quizzes.next_quiz_date ? formatShortDate(quizzes.next_quiz_date) : "None",
    },
  ];

  const attendanceRows: StatRow[] = [
    { label: "Attendance records", value: attendance.total_records },
    { label: "Attended", value: attendance.attended },
    { label: "Missed", value: attendance.missed },
    { label: "Recorded percentage", value: formatPct(attendance.recorded_pct) },
    { label: "Participants", value: attendance.participants },
  ];

  return (
    <div className="space-y-4">
      <AdminWarningsCard warnings={warnings} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Students" value={students.total} icon={Users} />
        <MetricCard label="Sections" value={academic.section_count} icon={LayoutGrid} />
        <MetricCard label="Subjects" value={academic.subject_count} icon={BookOpen} />
        <MetricCard label="Timetable entries" value={schedule.timetable_entry_count} icon={ClipboardList} />
        <MetricCard label="Class sessions" value={schedule.class_session_total} icon={CalendarDays} />
        <MetricCard label="Attendance records" value={attendance.total_records} icon={GraduationCap} />
        <MetricCard label="Active events" value={events.total_active} icon={CalendarClock} />
        <MetricCard label="Quiz schedules" value={quizzes.schedule_total} icon={CalendarClock} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <AdminSectionCard
          title="Academic status"
          icon={LayoutGrid}
          description={
            academic.active_session
              ? `${academic.active_session}${
                  academic.semester_count > 1
                    ? ` · ${academic.semester_count} semesters`
                    : academic.semester_name
                      ? ` · ${academic.semester_name}`
                      : ""
                }`
              : "No active session configured"
          }
          rows={academicRows}
        />
        <AdminSectionCard
          title="Students"
          icon={Users}
          description="Registered student accounts and assignment status"
          rows={studentRows}
        />
        <AdminSectionCard
          title="Curriculum"
          icon={BookOpen}
          description="Subject catalog and enrollment distribution"
          rows={curriculumRows}
        />
        <AdminSectionCard
          title="Schedule"
          icon={ClipboardList}
          description="Timetable and class-session counts (read-only)"
          rows={scheduleRows}
        />
        <AdminSectionCard
          title="Quizzes"
          icon={CalendarClock}
          description="Quiz cycles and schedule projection status"
          rows={quizRows}
        />
        <AdminSectionCard
          title="Attendance"
          icon={GraduationCap}
          description={
            attendance.recorded_pct !== null
              ? `${formatPct(attendance.recorded_pct)} recorded (Attended / Attended + Missed)`
              : "No recorded attendance yet"
          }
          rows={attendanceRows}
        />
      </div>

      <AdminEventsCard events={events} />

      <GlassCard className="p-6">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-primary" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-foreground">
            Available now
          </h2>
        </div>
        <div className="mt-4 flex flex-col gap-3">
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <Users
                className="size-4 text-muted-foreground"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Students
                </p>
                <p className="text-xs text-muted-foreground">
                  Scoped student list, search and academic context.
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
              Open
            </Button>
          </div>
          {/* Phase 24.6: Curriculum (scoped reads; writes HEAD_ADMIN only) */}
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <BookOpen
                className="size-4 text-muted-foreground"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Curriculum
                </p>
                <p className="text-xs text-muted-foreground">
                  Subject catalog, elective slots, and applicability flags
                  (management is global-administrator only).
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="self-start sm:self-auto"
              nativeButton={false}
              render={<Link href="/admin/curriculum" />}
            >
              Open
            </Button>
          </div>
          {/* Phase 24.7-D: Timetable (scoped reads; writes HEAD + CLASS only) */}
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <CalendarDays
                className="size-4 text-muted-foreground"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Timetable
                </p>
                <p className="text-xs text-muted-foreground">
                  Weekly academic schedule per section, with conflict detection
                  and elective-slot resolution (management is global or section-scoped).
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="self-start sm:self-auto"
              nativeButton={false}
              render={<Link href="/admin/timetable" />}
            >
              Open
            </Button>
          </div>
          {/* Phase 24.8: Quiz Schedules (scoped reads; writes HEAD_ADMIN only) */}
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <ClipboardList
                className="size-4 text-muted-foreground"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Quiz Schedules
                </p>
                <p className="text-xs text-muted-foreground">
                  Quiz cycles, dates, and targets — synchronized with the
                  authoritative QUIZ_DAY events (management is global only).
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="self-start sm:self-auto"
              nativeButton={false}
              render={<Link href="/admin/quizzes" />}
            >
              Open
            </Button>
          </div>
          {/* Phase 24.9: Events (scoped reads; global/closure writes HEAD-only) */}
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <CalendarClock
                className="size-4 text-muted-foreground"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Events
                </p>
                <p className="text-xs text-muted-foreground">
                  Holidays, extras, cancellations, and quizzes — through the
                  canonical event architecture (quiz-schedule-managed QUIZ_DAY
                  events stay in Quiz Schedules).
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="self-start sm:self-auto"
              nativeButton={false}
              render={<Link href="/admin/events" />}
            >
              Open
            </Button>
          </div>
          {/* Phase 24.11: Admins & Scopes (HEAD_ADMIN only) */}
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <ShieldCheck
                className="size-4 text-muted-foreground"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Admins
                </p>
                <p className="text-xs text-muted-foreground">
                  Administrative accounts and their scopes — assignment,
                  revocation (deactivation), and reactivation (global only).
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="self-start sm:self-auto"
              nativeButton={false}
              render={<Link href="/admin/admins" />}
            >
              Open
            </Button>
          </div>
          {/* Phase 24.12: Attendance analytics (scoped reads) */}
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <BarChart3
                className="size-4 text-muted-foreground"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Attendance
                </p>
                <p className="text-xs text-muted-foreground">
                  Read-only attendance analytics by section and subject, scoped
                  to the viewer&apos;s authority (global / class / elective).

                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="self-start sm:self-auto"
              nativeButton={false}
              render={<Link href="/admin/attendance" />}
            >
              Open
            </Button>
          </div>
          {/* Phase 24.5: Academic Structure (HEAD_ADMIN only) */}
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <BookOpen
                className="size-4 text-muted-foreground"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Academic Structure
                </p>
                <p className="text-xs text-muted-foreground">
                  Manage sessions, semesters, sections, and subsections (global administrators).
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="self-start sm:self-auto"
              nativeButton={false}
              render={<Link href="/admin/structure" />}
            >
              Open
            </Button>
          </div>
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <MessageSquareText
                className="size-4 text-muted-foreground"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-foreground">
                  Feedback Review
                </p>
                <p className="text-xs text-muted-foreground">
                  Review user feedback submissions (global administrators).
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="self-start sm:self-auto"
              nativeButton={false}
              render={<Link href="/tools/feedback" />}
            >
              Open
            </Button>
          </div>
        </div>
      </GlassCard>

      <GlassCard className="p-6">
        <div className="flex items-center gap-2">
          <CalendarDays className="size-4 text-muted-foreground" aria-hidden="true" />
          <h2 className="text-sm font-semibold text-foreground">
            Planned portal areas
          </h2>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          These administrative domains are planned for later phases and are
          not available yet. Nothing here links to fabricated pages.
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {FUTURE_AREAS.map((area) => (
            <Badge key={area.label} variant="neutral" className="gap-1">
              {area.label}
              <span className="text-muted-foreground/70">· {area.phase}</span>
            </Badge>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}

function DashboardErrorState({ status, onRetry }: { status?: number; onRetry: () => void }) {
  if (status === 403) {
    return (
      <GlassCard className="max-w-2xl">
        <div className="flex flex-col items-center justify-center text-center p-8">
          <ShieldAlert className="h-10 w-10 text-warning mb-4" />
          <h1 className="text-lg font-semibold text-foreground">
            Global administrator dashboard
          </h1>
          <p className="text-sm text-muted-foreground mt-2 max-w-md">
            The operational dashboard is available to global (HEAD_ADMIN)
            administrators only. Your scoped administrative authority remains
            enforced server-side on the existing authorized surfaces.
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-6"
            nativeButton={false}
            render={<Link href="/dashboard" />}
          >
            Go to student app
          </Button>
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="max-w-2xl border-red-900/50 bg-red-950/20">
      <div className="flex flex-col items-center justify-center text-center p-8">
        <AlertCircle className="h-10 w-10 text-red-500 mb-4" />
        <h1 className="text-lg font-semibold text-red-400">
          Could not load the dashboard
        </h1>
        <p className="text-sm text-red-400/80 mt-2 max-w-md">
          The server could not provide the administrative dashboard.
        </p>
        <Button variant="outline" size="sm" className="mt-6" onClick={onRetry}>
          Retry
        </Button>
      </div>
    </GlassCard>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-64 rounded-xl" />
        ))}
      </div>
    </div>
  );
}
