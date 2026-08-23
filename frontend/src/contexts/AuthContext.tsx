"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
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
  const router = useRouter();
  const pathname = usePathname();

  const loadUser = async () => {
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
      setUser(null);
      localStorage.removeItem("access_token");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUser();
  }, []);

  useEffect(() => {
    if (!loading) {
      const isPublicRoute = pathname === "/login" || pathname === "/signup";
      if (user && isPublicRoute) {
        router.push("/dashboard");
      } else if (!user && !isPublicRoute) {
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
