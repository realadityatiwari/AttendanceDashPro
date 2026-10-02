"use client";

import { Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

/**
 * UIA-013 — authenticated-shell gate.
 *
 * The authenticated route group must never paint the app chrome (nav,
 * greeting, cards) for a visitor with no session while AuthContext's
 * effect-driven redirect is still in flight. The gate renders the shell only
 * once auth has resolved AND a persisted token exists; until then it renders
 * a neutral full-screen loading state instead of the shell.
 *
 * Routing and auth semantics are unchanged: AuthContext still owns the
 * redirect to /login (no token) and /dashboard (token on a public route).
 * A session with a transiently failing profile fetch still passes the gate
 * and retries through SWR — `hasSession` reflects the token, not the profile.
 */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { loading, hasSession } = useAuth();

  if (loading || !hasSession) {
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
