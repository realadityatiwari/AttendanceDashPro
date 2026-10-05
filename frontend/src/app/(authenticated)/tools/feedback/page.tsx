"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useProfile, useAdminFeedback } from "@/hooks/useApi";
import { useAuth } from "@/contexts/AuthContext";
import { FeedbackType } from "@/types/api";
import { PageHeader } from "@/components/shared/PageHeader";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { formatTimestampDate } from "@/lib/date";
import { FEEDBACK_TYPES, feedbackTypeBadgeClass } from "@/lib/canonicalStatus";
import { MessageSquareText, RefreshCw } from "lucide-react";

// Filter values are backend contract values; labels/classes come from the
// canonical feedback-type vocabulary (25.UX-1) shared with the form.
const TYPE_OPTIONS: { value: FeedbackType | ""; label: string }[] = [
  { value: "", label: "All types" },
  ...FEEDBACK_TYPES,
];

const PAGE_SIZE = 20;

/**
 * Admin feedback review surface (Phase 21B).
 *
 * Lists feedback submissions from the admin-only backend contract
 * GET /api/v1/feedback/admin (require_admin). The backend is the
 * authorization boundary; the route additionally guards itself client-side
 * (UIA-008): students who deep-link or refresh here are redirected to the
 * dashboard instead of being shown an error that reads like a data failure.
 */
export default function FeedbackAdminPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { profile, isLoading: profileLoading, isError: profileError } = useProfile();
  const isAdmin = profile?.role === "ADMIN";

  const [feedbackType, setFeedbackType] = useState<FeedbackType | "">("");
  const [page, setPage] = useState(1);

  const { feedback, isLoading, isError, mutate } = useAdminFeedback({
    page,
    page_size: PAGE_SIZE,
    feedback_type: feedbackType,
  });

  // UIA-008: this surface is admin-only. The route itself is guarded — a
  // student who deep-links or refreshes here is redirected to the dashboard
  // instead of being shown an error that looks like a data failure. The
  // backend stays the authorization boundary (GET /api/v1/feedback/admin
  // still 403s non-admins); the role check only avoids rendering the admin
  // surface. Loading and unauthenticated states render nothing admin-flavored
  // while AuthContext resolves, mirroring the (admin) route-group layout.
  useEffect(() => {
    if (authLoading || !user || profileLoading || profileError) return;
    if (profile && !isAdmin) {
      router.replace("/dashboard");
    }
  }, [authLoading, user, profileLoading, profileError, profile, isAdmin, router]);

  if (authLoading) {
    return (
      <div className="flex-1 py-8 w-full max-w-4xl mx-auto">
        <PageHeader title="Feedback" />
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="p-4">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="mt-3 h-4 w-full" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Unauthenticated: AuthContext owns the redirect to /login — render nothing
  // admin-flavored meanwhile (same contract as the (admin) route-group layout).
  if (!user) {
    return null;
  }

  if (profileLoading || profileError || !profile) {
    return (
      <div className="flex-1 py-8 w-full max-w-4xl mx-auto">
        <PageHeader title="Feedback" />
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="p-4">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="mt-3 h-4 w-full" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Confirmed non-admin: the redirect effect above is in flight; render
  // nothing so no part of the admin surface (not even its header) appears.
  if (!isAdmin) {
    return null;
  }

  const handleTypeChange = (next: FeedbackType | "") => {
    setFeedbackType(next);
    setPage(1);
  };

  return (
    <div className="flex-1 py-8 w-full max-w-4xl mx-auto">
      <PageHeader
        title="Feedback"
        description="Feedback submitted by students."
      />

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by feedback type">
          {TYPE_OPTIONS.map(({ value, label }) => (
            <Button
              key={value || "all"}
              variant={feedbackType === value ? "default" : "outline"}
              size="sm"
              onClick={() => handleTypeChange(value)}
            >
              {label}
            </Button>
          ))}
        </div>
        <Button variant="ghost" size="sm" onClick={() => mutate()} aria-label="Refresh feedback">
          <RefreshCw className="size-4" aria-hidden="true" />
          Refresh
        </Button>
      </div>

      {isError ? (
        <ErrorState
          message={isError?.message
            ? `Could not load feedback: ${isError.message}`
            : "Could not load feedback. The admin feedback service may be unavailable."}
        />
      ) : isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-4">
              <div className="flex items-center justify-between gap-3">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-5 w-20" />
              </div>
              <Skeleton className="mt-3 h-4 w-full" />
              <Skeleton className="mt-2 h-4 w-2/3" />
            </Card>
          ))}
        </div>
      ) : feedback && feedback.items.length > 0 ? (
        <>
          <div className="space-y-3">
            {feedback.items.map((item) => (
              <Card key={item.id} className="p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium text-foreground">{item.name}</span>
                    <span className="font-mono text-xs text-muted-foreground">
                      {item.roll_number}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={cn("text-xs", feedbackTypeBadgeClass(item.feedback_type))}>
                      {item.feedback_type}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {/* 25.UX-1: created_at is a backend timestamp — the
                          timestamp-aware formatter replaces the date-only
                          parser that could silently render today's date. */}
                      {formatTimestampDate(item.created_at)}
                    </span>
                  </div>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-foreground">{item.message}</p>
                {item.context && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Context: {item.context}
                  </p>
                )}
              </Card>
            ))}
          </div>

          {feedback.pages > 1 && (
            <div className="mt-6 flex items-center justify-between">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <span className="text-xs text-muted-foreground">
                Page {feedback.page} of {feedback.pages} · {feedback.total} total
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= feedback.pages}
                onClick={() => setPage((p) => Math.min(feedback.pages, p + 1))}
              >
                Next
              </Button>
            </div>
          )}
        </>
      ) : (
        <EmptyState
          icon={<MessageSquareText className="h-10 w-10 text-muted-foreground mb-4" />}
          title="No feedback yet"
          message="Student feedback submissions will appear here."
        />
      )}
    </div>
  );
}