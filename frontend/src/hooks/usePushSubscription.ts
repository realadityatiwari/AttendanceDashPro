"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useNotificationPermission } from "@/hooks/useNotificationPermission";
import { usePushSubscriptionMutations } from "@/hooks/useApi";
import {
  arrayBufferToBase64Url,
  isVapidConfigured,
  urlBase64ToUint8Array,
  VAPID_PUBLIC_KEY,
} from "@/lib/push";
import { PushSubscriptionCreate, PushSubscriptionResponse } from "@/types/api";

/**
 * Phase 11C-P2: browser-side Web Push subscription lifecycle.
 *
 * Turns the P1 notification-permission state into an actual PushSubscription
 * and keeps it persisted against the authenticated backend
 * (POST/DELETE /api/v1/push-subscriptions). The owner is always the
 * authenticated user (backend derives it from the JWT).
 *
 * Invariants:
 * - Nothing subscribes on page load or merely because permission is granted —
 *   subscription is always initiated by the user's explicit action (enable()).
 * - An existing browser PushSubscription is REUSED, never re-created
 *   (getSubscription() is always checked before subscribe()), so multiple
 *   tabs can never create duplicate browser subscriptions.
 * - An existing browser subscription is synchronized to the backend when the
 *   surface becomes active (Settings open), keeping Browser ↔ Backend aligned.
 * - VAPID is NOT implemented here (that is P3): without the configured public
 *   key the flow degrades to an honest "push setup unavailable" state with a
 *   retry path.
 * - Every failure is contained: no auth invalidation, no logout, no breakage
 *   of the rest of the application — apiFetch's 401/403/network semantics are
 *   untouched.
 */
