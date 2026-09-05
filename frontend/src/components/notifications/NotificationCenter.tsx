"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Bell,
  BookOpen,
  CalendarClock,
  CalendarDays,
  Check,
  CheckCheck,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Target,
  X,
} from "lucide-react";
import { ShellDialog } from "@/components/shell/ShellDialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/feedback/toast";
import {
  useNotifications,
  useNotificationMutation,
} from "@/hooks/useApi";
import { NotificationItem, NotificationKind } from "@/types/api";
import { formatLongDate } from "@/lib/date";

interface NotificationCenterProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface KindMeta {
  label: string;
  badge: "primary" | "warning" | "danger" | "success" | "neutral";
  icon: typeof BookOpen;
  iconClass: string;
}

const KIND_META: Record<NotificationKind, KindMeta> = {
  CLASS_REMINDER: {
    label: "Class reminder",
    badge: "primary",
    icon: BookOpen,
    iconClass: "bg-primary/15 text-primary",
  },
  QUIZ_APPROACHING: {
    label: "Quiz",
    badge: "warning",
    icon: CalendarClock,
    iconClass: "bg-warning/15 text-warning",
  },
  ATTENDANCE_THRESHOLD: {
    label: "Attendance",
    badge: "danger",
    icon: AlertTriangle,
    iconClass: "bg-destructive/15 text-destructive",
  },
  MUST_ATTEND: {
    label: "Must attend",
    badge: "danger",
    icon: Target,
    iconClass: "bg-destructive/15 text-destructive",
  },
  SAFE_SKIP: {
    label: "Safe skip",
    badge: "success",
    icon: CheckCircle2,
    iconClass: "bg-success/15 text-success",
  },
  ACADEMIC_EVENT: {
    label: "Event",
    badge: "neutral",
    icon: CalendarDays,
    iconClass: "bg-muted text-muted-foreground",
  },
};

/**
 * Notification center — Phase 11D.
 *
 * Renders the persisted inbox served by GET /api/v1/notifications (newest
 * first, unread rows visually emphasized). Each row carries the backend kind,
 * message, subject context and occurrence date; unread rows expose a "Mark as
 * read" action and every row a dismiss action, both via
 * PATCH /api/v1/notifications/{id}. Mutations update the SWR cache only after
 * a genuine 2xx response (never optimistically, never faked); failures are
 * surfaced in an explicit banner and the list stays unchanged. The bell badge
 * subscribes to the same SWR key, so read/dismiss stays in sync with it.
 *
 * The SWR key is gated on `open` (like usePreferences) — the inbox is fetched
 * when the center opens, not at shell mount.
 */
