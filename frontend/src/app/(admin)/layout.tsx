"use client";

import { AlertCircle, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useAdminMe } from "@/hooks/useApi";
import { AdminShell } from "@/components/admin/AdminShell";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { GlassCard } from "@/components/shared/GlassCard";

/**
 * Admin Portal route-group layout (Phase 24.1).
 *
 * State machine (mutually exclusive, never renders a functional-looking
 * portal without backend-confirmed admin identity):
 *  - loading: auth context or /api/v1/admin/me still resolving — skeletons only.
 *  - unauthenticated: existing AuthContext redirect to /login takes over
 *    (no second auth mechanism; nothing admin is rendered meanwhile).
 *  - unauthorized: backend responded 403 (authenticated user with no
 *    effective administrative role — STUDENT included). Backend-authoritative.
 *  - api failure: any other error — retry revalidates; no scope/role faking.
 *  - authenticated admin: AdminShell with backend identity.
 *
 * Role/scope data is presentation-only; every admin capability stays
 * server-gated (Phase 23.11 gates).
 */
export default function AdminPortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading: authLoading } = useAuth();
  const { identity, isError, mutate } = useAdminMe();

  if (authLoading) {
    return <AdminLoadingState />;
  }

  // Unauthenticated: AuthContext redirects to /login; render nothing admin.
  if (!user) {
    return null;
  }

  if (isError) {
    const status = (isError as Error & { status?: number }).status;
    if (status === 403) {
      return (
        <div className="flex min-h-screen items-center justify-center p-4">
          <GlassCard className="max-w-md">
            <div className="flex flex-col items-center justify-center text-center p-8">
              <ShieldAlert className="h-10 w-10 text-warning mb-4" />
              <h1 className="text-lg font-semibold text-foreground">
                Administrative access required
              </h1>
              <p className="text-sm text-muted-foreground mt-2 max-w-sm">
                This authenticated account does not hold an administrative
                role. The Admin Portal is available to authorized
                administrators only.
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
        </div>
      );
    }

    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <GlassCard className="max-w-md border-red-900/50 bg-red-950/20">
          <div className="flex flex-col items-center justify-center text-center p-8">
            <AlertCircle className="h-10 w-10 text-red-500 mb-4" />
            <h1 className="text-lg font-semibold text-red-400">
              Could not load the Admin Portal
            </h1>
            <p className="text-sm text-red-400/80 mt-2 max-w-sm">
              The server could not provide your administrative identity.
              {isError instanceof Error && isError.message
                ? ` (${isError.message})`
                : null}
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-6"
              onClick={() => mutate()}
            >
              Retry
            </Button>
          </div>
        </GlassCard>
      </div>
    );
  }

  if (!identity) {
    return <AdminLoadingState />;
  }

  return <AdminShell identity={identity}>{children}</AdminShell>;
}

function AdminLoadingState() {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <div className="shrink-0 border-b border-border">
        <div className="flex h-14 items-center gap-4 px-4 sm:px-6 lg:px-8">
          <Skeleton className="h-7 w-7 rounded-md" />
          <Skeleton className="h-4 w-44" />
          <div className="ml-auto flex items-center gap-3">
            <Skeleton className="h-8 w-8 rounded-full" />
          </div>
        </div>
        <div className="flex gap-2 px-4 pb-2 sm:px-6 lg:px-8">
          <Skeleton className="h-8 w-24 rounded-md" />
          <Skeleton className="h-8 w-28 rounded-md" />
        </div>
      </div>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-5xl space-y-4 p-4 md:p-6 lg:p-8">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="h-36 w-full rounded-xl" />
          <Skeleton className="h-28 w-full rounded-xl" />
        </div>
      </main>
    </div>
  );
}
