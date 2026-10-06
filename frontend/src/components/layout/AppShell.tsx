import { ReactNode } from "react";
import { TopNav } from "./TopNav";
import { MobileBottomNav } from "./MobileBottomNav";
import { ServiceWorkerRegistration } from "@/components/pwa/ServiceWorkerRegistration";
import { NotificationRefreshListener } from "@/components/pwa/NotificationRefreshListener";
import { ToastProvider } from "@/components/feedback/toast";

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
 *
 * Phase 11C-P5: mounts <NotificationRefreshListener /> which listens for the
 * service-worker invalidation signal and foreground/visibility recovery and
 * triggers targeted SWR revalidation of the canonical notification key — no
 * polling, no broad cache reset, no full-page reload.
 */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <ServiceWorkerRegistration />
      <NotificationRefreshListener />
      <ToastProvider>
        <TopNav />

        {/* 25.UX-7: scroll-padding keeps keyboard focus clear of the fixed
            mobile bottom nav (WCAG 2.4.11 Focus Not Obscured) — the browser's
            scroll-into-view now leaves the same 7rem the content padding
            reserves; md+ resets it because the nav is md:hidden. */}
        <main className="flex-1 overflow-y-auto scroll-pb-28 md:scroll-pb-0">
          <div className="mx-auto w-full max-w-5xl p-4 pb-28 md:p-6 lg:p-8">
            {children}
          </div>
        </main>

        <MobileBottomNav />
      </ToastProvider>
    </div>
  );
}