export function NotificationCenter({ open, onOpenChange }: NotificationCenterProps) {
  const { notifications, isLoading, isError, mutate } = useNotifications(open);
  const { updateNotification } = useNotificationMutation();
  const { toast } = useToast();

  // UI-014: per-row pending state (ids of rows with an in-flight mutation)
  // plus a separate mark-all lock — unrelated rows stay interactive while
  // another row's request runs, and mark-all cannot race a row action.
  const [pendingIds, setPendingIds] = useState<string[]>([]);
  const [markAllPending, setMarkAllPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const items = notifications?.items ?? [];
  const unreadCount = notifications?.unread_count ?? 0;

  const setRowPending = (id: string, pending: boolean) => {
    setPendingIds((prev) =>
      pending ? [...prev, id] : prev.filter((x) => x !== id)
    );
  };

  const applyCacheUpdate = (transform: (items: NotificationItem[]) => NotificationItem[]) => {
    mutate(
      (current) => {
        if (!current) return current;
        const items = transform(current.items);
        return {
          ...current,
          items,
          unread_count: items.filter((i) => !i.is_read).length,
        };
      },
      false
    );
  };

  // D-11/D-12: dismissal is immediate; the same idempotent PATCH with
  // `is_dismissed: false` makes a genuine undo possible — no fake restore,
  // the canonical SWR key is revalidated so the row returns in server order.
  const undoDismiss = async (item: NotificationItem) => {
    if (!item.notification_id) return;
    try {
      await updateNotification(item.notification_id, { is_dismissed: false });
      await mutate();
    } catch {
      toast({
        variant: "error",
        title: "Couldn't restore the notification",
        description: "Please try again.",
      });
    }
  };

  const runAction = async (
    item: NotificationItem,
    payload: { is_read?: boolean; is_dismissed?: boolean }
  ) => {
    if (!item.notification_id || markAllPending) return;
    if (pendingIds.includes(item.notification_id)) return;
    setRowPending(item.notification_id, true);
    setActionError(null);
    try {
      const updated = await updateNotification(item.notification_id, payload);
      if (payload.is_dismissed) {
        applyCacheUpdate((rows) =>
          rows.filter((r) => r.notification_id !== item.notification_id)
        );
        toast({
          variant: "info",
          title: "Notification dismissed",
          duration: 8000,
          action: {
            label: "Undo",
            onClick: () => {
              void undoDismiss(item);
            },
          },
        });
      } else {
        applyCacheUpdate((rows) =>
          rows.map((r) =>
            r.notification_id === updated.notification_id ? updated : r
          )
        );
      }
    } catch (error) {
      const detail =
        error instanceof Error && error.message !== "API request failed"
          ? error.message
          : "The backend did not accept the request.";
      setActionError(detail);
    } finally {
      setRowPending(item.notification_id, false);
    }
  };

  // D-12: mark-all runs the EXISTING per-notification PATCH sequentially over
  // the currently unread ids — no bulk endpoint, no uncontrolled burst. Each
  // row's cache entry updates only after its genuine 2xx; failures leave
  // those rows untouched (server truth) and are reported honestly.
  const handleMarkAllRead = async () => {
    if (markAllPending || pendingIds.length > 0) return;
    const unread = items.filter(
      (i): i is NotificationItem & { notification_id: string } =>
        !i.is_read && i.notification_id !== null
    );
    if (unread.length === 0) return;
    setMarkAllPending(true);
    setActionError(null);
    let succeeded = 0;
    try {
      for (const row of unread) {
        try {
          const updated = await updateNotification(row.notification_id, {
            is_read: true,
          });
          applyCacheUpdate((rows) =>
            rows.map((r) =>
              r.notification_id === updated.notification_id ? updated : r
            )
          );
          succeeded += 1;
        } catch {
          // Row stays unread in the cache; counted as failed below.
        }
      }
      const failed = unread.length - succeeded;
      if (failed === 0) {
        toast({
          variant: "success",
          title: `Marked ${succeeded} ${succeeded === 1 ? "notification" : "notifications"} read`,
        });
      } else if (succeeded === 0) {
        const message = "Couldn't mark notifications as read. Please try again.";
        setActionError(message);
        toast({
          variant: "error",
          title: "Couldn't mark notifications as read",
          description: "Please try again.",
        });
      } else {
        const message = `${failed} ${failed === 1 ? "notification" : "notifications"} couldn't be marked read.`;
        setActionError(message);
        toast({
          variant: "warning",
          title: `Marked ${succeeded} of ${unread.length} read`,
          description: message,
        });
      }
    } finally {
      setMarkAllPending(false);
    }
  };

  return (
    <ShellDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Notifications"
      description={
        unreadCount > 0
          ? `${unreadCount} unread`
          : "You're all caught up"
      }
      width="md"
      mobileSheet
    >
      {isLoading && !notifications ? (
        <div className="space-y-3 py-1" aria-label="Loading notifications">
          {[0, 1, 2].map((i) => (
            <div key={i} className="flex items-start gap-3 rounded-lg border border-border bg-background p-3">
              <Skeleton className="size-9 shrink-0 rounded-lg" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3.5 w-2/3" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            </div>
          ))}
        </div>
      ) : isError && !notifications ? (
        <div className="flex flex-col gap-3 py-1">
          <div className="flex gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 p-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
            <p className="text-xs leading-relaxed text-destructive">
              Notifications could not be loaded. Nothing was changed.
            </p>
          </div>
          <Button variant="outline" onClick={() => mutate()}>
            <RefreshCw className="size-4" aria-hidden="true" />
            Retry
          </Button>
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-8 text-center">
          <Bell className="size-8 text-muted-foreground/60" aria-hidden="true" />
          <p className="text-sm font-medium text-foreground">No notifications yet</p>
          <p className="text-xs text-muted-foreground">
            Class, quiz, attendance and event updates will appear here.
          </p>
        </div>
      ) : (
        <>
          {/* D-12: mark-all operates on the currently unread rows only. */}
          {unreadCount > 0 && (
            <div className="flex items-center justify-between gap-3 pb-2">
              <span className="text-xs text-muted-foreground">
                {unreadCount} unread
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={markAllPending || pendingIds.length > 0}
                onClick={handleMarkAllRead}
              >
                {markAllPending ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                ) : (
                  <CheckCheck className="size-3.5" aria-hidden="true" />
                )}
                Mark all read
              </Button>
            </div>
          )}
          <div className="flex max-h-[60dvh] flex-col gap-2 overflow-y-auto py-1 pr-1 md:max-h-[26rem]">
          {actionError && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-2.5">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-destructive" aria-hidden="true" />
              <p className="text-xs leading-relaxed text-destructive">
                The action could not be saved: {actionError}. Nothing was changed —
                try again.
              </p>
            </div>
          )}
          {items.map((item) => {
            const meta = KIND_META[item.kind] ?? KIND_META.ACADEMIC_EVENT;
            const Icon = meta.icon;
            const rowId = item.notification_id;
            const rowPending = rowId !== null && pendingIds.includes(rowId);
            return (
              <div
                key={item.id}
                className={item.is_read ? "rounded-lg border border-border bg-background p-3" : "rounded-lg border border-border bg-muted/40 p-3"}
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:gap-3">
                  <div className="flex items-start gap-3 sm:min-w-0 sm:flex-1">
                    <span
                      className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${meta.iconClass}`}
                    >
                      <Icon className="size-4" aria-hidden="true" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <Badge variant={meta.badge}>{meta.label}</Badge>
                        {!item.is_read && (
                          <span className="size-1.5 rounded-full bg-primary" aria-label="Unread" />
                        )}
                      </div>
                      <p
                        className={`mt-1.5 text-sm leading-snug ${
                          item.is_read ? "text-muted-foreground" : "font-medium text-foreground"
                        }`}
                      >
                        {item.message}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {[item.subject_code, formatLongDate(item.date)]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center justify-end gap-1 sm:items-start">
                    {!item.is_read && (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={markAllPending || rowPending}
                        onClick={() =>
                          runAction(item, { is_read: true })
                        }
                        aria-label={`Mark as read: ${item.message}`}
                      >
                        {rowPending && <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />}
                        <Check className="size-3.5" aria-hidden="true" />
                        Read
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled={markAllPending || rowPending}
                      onClick={() => runAction(item, { is_dismissed: true })}
                      aria-label={`Dismiss: ${item.message}`}
                    >
                      {rowPending ? (
                        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                      ) : (
                        <X className="size-3.5" aria-hidden="true" />
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            );
          })}
          </div>
        </>
      )}
    </ShellDialog>
  );
}