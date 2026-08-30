"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  CalendarClock,
  CalendarDays,
  CalendarRange,
  FlaskConical,
  History,
  LayoutDashboard,
  Menu,
  MessageSquareText,
  TestTubes,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useProfile } from "@/hooks/useApi";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

const PRIMARY_TABS = [
  { label: "Home", href: "/dashboard", icon: LayoutDashboard },
  { label: "Attendance", href: "/subjects", icon: BookOpen },
  { label: "History", href: "/history", icon: History },
] as const;

const MORE_ITEMS = [
  { label: "Track", href: "/tools/laboratory", icon: FlaskConical },
  { label: "Laboratory", href: "/laboratory", icon: TestTubes },
  { label: "Quiz Eligibility", href: "/tools/quiz-schedule", icon: CalendarClock },
  { label: "Calendar", href: "/calendar", icon: CalendarRange },
  { label: "Events", href: "/tools/events", icon: CalendarDays },
] as const;

const ADMIN_MORE_ITEM = { label: "Feedback", href: "/tools/feedback", icon: MessageSquareText } as const;

/**
 * Mobile primary navigation — Phase 12A.
 *
 * Exactly three bottom-navigation tabs (Home, Attendance, History) visible
 * only below `md`; the "More" tab opens a bottom-sheet surface hosting the
 * secondary destinations (Track, Laboratory, Quiz Eligibility, Calendar,
 * Events). Profile is intentionally NOT a tab or sheet entry: it is already
 * reachable from the avatar in the top-right corner on every viewport, so
 * duplicating it here would only crowd the nav. Desktop navigation is
 * untouched (TopNav remains hidden below `md` exactly as before). Uses the
 * same routing/active-route conventions as TopNav (next/link + usePathname
 * exact match) and the existing dark design tokens.
 */
export function MobileBottomNav() {
  const pathname = usePathname();
  const { profile } = useProfile();
  const [moreOpen, setMoreOpen] = useState(false);

  const moreItems = profile?.role === "ADMIN"
    ? [...MORE_ITEMS, ADMIN_MORE_ITEM]
    : MORE_ITEMS;

  return (
    <>
      <nav
        aria-label="Mobile primary"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
      >
        <div className="grid grid-cols-4">
          {PRIMARY_TABS.map(({ label, href, icon: Icon }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-14 flex-col items-center justify-center gap-1 rounded-md py-2.5 text-[0.65rem] font-medium transition-colors",
                  active
                    ? "text-primary"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                )}
              >
                <Icon className="size-5" aria-hidden="true" />
                {label}
              </Link>
            );
          })}
          <button
            type="button"
            aria-label="Open more"
            aria-expanded={moreOpen}
            onClick={() => setMoreOpen((v) => !v)}
            className={cn(
              "flex min-h-14 flex-col items-center justify-center gap-1 rounded-md py-2.5 text-[0.65rem] font-medium transition-colors",
              moreOpen
                ? "text-primary"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
            )}
          >
            <Menu className="size-5" aria-hidden="true" />
            More
          </button>
        </div>
      </nav>

      <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
        <SheetContent
          side="bottom"
          className="rounded-t-2xl pb-[max(env(safe-area-inset-bottom),1rem)]"
        >
          <SheetHeader>
            <SheetTitle>More</SheetTitle>
            <SheetDescription>Academic tools</SheetDescription>
          </SheetHeader>
          <div className="flex flex-col gap-1 px-4 pb-2">
            {moreItems.map(({ label, href, icon: Icon }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMoreOpen(false)}
                  className={cn(
                    "flex h-12 items-center gap-3 rounded-lg px-4 text-sm font-medium transition-colors",
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
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}