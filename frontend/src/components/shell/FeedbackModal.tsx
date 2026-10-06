"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, Send } from "lucide-react";
import { ShellDialog } from "@/components/shell/ShellDialog";
import { Button } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { apiFetch } from "@/lib/api";
import { FEEDBACK_TYPES } from "@/lib/canonicalStatus";
import type { FeedbackType } from "@/types/api";

interface FeedbackModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Type vocabulary is canonical (lib/canonicalStatus) — shared with the
// feedback review surface so labels can never drift (25.UX-1).

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
          : "We couldn't send your feedback. Please try again.";
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
        // 25.UX-7: the form is replaced by this panel after a successful
        // submit — role="status" announces the outcome that would otherwise
        // be visually apparent only.
        <div
          role="status"
          className="flex flex-col items-center gap-3 py-6 text-center"
        >
          <CheckCircle2 className="size-10 text-success" aria-hidden="true" />
          <p className="text-sm font-medium text-foreground">Thank you!</p>
          <p className="text-sm text-muted-foreground">
            Your feedback has been saved.
          </p>
          {/* UIA-038: an explicit way out of the success state — previously
              the only close affordance was the dialog header. */}
          <Button className="mt-1" onClick={() => handleOpenChange(false)}>
            Done
          </Button>
        </div>
      ) : state.status === "error" ? (
        <div className="flex flex-col gap-3 py-2">
          {/* 25.UX-7: submission failures are announced (same role="alert"
              contract as the Event form's error banner). */}
          <div
            role="alert"
            className="flex gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3"
          >
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
            <legend id="feedback-type-legend" className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Feedback type
            </legend>
            {/* 25.UX-2: the chips are the shared SegmentedControl primitive
                (tint variant). The grid layout is the fieldset's former
                grid-cols-2; the primitive lifts the chips to the shared
                40px touch / 32px pointer floor. */}
            <SegmentedControl
              value={feedbackType}
              onValueChange={setFeedbackType}
              options={FEEDBACK_TYPES}
              variant="tint"
              aria-labelledby="feedback-type-legend"
              // 25.UX-7: the inline error is programmatically associated with
              // the control group (Error Placement — aria-describedby).
              aria-describedby={typeError ? "feedback-type-error" : undefined}
              className="grid grid-cols-2 gap-2"
            />
            {typeError && (
              <p id="feedback-type-error" className="mt-1.5 text-xs text-destructive">
                {typeError}
              </p>
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
            aria-invalid={messageError ? true : undefined}
            // 25.UX-7: the hint slot doubles as the error message — one stable
            // id keeps the association valid in both states.
            aria-describedby="feedback-message-hint"
            placeholder="How can we improve AttendanceDash Pro?"
            className="mt-2 w-full resize-none rounded-lg border border-border bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-ring focus:ring-2 focus:ring-ring/40 focus:outline-none"
          />
          <div className="mt-1 flex items-center justify-between">
            {messageError ? (
              <p id="feedback-message-hint" className="text-xs text-destructive">
                {messageError}
              </p>
            ) : (
              <p id="feedback-message-hint" className="text-xs text-muted-foreground">
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