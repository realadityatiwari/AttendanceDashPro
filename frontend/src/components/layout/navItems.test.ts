import { describe, it, expect } from "vitest";
import {
  NAV_ITEMS,
  mobileTabItems,
  moreItemsForRole,
  navItemsForRole,
} from "./navItems";

describe("UIA-005: Navigation IA & Mobile Attendance", () => {
  it("includes all canonical items in desktop navigation (lg+)", () => {
    const desktopHrefs = NAV_ITEMS.map((item) => item.href);
    expect(desktopHrefs).toContain("/dashboard");
    expect(desktopHrefs).toContain("/tools/laboratory"); // Mark Attendance
    expect(desktopHrefs).toContain("/subjects"); // Attendance
    expect(desktopHrefs).toContain("/history");
    expect(desktopHrefs).toContain("/laboratory");
    expect(desktopHrefs).toContain("/tools/quiz-schedule");
    expect(desktopHrefs).toContain("/calendar");
    expect(desktopHrefs).toContain("/tools/events");
    expect(navItemsForRole("STUDENT").length).toBeGreaterThan(0);
  });

  it("places Mark Attendance in primary mobile tabs as a daily action", () => {
    const tabs = mobileTabItems();
    const tabHrefs = tabs.map((t) => t.href);
    expect(tabHrefs).toEqual(["/dashboard", "/tools/laboratory", "/history"]);

    const markAttendanceTab = tabs.find(
      (t) => t.href === "/tools/laboratory"
    );
    expect(markAttendanceTab).toBeDefined();
    expect(markAttendanceTab?.label).toBe("Mark Attendance");
  });

  it("places subject analytics under More so there are no duplicate or competing attendance items", () => {
    const tabs = mobileTabItems();
    const more = moreItemsForRole();

    const tabHrefs = tabs.map((t) => t.href);
    const moreHrefs = more.map((m) => m.href);

    // /tools/laboratory is in tabs, NOT in More
    expect(tabHrefs).toContain("/tools/laboratory");
    expect(moreHrefs).not.toContain("/tools/laboratory");

    // /subjects is in More, NOT in tabs
    expect(moreHrefs).toContain("/subjects");
    expect(tabHrefs).not.toContain("/subjects");

    // Zero overlap between mobile tabs and More sheet items
    const overlap = tabHrefs.filter((href) => moreHrefs.includes(href));
    expect(overlap).toEqual([]);
  });

  it("appends Feedback item to More items for admin users only", () => {
    const studentMore = moreItemsForRole("STUDENT");
    expect(studentMore.map((i) => i.href)).not.toContain("/tools/feedback");

    const adminMore = moreItemsForRole("ADMIN");
    expect(adminMore.map((i) => i.href)).toContain("/tools/feedback");
  });
});
