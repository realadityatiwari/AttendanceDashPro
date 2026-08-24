"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FlaskConical,
  TestTubes,
  CalendarClock,
  BookOpen,
  History,
  CalendarDays,
  CalendarRange,
  Gauge,
  MessageSquareText,
} from "lucide-react";
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

const NAV_ITEMS = [
  { label: "Home", href: "/dashboard", icon: LayoutDashboard },
  { label: "Track", href: "/tools/laboratory", icon: FlaskConical },
  { label: "Laboratory", href: "/laboratory", icon: TestTubes },
  { label: "Quiz Eligibility", href: "/tools/quiz-schedule", icon: CalendarClock },
  { label: "Attendance", href: "/subjects", icon: BookOpen },
  { label: "History", href: "/history", icon: History },
  { label: "Calendar", href: "/calendar", icon: CalendarRange },
  { label: "Events", href: "/tools/events", icon: CalendarDays },
];

const ADMIN_NAV_ITEM = { label: "Feedback", href: "/tools/feedback", icon: MessageSquareText };

/**
 * Full-width compact top navigation bar. Replaces the legacy sidebar:
 * brand on the left, primary navigation in the middle, authenticated user
 * menu on the right. Navigation links are hidden below `md` — the mobile
 * navigation pattern is a dedicated later phase.
 */
export function TopNav() {
  const pathname = usePathname();
  const { profile } = useProfile();
  const [activeModal, setActiveModal] = useState<ShellModalId | null>(null);
  const { deferredPrompt, isStandalone } = useInstallPrompt();

  const closeModal = (open: boolean) => {
    if (!open) setActiveModal(null);
  };

  const navItems = profile?.role === "ADMIN"
    ? [...NAV_ITEMS, ADMIN_NAV_ITEM]
    : NAV_ITEMS;

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-background px-4 sm:px-6 lg:px-8">
      <Link
        href="/dashboard"
        className="flex shrink-0 items-center gap-2 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
      >
        <span className="flex size-7 items-center justify-center rounded-md bg-primary/15 text-primary">
          <Gauge className="size-4" aria-hidden="true" />
        </span>
        <span className="text-[0.95rem] font-semibold tracking-tight text-foreground">
          AttendanceDash <span className="font-normal text-muted-foreground">Pro</span>
        </span>
      </Link>

      <nav
        aria-label="Primary"
        className="hidden min-w-0 items-center gap-1 md:flex lg:gap-1.5"
      >
        {navItems.map(({ label, href, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                active
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="ml-auto flex items-center gap-1">
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