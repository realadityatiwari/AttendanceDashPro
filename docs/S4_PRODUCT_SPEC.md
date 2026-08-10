# S4.0 Product Specification Freeze

## 1. Product Objective
The objective of Phase S4 is to mature AttendanceDash Pro into a highly polished, production-grade SaaS application. While S3 finalized the core computational engines, S4 focuses on introducing a unified design system and separating key product responsibilities (Overall Attendance vs. Quiz Eligibility vs. Forecast) to ensure a disciplined, unambiguous user experience.

## 2. Visual Direction
The application will adopt a modern, dark SaaS/PWA aesthetic characterized by:
- A restrained blue primary accent.
- Semantic status colors: Green (Safe), Amber (Warning/Caution), Red (Critical/Danger).
- Compact cards with clean information hierarchy.
- Consistent typography, spacing, border radiuses, and borders.
- Precise alignment over a disciplined grid.
- Intentionally distinct layouts for mobile, tablet, and desktop viewports, minimizing visual clutter and relying on expandable details only where useful.

## 3. Dashboard Responsibility
The dashboard serves as the central hub of the application. Its responsibility is to present high-level, actionable summaries, primarily surfacing:
- Today's Daily Attendance state.
- A high-level Hero section summarizing Overall Attendance.
- Quick entry points to deeper analytical views.

## 4. Daily Attendance Responsibility
Daily attendance is a core, first-class workflow.
- It displays today's actual scheduled classes.
- Users can log attendance (Present/Absent) specifically for Lectures, Tutorials, and Practicals/Labs.
- Mutations here must natively connect to the attendance engine, immediately propagating to the overarching dataset, updating current attendance, forecasting, quiz eligibility, history, and cloud persistence.

## 5. Quiz Eligibility Responsibility
Quiz Eligibility is a dedicated product responsibility explicitly separated from overall stats.
- **Title:** "Quiz Eligibility"
- Must present distinct tabs for the 1st, 2nd, and 3rd Quiz.
- Only applicable *theory* subjects are shown; practicals/labs are strictly excluded.
- Evaluates routes logically: (Criterion 1 qualifies) OR (Criterion 2 qualifies) = Eligible.
- Exposes: Lecture %, Tutorial %, Average %, Required Percentage, Eligibility Status, and Qualifying Criterion.

## 6. Overall Attendance Responsibility
Overall Attendance provides a holistic view from the start of the semester (e.g., 15 July 2026) to the current date.
- **Title:** "Overall Attendance" (or "Overall Attendance per subject").
- Includes both theory and practical subjects.
- Displays comprehensive subject-level attendance information (Lecture %, Tutorial %, Practical %, Overall %).
- **Constraint:** This section strictly must NOT contain Quiz Eligibility logic or badges. The dashboard hero derives its data from this overall model.

## 7. History Responsibility
The History section is responsible for providing a chronological, immutable ledger of all attendance mutations. It serves as an audit trail for user activity, distinct from aggregated current/forecast views.

## 8. Academic Events Responsibility
Academic Events represent real-world schedule mutations (P0 product requirement).
- Events apply to an EXACT DATE (past, present, or future) and mutate the actual schedule.
- They are not cosmetic UI labels. A future event resides in the future schedule and dynamically participates in the forecast logic. Past events retroactively affect historical analytics.

## 9. Profile Responsibility
The profile and account configuration will eventually migrate to a dedicated profile menu.
- **Desktop:** Accessible via top navigation (Avatar/Name).
- **Mobile:** Accessible via a compact menu or top area.
- Will house: Profile, Dark Mode, Install App, Send Feedback, Sign Out, and Reset All Data. (Note: Implementation deferred beyond S4.0/S4.1).

## 10. Current vs Forecast Definition
- **Current Attendance:** Strictly defined as actual attended classes divided by actual class opportunities *that have already occurred*. It must never be contaminated with arbitrary future scheduled classes.
- **Forecast Attendance:** Predicts the outcome ("What happens if I attend/miss future scheduled classes?"). Future classes belong strictly to the forecast and do not conflate with current attendance.

## 11. Quiz Eligibility Definition
Quiz eligibility enforces the authoritative academic rules governing test participation based on current or forecasted attendance trajectories. It requires clear comparison against institutional percentage thresholds without mixing into the generic Overall Attendance dashboard.

## 12. Academic Event Semantics
- **EXTRA LECTURE/TUTORIAL/PRACTICAL:** Injects a real class occurrence into the exact date.
- **SURPRISE QUIZ:** Creates the appropriate event/academic occurrence per existing project semantics.
- **HOLIDAY DECLARED:** Invalidates/removes attendance opportunities for the affected day. It does NOT convert scheduled classes into absences.
- **CANCELLED LECTURE/TUTORIAL/LAB:** Cancels only the specifically affected class type occurrence.

## 13. Responsive Principles
Mobile design is intentionally uncoupled from the desktop UI to avoid the "shrunken desktop" trap.
- **Mobile (360px - 412px):** Optimized for thumb reach, utilizes bottom navigation, prioritizes vertical stacking.
- **Tablet (768px - 1024px):** Transitional layouts leveraging split views or dense grid packing.
- **Desktop (1280px - 1920px):** Top navigation, expansive data tables, side-by-side analytical cards.
- **Rules:** No horizontal overflow, no clipped content, adequate touch target sizing.

## 14. Visual Consistency Requirements
Every component must adhere to a strict, cohesive design system governing:
- Scale (Typography, Spacing).
- Color variables (Primary, Semantic Status, Surface, Text).
- Component dimensions (Border radii, Button sizing, Card padding).
- Interactive states (Hover, Focus, Active).
- No arbitrary, one-off inline styling is permitted.

## 15. Acceptance Criteria
- UI precisely adheres to the defined dark SaaS/PWA visual language.
- "Quiz Eligibility" and "Overall Attendance" are definitively separated in the interface and backend querying.
- Daily attendance successfully updates all unified state hooks without desynchronization.
- Academic events manipulate the schedule without corrupting historical baselines.
- The UI gracefully scales across the defined viewport breakpoints.
