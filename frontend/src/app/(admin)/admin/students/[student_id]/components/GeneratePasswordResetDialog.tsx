import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AdminStudentDetail } from "@/types/api";
import { usePasswordResetIssuance } from "@/hooks/useApi";
import { Loader2, AlertTriangle, Copy, Check } from "lucide-react";

/**
 * Stage 3A — "Generate password reset" action for the scoped admin student
 * detail page.
 *
 * Issues a ONE-TIME single-use reset token via
 * POST /api/v1/admin/students/{id}/password-reset. The backend resolves the
 * student and enforces the acting admin's existing scope (HEAD global, CLASS
 * assigned sections, ELECTIVE roster; SUBSECTION inert-deny). The raw token is
 * shown exactly once here and MUST be delivered to the student out-of-band
 * (in person, securely) — it is never emailed, never persisted in storage or
 * URLs, and is cleared when the dialog closes or the component unmounts.
 *
 * The admin never sees or sets the student's password.
 */
export function GeneratePasswordResetDialog({
  student,
  open,
  onOpenChange,
}: {
  student: AdminStudentDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { issuePasswordReset } = usePasswordResetIssuance();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [prevOpen, setPrevOpen] = useState(open);

  // Clear the sensitive raw token whenever the dialog is dismissed, so a
  // reopened dialog never re-displays a previous secret. Adjusting state
  // during render on a prop change is React's recommended pattern (no effect,
  // no cascading render).
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (!open) {
      setResetToken(null);
      setExpiresAt(null);
      setCopied(false);
      setError(null);
    }
  }

  const handleGenerate = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await issuePasswordReset(student.id);
      setResetToken(result.reset_token);
      setExpiresAt(result.expires_at);
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? err.message
          : "Failed to generate a password reset token"
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopy = async () => {
    if (!resetToken) return;
    try {
      await navigator.clipboard.writeText(resetToken);
      setCopied(true);
    } catch {
      // Clipboard may be unavailable; the token remains visible to copy by hand.
    }
  };

  const handleClose = (next: boolean) => {
    if (isSubmitting) return;
    onOpenChange(next);
  };

  const formattedExpiry = expiresAt
    ? new Date(expiresAt).toLocaleString()
    : null;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Generate password reset</DialogTitle>
          <DialogDescription>
            Create a single-use reset token for {student.name}. Deliver it to the
            student privately (in person or through a secure channel) — it is
            shown only once and expires shortly.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-4">
          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-destructive bg-destructive/15 p-3 text-sm text-destructive"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <p>{error}</p>
            </div>
          )}

          {!resetToken ? (
            <>
              <div className="flex items-start gap-2 rounded-md border border-warning/20 bg-warning/10 p-3 text-sm text-warning-foreground">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <p>
                  Issuing a new token immediately invalidates any outstanding
                  reset token for this student. The administrator cannot view or
                  set the student&apos;s password — the student chooses it when
                  redeeming the token.
                </p>
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => handleClose(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="button" onClick={handleGenerate} disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
                  Generate reset token
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="space-y-2">
                <label htmlFor="resetToken" className="text-sm font-medium text-foreground">
                  Reset token (shown once)
                </label>
                <div className="flex items-center gap-2">
                  <code
                    id="resetToken"
                    className="flex-1 break-all rounded-md border border-border bg-muted p-3 font-mono text-xs text-foreground"
                  >
                    {resetToken}
                  </code>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    aria-label="Copy reset token"
                    onClick={handleCopy}
                  >
                    {copied ? (
                      <Check className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <Copy className="h-4 w-4" aria-hidden="true" />
                    )}
                  </Button>
                </div>
                {formattedExpiry && (
                  <p className="text-xs text-muted-foreground">
                    Expires {formattedExpiry}. The student redeems it at the
                    &quot;Reset password&quot; page using this token.
                  </p>
                )}
              </div>
              <div className="flex justify-end gap-2 pt-4">
                <Button type="button" onClick={() => handleClose(false)}>
                  Done
                </Button>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}