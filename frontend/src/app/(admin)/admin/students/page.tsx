"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { AlertCircle, Search, ShieldAlert, Users } from "lucide-react";
import { useAdminStudents } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { AdminStudentSummary } from "@/types/api";

const PAGE_SIZE = 20;

/**
 * Phase 24.3 scoped student list/search for the Admin Portal.
 *
 * Scope is resolved SERVER-SIDE from the acting admin's active scopes
 * (GET /api/v1/admin/students): HEAD_ADMIN sees all, CLASS_ADMIN the assigned
 * sections, ELECTIVE_ADMIN the choice-roster, SUBSECTION_ADMIN an inert empty
 * result. The frontend renders only what the backend returns; hiding here is
 * never a security boundary. Loading / error / empty / inert states are
 * truthful and mutually exclusive.
 */
export default function AdminStudentsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  // Debounce-free deliberate re-fetch per submitted query (single logical
  // SWR key per (q, page)); the Enter/submit handler owns query changes.
  const q = useMemo(() => search.trim(), [search]);
  const { students, isLoading, isError, mutate } = useAdminStudents({
    q: q || undefined,
    page,
    page_size: PAGE_SIZE,
  });

  const status = (isError as Error & { status?: number } | null)?.status;

  return (
    <div>
      <PageHeader
        title="Students"
        description="Scoped student list and search. Visibility reflects your administrative scope."
      >
        <div className="flex items-center gap-2">
          <Badge variant="neutral">Read only</Badge>
        </div>
      </PageHeader>

      <form
        className="mb-4 flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
        }}
      >
        <div className="relative w-full max-w-md">
          <Search
            className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by roll number or name"
            aria-label="Search students"
            className="pl-8"
          />
        </div>
        <Button type="submit" variant="outline" size="sm">
          Search
        </Button>
      </form>

      {isLoading && !students ? (
        <ListSkeleton />
      ) : isError ? (
        status === 403 ? (
          <ForbiddenState />
        ) : (
          <ErrorState message={(isError as Error).message} onRetry={() => mutate()} />
        )
      ) : !students ? (
        <ListSkeleton />
      ) : students.items.length === 0 ? (
        <EmptyState
          title={q ? "No students match your search" : "No students in your scope"}
          message={
            q
              ? "Try a different roll number or name."
              : "No student accounts fall inside your current administrative scope."
          }
          icon={<Users className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      ) : (
        <StudentList students={students.items} total={students.total} page={students.page} pages={students.pages} onPage={setPage} />
      )}
    </div>
  );
}

function StudentList({
  students,
  total,
  page,
  pages,
  onPage,
}: {
  students: AdminStudentSummary[];
  total: number;
  page: number;
  pages: number;
  onPage: (p: number) => void;
}) {
  return (
    <GlassCard>
      <div className="flex items-center justify-between gap-3 border-b border-border/60 px-4 py-3">
        <p className="text-sm text-muted-foreground">
          {total} student{total === 1 ? "" : "s"}
        </p>
        <p className="text-xs text-muted-foreground">
          Page {page} of {Math.max(pages, 1)}
        </p>
      </div>

      <ul className="divide-y divide-border/60">
        {students.map((s) => (
          <li key={s.id}>
            <Link
              href={`/admin/students/${s.id}`}
              className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-muted/40"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">
                  {s.name}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {s.roll_number}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {s.section_name ? (
                  <Badge variant="secondary">{s.section_name}</Badge>
                ) : (
                  <Badge variant="warning">Unplaced</Badge>
                )}
                {s.subsection_name && (
                  <Badge variant="neutral">{s.subsection_name}</Badge>
                )}
              </div>
            </Link>
          </li>
        ))}
      </ul>

      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 border-t border-border/60 px-4 py-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-xs text-muted-foreground tabular-nums">
            {page} / {pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pages}
            onClick={() => onPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </GlassCard>
  );
}

function ForbiddenState() {
  return (
    <GlassCard className="max-w-2xl">
      <div className="flex flex-col items-center justify-center text-center p-8">
        <ShieldAlert className="h-10 w-10 text-warning mb-4" />
        <h1 className="text-lg font-semibold text-foreground">
          Administrative access required
        </h1>
        <p className="text-sm text-muted-foreground mt-2 max-w-md">
          This authenticated account does not hold an administrative role. The
          student list is available to authorized administrators only.
        </p>
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
          Could not load the student list
        </h1>
        {message && <p className="text-sm text-red-400/80 mt-2 max-w-md">{message}</p>}
        <Button variant="outline" size="sm" className="mt-6" onClick={onRetry}>
          Retry
        </Button>
      </div>
    </GlassCard>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-3">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <Skeleton key={i} className="h-16 w-full rounded-xl" />
      ))}
    </div>
  );
}
