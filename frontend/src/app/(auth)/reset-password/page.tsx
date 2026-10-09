"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Eye, EyeOff, CheckCircle2 } from "lucide-react";
import { useResetPassword } from "@/hooks/useApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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

/**
 * Stage 3A — public password reset (redemption of an admin-issued token).
 *
 * The reset token is the recovery proof: no login or old password is required.
 * The token is captured via the URL FRAGMENT (`#token=...`) when present —
 * fragments are never sent to the server and never appear in HTTP request
 * logs — or entered manually. The fragment is stripped from the address bar
 * immediately after being read so it cannot linger in history. The token is
 * sent to the backend in the POST body only.
 *
 * Redeeming does NOT start a session; on success the student is directed to
 * sign in with the new password.
 */
export default function ResetPasswordPage() {
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [serverError, setServerError] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const submittingRef = useRef(false);
  const { resetPassword } = useResetPassword();

  // Read a fragment token once, then remove it from the address bar/history so
  // it is never kept, bookmarked, or forwarded. The state write is deferred to
  // a task (the same convention the login page uses) so this effect never sets
  // state synchronously.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const hash = window.location.hash.startsWith("#")
      ? window.location.hash.slice(1)
      : "";
    if (!hash) return;
    const token = new URLSearchParams(hash).get("token");
    if (!token) return;
    // Strip the fragment immediately — it must not linger in history/logs.
    window.history.replaceState(
      null,
      "",
      window.location.pathname + window.location.search
    );
    const timerId = window.setTimeout(() => setResetToken(token), 0);
    return () => window.clearTimeout(timerId);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submittingRef.current) return;

    const next: Record<string, string | undefined> = {};
    if (!resetToken.trim()) {
      next.resetToken = "Enter the reset token provided by your administrator.";
    }
    const policyError = validateNewPassword(newPassword);
    if (policyError) next.newPassword = policyError;
    if (confirmPassword !== newPassword) {
      next.confirmPassword = "Passwords do not match.";
    }
    setErrors(next);
    setServerError("");
    if (Object.keys(next).length > 0) return;

    submittingRef.current = true;
    setLoading(true);
    try {
      await resetPassword(resetToken.trim(), newPassword);
      // Clear all sensitive fields only after confirmed success.
      setNewPassword("");
      setConfirmPassword("");
      setResetToken("");
      setSuccess(true);
    } catch (err) {
      // The backend returns a single generic message for every invalid/
      // expired/used/revoked token — surface it honestly without echoing the
      // token itself.
      if (err instanceof Error && err.message) {
        setServerError(err.message);
      } else {
        setServerError("We couldn't reset your password. Please try again.");
      }
    } finally {
      submittingRef.current = false;
      setLoading(false);
    }
  };

  const labelClass =
    "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-foreground";

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md space-y-8 rounded-lg border bg-card p-8 shadow-sm">
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Reset your password
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">AttendanceDash Pro</p>
        </div>

        {success ? (
          <div className="space-y-6">
            <div
              role="status"
              className="flex items-center gap-2 rounded-md bg-success/10 p-3 text-sm text-success border border-success/30"
            >
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              Your password has been reset. Sign in with your new password.
            </div>
            <Button
              nativeButton={false}
              className="w-full"
              render={<Link href="/login" />}
            >
              Go to sign in
            </Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6" noValidate>
            <p className="text-sm text-muted-foreground">
              Enter the reset token your administrator provided, then choose a new
              password.
            </p>

            {serverError && (
              <div
                role="alert"
                className="rounded-md bg-destructive/15 p-3 text-sm text-destructive border border-destructive"
              >
                {serverError}
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="resetToken" className={labelClass}>
                Reset token
              </label>
              <Input
                id="resetToken"
                type="text"
                required
                autoComplete="off"
                spellCheck={false}
                value={resetToken}
                disabled={loading}
                onChange={(e) => {
                  setResetToken(e.target.value);
                  if (errors.resetToken) {
                    setErrors((p) => ({ ...p, resetToken: undefined }));
                  }
                }}
                placeholder="Paste the token you were given"
                aria-invalid={!!errors.resetToken}
                aria-describedby={errors.resetToken ? "resetToken-error" : undefined}
              />
              {errors.resetToken && (
                <p id="resetToken-error" className="text-xs text-destructive">
                  {errors.resetToken}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <label htmlFor="newPassword" className={labelClass}>
                New password
              </label>
              <div className="relative">
                <Input
                  id="newPassword"
                  type={showNewPassword ? "text" : "password"}
                  required
                  autoComplete="new-password"
                  value={newPassword}
                  disabled={loading}
                  maxLength={MAX_PASSWORD_LENGTH}
                  onChange={(e) => {
                    setNewPassword(e.target.value);
                    if (errors.newPassword) {
                      setErrors((p) => ({ ...p, newPassword: undefined }));
                    }
                  }}
                  placeholder="Min 8 characters"
                  className="pr-10"
                  aria-invalid={!!errors.newPassword}
                  aria-describedby={errors.newPassword ? "newPassword-error" : undefined}
                />
                <button
                  type="button"
                  aria-label={showNewPassword ? "Hide new password" : "Show new password"}
                  aria-pressed={showNewPassword}
                  disabled={loading}
                  onClick={() => setShowNewPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-2.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded-md disabled:opacity-50"
                >
                  {showNewPassword ? (
                    <EyeOff className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>
              </div>
              {errors.newPassword && (
                <p id="newPassword-error" className="text-xs text-destructive">
                  {errors.newPassword}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <label htmlFor="confirmPassword" className={labelClass}>
                Confirm new password
              </label>
              <div className="relative">
                <Input
                  id="confirmPassword"
                  type={showConfirmPassword ? "text" : "password"}
                  required
                  autoComplete="new-password"
                  value={confirmPassword}
                  disabled={loading}
                  maxLength={MAX_PASSWORD_LENGTH}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    if (errors.confirmPassword) {
                      setErrors((p) => ({ ...p, confirmPassword: undefined }));
                    }
                  }}
                  placeholder="Re-enter new password"
                  className="pr-10"
                  aria-invalid={!!errors.confirmPassword}
                  aria-describedby={errors.confirmPassword ? "confirmPassword-error" : undefined}
                />
                <button
                  type="button"
                  aria-label={showConfirmPassword ? "Hide confirm password" : "Show confirm password"}
                  aria-pressed={showConfirmPassword}
                  disabled={loading}
                  onClick={() => setShowConfirmPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 flex items-center px-2.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 rounded-md disabled:opacity-50"
                >
                  {showConfirmPassword ? (
                    <EyeOff className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>
              </div>
              {errors.confirmPassword && (
                <p id="confirmPassword-error" className="text-xs text-destructive">
                  {errors.confirmPassword}
                </p>
              )}
            </div>

            <Button type="submit" disabled={loading} className="w-full">
              {loading ? "Resetting password..." : "Reset password"}
            </Button>
          </form>
        )}

        <p className="text-center text-sm text-muted-foreground">
          Remembered your password?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}