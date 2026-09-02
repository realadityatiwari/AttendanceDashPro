"use client";

import { useEffect } from "react";
import { useSWRConfig } from "swr";
import { NOTIFICATIONS_KEY } from "@/lib/api";

const NOTIFICATIONS_UPDATED_MESSAGE = "NOTIFICATIONS_UPDATED";

/**
 * Phase 11C-P5: centralized service-worker invalidation listener.
 *
 * Mounted once in the authenticated shell (AppShell). When the P1 service
 * worker receives a Web Push it displays the browser notification AND posts a
 * ``{ type: "NOTIFICATIONS_UPDATED" }`` message to every controlled window
 * client. This listener validates the message type and triggers targeted SWR
 * revalidation of the canonical notification key (NOTIFICATIONS_KEY) only:
 *
 * - the bell badge and the notification center share that key, so both update
 *   from the same canonical GET /api/v1/notifications response;
 * - no raw push payload is ever inserted into the inbox (the backend response
 *   is authoritative);
 * - no other SWR cache key is touched, no page reload, no polling;
 * - listener cleanup happens on unmount.
 *
 * Foreground / visibility recovery (returning to the app after a missed or
 * backgrounded signal) needs NO extra listener here: the bell's SWR hook runs
 * with STANDARD_CACHE (revalidateOnFocus: true, dedupingInterval: 60s) on the
 * always-mounted bell, so SWR's own focus/visibility revalidation catches the
 * notification key up with one deduped request per 60s window. Keeping that
 * policy in SWR (instead of adding a manual visibility handler) preserves the
 * pre-P5 focus-storm guardrail.
 */
export function NotificationRefreshListener() {
  const { mutate } = useSWRConfig();

  useEffect(() => {
    // Guard: no service worker support (SSR / unsupported browser).
    if (!("serviceWorker" in navigator)) return;

    const onSwMessage = (event: MessageEvent) => {
      const data = event.data as Record<string, unknown> | undefined;
      if (data && data.type === NOTIFICATIONS_UPDATED_MESSAGE) {
        // Targeted revalidation of the canonical notification key. If the key
        // is currently gated off (no token / not mounted) this is a safe
        // no-op — SWR has no subscriber to revalidate.
        mutate(NOTIFICATIONS_KEY);
      }
    };

    navigator.serviceWorker.addEventListener("message", onSwMessage);

    return () => {
      navigator.serviceWorker.removeEventListener("message", onSwMessage);
    };
  }, [mutate]);

  return null;
}