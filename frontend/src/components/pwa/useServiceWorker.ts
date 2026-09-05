"use client";

import { useEffect, useRef, useState } from "react";

let serviceWorkerRegistered = false;

/**
 * Service worker registration for AttendanceDash Pro PWA.
 *
 * Policy:
 * - Registers only in the browser (client component)
 * - Does not break SSR (client-only execution)
 * - Caching strategy (Phase D): network-first navigation with cache
 *   fallback, network-only API (never caches authenticated data),
 *   precached verified static assets, versioned caches
 * - Does not cache personalized/authenticated data
 * - Does not interfere with beforeinstallprompt or useInstallPrompt
 * - Update lifecycle: the SW waits for reload (no skipWaiting), so a
 *   fresh shell is never paired with stale JS/CSS; when a new SW is
 *   installed we notify the user to reload, and while a page is open we
 *   check for updates on focus so clients eventually receive the new
 *   worker after deployment.
 */
export function useServiceWorker() {
  const [swRegistered, setSwRegistered] = useState(false);
  // UI-023: a newly installed waiting worker (while a controller exists)
  // means a new version is ready and a user-initiated reload will apply it.
  // Surfaced to the UI instead of console-only reporting.
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);

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

        // Listen for update found events
        registration.onupdatefound = () => {
          const installingWorker = registration.installing;
          if (!installingWorker) return;
          installingWorker.onstatechange = () => {
            if (installingWorker.state === "installed") {
              if (navigator.serviceWorker.controller) {
                // New content is available; the new SW is waiting (no
                // skipWaiting) and will activate once the user reloads.
                setUpdateAvailable(true);
              } else {
                console.log("Content cached for offline use");
              }
            }
          };
        };

        // Periodically check for a newer SW while a page is open, so
        // deployed updates reach active clients without forcing an
        // immediate (unsafe) takeover.
        const checkForUpdates = () => {
          registration.update().catch((error) => {
            console.error("SW update check failed: ", error);
          });
        };

        const handleFocus = () => checkForUpdates();
        window.addEventListener("focus", handleFocus);
        const intervalId = window.setInterval(checkForUpdates, 60 * 60 * 1000);

        cleanupRef.current = () => {
          window.removeEventListener("focus", handleFocus);
          window.clearInterval(intervalId);
        };
      })
      .catch((error) => {
        console.error("SW registration failed: ", error);
      });

    return () => {
      if (cleanupRef.current) {
        cleanupRef.current();
        cleanupRef.current = null;
      }
    };
  }, []);

  return { swRegistered, updateAvailable };
}