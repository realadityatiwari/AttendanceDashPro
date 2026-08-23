/* Phase 13 PWA Service Worker
 * Conservative caching strategy for AttendanceDash Pro
 * 
 * Policy:
 * - Cache static application shell assets on install
 * - Network-first for all API requests (never cache authenticated data)
 * - Return offline fallback for navigation when shell is cached
 * - Clean up old caches on activation
 * - Never cache personalized/authenticated responses
 */

const CACHE_NAME = "attendancedash-pro-v1";
const STATIC_ASSETS = [
  "/",
  "/_app",
  "/_error",
  "/favicon.ico",
  "/manifest.json",
  "/icons/icons-192.svg",
  "/icons/icons-512.svg",
  "/globals.css",
];

self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((name) => {
          if (name !== CACHE_NAME) {
            return caches.delete(name);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Only handle GET requests
  if (event.request.method !== "GET") {
    return;
  }

  const url = new URL(event.request.url);

  // Only cache same-origin requests
  if (url.origin !== self.origin) {
    // For cross-origin requests, just fetch from network
    event.respondWith(fetch(event.request));
    return;
  }

  // API requests: network-first, never cache
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).then((response) => {
        // Don't cache API responses
        const responseToCache = response.clone();
        // Intentally not caching - API responses are personalized
        return response;
      }).catch(() => {
        // Network failed - return offline fallback
        return new Response(
          JSON.stringify({ offline: true, error: "Network unavailable" }),
          {
            headers: { "Content-Type": "application/json" },
            status: 503,
          }
        );
      })
    );
    return;
  }

  // Navigation requests: cache-first with network fallback
  if (url.pathname === "/" || url.pathname.startsWith("/") || url.pathname.endsWith(".html")) {
    event.respondWith(
      caches.match(event.request).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(event.request).then((fetchResponse) => {
          // Cache the shell response for offline use
          const responseToCache = fetchResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.addAll([event.request.url]);
          });
          return fetchResponse;
        }).catch(() => {
          // Offline - return cached shell if available
          return cachedResponse || new Response(
            "<html><body>Offline - AttendanceDash Pro</body></html>",
            {
              headers: { "Content-Type": "text/html" },
            }
          );
        });
      })
    );
    return;
  }

  // Other requests: network-first
  event.respondWith(fetch(event.request));
});