export function usePushSubscription(enabled = true) {
  const {
    supported: notificationsSupported,
    permission,
    requestPermission,
  } = useNotificationPermission();

  const { registerPushSubscription, deletePushSubscription } =
    usePushSubscriptionMutations();

  // Keep the latest mutation functions available to effects without re-running
  // them on every render (the codebase creates these per render; they are
  // stateless apiFetch wrappers, so the initial values are already safe).
  const mutationsRef = useRef({ registerPushSubscription, deletePushSubscription });
  useEffect(() => {
    mutationsRef.current = { registerPushSubscription, deletePushSubscription };
  });

  // Browser-level push support: service worker + PushManager.
  const pushSupported =
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window;

  const [browserSubscription, setBrowserSubscription] =
    useState<PushSubscription | null>(null);
  const [backendSubscription, setBackendSubscription] =
    useState<PushSubscriptionResponse | null>(null);
  const [isWorking, setIsWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => setError(null), []);

  // Serialize a browser PushSubscription into the backend contract
  // (endpoint + URL-safe base64 p256dh/auth keys).
  const toCreatePayload = useCallback(
    (sub: PushSubscription): PushSubscriptionCreate => {
      const p256dh = sub.getKey("p256dh");
      const auth = sub.getKey("auth");
      return {
        endpoint: sub.endpoint,
        keys: {
          p256dh: p256dh ? arrayBufferToBase64Url(p256dh) : "",
          auth: auth ? arrayBufferToBase64Url(auth) : "",
        },
      };
    },
    [],
  );

  const persistToBackend = useCallback(
    async (sub: PushSubscription): Promise<PushSubscriptionResponse> => {
      return mutationsRef.current.registerPushSubscription(toCreatePayload(sub));
    },
    [toCreatePayload],
  );

  // Load-time synchronization (§12/§23): when the surface becomes active,
  // detect an EXISTING browser subscription (read-only — never subscribe here)
  // and synchronize it to the backend so Browser ↔ Backend stay aligned.
  useEffect(() => {
    if (!enabled || !pushSupported) return;
    let cancelled = false;

    (async () => {
      try {
        const registration = await navigator.serviceWorker.ready;
        const existing = await registration.pushManager.getSubscription();
        if (cancelled) return;
        setBrowserSubscription(existing);
        if (existing) {
          try {
            const backend = await persistToBackend(existing);
            if (!cancelled) setBackendSubscription(backend);
          } catch {
            // Non-fatal: never claim success when the backend sync failed.
            if (!cancelled) {
              setError(
                "Your existing browser notification subscription could not be synced to your account.",
              );
            }
          }
        }
      } catch {
        // PushManager/service-worker unavailable — leave everything in the
        // initial (not subscribed) state; nothing to do.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [enabled, pushSupported, persistToBackend]);

  /**
   * User-initiated enable flow (§9):
   * 1. Check browser support.
   * 2. Request notification permission (only on this explicit gesture).
   * 3. Ensure the service worker is registered/available.
   * 4. Reuse an existing PushSubscription when present (never duplicate).
   * 5. Otherwise subscribe() — requires the VAPID public key (P3).
   * 6. Persist the subscription to the authenticated backend.
   * 7. Update UI state.
   */
  const enable = useCallback(async () => {
    if (!pushSupported) {
      setError("Push notifications are not supported on this browser.");
      return;
    }

    // Step 2: permission. If already granted we continue; if the user denies
    // (or leaves it unanswered) we stop gracefully — the Settings UI reflects
    // the real permission state and never claims success.
    if (permission !== "granted") {
      const result = await requestPermission();
      if (result !== "granted") return;
    }

    setIsWorking(true);
    setError(null);
    try {
      // Steps 3–4: active service-worker registration, then reuse existing.
      const registration = await navigator.serviceWorker.ready;
      let sub = await registration.pushManager.getSubscription();

      // Step 5: create only when no subscription exists (§23 multi-tab safety).
      if (!sub) {
        if (!isVapidConfigured) {
          setError(
            "Push setup is unavailable because the server VAPID public key is not configured yet.",
          );
          return;
        }
        sub = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
        });
      }

      // Steps 6–7: persist (new or re-used) and reflect state.
      const backend = await persistToBackend(sub);
      setBrowserSubscription(sub);
      setBackendSubscription(backend);
    } catch (err) {
      // §14: never break the application; honest, retryable error state.
      setError(
        err instanceof Error && err.message
          ? err.message
          : "Browser push setup failed. Please try again.",
      );
    } finally {
      setIsWorking(false);
    }
  }, [pushSupported, permission, requestPermission, persistToBackend]);

  /**
   * User-initiated unsubscribe flow (§13):
   * 1. Remove the persisted backend record (by id) when one is known.
   * 2. Unsubscribe the browser subscription (live lookup, falls back to state).
   * 3. Never claim success when a required step failed — failures surface as
   *    an honest error with the state left as-is.
   */
  const disable = useCallback(async () => {
    setIsWorking(true);
    setError(null);
    const failures: string[] = [];

    try {
      // Live lookup — don't rely on possibly-stale state.
      let liveSub: PushSubscription | null = null;
      try {
        const registration = await navigator.serviceWorker.ready;
        liveSub = await registration.pushManager.getSubscription();
      } catch {
        liveSub = null;
      }

      // Step 1: remove the backend record (when known).
      const backendId = backendSubscription?.id;
      if (backendId) {
        try {
          await deletePushSubscription(backendId);
          setBackendSubscription(null);
        } catch {
          failures.push("The saved subscription could not be removed.");
        }
      }

      // Step 2: remove the browser subscription.
      const sub = liveSub ?? browserSubscription;
      if (sub) {
        try {
          await sub.unsubscribe();
          setBrowserSubscription(null);
        } catch {
          failures.push("This browser could not be unsubscribed.");
        }
      }

      // Nothing existed at all — that is a successful no-op (nothing to do).
    } finally {
      setIsWorking(false);
    }

    if (failures.length > 0) {
      setError(failures.join(" "));
    }
  }, [backendSubscription, browserSubscription, deletePushSubscription]);

  return {
    supported: notificationsSupported,
    pushSupported,
    permission,
    requestPermission,
    browserSubscription,
    backendSubscription,
    isWorking,
    error,
    enable,
    disable,
    clearError,
  } as const;
}
