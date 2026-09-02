import { ReactNode } from "react";
import { TopNav } from "./TopNav";
import { MobileBottomNav } from "./MobileBottomNav";
import { ServiceWorkerRegistration } from "@/components/pwa/ServiceWorkerRegistration";

interface AppShellProps {
  children: ReactNode;
}

/**
 * Authenticated application shell.
 *
 * Phase 12A: renders the mobile bottom navigation below `md` and reserves
 * bottom padding for it (the fixed nav must never cover the last interactive
 * element). Desktop behavior is unchanged: `md:p-6` / `lg:p-8` restore the
 * original desktop padding, and the bottom nav is `md:hidden`.
 *
 * Phase 11C-P1: mounts the side-effect-only <ServiceWorkerRegistration /> so
 * the PWA service worker registers when the application shell mounts.
 */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <ServiceWorkerRegistration />
      <TopNav />

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-5xl p-4 pb-28 md:p-6 lg:p-8">
          {children}
        </div>
      </main>

      <MobileBottomNav />
    </div>
  );
}