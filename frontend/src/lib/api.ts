// Production build must never silently fall back to a localhost API URL.
// NEXT_PUBLIC_API_URL is a build-time public variable (inlined into the
// client bundle). If it is missing or points at a development host while
// building for production, fail loudly instead of shipping a broken client.
// 8300: port 8080 sits inside a Windows reserved/excluded TCP port range on
// the dev machine (WinError 10013 at bind), so the local dev backend uses 8300.
const DEV_API_URL = "http://127.0.0.1:8300";
const configuredApiUrl = (process.env.NEXT_PUBLIC_API_URL || "").trim();
const isLocalDevUrl = /^https?:\/\/(localhost|127\.0\.0\.1|0\.0\.0\.0)/.test(configuredApiUrl);

if (process.env.NODE_ENV === "production" && (!configuredApiUrl || isLocalDevUrl)) {
  throw new Error(
    "NEXT_PUBLIC_API_URL must be set to the production backend HTTPS URL " +
    "when building for production (e.g. https://your-api.onrender.com). " +
    "Refusing to fall back to a localhost API URL."
  );
}

const API_BASE_URL = configuredApiUrl || DEV_API_URL;

/** The guarded, build-time production API base URL (no localhost fallback in
 * production builds). Shared by apiFetch and the auth pages so every request
 * uses the same guard and the same base URL. */
export { API_BASE_URL };

/** Shared SWR cache key for the authenticated student profile endpoint.
 * AuthContext and useProfile() consume the same key so SWR coalesces them
 * into one /student/me request. */
export const PROFILE_KEY = "/api/v1/student/me";

/** Shared SWR cache key for the canonical notification inbox endpoint.
 * The bell badge, the notification center, the PATCH mutation reconciliation,
 * the service-worker invalidation signal, and bell-open revalidation all
 * consume this ONE key so SWR coalesces them into a single request (Phase
 * 11C-P5 canonical key). GET /api/v1/notifications remains strictly read-only. */
export const NOTIFICATIONS_KEY = "/api/v1/notifications";

// ── Single-flight refresh-token renewal ───────────────────────────────────
//
// Phase 25.2: opaque HttpOnly refresh cookie → POST /api/v1/auth/refresh
// returns a new access_token. One in-flight refresh at any time; all
// concurrent 401s share the same promise.

type RefreshResult =
  | { ok: true; token: string }
  | { ok: false; permanent: boolean };

let _refreshPromise: Promise<RefreshResult> | null = null;

async function _attemptRefresh(): Promise<RefreshResult> {
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) {
        return { ok: false, permanent: true };
      }

      const data = await response.json();
      if (typeof data.access_token !== "string") {
        return { ok: false, permanent: true };
      }

      localStorage.setItem("access_token", data.access_token);
      return { ok: true, token: data.access_token };
    } catch {
      // Network error during refresh — transient, not a permanent auth
      // failure. The caller should keep the existing token and let SWR
      // retry naturally.
      return { ok: false, permanent: false };
    } finally {
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
}

// ── apiFetch ──────────────────────────────────────────────────────────────

interface FetchOptions extends RequestInit {
  requireAuth?: boolean;
}

/**
 * Custom fetch wrapper that automatically attaches the JWT access token
 * to requests when requireAuth is true (which is the default).
 *
 * Phase 25.2: on a genuine 401 (never 403/5xx/network) the wrapper attempts
 * a single-flight refresh-token rotation before clearing auth. If the refresh
 * succeeds the original request is retried exactly once; if it fails with a
 * permanent error (HTTP 401 on the refresh endpoint) the existing logout path
 * runs. A transient network error during refresh does NOT clear auth — the
 * user stays on the page and SWR retries on the next focus/visibility event.
 */
