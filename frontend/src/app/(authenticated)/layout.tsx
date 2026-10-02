import { ReactNode } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { AuthGate } from "@/components/layout/AuthGate";

/**
 * UIA-013: the shell is gated on the resolved auth session so an
 * unauthenticated visit to a protected route never flashes the app chrome
 * before AuthContext redirects to /login. Route/auth semantics are unchanged.
 */
export default function AuthenticatedLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <AuthGate>
      <AppShell>{children}</AppShell>
    </AuthGate>
  );
}
