"use client";

import { Bell } from "lucide-react";
import { useNotifications } from "@/hooks/useApi";
import { ShellModalId } from "@/components/layout/UserMenu";

interface NotificationBellProps {
  onOpenModal: (modal: ShellModalId) => void;
}

/**
 * Notification bell — Phase 11D.
 *
 * Authenticated-shell entry to the notification center. Shows the backend
 * unread badge only when unread_count > 0 (capped at "99+" to avoid absurd
 * rendering). Fetches through the same SWR key the center uses, so read/
 * dismiss mutations update the badge in place. Opening the center triggers a
 * revalidation (one logical request at open time; no polling).
 */
export function NotificationBell({ onOpenModal }: NotificationBellProps) {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const { notifications, mutate } = useNotifications(!!token);

  const unreadCount = notifications?.unread_count ?? 0;
  const badge = unreadCount > 99 ? "99+" : String(unreadCount);

  const handleOpen = () => {
    onOpenModal("notifications");
    mutate();
  };

  return (
    <button
      type="button"
      aria-label={unreadCount > 0 ? `Notifications (${unreadCount} unread)` : "Notifications"}
      onClick={handleOpen}
      className="relative -m-1.5 flex items-center rounded-md p-2 text-muted-foreground outline-none transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring/60 sm:-m-1.5 sm:p-2"
    >
      <Bell className="size-5" aria-hidden="true" />
      {unreadCount > 0 && (
        <span className="absolute top-0 right-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[11px] leading-none font-semibold text-white">
          {badge}
        </span>
      )}
    </button>
  );
}