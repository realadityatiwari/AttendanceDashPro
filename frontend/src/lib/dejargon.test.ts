import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("UIA-003: Student-facing copy de-jargonization", () => {
  const bannedPatterns = [
    /backend-derived from the canonical attendance pipeline/i,
    /evaluated by the backend/i,
    /the server enforces/i,
    /Phase 1 design tokens/i,
    /the server verifies your selection/i,
    /Not available in the backend data model/i,
    /The backend did not accept the request/i,
    /with an offline shell/i,
  ];

  const studentFacingFiles = [
    "src/app/(authenticated)/laboratory/page.tsx",
    "src/app/(authenticated)/tools/quiz-schedule/page.tsx",
    "src/app/(authenticated)/tools/events/page.tsx",
    "src/app/(auth)/signup/page.tsx",
    "src/components/shell/AppearanceModal.tsx",
    "src/components/shell/ShellDialog.tsx",
    "src/components/shell/SettingsModal.tsx",
    "src/components/shell/FeedbackModal.tsx",
    "src/components/shell/InstallAppModal.tsx",
    "src/components/events/EventFormDialog.tsx",
    "src/components/shared/ErrorState.tsx",
  ];

  studentFacingFiles.forEach((fileRelPath) => {
    it(`ensures ${fileRelPath} contains no banned internal engineering jargon in JSX`, () => {
      const fullPath = path.resolve(__dirname, "..", "..", fileRelPath);
      const content = fs.readFileSync(fullPath, "utf-8");
      // Collapse whitespace (including CRLF + JSX line wrapping) so banned
      // phrases are caught even when they are broken across source lines.
      const normalized = content.replace(/\s+/g, " ");

      for (const pattern of bannedPatterns) {
        expect(normalized).not.toMatch(pattern);
      }
    });
  });
});
