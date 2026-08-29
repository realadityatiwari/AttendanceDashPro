"use client";

import Link from "next/link";
import {
  BadgeCheck,
  Clock,
  MessageSquareText,
  ShieldCheck,
} from "lucide-react";
import { useAdminMe } from "@/hooks/useApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassCard } from "@/components/shared/GlassCard";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AdminIdentity, AdminScopeDescriptor } from "@/types/api";

// Planned portal areas (Phase 24.0 sequence). LISTED AS UNAVAILABLE — these
// are NOT implemented in Phase 24.1 and no route exists for them; the list is
// presentation text only and must never imply working functionality.
const PLANNED_AREAS = [
  "Dashboard",
  "Students",
  "Structure",
  "Curriculum",
  "Timetable",
  "Sessions & Occurrences",
  "Electives",
  "Quizzes",
  "Events",
  "Admin & Scope Management",
  "Attendance",
  "Analytics",
] as const;

/**
 * Admin Portal overview (Phase 24.1) — identity/context and truthful shell
 * status only. No administrative feature domain is implemented in this
 * phase. All authorization remains server-side; this page renders the
 * backend-provided identity for context.
 */
export default function AdminOverviewPage() {
  const { identity, isLoading } = useAdminMe();

  return (
    <div>
      <PageHeader
        title="Admin Portal"
        description="Administrative control surface for AttendanceDash Pro."
      />

      {isLoading || !identity ? (
        <div className="space-y-4">
          <Skeleton className="h-36 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
        </div>
      ) : (
        <div className="space-y-4">
          <IdentityCard identity={identity} />
          <AvailabilityCard identity={identity} />
          <PlannedAreasCard />
        </div>
      )}
    </div>
  );
}

function IdentityCard({ identity }: { identity: AdminIdentity }) {
  return (
    <GlassCard className="p-6">
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <ShieldCheck className="size-5" aria-hidden="true" />
          </span>
          <div>
            <p className="text-base font-semibold text-foreground">
              {identity.display_name}
            </p>
            <p className="font-mono text-xs text-muted-foreground">
              {identity.roll_number || "No roll number"}
            </p>
          </div>
          {identity.is_global ? (
            <Badge variant="primary" className="ml-auto">
              Global authority
            </Badge>
          ) : (
            <Badge variant="neutral" className="ml-auto">
              Scoped authority
            </Badge>
          )}
        </div>

        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Administrative roles
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {identity.roles.length > 0 ? (
              identity.roles.map((role) => (
                <Badge key={role} variant="secondary">
                  {role}
                </Badge>
              ))
            ) : (
              <span className="text-sm text-muted-foreground">None</span>
            )}
          </div>
        </div>

        {identity.scopes.length > 0 && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Assigned scopes
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {identity.scopes.map((scope, index) => (
                <ScopeBadge key={index} scope={scope} />
              ))}
            </div>
          </div>
        )}

        {identity.roles.includes("SUBSECTION_ADMIN") && !identity.is_global && (
          <div className="rounded-lg border border-border bg-muted/40 p-3">
            <p className="text-sm text-muted-foreground">
              Subsection administration is not yet operational. Subsection
              scopes are recognized but carry no active capabilities until
              subsection-aware scheduling exists.
            </p>
          </div>
        )}
      </div>
    </GlassCard>
  );
}

function ScopeBadge({ scope }: { scope: AdminScopeDescriptor }) {
  let target = "No target resolved";
  if (scope.role === "CLASS_ADMIN" && scope.section_name) {
    target = `Section ${scope.section_name}`;
  } else if (scope.role === "SUBSECTION_ADMIN" && scope.subsection_name) {
    target = `Subsection ${scope.subsection_name}`;
  } else if (scope.role === "ELECTIVE_ADMIN" && scope.subject_code) {
    target = scope.subject_name
      ? `${scope.subject_code} — ${scope.subject_name}`
      : scope.subject_code;
  }
  return (
    <Badge variant="outline">
      {scope.role}: {target}
    </Badge>
  );
}

function AvailabilityCard({ identity }: { identity: AdminIdentity }) {
  return (
    <GlassCard className="p-6">
      <div className="flex items-center gap-2">
        <BadgeCheck className="size-4 text-primary" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-foreground">
          Available now
        </h2>
      </div>
      {identity.is_global ? (
        <div className="mt-4 flex flex-col gap-3">
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
          <p className="text-xs text-muted-foreground">
            Event, laboratory, and mid-sem administrative controls remain on
            their existing surfaces and stay server-gated.
          </p>
        </div>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          No portal feature areas are available to your assigned scopes yet.
          Your administrative authority is enforced server-side on the
          existing authorized surfaces.
        </p>
      )}
    </GlassCard>
  );
}

function PlannedAreasCard() {
  return (
    <GlassCard className="p-6">
      <div className="flex items-center gap-2">
        <Clock className="size-4 text-muted-foreground" aria-hidden="true" />
        <h2 className="text-sm font-semibold text-foreground">
          Coming in later phases
        </h2>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        The following administrative areas are planned for later phases of the
        Admin Portal and are not available yet.
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {PLANNED_AREAS.map((area) => (
          <Badge key={area} variant="neutral">
            {area}
          </Badge>
        ))}
      </div>
    </GlassCard>
  );
}
