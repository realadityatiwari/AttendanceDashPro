"use client";

import { Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

/**
 * UIA-013 — authenticated-shell gate.
 *
 * The authenticated route group must never paint the app chrome (nav,
 * greeting, cards) for a visitor with no session while AuthContext's
 * effect-driven redirect is still in flight. The gate renders the shell once
 * the persisted-token check has resolved AND a token exists.
 *
 * Perf batch 1: the gate opens on `authResolved` + `hasSession` (token
 * presence) and deliberately does NOT wait for the profile fetch — page data
 * hooks start in parallel with GET /student/me instead of behind it. The
 * 401 → refresh → redirect behavior is unchanged (it lives in apiFetch), and
 * a transiently failing profile fetch keeps the shell mounted and retries
 * through SWR. Components that render profile fields read them through their
 * own `useProfile()` hooks and already handle the in-flight state.
 *
 * Routing and auth semantics are unchanged: AuthContext still owns the
 * redirect to /login (no token) and /dashboard (token on a public route).
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { authResolved, hasSession } = useAuth();

  if (!authResolved || !hasSession) {
    return (
      <div
        className="flex h-screen items-center justify-center bg-background"
        role="status"
        aria-live="polite"
      >
        <Loader2
          className="size-6 animate-spin text-muted-foreground"
          aria-hidden="true"
        />
        <span className="sr-only">Loading your session…</span>
      </div>
    );
  }

  return <>{children}</>;
}
