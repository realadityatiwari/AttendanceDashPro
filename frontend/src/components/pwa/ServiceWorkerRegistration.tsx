"use client";

import { useServiceWorker } from "@/components/pwa/useServiceWorker";

/**
 * Registers the service worker when the authenticated application shell mounts.
 *
 * Renders nothing — this is a side-effect-only component. The service worker
 * registration is scoped to the browser (never SSR), runs at most once, and
 * cannot block the initial page render (errors are swallowed).
 *
 * Phase 11C-P1: service-worker registration is the browser-side foundation
 * for Web Push. No subscription, VAPID, or backend dispatch is created here.
 */
export function ServiceWorkerRegistration() {
  useServiceWorker();
  return null;
}