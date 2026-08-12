import { auth } from "./firebase";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FetchOptions extends RequestInit {
  requireAuth?: boolean;
}

/**
 * Custom fetch wrapper that automatically attaches the Firebase ID token
 * to requests when requireAuth is true (which is the default).
 */
export async function apiFetch(endpoint: string, options: FetchOptions = {}) {
  const { requireAuth = true, headers, ...restOptions } = options;
  
  const requestHeaders = new Headers(headers);
  requestHeaders.set("Content-Type", "application/json");

  if (requireAuth) {
    const user = auth.currentUser;
    if (!user) {
      throw new Error("Authentication required for this request");
    }
    
    // Always get a fresh token (Firebase caches it anyway)
    const token = await user.getIdToken();
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  const url = `${API_BASE_URL}${endpoint}`;
  
  const response = await fetch(url, {
    ...restOptions,
    headers: requestHeaders,
  });

  if (!response.ok) {
    let errorMessage = "API request failed";
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      errorMessage = response.statusText;
    }
    throw new Error(errorMessage);
  }

  // Handle empty responses (e.g., 204 No Content)
  if (response.status === 204) {
    return null;
  }

  return response.json();
}
