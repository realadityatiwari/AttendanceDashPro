"use client";

import { useState } from "react";
import {
  AlertCircle,
  BookOpen,
  Plus,
  ShieldAlert,
} from "lucide-react";

import { useAdminMe, useAdminSubjects, useAdminSubjectMutations } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { EmptyState } from "@/components/shared/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AdminSubjectSummary,
  CreateSubjectRequest,
  ElectiveSlot,
  SubjectCategory,
  UpdateSubjectRequest,
} from "@/types/api";
import { CreateSubjectDialog } from "./components/CreateSubjectDialog";
import { EditSubjectDialog } from "./components/EditSubjectDialog";

/**
 * Phase 24.6 — Curriculum & Subject Management.
 *
 * Scoped subject list for the Admin Portal. Read scope is resolved
 * SERVER-SIDE (GET /api/v1/admin/subjects): HEAD_ADMIN sees all subjects,
 * CLASS_ADMIN the assigned section's semester, ELECTIVE_ADMIN the exact
 * assigned concrete subject, SUBSECTION_ADMIN an inert result. The frontend
 * renders only what the backend returns; hiding here is never a security
 * boundary. Writes (create/edit) are HEAD_ADMIN only — the backend enforces
 * 403; the buttons are hidden for non-global admins as presentation only.
 */
export default function CurriculumPage() {
  const { identity } = useAdminMe();
  const { subjects, isLoading, isError, mutate } = useAdminSubjects();
  const { createSubject, updateSubject } = useAdminSubjectMutations();

  const status = (isError as Error & { status?: number } | null)?.status;
  const isGlobal = identity?.is_global ?? false;

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<AdminSubjectSummary | null>(null);

  return (
    <div>
      <PageHeader
        title="Curriculum"
        description="Subject catalog, elective slots, and academic applicability flags. Visibility reflects your administrative scope; management is global-authority only."
      >
        <div className="flex items-center gap-2">
          <Badge variant={isGlobal ? "primary" : "neutral"}>
            {isGlobal ? "Manage" : "Read only"}
          </Badge>
          {isGlobal && (
            <Button size="sm" className="gap-2" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" />
              Add Subject
            </Button>
          )}
        </div>
      </PageHeader>

      {isLoading && !subjects ? (
        <SubjectsSkeleton />
      ) : isError ? (
        status === 403 ? (
          <ForbiddenState />
        ) : (
          <ErrorState message={(isError as Error).message} onRetry={() => mutate()} />
        )
      ) : !subjects || subjects.items.length === 0 ? (
        <EmptyState
          title="No subjects in your scope"
          message="No subjects fall inside your current administrative scope."
          icon={<BookOpen className="h-10 w-10 text-muted-foreground mb-4" />}
        />
      ) : (
        <div className="space-y-3">
          {subjects.items.map((subject) => (
            <SubjectCard
              key={subject.id}
              subject={subject}
              canEdit={isGlobal}
              onEdit={() => setEditing(subject)}
            />
          ))}
        </div>
      )}

      {isGlobal && (
        <CreateSubjectDialog
          open={createOpen}
          onOpenChange={setCreateOpen}
          onCreate={async (payload: CreateSubjectRequest) => {
            const res = await createSubject(payload);
            if (res.warnings?.length) {
              alert(res.warnings.map((w) => w.message).join("\n"));
            }
            await mutate();
          }}
        />
      )}

      {editing && (
        <EditSubjectDialog
          key={editing.id}
          subject={editing}
          open={Boolean(editing)}
          onOpenChange={(open) => !open && setEditing(null)}
          onUpdate={async (subjectId: string, payload: UpdateSubjectRequest) => {
            const res = await updateSubject(subjectId, payload);
            if (res.warnings?.length) {
              alert(res.warnings.map((w) => w.message).join("\n"));
            }
            await mutate();
          }}
        />
      )}
    </div>
  );
}

function SubjectCard({
  subject,
  canEdit,
  onEdit,
}: {
  subject: AdminSubjectSummary;
  canEdit: boolean;
  onEdit: () => void;
}) {
  const slotLabel =
    subject.elective_slot === ElectiveSlot.ELECTIVE_I
      ? "Elective-I"
      : subject.elective_slot === ElectiveSlot.ELECTIVE_II
        ? "Elective-II"
        : null;

  return (
    <GlassCard className="p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-base font-semibold text-foreground">
              {subject.code}
            </span>
            <span className="text-sm text-foreground">{subject.name}</span>
            {subject.tag && (
              <span className="text-xs text-muted-foreground">({subject.tag})</span>
            )}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {subject.semester_name}
            {subject.session_name ? ` · ${subject.session_name}` : ""}
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge variant={subject.category === SubjectCategory.LAB ? "secondary" : "neutral"}>
              {subject.category === SubjectCategory.LAB ? "Lab" : "Theory"}
            </Badge>
            {subject.is_anchor ? (
              <Badge variant="warning">Elective anchor · frozen</Badge>
            ) : slotLabel ? (
              <Badge variant="primary">{slotLabel}</Badge>
            ) : (
              <Badge variant="outline" className="text-muted-foreground">
                Common subject
              </Badge>
            )}
            <Badge variant="outline" className="text-muted-foreground">
              {subject.quiz_applicable ? "Quiz" : "No quiz"}
            </Badge>
            <Badge variant="outline" className="text-muted-foreground">
              {subject.attendance_applicable ? "Attendance" : "No attendance"}
            </Badge>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {subject.enrollment_count} enrollment
            {subject.enrollment_count === 1 ? "" : "s"} · {subject.elective_choice_count} elective
            choice{subject.elective_choice_count === 1 ? "" : "s"}
          </p>
        </div>
        {canEdit && (
          <Button variant="outline" size="sm" className="self-start" onClick={onEdit}>
            Edit
          </Button>
        )}
      </div>
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
          The curriculum is available to authorized administrators only.
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
          Could not load the curriculum
        </h1>
        {message && <p className="text-sm text-red-400/80 mt-2 max-w-md">{message}</p>}
        <Button variant="outline" size="sm" className="mt-6" onClick={onRetry}>
          Retry
        </Button>
      </div>
    </GlassCard>
  );
}

function SubjectsSkeleton() {
  return (
    <div className="space-y-3">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <Skeleton key={i} className="h-28 w-full rounded-xl" />
      ))}
    </div>
  );
}
