"use client";

import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useProfile } from "@/hooks/useApi";
import { UserMenu, ShellModalId } from "@/components/layout/UserMenu";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import { NotificationCenter } from "@/components/notifications/NotificationCenter";
import { ProfileModal } from "@/components/shell/ProfileModal";
import { AppearanceModal } from "@/components/shell/AppearanceModal";
import { SettingsModal } from "@/components/shell/SettingsModal";
import { FeedbackModal } from "@/components/shell/FeedbackModal";
import { InstallAppModal } from "@/components/shell/InstallAppModal";
import { useInstallPrompt } from "@/hooks/useInstallPrompt";
import {
  navItemsForRole,
  moreItemsForRole,
  type NavItem,
} from "@/components/layout/navItems";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/**
 * Full-width compact top navigation bar. Phase 4 responsive IA (D-03):
 *  - lg and above: the full navigation inline (existing design).
 *  - md to lg: primary destinations inline + secondary destinations under a
 *    "More" dropdown, so the row can never overflow at tablet widths.
 *  - below md: the nav is hidden (mobile uses MobileBottomNav) and, for
 *    non-home routes, the header shows the current page title (D-04).
 *
 * Navigation data is shared with MobileBottomNav via navItems.ts — labels,
 * routes and the mobile titles are defined once. Route availability is
 * unchanged in every band.
 */
export function TopNav() {
  const pathname = usePathname();
  const { profile } = useProfile();
  const [activeModal, setActiveModal] = useState<ShellModalId | null>(null);
  const { deferredPrompt, isStandalone } = useInstallPrompt();

  const closeModal = (open: boolean) => {
    if (!open) setActiveModal(null);
  };

  const items = navItemsForRole(profile?.role);
  const secondaryItems = moreItemsForRole(profile?.role);
  const primaryItems = items.filter(
    (item) => !secondaryItems.some((secondary) => secondary.href === item.href)
  );
  const moreActive = secondaryItems.some((item) => item.href === pathname);
  // D-04: current page title for the mobile header (undefined on Home).
  const activeTitle = items.find((item) => item.href === pathname)?.title;

  const renderItem = ({ label, href, icon: Icon }: NavItem) => {
    const active = pathname === href;
    return (
      <Link
        key={href}
        href={href}
        aria-current={active ? "page" : undefined}
        className={cn(
          // Atomic items: never shrink, never wrap (Phase 4 correction —
          // long D-01 labels must stay on one line at lg+).
          "flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors",
          active
            ? "bg-secondary text-foreground"
            : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
        )}
      >
        <Icon className="size-4" aria-hidden="true" />
        {label}
      </Link>
    );
  };

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background px-4 sm:px-6 lg:px-8">
      <Link
        href="/dashboard"
        className="flex shrink-0 items-center gap-2.5 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
      >
        <Image
          src="/brand/logo-mark.png"
          alt="AttendanceDash Pro"
          width={28}
          height={28}
          className="size-7 shrink-0"
          priority
        />
        <span
          className={cn(
            "text-[0.95rem] font-semibold tracking-tight text-foreground",
            // D-04: on small screens the page title replaces the wordmark.
            activeTitle && "hidden sm:inline"
          )}
        >
          AttendanceDash <span className="font-normal text-muted-foreground">Pro</span>
        </span>
      </Link>

      {activeTitle && (
        <div className="min-w-0 flex-1 text-center md:hidden">
          <span className="block truncate text-sm font-semibold text-foreground">
            {activeTitle}
          </span>
        </div>
      )}

      {/* lg and above: full navigation (atomic single-line items) */}
      <nav
        aria-label="Primary"
        className="hidden shrink-0 items-center gap-1 lg:flex"
      >
        {items.map(renderItem)}
      </nav>

      {/* md to lg: primary destinations + More dropdown for secondary */}
      <nav
        aria-label="Primary"
        className="hidden shrink-0 items-center gap-1 md:flex lg:hidden"
      >
        {primaryItems.map(renderItem)}
        <DropdownMenu>
          <DropdownMenuTrigger
            aria-current={moreActive ? "true" : undefined}
            className={cn(
              "flex shrink-0 items-center gap-1 whitespace-nowrap rounded-md px-2.5 py-1.5 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/60",
              moreActive
                ? "bg-secondary text-foreground"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground data-popup-open:bg-muted/60 data-popup-open:text-foreground"
            )}
          >
            More
            <ChevronDown className="size-3.5" aria-hidden="true" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56">
            {secondaryItems.map((item) => (
              <DropdownMenuItem
                key={item.href}
                render={
                  <Link
                    href={item.href}
                    aria-current={pathname === item.href ? "page" : undefined}
                  />
                }
              >
                <item.icon className="size-4" aria-hidden="true" />
                {item.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </nav>

      <div className="ml-auto flex shrink-0 items-center gap-2 sm:gap-3">
        <NotificationBell onOpenModal={setActiveModal} />
        <UserMenu onOpenModal={setActiveModal} />
      </div>

      <ProfileModal
        open={activeModal === "profile"}
        onOpenChange={closeModal}
      />
      <AppearanceModal
        open={activeModal === "appearance"}
        onOpenChange={closeModal}
      />
      <SettingsModal
        open={activeModal === "settings"}
        onOpenChange={closeModal}
      />
      <FeedbackModal
        open={activeModal === "feedback"}
        onOpenChange={closeModal}
      />
      <InstallAppModal
        open={activeModal === "install"}
        onOpenChange={closeModal}
        deferredPrompt={deferredPrompt}
        isStandalone={isStandalone}
      />
      <NotificationCenter
        open={activeModal === "notifications"}
        onOpenChange={closeModal}
      />
    </header>
  );
}
