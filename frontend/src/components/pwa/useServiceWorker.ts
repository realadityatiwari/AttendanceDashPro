"use client";

import { useEffect, useState } from "react";

let serviceWorkerRegistered = false;

/**
 * Service worker registration for AttendanceDash Pro PWA.
 * 
 * Policy:
 * - Registers only in the browser (client component)
 * - Does not break SSR (client-only execution)
 * - Uses conservative caching: static assets cached on install,
 *   network-first for all API requests
 * - Does not cache personalized/authenticated data
 * - Does not interfere with beforeinstallprompt or useInstallPrompt
 */
export function useServiceWorker() {
  const [swRegistered, setSwRegistered] = useState(false);

  useEffect(() => {
    // Skip if already registered
    if (serviceWorkerRegistered) return;

    // Skip if no service worker support
    if (!("serviceWorker" in navigator)) return;

    const swUrl = "/service-worker.js";

    navigator.serviceWorker
      .register(swUrl)
      .then((registration) => {
        serviceWorkerRegistered = true;
        setSwRegistered(true);
        console.log("SW registered: scope = ", registration.scope);

        // Listen for update found events
        registration.onupdatefound = () => {
          const installingWorker = registration.installing;
          if (!installingWorker) return;
          installingWorker.onstatechange = () => {
            if (installingWorker.state === "installed") {
              if (navigator.serviceWorker.controller) {
                // New content is available
                console.log("New content available; reload page recommended");
              } else {
                // Content cached for offline use
                console.log("Content cached for offline use");
              }
            }
          };
        };
      })
      .catch((error) => {
        console.error("SW registration failed: ", error);
      });
  }, [serviceWorkerRegistered]); // eslint-disable-line react-hooks/exhaustive-deps

  return { swRegistered };
}