"use client";

import { useServiceWorker } from "@/components/pwa/useServiceWorker";
import { UpdateBanner } from "@/components/feedback/UpdateBanner";

/**
 * Registers the service worker when the authenticated application shell mounts.
 *
 * Renders nothing while the shell runs normally; when the service worker
 * reports a newly installed waiting version it renders the update-available
 * banner (UI-023) so the user can apply the update with an explicit reload.
 *
 * Phase 11C-P1: service-worker registration is the browser-side foundation
 * for Web Push. No subscription, VAPID, or backend dispatch is created here.
 */
export function ServiceWorkerRegistration() {
  const { updateAvailable } = useServiceWorker();
  return updateAvailable ? <UpdateBanner /> : null;
}