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

// ---------------------------------------------------------------------------
// 25.UX-1: canonical state surfaces. The audited student surfaces must keep
// consuming the semantic token system and the canonical status/date layers —
// the raw-palette and duplicated-map bypasses may not quietly reappear.
// ---------------------------------------------------------------------------

const UX1_TOKEN_FILES = [
  "components/shared/ErrorState.tsx",
  "app/(authenticated)/calendar/page.tsx",
  "app/(authenticated)/tools/events/page.tsx",
  "app/(authenticated)/laboratory/page.tsx",
  "app/(authenticated)/history/page.tsx",
  "components/notifications/NotificationBell.tsx",
  "components/dashboard/SubjectAttendanceCard.tsx",
];

describe("25.UX-1: semantic tokens on the audited error/status surfaces", () => {
  it("uses no raw red/emerald/amber palette classes in the migrated files", () => {
    const offenders = UX1_TOKEN_FILES.filter((rel) =>
      /(bg|border|text)-(red|emerald|amber)-/.test(read(rel))
    );
    expect(offenders).toEqual([]);
  });

  it("uses no hardcoded white on token surfaces (bell badge, switch thumbs)", () => {
    expect(read("components/notifications/NotificationBell.tsx")).not.toMatch(
      /text-white\b/
    );
    expect(read("components/shell/SettingsModal.tsx")).not.toMatch(/bg-white\b/);
  });

  it("removes the EventRow h-7 touch-target override (UIA-030 floor)", () => {
    // Scoped to className usage so explanatory comments never trip it.
    expect(read("components/events/EventRow.tsx")).not.toMatch(
      /className="[^"]*\bh-7\b/
    );
  });

  it("keeps the laboratory experiment status text visible on mobile", () => {
    const lab = read("app/(authenticated)/laboratory/page.tsx");
    expect(lab).not.toMatch(/hidden sm:inline">\{statusText\}/);
  });

  it("sources subject-health labels from the canonical vocabulary", () => {
    const card = read("components/dashboard/SubjectAttendanceCard.tsx");
    expect(card).toContain("attendanceStatusLabel");
    expect(card).not.toMatch(/label:\s*"Watch"/);
  });

  it("keeps the dashboard classTypeLabel delegated to the canonical module", () => {
    expect(read("components/dashboard/home/status.ts")).not.toContain(
      "export function classTypeLabel"
    );
  });

  it("renders no raw YYYY-MM-DD laboratory dates to students", () => {
    const lab = read("app/(authenticated)/laboratory/page.tsx");
    expect(lab).not.toMatch(/\{item\.date\}/);
    // Ban only *unformatted* renders (bare value or ?? fallback); the fixed
    // ternary routes the value through formatDateMedium and is legitimate.
    expect(lab).not.toMatch(/\{ms\.session_date\s*(\?\?|\})/);
  });

  it("has no formatter-output string surgery in student surfaces", () => {
    expect(read("app/(authenticated)/calendar/page.tsx")).not.toMatch(
      /formatLongDate\([^)]*\)\.replace/
    );
    for (const rel of [
      "app/(authenticated)/history/page.tsx",
      "components/events/EventRow.tsx",
      "components/dashboard/home/UpcomingEventsCard.tsx",
    ]) {
      expect(read(rel)).not.toMatch(/formatShortDate\([^)]*\)\.split/);
    }
  });

  it("has no Intl.DateTimeFormat month formatters outside lib/date", () => {
    for (const rel of [
      "app/(authenticated)/calendar/page.tsx",
      "components/calendar/CalendarGrid.tsx",
    ]) {
      expect(read(rel)).not.toContain("Intl.DateTimeFormat");
    }
  });
});

// ---------------------------------------------------------------------------
// 25.UX-2: shared micro-UI primitives. The consolidated micro-typography,
// micro-badge, and segmented-control patterns may not quietly reappear in
// student-facing sources (admin sources are out of scope for these guards).
// ---------------------------------------------------------------------------

const studentSources = () =>
  sourceFiles
    .map((file) => path.relative(SRC, file).split(path.sep).join("/"))
    .filter((rel) => !/\.test\.(ts|tsx)$/.test(rel))
    .filter((rel) => !rel.includes("admin"));

describe("25.UX-2: micro-UI consolidation", () => {
  it("uses the --text-2xs token instead of arbitrary 11px text in student sources", () => {
    const offenders = studentSources().filter((rel) =>
      read(rel).includes("text-[11px]")
    );
    expect(offenders).toEqual([]);
  });

  it("defines the --text-2xs token in the theme", () => {
    expect(read("app/globals.css")).toMatch(/--text-2xs\s*:/);
  });

  it("encodes micro badges via the Badge xs size, not raw h-4 overrides", () => {
    const offenders = studentSources().filter((rel) =>
      /<Badge[^>]*h-4/.test(read(rel))
    );
    expect(offenders).toEqual([]);
  });

  it("owns segmented-control aria-pressed state in the primitive only", () => {
    for (const rel of [
      "app/(authenticated)/tools/quiz-schedule/page.tsx",
      "app/(authenticated)/laboratory/page.tsx",
      "components/shell/FeedbackModal.tsx",
    ]) {
      expect(read(rel)).not.toContain("aria-pressed");
    }
  });

  it("keeps the SegmentedControl primitive free of domain logic and data imports", () => {
    const primitive = read("components/ui/segmented-control.tsx");
    expect(primitive).not.toMatch(
      /from "@\/(hooks|lib\/api|lib\/canonicalStatus|lib\/date)/
    );
    expect(primitive).not.toMatch(/useSWR|apiFetch/);
  });
});

