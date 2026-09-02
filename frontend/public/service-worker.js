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

// ---------------------------------------------------------------------------
// Phase 11C-P1: Web Push foundation (browser-side only).
//
// Delivery/display infrastructure: a `push` event displays a notification
// and a `notificationclick` event routes the user back into the app. There is
// NO subscription creation, NO VAPID, NO backend dispatch, and NO network
// calls from the service worker here — push payloads are parsed defensively
// and displayed as-is. The in-app notification system remains canonical.
// ---------------------------------------------------------------------------

const PUSH_TITLE_MAX_LENGTH = 100;
const PUSH_BODY_MAX_LENGTH = 400;
const PUSH_TAG_MAX_LENGTH = 64;
const PUSH_URL_MAX_LENGTH = 500;
const DEFAULT_PUSH_TITLE = "AttendanceDash Pro";
const DEFAULT_PUSH_ICON = "/brand/icon-192.png";
const DEFAULT_PUSH_URL = "/dashboard";

/**
 * Coerce an unknown value to a bounded string, or return the fallback when
 * the value is not a string (or exceeds the maximum length).
 */
function pushString(value, fallback, maxLength) {
  if (typeof value !== "string") return fallback;
  const trimmed = value.trim();
  if (trimmed.length === 0 || trimmed.length > maxLength) return fallback;
  return trimmed;
}

/**
 * Resolve a push-provided destination to an application URL.
 *
 * Security: only same-origin relative paths are accepted. Protocol-relative
 * ("//host/path") and absolute URLs to other origins are rejected so a push
 * payload can never navigate the user to an arbitrary external site. Returns
 * null when the candidate is not a safe application path.
 */
function resolvePushUrl(candidate) {
  const raw = pushString(candidate, null, PUSH_URL_MAX_LENGTH);
  if (raw === null) return null;
  if (!raw.startsWith("/")) return null;
  // Protocol-relative or scheme-qualified external destinations.
  if (raw.startsWith("//")) return null;
  try {
    const url = new URL(raw, self.location.origin);
    if (url.origin !== self.location.origin) return null;
    return url.pathname + url.search + url.hash;
  } catch {
    return null;
  }
}

/**
 * Parse a push payload into safe showNotification options.
 *
 * Supported shape (all fields optional):
 *   { "title": string, "body": string, "icon": string, "badge": string,
 *     "tag": string, "url": string }
 * Malformed JSON, empty payloads, missing fields and wrong types all fall
 * back to safe defaults — nothing is executed and nothing is interpolated
 * into markup.
 */
function parsePushPayload(text) {
  let data = null;
  if (typeof text === "string" && text.trim().length > 0) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  const obj = data !== null && typeof data === "object" && !Array.isArray(data) ? data : {};

  const title = pushString(obj.title, DEFAULT_PUSH_TITLE, PUSH_TITLE_MAX_LENGTH);
  const body = pushString(obj.body, "", PUSH_BODY_MAX_LENGTH);
  const icon = pushString(obj.icon, DEFAULT_PUSH_ICON, PUSH_URL_MAX_LENGTH);
  const badge = pushString(obj.badge, DEFAULT_PUSH_ICON, PUSH_URL_MAX_LENGTH);
  const tag = pushString(obj.tag, "", PUSH_TAG_MAX_LENGTH);
  const url = resolvePushUrl(obj.url);

  return {
    title,
    body,
    icon,
    badge,
    tag,
    url: url ?? DEFAULT_PUSH_URL,
  };
}

self.addEventListener("push", (event) => {
  const payload = parsePushPayload(event.data ? event.data.text() : "");

  const options = {
    body: payload.body,
    icon: payload.icon,
    badge: payload.badge,
    data: { url: payload.url },
  };
  if (payload.tag) {
    options.tag = payload.tag;
  }

  // waitUntil keeps the notification display alive until showNotification
  // resolves. This is display-only — no API calls, no cache writes, no
  // database access. Failures are swallowed so a bad push can never crash
  // the worker or the page.
  event.waitUntil(
    self.registration.showNotification(payload.title, options).catch(() => {})
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  // The destination was validated when the notification was shown
  // (parsePushPayload -> resolvePushUrl). Re-validate defensively here so a
  // tampered notification data object can never open an external origin.
  const rawUrl =
    event.notification.data && typeof event.notification.data === "object"
      ? event.notification.data.url
      : undefined;
  const destination = resolvePushUrl(rawUrl) ?? DEFAULT_PUSH_URL;

  event.waitUntil(
    (async () => {
      const windowClients = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });

      for (const client of windowClients) {
        try {
          const clientOrigin = new URL(client.url).origin;
          if (clientOrigin !== self.location.origin) continue;
        } catch {
          continue;
        }

        // Focus the existing app window first.
        await client.focus().catch(() => {});
        // Navigate to the destination where supported (same-origin
        // only, which resolvePushUrl guarantees). Older browsers throw
        // for cross-origin navigations; ours cannot be cross-origin.
        try {
          if (client.navigate) {
            await client.navigate(destination);
          }
        } catch {
          // Navigation unsupported or failed — the app is already
          // focused, which is an acceptable fallback.
        }
        return;
      }

      // No existing app window: open one at the validated destination.
      const url = new URL(destination, self.location.origin);
      await self.clients.openWindow(url.href).catch(() => {});
    })()
  );
});