"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const [rollNumber, setRollNumber] = useState("");
  const [password, setPassword] = useState("");
  // UI-028: password visibility toggle — parity with the signup page.
  const [showPassword, setShowPassword] = useState(false);
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
            <Input
              id="rollNumber"
              type="text"
              required
              value={rollNumber}
              onChange={(e) => setRollNumber(e.target.value)}
              placeholder="13 digit roll number"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="password" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-foreground">
              Password
            </label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min 8 characters"
                className="pr-10"
              />
              <button
                type="button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() => setShowPassword(v => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-2.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded-md"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <Button type="submit" disabled={loading} className="w-full">
            {loading ? "Signing in..." : "Sign in"}
          </Button>
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