// ---------------------------------------------------------------------------
// 25.UX-3: global semantic + formatting system. The canonical vocabularies
// (labels, humanizers, elective slots, time display) have ONE home each;
// the audited second names and raw renderings may not reappear.
// ---------------------------------------------------------------------------

describe("25.UX-3: canonical semantic + formatting system", () => {
  it("has one event-type humanizer (the dashboard helper is gone)", () => {
    // Scoped to the export so the migration note in the file never trips it.
    expect(read("components/dashboard/home/status.ts")).not.toMatch(
      /export (function|const) eventTypeLabel/
    );
    expect(read("components/dashboard/home/UpcomingEventsCard.tsx")).toContain(
      "humanizeEventType"
    );
  });

  it("uses the canonical Department Elective register (no Departmental variant)", () => {
    expect(read("components/events/eventRules.ts")).not.toContain(
      "Departmental"
    );
    expect(read("lib/canonicalStatus.ts")).toContain("Department Elective-I");
  });

  it("labels the dashboard quiz middle bucket with the canonical Recoverable", () => {
    const card = read("components/dashboard/home/QuizSnapshotCard.tsx");
    expect(card).toContain("Recoverable");
    expect(card).not.toMatch(/Attention\s*<\/div>/);
  });

  it("renders session times through formatTime, never raw API strings", () => {
    expect(read("components/dashboard/TrackSessionCard.tsx")).toContain(
      "formatTime(session.start_time)"
    );
    expect(read("app/(authenticated)/history/page.tsx")).toContain(
      "formatTime(item.start_time)"
    );
    expect(read("lib/date.ts")).toContain("export function formatTime");
    // No raw "HH:MM:SS" interpolations remain in the audited consumers.
    expect(read("components/dashboard/TrackSessionCard.tsx")).not.toMatch(
      /\$\{session\.(start|end)_time\}/
    );
    expect(read("app/(authenticated)/history/page.tsx")).not.toContain(
      "${item.start_time}"
    );
  });

  it("renders quiz thresholds through the canonical percent formatter", () => {
    expect(read("components/quiz/QuizEligibilityCard.tsx")).not.toMatch(
      /toFixed\(0\)\}%/
    );
    expect(read("components/dashboard/home/QuizSnapshotCard.tsx")).not.toMatch(
      /Math\.round\(quiz\.threshold\)/
    );
    expect(read("components/dashboard/home/WeeklyAttendanceCard.tsx")).not.toMatch(
      /Math\.round\(pct\)/
    );
  });

  it("derives Track and History class-type badges from the canonical label", () => {
    expect(read("components/dashboard/TrackSessionCard.tsx")).not.toMatch(
      /ClassType\.LECTURE \? "LECTURE"/
    );
    expect(read("app/(authenticated)/history/page.tsx")).not.toMatch(
      /ClassType\.LECTURE \? "LECTURE"/
    );
  });
});

// ---------------------------------------------------------------------------
// 25.UX-6: responsive pass. jsdom cannot measure CSS, so — like the other
// guards here — these assert the source-level responsive decisions: the
// fixed-width mobile columns that clipped at touch widths, the wrap fallback
// for the one long-content truncate, and the notification action row.
// ---------------------------------------------------------------------------

