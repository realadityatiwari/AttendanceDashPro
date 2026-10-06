import {
  BookOpen,
  CalendarClock,
  CalendarDays,
  CalendarRange,
  ClipboardCheck,
  History,
  LayoutDashboard,
  MessageSquareText,
  TestTubes,
} from "lucide-react";
import type { ComponentType } from "react";

export interface NavItem {
  /** User-facing navigation label (D-01 terminology). */
  label: string;
  href: string;
  icon: ComponentType<{ className?: string }>;
  /**
   * Page title shown in the mobile header (D-04). Undefined for Home — the
   * dashboard keeps its brand wordmark and greeting instead of a title.
   */
  title?: string;
}

/**
 * Single source of truth for student navigation (Phase 4, D-01..D-04).
 *
 * Routes are UNCHANGED — only user-facing labels/titles were clarified:
 * the daily marking destination (/tools/laboratory) is "Mark Attendance"
 * and the experiments destination (/laboratory) is "Lab Experiments".
 *
 * Groups derived from these lists:
 *  - Desktop (lg+): every item, in order.
 *  - Desktop (md–lg): every item NOT in MORE_HREFS, plus a "More" dropdown
 *    holding MORE_HREFS (D-03 overflow fix).
 *  - Mobile bottom bar: MOBILE_TAB_HREFS as tabs + MORE_HREFS under "More".
 */
export const NAV_ITEMS: NavItem[] = [
  { label: "Home", href: "/dashboard", icon: LayoutDashboard },
  {
    label: "Mark Attendance",
    href: "/tools/laboratory",
    icon: ClipboardCheck,
    // UIA-021: no mobile header title for this route — the page renders its
    // own h1, so the fixed header would otherwise stack the same title twice.
    // The tab label above still names the destination.
  },
  {
    label: "Lab Experiments",
    href: "/laboratory",
    icon: TestTubes,
    title: "Lab Experiments",
  },
  {
    label: "Quiz Eligibility",
    href: "/tools/quiz-schedule",
    icon: CalendarClock,
    title: "Quiz Eligibility",
  },
  {
    // 25.UX-3: the nav label stays "Attendance" (D-01 destination naming),
    // but the mobile header title now matches the page h1 ("Subjects
    // Overview") like every other title in this list — one route can no
    // longer present two different names for itself.
    label: "Attendance",
    href: "/subjects",
    icon: BookOpen,
    title: "Subjects Overview",
  },
  { label: "History", href: "/history", icon: History, title: "Attendance History" },
  { label: "Calendar", href: "/calendar", icon: CalendarRange, title: "Calendar" },
  { label: "Events", href: "/tools/events", icon: CalendarDays, title: "Academic Events" },
];

export const ADMIN_NAV_ITEM: NavItem = {
  label: "Feedback",
  href: "/tools/feedback",
  icon: MessageSquareText,
  title: "Feedback",
};

/**
 * Fixed mobile bottom tabs (UIA-005): the daily marking destination is a
 * primary tab, and the per-subject analytics page moves under "More" so the
 * tab named "Mark Attendance" is exactly the action it promises (no
 * competing Attendance items, no duplicate links).
 */
const MOBILE_TAB_HREFS = ["/dashboard", "/tools/laboratory", "/history"];

/**
 * Destinations surfaced under "More" — the mobile bottom sheet and the
 * md–lg desktop dropdown. Order defines display order in both.
 */
const MORE_HREFS = [
  "/subjects",
  "/laboratory",
  "/tools/quiz-schedule",
  "/calendar",
  "/tools/events",
];

export function navItemsForRole(role?: string): NavItem[] {
  return role === "ADMIN" ? [...NAV_ITEMS, ADMIN_NAV_ITEM] : NAV_ITEMS;
}

/** Mobile bottom-bar tabs in display order. */
export function mobileTabItems(role?: string): NavItem[] {
  const items = navItemsForRole(role);
  return MOBILE_TAB_HREFS.map((href) => items.find((i) => i.href === href)).filter(
    (item): item is NavItem => Boolean(item)
  );
}

/** "More" destinations in display order (admin Feedback appended for admins). */
export function moreItemsForRole(role?: string): NavItem[] {
  const items = navItemsForRole(role);
  const secondary = MORE_HREFS.map((href) =>
    items.find((i) => i.href === href)
  ).filter((item): item is NavItem => Boolean(item));
  return role === "ADMIN" ? [...secondary, ADMIN_NAV_ITEM] : secondary;
}
