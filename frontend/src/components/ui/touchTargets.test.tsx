import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { buttonVariants } from "./button";
import { MENU_ITEM_TOUCH_FLOOR } from "./dropdown-menu";
import { MobileBottomNav } from "@/components/layout/MobileBottomNav";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

vi.mock("@/hooks/useApi", () => ({
  useProfile: () => ({ profile: { role: "STUDENT" } }),
}));

/**
 * UIA-030/UIA-031 regression coverage: the interactive floor is encoded in
 * the shared primitives (40px touch / 32px pointer) and the mobile bottom-nav
 * labels are readable without growing the navigation footprint.
 */
describe("UIA-030: shared touch-target floor", () => {
  const SIZES = ["default", "xs", "sm", "lg", "icon", "icon-xs", "icon-sm", "icon-lg"] as const;

  it("no button size drops below the floor on either input class", () => {
    for (const size of SIZES) {
      const classes = buttonVariants({ size });
      expect(classes).not.toMatch(/sm:(h|size)-(6|7)\b/);
      expect(classes).toMatch(/sm:(h|size)-(8|9)\b/);
      expect(classes).toMatch(/(h|size)-(10|11)\b/);
    }
  });

  it("exports the menu-row floor used by every menu item type", () => {
    expect(MENU_ITEM_TOUCH_FLOOR).toContain("min-h-10");
    expect(MENU_ITEM_TOUCH_FLOOR).toContain("sm:min-h-8");
  });
});

describe("UIA-031: bottom-nav label readability", () => {
  it("uses 12px labels and keeps the tab height", () => {
    render(<MobileBottomNav />);
    const mark = screen.getByRole("link", { name: /mark attendance/i });
    expect(mark.className).toContain("text-xs");
    expect(mark.className).not.toContain("text-[0.65rem]");
    expect(mark.className).toContain("min-h-14");
  });
});
