"use client";

import { ReactNode } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import {
  LogOut,
  MessageSquareText,
  ShieldCheck,
  LayoutDashboard,
  Users,
  BookOpen,
  FolderTree,
  CalendarClock,
  ClipboardList,
  CalendarDays,
  BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { AdminIdentity } from "@/types/api";

const ADMIN_NAV_ITEMS = [
  { label: "Overview", href: "/admin", icon: LayoutDashboard, globalOnly: false },
  { label: "Students", href: "/admin/students", icon: Users, globalOnly: false },
  // Phase 24.6: Curriculum (scoped reads — any admin; writes HEAD-only,
  // backend-enforced). Shown for all admins; the page hides write controls
  // for non-global admins (presentation; backend is authoritative).
  { label: "Curriculum", href: "/admin/curriculum", icon: BookOpen, globalOnly: false },
  // Phase 24.7-D: Timetable (scoped reads — any admin; writes HEAD + CLASS
  // only, backend-enforced). Shown for all admins; the page hides write
  // controls for non-writers (presentation; backend is authoritative).
  { label: "Timetable", href: "/admin/timetable", icon: CalendarClock, globalOnly: false },
  // Phase 24.8: Quiz Schedules (scoped reads — any admin; writes HEAD-only,
  // backend-enforced). Shown for all admins; the page hides write controls
  // for non-global admins (presentation; backend is authoritative).
  { label: "Quiz Schedules", href: "/admin/quizzes", icon: ClipboardList, globalOnly: false },
  // Phase 24.9: Events (scoped reads — any admin; global/closure writes
  // HEAD-only, backend-enforced). Shown for all admins; the page hides write
  // controls for non-global admins (presentation; backend authoritative).
  { label: "Events", href: "/admin/events", icon: CalendarDays, globalOnly: false },
  // Phase 24.11: Admins & Scopes (HEAD_ADMIN only — backend enforces 403 for
  // scoped admins). Shown for global administrators only (presentation filter;
  // the backend is authoritative).
  { label: "Admins", href: "/admin/admins", icon: ShieldCheck, globalOnly: true },
  // Phase 24.12: Attendance analytics (scoped reads — HEAD all, CLASS own
  // sections, ELECTIVE own subject; backend-enforced). Shown for all admins;
  // the page renders only in-scope data (presentation; backend authoritative).
  { label: "Attendance", href: "/admin/attendance", icon: BarChart3, globalOnly: false },
  // Phase 24.5: Academic Structure (HEAD_ADMIN only — backend enforces 403).
  // Shown for global administrators only (presentation filter; backend is authoritative).
  { label: "Structure", href: "/admin/structure", icon: FolderTree, globalOnly: true },
  // Existing admin surface (GET /api/v1/feedback/admin is require_head_admin-
  // gated server-side). Shown for global administrators only — presentation
  // filtering; the backend remains the boundary.
  { label: "Feedback Review", href: "/tools/feedback", icon: MessageSquareText, globalOnly: true },
] as const;


/**
 * Admin Portal shell (Phase 24.1) — deliberately separate from the student
 * AppShell. Reuses the existing design tokens, Button/Badge/Avatar primitives,
 * the existing AuthContext logout, and the same responsive conventions
 * (nav collapses to a horizontally scrollable row below `md`; no separate
 * mobile architecture). Identity comes from the backend (/api/v1/admin/me)
 * and is rendered for context only.
 */
export function AdminShell({
  identity,
  children,
}: {
  identity: AdminIdentity;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const { logout } = useAuth();

  const displayName = identity.display_name || "Admin";
  const initials = displayName.trim().charAt(0).toUpperCase() || "?";
  const navItems = ADMIN_NAV_ITEMS.filter(
    (item) => !item.globalOnly || identity.is_global
  );

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <header className="shrink-0 border-b border-border bg-background">
        <div className="flex h-14 items-center gap-4 px-4 sm:px-6 lg:px-8">
          <span className="flex items-center gap-2">
            <Image
              src="/brand/logo-mark.png"
              alt="AttendanceDash Pro"
              width={28}
              height={28}
              className="size-7 shrink-0"
              priority
            />
            <span className="text-[0.95rem] font-semibold tracking-tight text-foreground">
              AttendanceDash{" "}
              <span className="font-normal text-muted-foreground">
                Admin
              </span>
            </span>
          </span>

          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              nativeButton={false}
              render={<Link href="/dashboard" />}
            >
              <LayoutDashboard className="size-4" aria-hidden="true" />
              Student app
            </Button>
            <Avatar className="h-8 w-8 border border-border bg-surface2">
              <AvatarFallback className="text-xs font-semibold">
                {initials}
              </AvatarFallback>
            </Avatar>
            <span className="hidden text-sm font-semibold text-foreground sm:block">
              {displayName}
            </span>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Sign out"
              onClick={logout}
            >
              <LogOut className="size-4" aria-hidden="true" />
            </Button>
          </div>
        </div>

        <nav
          aria-label="Admin"
          className="flex items-center gap-1 overflow-x-auto px-4 pb-2 sm:px-6 lg:px-8"
        >
          {navItems.map(({ label, href, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
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
          {identity.is_global ? (
            <Badge variant="primary" className="ml-2 hidden sm:inline-flex">
              Global authority
            </Badge>
          ) : (
            <Badge variant="neutral" className="ml-2 hidden sm:inline-flex">
              Scoped authority
            </Badge>
          )}
        </nav>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-5xl p-4 md:p-6 lg:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
