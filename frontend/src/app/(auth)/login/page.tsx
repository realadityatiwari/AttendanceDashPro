"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { API_BASE_URL } from "@/lib/api";

export default function LoginPage() {
  const [rollNumber, setRollNumber] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // UI-026: set by apiFetch when a genuine session expiry forced the redirect.
  // Read once and cleared so a manual revisit never shows a stale notice.
  const [sessionExpired, setSessionExpired] = useState(false);
  const { refreshUser } = useAuth();
  const router = useRouter();

  useEffect(() => {
    let expired = false;
    try {
      if (sessionStorage.getItem("session_expired") === "1") {
        sessionStorage.removeItem("session_expired");
        expired = true;
      }
    } catch {
      // Storage unavailable (privacy mode) — notice is best-effort.
    }
    if (!expired) return;
    // Deferred so the effect never sets state synchronously (cascading-render
    // lint rule); the one-frame delay is imperceptible.
    const timerId = window.setTimeout(() => setSessionExpired(true), 0);
    return () => window.clearTimeout(timerId);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        // Phase 25.2: credentials are included so the backend's HttpOnly
        // refresh cookie (Set-Cookie on the login response) is stored by the
        // browser for the cross-origin architecture (dev localhost→127.0.0.1,
        // production Vercel→Render). The JSON contract is unchanged.
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ roll_number: rollNumber.trim(), password }),
      });

      if (!response.ok) {
        let errorMessage = "Failed to log in.";
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {}
        throw new Error(errorMessage);
      }

      const data = await response.json();
      localStorage.setItem("access_token", data.access_token);

      // Update auth context state. A transient profile fetch failure must
      // not block navigation — the session token is already stored and the
      // dashboard retries through SWR.
      try {
        await refreshUser();
      } catch {
        // Profile refresh failed transiently; navigate anyway.
      }

      router.push("/dashboard");
    } catch (err) {
      // Network-level failures surface as TypeError with the browser's raw
      // "Failed to fetch" — replace it with an actionable message. HTTP
      // errors (4xx/5xx) keep their backend-provided detail.
      if (err instanceof TypeError) {
        setError("Unable to reach the server. Check your connection and try again.");
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("Failed to log in.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md space-y-8 rounded-lg border bg-card p-8 shadow-sm">
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">AttendanceDash Pro</h1>
          <p className="mt-2 text-sm text-muted-foreground">Student Portal</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {sessionExpired && (
            <div
              role="status"
              className="rounded-md bg-warning/10 p-3 text-sm text-warning border border-warning/30"
            >
              Your session has expired. Please sign in again.
            </div>
          )}
          {error && (
            <div className="rounded-md bg-destructive/15 p-3 text-sm text-destructive border border-destructive">
              {error}
            </div>
          )}
          
          <div className="space-y-2">
            <label htmlFor="rollNumber" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-foreground">
              Roll Number
            </label>
            <input
              id="rollNumber"
              type="text"
              required
              value={rollNumber}
              onChange={(e) => setRollNumber(e.target.value)}
              placeholder="13 digit roll number"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-foreground">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min 8 characters"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          Don&apos;t have an account?{" "}
          <Link href="/signup" className="font-medium text-primary hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
