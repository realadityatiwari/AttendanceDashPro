"use client";

import { useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  CalendarClock,
  CalendarDays,
  Check,
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

  const [pendingId, setPendingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const items = notifications?.items ?? [];
  const unreadCount = notifications?.unread_count ?? 0;

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

  const runAction = async (
    item: NotificationItem,
    payload: { is_read?: boolean; is_dismissed?: boolean }
  ) => {
    if (!item.notification_id || pendingId) return;
    setPendingId(item.notification_id);
    setActionError(null);
    try {
      const updated = await updateNotification(item.notification_id, payload);
      if (payload.is_dismissed) {
        applyCacheUpdate((items) =>
          items.filter((i) => i.notification_id !== item.notification_id)
        );
      } else {
        applyCacheUpdate((items) =>
          items.map((i) =>
            i.notification_id === updated.notification_id ? updated : i
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
      setPendingId(null);
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
          <CalendarDays className="size-8 text-muted-foreground/60" aria-hidden="true" />
          <p className="text-sm font-medium text-foreground">No notifications yet</p>
          <p className="text-xs text-muted-foreground">
            Class, quiz, attendance and event updates will appear here.
          </p>
        </div>
      ) : (
        <div className="flex max-h-[26rem] flex-col gap-2 overflow-y-auto py-1 pr-1">
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
            const pending = pendingId === item.notification_id;
            return (
              <div
                key={item.id}
                className={item.is_read ? "rounded-lg border border-border bg-background p-3" : "rounded-lg border border-border bg-muted/40 p-3"}
              >
                <div className="flex items-start gap-3">
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
                  <div className="flex shrink-0 items-center gap-1">
                    {!item.is_read && (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={pendingId !== null}
                        onClick={() =>
                          runAction(item, { is_read: true })
                        }
                        aria-label={`Mark as read: ${item.message}`}
                      >
                        {pending && <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />}
                        <Check className="size-3.5" aria-hidden="true" />
                        Read
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled={pendingId !== null}
                      onClick={() => runAction(item, { is_dismissed: true })}
                      aria-label={`Dismiss: ${item.message}`}
                    >
                      {pending ? (
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
      )}
    </ShellDialog>
  );
}