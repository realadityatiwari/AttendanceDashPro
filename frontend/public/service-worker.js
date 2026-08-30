/* Phase D: Service Worker Reliability & Cache Strategy
 * Strategy:
 * - Navigation: network-first with cache fallback (fresh shell after deploy)
 * - API: network-only, never cache (auth isolation)
 * - Static assets: precache verified paths only
 * - Cache versioning: bump CACHE_VERSION to invalidate all caches
 * - Update lifecycle: wait for reload (no skipWaiting) to avoid HTML/JS mismatch
 */

const CACHE_VERSION = "v3";
const CACHE_NAME = `attendancedash-pro-${CACHE_VERSION}`;

// Only precache assets that are verified to exist as static files.
// Do NOT add Next.js build artifacts (/_next/static/*) — they are
// content-addressed and cached by the browser's HTTP cache.
// Do NOT add /_app, /_error, /globals.css — these are NOT produced
// as static files by the App Router build and would fail install.
const STATIC_ASSETS = [
  "/",
  "/favicon.ico",
  "/manifest.json",
  "/brand/icon-192.png",
  "/brand/icon-512.png",
];

self.addEventListener("install", (event) => {
  // Do NOT skipWaiting — let the new SW wait until all clients close.
  // This avoids serving a new HTML shell that references old JS/CSS
  // (HTML/JS mismatch). The registration hook notifies the user to
  // reload when a new SW is installed.
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch(() => {
        // Do not fail installation if one asset path is missing
        // (e.g., favicon.ico may not be present in all environments).
      });
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
  // Claim all clients when activated so navigation is handled by the
  // current SW. This is safe because navigation is network-first:
  // a freshly activated SW fetches the latest HTML.
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  if (url.origin !== self.origin) return;

  // API requests: network-only, never cache authenticated data.
  // Preserves the existing principle that /api/* stays network-driven.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).catch(() => {
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

  // Navigation requests: network-first with cache fallback.
  // This ensures users get the latest HTML shell after deployment,
  // while preserving offline shell access when the network is down.
  // request.mode === "navigate" matches only navigation requests,
  // not subresource loads (JS, CSS, images).
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            // Cache the navigation response for offline fallback.
            // cache.put (not addAll) so non-200 responses never throw.
            cache.put(event.request, cloned);
          });
          return response;
        })
        .catch(() => {
          return caches.match(event.request).then((cached) => {
            if (cached) return cached;
            // Last resort: minimal offline fallback
            return new Response(
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

  // Non-navigation, non-API requests (JS, CSS, images, fonts):
  // let the browser handle them normally via its HTTP cache.
  // Do not intercept — Next.js build artifacts are content-addressed
  // and the browser cache is sufficient.
});