export async function apiFetch(endpoint: string, options: FetchOptions = {}) {
  const { requireAuth = true, headers, ...restOptions } = options;

  const requestHeaders = new Headers(headers);
  requestHeaders.set("Content-Type", "application/json");

  if (requireAuth) {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    if (!token) {
      throw new Error("Authentication required for this request");
    }
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  const url = `${API_BASE_URL}${endpoint}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...restOptions,
      headers: requestHeaders,
    });
  } catch (err) {
    // Network-level failure (backend unreachable, TLS, DNS, CORS preflight
    // rejection, connection reset). The browser's raw "Failed to fetch" is
    // not actionable; translate it while preserving the original error as
    // the cause for debugging.
    console.error(`Network request failed: ${url}`, err);
    throw new Error(
      "Unable to reach the server. Check your connection and try again.",
      { cause: err },
    );
  }

  if (!response.ok) {
    // Phase 25.2: attempt refresh on genuine 401 with auth required.
    // Never on 403, 5xx, network errors, or non-auth requests.
    if (response.status === 401 && requireAuth) {
      const refreshResult = await _attemptRefresh();

      if (refreshResult.ok) {
        // Retry the original request exactly once with the new token.
        requestHeaders.set("Authorization", `Bearer ${refreshResult.token}`);
        try {
          response = await fetch(url, { ...restOptions, headers: requestHeaders });
        } catch (err) {
          // Network error on retry — same as any other network failure.
          throw new Error(
            "Unable to reach the server. Check your connection and try again.",
            { cause: err },
          );
        }
        if (response.ok) {
          if (response.status === 204) return null;
          return response.json();
        }
        // Retry failed (any status, including 401). Fall through to the
        // standard error handling below. A second 401 after a fresh token
        // means the session is genuinely dead — the 401 handler clears auth.
      } else if (!refreshResult.permanent) {
        // Transient network failure during the refresh call itself. The
        // original 401 is still valid, but the inability to reach the
        // refresh endpoint is not a reason to destroy the session. Throw
        // without a status so AuthContext does NOT clear the token; SWR
        // will retry on the next focus/visibility event.
        throw new Error("Session renewal failed. Please try again.");
      }
      // permanent refresh failure: fall through to the existing 401
      // handling below (clear token + redirect).
    }

    // Existing error handling (Phase 24.1 / 24.7-F).
    // 401/403 clear auth and redirect; 5xx and transient errors preserve
    // the token so SWR can retry.
    if (response.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      // UI-026: mark the session as expired so the login page can explain the
      // redirect instead of the user being silently dropped onto the form.
      // Idempotent for concurrent 401s; read once and cleared on the login page.
      try {
        sessionStorage.setItem('session_expired', '1');
      } catch {
        // Storage may be unavailable (privacy mode) — messaging is best-effort.
      }
      // Redirect to login if not already there
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    let errorMessage = "API request failed";
    let errorData: Record<string, unknown> = {};
    try {
      errorData = await response.json();
      if (typeof errorData.detail === "string") {
        errorMessage = errorData.detail || (errorData.message as string) || errorMessage;
      } else if (typeof errorData.detail === "object" && errorData.detail !== null) {
        // Structured detail (e.g. 409 conflict with "message" + "conflicts").
        const structured = errorData.detail as { message?: string };
        errorMessage = structured.message || errorMessage;
      } else {
        errorMessage = (errorData.message as string) || errorMessage;
      }
    } catch {
      errorMessage = response.statusText;
    }
    // Phase 24.1: preserve the HTTP status on the thrown error so callers can
    // distinguish authorization failures (403) from other API failures.
    // Additive only — existing consumers are unaffected.
    // Phase 24.7-F: also attach the raw response body so callers (e.g. the
    // timetable form) can access structured fields like "conflicts".
    const error = new Error(errorMessage) as Error & { status?: number; body?: Record<string, unknown> };
    error.status = response.status;
    error.body = errorData;
    throw error;
  }

  // Handle empty responses (e.g., 204 No Content)
  if (response.status === 204) {
    return null;
  }

  return response.json();
}
