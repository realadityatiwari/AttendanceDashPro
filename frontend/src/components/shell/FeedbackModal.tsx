"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, Send } from "lucide-react";
import { ShellDialog } from "@/components/shell/ShellDialog";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";

interface FeedbackModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type FeedbackType = "BUG" | "SUGGESTION" | "QUESTION" | "PRAISE";

const FEEDBACK_TYPES: { value: FeedbackType; label: string }[] = [
  { value: "BUG", label: "Bug" },
  { value: "SUGGESTION", label: "Suggestion" },
  { value: "QUESTION", label: "Question" },
  { value: "PRAISE", label: "Praise" },
];

type FeedbackState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "success" }
  | { status: "error"; message: string };

const MIN_MESSAGE_LENGTH = 10;

/**
 * Feedback form. Submits to the real backend contract
 * `POST /api/v1/feedback` (body: { feedback_type, message }, JWT auth).
 * Success is shown only after a genuine 2xx response; any failure surfaces
 * an explicit error — the form never fakes persistence.
 */
export function FeedbackModal({ open, onOpenChange }: FeedbackModalProps) {
  const [feedbackType, setFeedbackType] = useState<FeedbackType | null>(null);
  const [message, setMessage] = useState("");
  const [state, setState] = useState<FeedbackState>({ status: "idle" });

  const reset = () => {
    setFeedbackType(null);
    setMessage("");
    setState({ status: "idle" });
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const messageError =
    message.length > 0 && message.length < MIN_MESSAGE_LENGTH
      ? `Message must be at least ${MIN_MESSAGE_LENGTH} characters`
      : null;
  const typeError = state.status === "idle" && feedbackType === null && message.length > 0
    ? "Select a feedback type"
    : null;
  const submitting = state.status === "submitting";
  const canSubmit =
    !submitting &&
    feedbackType !== null &&
    message.trim().length >= MIN_MESSAGE_LENGTH;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setState({ status: "submitting" });
    try {
      await apiFetch("/api/v1/feedback", {
        method: "POST",
        body: JSON.stringify({
          feedback_type: feedbackType,
          message: message.trim(),
        }),
      });
      setState({ status: "success" });
    } catch (error) {
      const detail =
        error instanceof Error && error.message !== "API request failed"
          ? error.message
          : "The backend did not accept the request.";
      setState({
        status: "error",
        message:
          `Your feedback could not be saved: ${detail} ` +
          "The feedback service is temporarily unavailable. Nothing was persisted.",
      });
    }
  };

  return (
    <ShellDialog
      open={open}
      onOpenChange={handleOpenChange}
      title="Send Feedback"
      description="Help us improve AttendanceDash Pro"
      width="md"
    >
      {state.status === "success" ? (
        <div className="flex flex-col items-center gap-3 py-6 text-center">
          <CheckCircle2 className="size-10 text-success" aria-hidden="true" />
          <p className="text-sm font-medium text-foreground">Thank you!</p>
          <p className="text-sm text-muted-foreground">
            Your feedback has been saved.
          </p>
        </div>
      ) : state.status === "error" ? (
        <div className="flex flex-col gap-3 py-2">
          <div className="flex gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
            <p className="text-xs leading-relaxed text-destructive">
              {state.message}
            </p>
          </div>
          <Button variant="outline" onClick={() => setState({ status: "idle" })}>
            Try again
          </Button>
        </div>
      ) : (
        <>
          <fieldset className="mb-4">
            <legend className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Feedback type
            </legend>
            <div className="grid grid-cols-2 gap-2">
              {FEEDBACK_TYPES.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={feedbackType === value}
                  onClick={() => setFeedbackType(value)}
                  className={cn(
                    "rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
                    feedbackType === value
                      ? "border-primary/50 bg-primary/10 text-primary"
                      : "border-border bg-background text-muted-foreground hover:text-foreground"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            {typeError && (
              <p className="mt-1.5 text-xs text-destructive">{typeError}</p>
            )}
          </fieldset>

          <label
            htmlFor="feedback-message"
            className="text-xs font-medium uppercase tracking-wider text-muted-foreground"
          >
            Message
          </label>
          <textarea
            id="feedback-message"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            maxLength={1000}
            rows={4}
            placeholder="How can we improve AttendanceDash Pro?"
            className="mt-2 w-full resize-none rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-ring focus:ring-2 focus:ring-ring/40 focus:outline-none"
          />
          <div className="mt-1 flex items-center justify-between">
            {messageError ? (
              <p className="text-xs text-destructive">{messageError}</p>
            ) : (
              <p className="text-xs text-muted-foreground">
                {message.length}/1000 characters
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              <span className="font-medium">{MIN_MESSAGE_LENGTH}+</span> characters required
            </p>
          </div>

          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={() => handleOpenChange(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!canSubmit || submitting}
            >
              {submitting ? (
                <Loader2 className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <Send className="size-4" aria-hidden="true" />
              )}
              Submit
            </Button>
          </div>
        </>
      )}
    </ShellDialog>
  );
}