// Production build must never silently fall back to a localhost API URL.
// NEXT_PUBLIC_API_URL is a build-time public variable (inlined into the
// client bundle). If it is missing or points at a development host while
// building for production, fail loudly instead of shipping a broken client.
const DEV_API_URL = "http://127.0.0.1:8080";
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

interface FetchOptions extends RequestInit {
  requireAuth?: boolean;
}

/**
 * Custom fetch wrapper that automatically attaches the JWT access token
 * to requests when requireAuth is true (which is the default).
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
    if (response.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
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
