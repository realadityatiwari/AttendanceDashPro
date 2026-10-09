"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";
import { useChangePassword } from "@/hooks/useApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CheckCircle2 } from "lucide-react";

// Mirrors the backend password policy (validate_password_policy in
// backend/app/api/v1/endpoints/auth.py). The server remains authoritative.
const MIN_PASSWORD_LENGTH = 8;
const MAX_PASSWORD_LENGTH = 128;

function validateNewPassword(value: string): string | null {
  if (value.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  if (value.length > MAX_PASSWORD_LENGTH) {
    return `Password must not exceed ${MAX_PASSWORD_LENGTH} characters.`;
  }
  if (!/[A-Za-z]/.test(value)) return "Password must contain at least one letter.";
  if (!/[0-9]/.test(value)) return "Password must contain at least one digit.";
  return null;
}

type Mode = "signin" | "change";

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>("signin");
  const [rollNumber, setRollNumber] = useState("");
  const [password, setPassword] = useState("");
  // UI-028: password visibility toggle — parity with the signup page.
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // UI-026: set by apiFetch when a genuine session expiry forced the redirect.
  // Read once and cleared so a manual revisit never shows a stale notice.
  const [sessionExpired, setSessionExpired] = useState(false);

  // ── Change-password mode (authenticated re-auth flow) ────────────────────
  // The user proves ownership with their CURRENT credentials: the login call
  // below authenticates them and yields an access token, which is used ONLY
  // in memory to call the existing authenticated change-password endpoint.
  // The token is never written to localStorage and no session is started, so
  // AuthContext stays unauthenticated and this page is not redirected away.
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [changeErrors, setChangeErrors] = useState<Record<string, string | undefined>>({});
  const [changeSuccess, setChangeSuccess] = useState(false);
  const changeSubmittingRef = useRef(false);
  const { changePassword } = useChangePassword();

  const { refreshUser } = useAuth();
  const router = useRouter();

  const switchMode = (next: Mode) => {
    setMode(next);
    setError("");
    setChangeErrors({});
    setChangeSuccess(false);
  };

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

  // Authenticated re-auth change: verify the current credentials with the
  // existing login endpoint, then call the existing authenticated
  // change-password endpoint with the returned token (in memory only). The
  // temporary session created by login is revoked best-effort afterwards.
  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (changeSubmittingRef.current) return;

    const next: Record<string, string | undefined> = {};
    const trimmedRoll = rollNumber.trim();
    if (!/^\d{13}$/.test(trimmedRoll)) {
      next.rollNumber = "Roll number must be 13 digits.";
    }
    if (!password) next.currentPassword = "Enter your current password.";
    const policyError = validateNewPassword(newPassword);
    if (policyError) next.newPassword = policyError;
    if (confirmPassword !== newPassword) next.confirmPassword = "Passwords do not match.";
    setChangeErrors(next);
    setError("");
    if (Object.keys(next).length > 0) return;

    changeSubmittingRef.current = true;
    setLoading(true);
    try {
      // 1. Authenticate with the CURRENT credentials (existing login flow).
      const loginResponse = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ roll_number: trimmedRoll, password }),
      });
      if (!loginResponse.ok) {
        let message = "Incorrect roll number or password";
        try {
          const data = await loginResponse.json();
          message = data.detail || message;
        } catch {}
        throw new Error(message);
      }
      const { access_token: tempToken } = await loginResponse.json();

      // 2. Change the password through the EXISTING authenticated endpoint,
      //    using the temporary token (never persisted to localStorage).
      await changePassword(password, newPassword, tempToken);

      // 3. Best-effort revoke the temporary session's refresh family. The
      //    change endpoint already revokes all refresh families, so this is
      //    partly redundant; it also clears the cookie for a clean state.
      fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
      }).catch(() => {});

      // Clear the change drafts only after confirmed success.
      setNewPassword("");
      setConfirmPassword("");
      setPassword("");
      setChangeSuccess(true);
    } catch (err) {
      if (err instanceof TypeError) {
        setError("Unable to reach the server. Check your connection and try again.");
      } else if (err instanceof Error && err.message) {
        setError(err.message);
      } else {
        setError("We couldn't change your password. Please try again.");
      }
    } finally {
      changeSubmittingRef.current = false;
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md space-y-8 rounded-lg border bg-card p-8 shadow-sm">
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">AttendanceDash Pro</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {mode === "signin" ? "Student Portal" : "Change your password"}
          </p>
        </div>

        {mode === "signin" ? (
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
              <div
                role="alert"
                className="rounded-md bg-destructive/15 p-3 text-sm text-destructive border border-destructive"
              >
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
                // 25.UX-7: WCAG 1.3.5 input purpose — the roll number is the
                // sign-in identifier, so password managers must recognize it.
                autoComplete="username"
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
                  // 25.UX-7: current-password — never blocks paste or
                  // password-manager autofill (Accessible Authentication).
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 8 characters"
                  className="pr-10"
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword(v => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-2.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded-md"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                </button>
              </div>
            </div>

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        ) : (
          <form onSubmit={handleChangePassword} className="space-y-6" noValidate>
            {changeSuccess ? (
              <div
                role="status"
                className="flex items-center gap-2 rounded-md bg-success/10 p-3 text-sm text-success border border-success/30"
              >
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                Your password has been changed. Sign in with your new password.
              </div>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  Confirm your identity with your current password, then choose a
                  new one.
                </p>

                {error && (
                  <div
                    role="alert"
                    className="rounded-md bg-destructive/15 p-3 text-sm text-destructive border border-destructive"
                  >
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
                    autoComplete="username"
                    value={rollNumber}
                    disabled={loading}
                    onChange={(e) => {
                      setRollNumber(e.target.value);
                      if (changeErrors.rollNumber) setChangeErrors((p) => ({ ...p, rollNumber: undefined }));
                    }}
                    placeholder="13 digit roll number"
                    aria-invalid={!!changeErrors.rollNumber}
                    aria-describedby={changeErrors.rollNumber ? "rollNumber-error" : undefined}
                  />
                  {changeErrors.rollNumber && (
                    <p id="rollNumber-error" className="text-xs text-destructive">{changeErrors.rollNumber}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <label htmlFor="password" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-foreground">
                    Current password
                  </label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      required
                      autoComplete="current-password"
                      value={password}
                      disabled={loading}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        if (changeErrors.currentPassword) setChangeErrors((p) => ({ ...p, currentPassword: undefined }));
                      }}
                      placeholder="Min 8 characters"
                      className="pr-10"
                      aria-invalid={!!changeErrors.currentPassword}
                      aria-describedby={changeErrors.currentPassword ? "currentPassword-error" : undefined}
                    />
                    <button
                      type="button"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      aria-pressed={showPassword}
                      disabled={loading}
                      onClick={() => setShowPassword(v => !v)}
                      className="absolute inset-y-0 right-0 flex items-center px-2.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded-md disabled:opacity-50"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                    </button>
                  </div>
                  {changeErrors.currentPassword && (
                    <p id="currentPassword-error" className="text-xs text-destructive">{changeErrors.currentPassword}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <label htmlFor="newPassword" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-foreground">
                    New password
                  </label>
                  <div className="relative">
                    <Input
                      id="newPassword"
                      type={showNewPassword ? "text" : "password"}
                      autoComplete="new-password"
                      value={newPassword}
                      disabled={loading}
                      maxLength={MAX_PASSWORD_LENGTH}
                      onChange={(e) => {
                        setNewPassword(e.target.value);
                        if (changeErrors.newPassword) setChangeErrors((p) => ({ ...p, newPassword: undefined }));
                      }}
                      placeholder="Min 8 characters"
                      className="pr-10"
                      aria-invalid={!!changeErrors.newPassword}
                      aria-describedby={changeErrors.newPassword ? "newPassword-error" : undefined}
                    />
                    <button
                      type="button"
                      aria-label={showNewPassword ? "Hide new password" : "Show new password"}
                      aria-pressed={showNewPassword}
                      disabled={loading}
                      onClick={() => setShowNewPassword(v => !v)}
                      className="absolute inset-y-0 right-0 flex items-center px-2.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded-md disabled:opacity-50"
                    >
                      {showNewPassword ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                    </button>
                  </div>
                  {changeErrors.newPassword && (
                    <p id="newPassword-error" className="text-xs text-destructive">{changeErrors.newPassword}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <label htmlFor="confirmPassword" className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-foreground">
                    Confirm new password
                  </label>
                  <div className="relative">
                    <Input
                      id="confirmPassword"
                      type={showConfirmPassword ? "text" : "password"}
                      autoComplete="new-password"
                      value={confirmPassword}
                      disabled={loading}
                      maxLength={MAX_PASSWORD_LENGTH}
                      onChange={(e) => {
                        setConfirmPassword(e.target.value);
                        if (changeErrors.confirmPassword) setChangeErrors((p) => ({ ...p, confirmPassword: undefined }));
                      }}
                      placeholder="Re-enter new password"
                      className="pr-10"
                      aria-invalid={!!changeErrors.confirmPassword}
                      aria-describedby={changeErrors.confirmPassword ? "confirmPassword-error" : undefined}
                    />
                    <button
                      type="button"
                      aria-label={showConfirmPassword ? "Hide confirm password" : "Show confirm password"}
                      aria-pressed={showConfirmPassword}
                      disabled={loading}
                      onClick={() => setShowConfirmPassword(v => !v)}
                      className="absolute inset-y-0 right-0 flex items-center px-2.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded-md disabled:opacity-50"
                    >
                      {showConfirmPassword ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                    </button>
                  </div>
                  {changeErrors.confirmPassword && (
                    <p id="confirmPassword-error" className="text-xs text-destructive">{changeErrors.confirmPassword}</p>
                  )}
                </div>

                <Button type="submit" disabled={loading} className="w-full">
                  {loading ? "Changing password..." : "Change password"}
                </Button>
              </>
            )}
          </form>
        )}

        {mode === "signin" ? (
          <p className="text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="font-medium text-primary hover:underline">
              Create one
            </Link>
          </p>
        ) : null}

        <p className="text-center text-sm text-muted-foreground">
          {mode === "signin" ? (
            <button
              type="button"
              onClick={() => switchMode("change")}
              className="font-medium text-primary hover:underline"
            >
              Change your password
            </button>
          ) : (
            <button
              type="button"
              onClick={() => switchMode("signin")}
              className="font-medium text-primary hover:underline"
            >
              Back to sign in
            </button>
          )}
        </p>
      </div>
    </div>
  );
}
