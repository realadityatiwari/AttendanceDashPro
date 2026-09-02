// Phase 11C-P2: the smallest clean frontend configuration boundary for Web
// Push, plus the encoding helpers the future push implementation (P3) needs.
//
// Web Push subscription requires the application's PUBLIC VAPID key. P2 does
// NOT implement VAPID (that is P3): this module only exposes the documented
// public-key configuration hook. The value is a build-time PUBLIC variable
// (inlined into the client bundle by Next.js) — it must NEVER be a private
// key. When the value is missing the app degrades to an honest "push setup
// unavailable" state instead of pretending the system is production-ready.

export const VAPID_PUBLIC_KEY = (process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || "").trim();

/** True when a public VAPID key has been configured (P3 provides the value). */
export const isVapidConfigured = VAPID_PUBLIC_KEY.length > 0;

/**
 * Convert a URL-safe (base64url) Base64 string — the standard encoding of a
 * Web Push VAPID public key — into a Uint8Array as required by
 * PushManager.subscribe()'s `applicationServerKey` option.
 *
 * Follows the WHATWG base64url decoding rules: unpadded input, `-` and `_`
 * mapped back to `+` and `/`, with padding restored before atob().
 */
export function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  // Allocate over an explicit ArrayBuffer so the result is a
  // Uint8Array<ArrayBuffer> — required by PushManager.subscribe()'s
  // `applicationServerKey` BufferSource typing.
  const outputArray = new Uint8Array(new ArrayBuffer(rawData.length));
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

/**
 * Convert the raw key bytes of a browser PushSubscription (getKey("p256dh") /
 * getKey("auth")) into the URL-safe, unpadded base64 strings the Web Push
 * contract (and the backend push_subscriptions table) stores. Standard
 * btoa() output is padded base64 with `+`/`/`; the Web Push wire format uses
 * base64url, so the characters are swapped and padding stripped.
 */
export function arrayBufferToBase64Url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; ++i) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
