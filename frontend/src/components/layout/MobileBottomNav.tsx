"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { useProfile } from "@/hooks/useApi";
import { mobileTabItems, moreItemsForRole } from "@/components/layout/navItems";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

/**
 * Mobile primary navigation — Phase 12A, Phase 4 refinements.
 *
 * Three fixed bottom tabs (Home, Attendance, History) plus a "More" sheet
 * hosting the secondary destinations. Navigation data comes from the shared
 * navItems.ts source (D-01 labels) so desktop and mobile can never drift.
 *
 * Phase 4 (D-04/UI-008): when the current route belongs to the "More" group,
 * the More control is highlighted and marked aria-current, so the user's
 * location stays visible inside secondary sections.
 */
export function MobileBottomNav() {
  const pathname = usePathname();
  const { profile } = useProfile();
  const [moreOpen, setMoreOpen] = useState(false);

  const tabs = mobileTabItems(profile?.role);
  const moreItems = moreItemsForRole(profile?.role);
  const moreActive = moreItems.some((item) => item.href === pathname);

  return (
    <>
      <nav
        aria-label="Mobile primary"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
      >
        <div className="grid grid-cols-4">
          {tabs.map(({ label, href, icon: Icon }) => {
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
            aria-current={moreActive ? "true" : undefined}
            onClick={() => setMoreOpen((v) => !v)}
            className={cn(
              "flex min-h-14 flex-col items-center justify-center gap-1 rounded-md py-2.5 text-[0.65rem] font-medium transition-colors",
              moreOpen || moreActive
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
                  aria-current={active ? "page" : undefined}
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
