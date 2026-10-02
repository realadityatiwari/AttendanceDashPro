import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MobileBottomNav } from "./MobileBottomNav";

let currentPath = "/dashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => currentPath,
}));

vi.mock("@/hooks/useApi", () => ({
  useProfile: () => ({
    profile: { role: "STUDENT" },
  }),
}));

describe("UIA-005: MobileBottomNav component", () => {
  it("renders Mark Attendance in the bottom navigation bar", () => {
    currentPath = "/dashboard";
    render(<MobileBottomNav />);

    const markTab = screen.getByRole("link", { name: /mark attendance/i });
    expect(markTab).toBeInTheDocument();
    expect(markTab).toHaveAttribute("href", "/tools/laboratory");
  });

  it("marks Mark Attendance as active when currentPath is /tools/laboratory", () => {
    currentPath = "/tools/laboratory";
    render(<MobileBottomNav />);

    const markTab = screen.getByRole("link", { name: /mark attendance/i });
    expect(markTab).toHaveAttribute("aria-current", "page");

    const homeTab = screen.getByRole("link", { name: /home/i });
    expect(homeTab).not.toHaveAttribute("aria-current");
  });

  it("highlights the More button when active path is a secondary destination (/subjects)", () => {
    currentPath = "/subjects";
    render(<MobileBottomNav />);

    const moreButton = screen.getByRole("button", { name: /more/i });
    expect(moreButton).toHaveAttribute("aria-current", "true");
  });
});
