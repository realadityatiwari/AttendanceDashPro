"use client";

import { createContext, useContext, useEffect, useRef, useState, ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { apiFetch } from "@/lib/api";

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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const inFlight = useRef(false);
  const router = useRouter();
  const pathname = usePathname();

  const loadUser = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        setUser(null);
        return;
      }
      const data = await apiFetch("/api/v1/student/me");
      setUser(data);
    } catch (error) {
      console.error("Failed to fetch user profile", error);
      // Only destroy the session on a genuine authentication rejection
      // (401/403). Transient failures — Render free-tier cold starts, flaky
      // mobile networks, brief 5xx blips — must NOT log the user out,
      // otherwise the app redirects to /login on every backend hiccup.
      const status = (error as { status?: number } | undefined)?.status;
      if (status === 401 || status === 403) {
        setUser(null);
        localStorage.removeItem("access_token");
      }
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUser();
  }, []);

  // Self-healing: if a transient failure (cold start, flaky network) left us
  // with a stored token but no user, retry the profile fetch when the app
  // regains focus/visibility — instead of forcing the user to re-login or
  // reload. Never clears the token on these retries.
  useEffect(() => {
    const hasStoredToken = () =>
      typeof window !== "undefined" ? Boolean(localStorage.getItem("access_token")) : false;

    const retry = () => {
      if (hasStoredToken() && user === null) {
        loadUser();
      }
    };
    window.addEventListener("focus", retry);
    document.addEventListener("visibilitychange", retry);
    return () => {
      window.removeEventListener("focus", retry);
      document.removeEventListener("visibilitychange", retry);
    };
  }, [user]);

  useEffect(() => {
    if (!loading) {
      const isPublicRoute = pathname === "/login" || pathname === "/signup";
      // Redirect to /login only when there is genuinely no session token.
      // When a token exists but the profile fetch failed transiently, stay on
      // the current page and let SWR retry instead of bouncing the user out.
      const hasToken =
        typeof window !== "undefined" ? Boolean(localStorage.getItem("access_token")) : false;
      if (user && isPublicRoute) {
        router.push("/dashboard");
      } else if (!user && !hasToken && !isPublicRoute) {
        router.push("/login");
      }
    }
  }, [user, loading, pathname, router]);

  const getToken = async () => {
    return typeof window !== 'undefined' ? localStorage.getItem("access_token") : null;
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, getToken, logout, refreshUser: loadUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
