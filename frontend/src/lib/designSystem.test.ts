import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

/**
 * UIA-023/UIA-004/UIA-017 regression coverage at the source level (same
 * pattern as the dejargon guard): the design-system consolidations must not
 * quietly reappear.
 */

const SRC = path.resolve(__dirname, "..");

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name.startsWith(".")) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(entry.name)) out.push(full);
  }
  return out;
}

const sourceFiles = walk(SRC);
const read = (rel: string) => fs.readFileSync(path.join(SRC, rel), "utf-8");

describe("UIA-023: one Card primitive", () => {
  it("removed the GlassCard wrapper", () => {
    expect(fs.existsSync(path.join(SRC, "components/shared/GlassCard.tsx"))).toBe(false);
  });

  it("has no remaining GlassCard imports or usages", () => {
    // Production sources only — this guard file itself names the component.
    const offenders = sourceFiles
      .filter((file) => !/\.test\.(ts|tsx)$/.test(file))
      .filter((file) => fs.readFileSync(file, "utf-8").includes("GlassCard"))
      .map((file) => path.relative(SRC, file));
    expect(offenders).toEqual([]);
  });
});

describe("UIA-004: consolidated formula copy", () => {
  it("declares the formula once in lib/formula.ts", () => {
    const formula = read("lib/formula.ts");
    expect(formula).toContain("POOLED_ATTENDANCE_FORMULA");
    expect(formula).toContain("POOLED_ATTENDANCE_EXPLANATION");
  });

  it("does not repeat the formula on individual subject or quiz cards", () => {
    expect(read("components/dashboard/SubjectAttendanceCard.tsx")).not.toMatch(
      /Combined attendance/
    );
    expect(read("components/quiz/QuizEligibilityCard.tsx")).not.toMatch(
      /Combined attendance =/
    );
    expect(read("components/quiz/QuizEligibilityCard.tsx")).not.toMatch(/Formula:/);
  });
});

describe("UIA-017: quiz error card uses semantic tokens", () => {
  it("contains no raw red palette classes", () => {
    expect(read("components/quiz/QuizEligibilityCard.tsx")).not.toMatch(
      /(bg|border|text)-red-/
    );
  });
});

describe("UIA-033: events explanation appears once", () => {
  it("does not restate the event-types explanation in the manage card", () => {
    // The amber banner carries the explanation; the manage row is the action.
    expect(read("app/(authenticated)/tools/events/page.tsx")).not.toMatch(
      /Add extras, cancellations/
    );
  });
});

describe("UIA-035: calendar class-count wording", () => {
  it("spells out classes instead of the cryptic 'cl.' abbreviation", () => {
    const grid = read("components/calendar/CalendarGrid.tsx");
    expect(grid).not.toMatch(/\bcl\./);
    expect(grid).toContain("classLabel");
  });
});

describe("UIA-039: font-heading token exists", () => {
  it("defines --font-heading so font-heading utilities resolve", () => {
    expect(read("app/globals.css")).toMatch(/--font-heading\s*:/);
  });
});

describe("UIA-029: one profile surface", () => {
  it("removed the duplicate ProfileModal shell dialog", () => {
    expect(fs.existsSync(path.join(SRC, "components/shell/ProfileModal.tsx"))).toBe(false);
  });

  it("has no remaining ProfileModal imports or usages", () => {
    // Imports/renders only — the profile page documents the merge in a
    // comment, which is intentional history, not a live reference.
    const offenders = sourceFiles
      .filter((file) => !/\.test\.(ts|tsx)$/.test(file))
      .filter((file) => /(import[^\n]*ProfileModal|<ProfileModal)/.test(fs.readFileSync(file, "utf-8")))
      .map((file) => path.relative(SRC, file));
    expect(offenders).toEqual([]);
  });

  it("routes the user-menu Profile action to the /profile page", () => {
    expect(read("components/layout/UserMenu.tsx")).toContain('href="/profile"');
  });
});