describe("25.UX-6: responsive touch-width guards", () => {
  it("keeps the weekly attendance row columns fluid below sm", () => {
    const card = read("components/dashboard/home/WeeklyAttendanceCard.tsx");
    // The three fixed mobile columns that left ~64px of progress bar at
    // 360px are fluid at touch widths; sm+ keeps the desktop widths.
    expect(card).toContain('w-12 shrink-0 text-xs font-medium text-foreground sm:w-16');
    expect(card).toContain('w-10 shrink-0 text-right text-xs tabular-nums');
    expect(card).toContain('min-w-0 text-right text-xs tabular-nums');
    expect(card).not.toMatch(/className="w-24 shrink-0/);
  });

  it("uses the 2-column mobile stat strip on the history summary", () => {
    const page = read("app/(authenticated)/history/page.tsx");
    // Five aggregates stacked 3-over-2 at touch widths; 2-col matches the
    // dashboard QuizSnapshotCard mobile pattern. Desktop stays 5-col.
    expect(page).toContain("grid grid-cols-2 sm:grid-cols-5 gap-2");
    expect(page).not.toContain("grid grid-cols-3 sm:grid-cols-5");
  });

  it("wraps the history subject name on mobile and keeps a title fallback for the desktop truncate", () => {
    const page = read("app/(authenticated)/history/page.tsx");
    expect(page).toContain('sm:max-w-md sm:truncate min-w-0" title={item.subject_name}');
  });

  it("gives notification row actions a dedicated touch-width row with ≥8px target gaps", () => {
    const center = read("components/notifications/NotificationCenter.tsx");
    // Touch: actions row below content with 8px gaps; sm+: corner layout.
    expect(center).toContain("flex flex-col gap-2.5 sm:flex-row sm:items-start sm:gap-3");
    expect(center).toContain("gap-2 sm:items-start sm:gap-1");
  });

  it("keeps shell field values wrapping instead of squeezing their labels", () => {
    const shell = read("components/shell/ShellDialog.tsx");
    expect(shell).toContain("min-w-0 break-words text-right text-sm font-medium");
  });

  it("extends the event-form radio/checkbox hit areas to the touch floor", () => {
    const form = read("components/events/EventFormDialog.tsx");
    // Same before:-inset extension pattern as the Settings switches.
    expect(form.match(/before:-inset-1\.5 before:content-/g)?.length).toBe(3);
    expect(form).toContain("h-4.5 w-4.5");
  });
});

// ---------------------------------------------------------------------------
// 25.UX-7: accessibility + interaction-quality guards. jsdom cannot measure
// CSS or run a screen reader, so these assert the source-level accessibility
// decisions the same way the responsive guards do: announced error/outcome
// states, programmatically associated form errors, input-purpose autocomplete,
// reliable (non-color-only, non-bare-span) unread state, reduced-motion
// suppression on dialogs/sheets, and scroll padding that keeps focus clear of
// the fixed mobile bottom nav.
// ---------------------------------------------------------------------------

describe("25.UX-7: accessibility & interaction guards", () => {
  it("announces the event form's consolidated validation/server error banner", () => {
    const form = read("components/events/EventFormDialog.tsx");
    expect(form).toContain('role="alert"');
  });

  it("announces both Settings modal failure states and the save status", () => {
    const modal = read("components/shell/SettingsModal.tsx");
    // Preferences load failure + save failure are both direct consequences of
    // opening / acting in the dialog.
    expect(modal.match(/role="alert"/g)?.length).toBe(2);
    expect(modal).toContain('role="status"');
  });

  it("announces the quiz eligibility load failure", () => {
    expect(read("components/quiz/QuizEligibilityCard.tsx")).toContain(
      'role="alert"'
    );
  });

  it("keeps feedback form errors programmatically associated with their controls", () => {
    const modal = read("components/shell/FeedbackModal.tsx");
    // The hint slot below the textarea has one stable id that serves both the
    // character counter and the error, and the textarea references it.
    expect(modal).toContain('aria-describedby="feedback-message-hint"');
    expect(modal.match(/id="feedback-message-hint"/g)?.length).toBe(2);
    expect(modal).toContain('aria-invalid={messageError ? true : undefined}');
    // The type error is linked to the segmented control group.
    expect(modal).toContain('aria-describedby={typeError ? "feedback-type-error" : undefined}');
    // The primitive accepts the association hook.
    expect(read("components/ui/segmented-control.tsx")).toContain(
      '"aria-describedby"?: string;'
    );
  });

  it("gives the feedback modal's success and failure panels real roles", () => {
    const modal = read("components/shell/FeedbackModal.tsx");
    expect(modal).toContain('role="status"');
    expect(modal).toContain('role="alert"');
  });

  it("declares sign-in input purpose via autocomplete (WCAG 1.3.5)", () => {
    const login = read("app/(auth)/login/page.tsx");
    expect(login).toContain('autoComplete="username"');
    expect(login).toContain('autoComplete="current-password"');

    const signup = read("app/(auth)/signup/page.tsx");
    expect(signup).toContain('autoComplete="name"');
    expect(signup).toContain('autoComplete="username"');
    // Both password fields (password + confirm) are account-creation inputs.
    expect(signup.match(/autoComplete="new-password"/g)?.length).toBe(2);
  });

  it("carries the notification unread state as text, not a bare-span aria-label", () => {
    const center = read("components/notifications/NotificationCenter.tsx");
    // A <span> has no implicit role, so aria-label on it is not reliably
    // announced; the sr-only text node is.
    expect(center).toContain('<span className="sr-only">Unread</span>');
    expect(center).not.toContain('aria-label="Unread"');
  });

  it("suppresses dialog and sheet motion under prefers-reduced-motion", () => {
    // tw-animate-css has no built-in reduce handling; the toast already uses
    // motion-reduce:animate-none — the dialog overlay + popup must too.
    const dialog = read("components/ui/dialog.tsx");
    expect(dialog.match(/motion-reduce:animate-none/g)?.length).toBe(2);

    // The sheet animates with CSS transitions instead of animate-in.
    const sheet = read("components/ui/sheet.tsx");
    expect(sheet.match(/motion-reduce:transition-none/g)?.length).toBe(2);
  });

  it("keeps keyboard focus clear of the fixed mobile bottom nav while scrolling", () => {
    const shell = read("components/layout/AppShell.tsx");
    // The scroll container reserves the same 7rem the content padding does;
    // md+ resets it because the nav is md:hidden.
    expect(shell).toContain("scroll-pb-28 md:scroll-pb-0");
  });
});
