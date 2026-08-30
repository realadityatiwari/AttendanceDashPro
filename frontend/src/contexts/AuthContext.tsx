"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import useSWR, { useSWRConfig } from "swr";
import { apiFetch, PROFILE_KEY } from "@/lib/api";

// Assuming User type from backend schema (StudentProfile)
export interface User {
  id: string;
  display_name: string;
  roll_number: string;
  section_name: string | null;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  getToken: () => Promise<string | null>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  getToken: async () => null,
  logout: () => {},
  refreshUser: async () => {},
});

// Same config family as STANDARD_CACHE in useApi.ts so the shared profile
// resource behaves identically for AuthContext and the UI consumers.
const PROFILE_CACHE = {
  revalidateOnFocus: true,
  dedupingInterval: 60000, // 1 minute
};

// Token presence lifecycle:
//   "unknown"  -> initial render, still reading localStorage (auth hydration)
//   "present"  -> a persisted access_token exists
//   "absent"   -> no persisted access_token
type TokenStatus = "unknown" | "present" | "absent";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [tokenStatus, setTokenStatus] = useState<TokenStatus>("unknown");
  const router = useRouter();
  const pathname = usePathname();
  const { mutate: globalMutate } = useSWRConfig();

  // Read the persisted token exactly once on the client. A token is never
  // removed here — only on a genuine 401/403 or explicit logout.
  useEffect(() => {
    setTokenStatus(localStorage.getItem("access_token") ? "present" : "absent");
  }, []);

  // Shared SWR profile resource. AuthContext and useProfile() use the SAME
  // cache key (PROFILE_KEY), so SWR coalesces them into ONE /student/me
  // request. The key is gated on token presence: no token -> no fetch, and a
  // cached profile can never surface as user while the token is absent.
  const { data, error, isLoading, mutate } = useSWR<User | null>(
    tokenStatus === "present" ? PROFILE_KEY : null,
    (url: string) => apiFetch(url),
    PROFILE_CACHE
  );

  // user is DERIVED from the shared profile resource, gated on the token.
  // Removing the token (key -> null) immediately yields null user — a stale
  // cached profile can never authenticate.
  const user = tokenStatus === "present" ? (data ?? null) : null;

  // Hydration/loading: unknown token state OR an in-flight first profile
  // fetch. A loading state must never redirect to /login.
  const loading = tokenStatus === "unknown" || (tokenStatus === "present" && isLoading);

  // Genuine authentication rejection: destroy the session. Transient failures
  // (no status / 5xx) keep the token and let SWR retry on focus — they must
  // NOT log the user out. apiFetch already hard-redirects on 401; this keeps
  // local state consistent for 401/403 and clears any cached profile.
  useEffect(() => {
    if (error) {
      const status = (error as { status?: number } | undefined)?.status;
      if (status === 401 || status === 403) {
        localStorage.removeItem("access_token");
        setTokenStatus("absent");
        globalMutate(PROFILE_KEY, () => undefined, { revalidate: false });
      }
    }
  }, [error, globalMutate]);

  // Self-healing: if a transient failure (cold start, flaky network) left us
  // with a token but no user, retry the shared profile fetch when the app
  // regains focus/visibility — instead of forcing a re-login or reload. SWR
  // dedupes in-flight fetches, so this never stacks duplicate requests.
  useEffect(() => {
    const retry = () => {
      if (tokenStatus === "present" && user === null) {
        mutate();
      }
    };
    window.addEventListener("focus", retry);
    document.addEventListener("visibilitychange", retry);
    return () => {
      window.removeEventListener("focus", retry);
      document.removeEventListener("visibilitychange", retry);
    };
  }, [tokenStatus, user, mutate]);

  useEffect(() => {
    if (!loading) {
      const isPublicRoute = pathname === "/login" || pathname === "/signup";
      // Redirect to /login only when there is genuinely no session token.
      // When a token exists but the profile fetch failed transiently, stay on
      // the current page and let SWR retry instead of bouncing the user out.
      if (user && isPublicRoute) {
        router.push("/dashboard");
      } else if (!user && tokenStatus === "absent" && !isPublicRoute) {
        router.push("/login");
      }
    }
  }, [user, loading, pathname, router, tokenStatus]);

  const getToken = async () => {
    return typeof window !== 'undefined' ? localStorage.getItem("access_token") : null;
  };

  // Re-sync token state and revalidate the shared profile. Used by the
  // login/signup flow right after persisting a fresh token. Clearing ALL
  // cached SWR data first prevents any previous user's session data from
  // flashing after a new login (cross-user isolation).
  const refreshUser = async () => {
    const token = localStorage.getItem("access_token");
    if (token) {
      globalMutate(() => true, () => undefined, { revalidate: false });
      setTokenStatus("present");
      await globalMutate(PROFILE_KEY);
    } else {
      setTokenStatus("absent");
    }
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    // Clear the ENTIRE SWR cache so no stale per-user data survives into the
    // next session (cross-user isolation); the profile can never re-authenticate.
    globalMutate(() => true, () => undefined, { revalidate: false });
    setTokenStatus("absent");
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, getToken, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
