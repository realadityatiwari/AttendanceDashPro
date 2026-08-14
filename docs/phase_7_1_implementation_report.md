# Phase 7.1 — Canonical Quiz Eligibility Contract + Reference Subject Cards

Implementation report (2026-08-15). Authorized scope: implement the production quiz
eligibility experience on the existing canonical architecture — complete quiz
schedule, truthful eligibility states (ELIGIBLE / RECOVERABLE / NOT_ELIGIBLE /
UNRESOLVED), the official "(Criterion I) OR (Criterion II)" policy, an extended
eligibility API (no parallel system), and reference subject cards in React
(presentation-only, existing dark design system).

---

## Phase 7.1 RESULT

**PASS** — 26/26 Phase 7.1 verification checks; frozen regression 6.5 (23/23),
6.6 (36/36), 6.7 (31/31) all green; static gates green (compileall, tsc, ESLint,
production build). One deliberate, documented maintenance to the frozen Phase 6.7
verifier: its four hardcoded authoritative-count assertions were advanced from 17
to 18 because the canonical quiz schedule now genuinely contains 18 scheduled
quizzes (BCS-054 Q3 resolved). The assertion strength is unchanged.

## QUIZ SCHEDULE

- **BCS-054 Quiz III resolved** to its authoritative date **2026-10-23** from
  `timetable.json` (the institutional timetable the seed pipeline itself uses).
  The hardcoded "officially unresolved" override was removed from
  `seed_academic_baseline.py`, so fresh reseeds derive the date correctly.
- Live DB: the single `quiz_schedules` row was updated (date 2026-10-23,
  SCHEDULED) and the canonical `seed_academic_events.py` created the matching
  18th QUIZ_DAY academic event (calendar/read-only, zero session mutation).
- Complete canonical schedule now = 18 dated SCHEDULED rows — all 6 theory
  subjects × 3 cycles, exactly matching `timetable.json` (verified check 1/2/3).
- Labs (BCS-551/552/553) have no quiz schedules and remain excluded.
- BCS-054 Q1/Q2 windows are **unchanged** by the resolution (verified checks 7/8);
  Q3 now yields a real window [2026-09-28 … 2026-10-22] (check 9).

## ELIGIBILITY CONTRACT

The existing endpoint `GET /api/v1/quiz-eligibility/{subject_code}/{cycle}` now
returns the canonical contract (schemas/attendance.py — extended additively,
backward-compatible; no parallel system):

- **State** (`state`): `ELIGIBLE` — current attendance satisfies the policy;
  `RECOVERABLE` — below the requirement now but reachable via the remaining
  pending classes; `NOT_ELIGIBLE` — the requirement cannot be reached within the
  window; `UNRESOLVED` — only emitted when no confirmed quiz date exists (no
  fabricated results).
- **`is_eligible`** redefined to `state == ELIGIBLE` (fixes audit finding Q-D1:
  reachability ≠ eligibility). The dashboard quiz snapshot picks this up
  automatically with **zero dashboard changes** (Phase 6 freeze respected).
- **Criteria** per `S4_PRODUCT_SPEC.md:32-33` — `(Criterion I qualifies) OR
  (Criterion II qualifies) = Eligible`:
  - Criterion I — Lecture attendance % vs required %.
  - Criterion II — Combined (Lecture + Tutorial) average vs required %
    (collapses to lecture % for subjects without tutorials, e.g. BNC-501).
  - Final result: `combination: "Criterion I OR Criterion II"` + PASS/FAIL +
    explanation.
- **Thresholds** now come from the persisted `eligibility_policies` for **both**
  routes (lecture + combined — fixes Q-D5); engine 70/75/75 remains the fallback.
- **UI analytics** (fixes Q-D2): `subject_name`, `category`, `quiz_date`,
  `window_start/end`, `lecture`/`tutorial` counts (`total/attended/missed/pending`),
  `lecture_pct`, `tutorial_pct`, `average_pct`, `required_percentage`,
  `recoverable`, `explanation`, criteria structure — all computed by the engines.
- **Practical exclusion** (fixes Q-D4): `subjects.quiz_applicable` is
  authoritative; lab subjects return 404 (checks 4/21).
- **Optimization** unchanged: `lecture_deficit/tutorial_deficit/safe_skip_*/is_reachable`
  remain exactly the attendance engine's optimizer output (check 19).
- **State derivation** reuses the existing engine's counts/formulas at two
  scenarios (current = pending-not-yet-attended; best case = pending all attended).
  It adds no second mathematical model.

## REFERENCE UI

`/tools/quiz-schedule` (retitled **Quiz Eligibility**) now implements the
reference subject-card design per S4 §5:

- **Cycle tabs** (Quiz I / II / III) — distinct tabs per the spec, defaulting to
  Quiz I (the next upcoming cycle).
- **Per-subject cards** (one per quiz-applicable subject, selected cycle):
  subject code, **THEORY** badge, subject name, status badge
  (Eligible=green, Recoverable=amber, Not Eligible=red, Unresolved=neutral);
  window + quiz date; Lecture attended/total + % progress; Tutorial row only when
  tutorials exist; Average vs Required; expandable **View Calculation**
  (Criterion I, Criterion II, Final Result, Must Attend / Safe Skip); state
  explanation.
- **No business math in React** — every value is rendered verbatim from the
  backend contract (formatting only).
- **States:** loading skeletons, per-card error + Retry, truthful empty state,
  Unresolved variant renders no fabricated dates/percentages.
- **Design system:** existing dark surfaces, #3B82F6 primary, existing
  Badge/Progress/Button/GlassCard primitives; no gradients/purple; no nav
  redesign (mobile = Phase 12).
- Old `SubjectQuizSchedule.tsx` deleted (replaced; no other importers).

## FILES CHANGED

| Layer | Files |
|---|---|
| Backend (app) | `app/schemas/attendance.py` (EligibilityState, CriterionResult, FinalCriterionResult, EligibilityResult extension) · `app/engines/eligibility_engine.py` (criteria + state + policy_thresholds) · `app/services/eligibility_service.py` (quiz_applicable 404, persisted thresholds, subject_name/category/quiz_date) |
| Backend (scripts) | `scripts/verify_phase_7_1.py` **NEW** · `scripts/seed_academic_baseline.py` (BCS-054 override removed) · `scripts/verify_phase_6_7.py` (count assertions 17→18, maintained not weakened) |
| Frontend | `src/types/api.ts` (EligibilityResult/EligibilityState/CriterionResult) · `src/components/quiz/QuizEligibilityCard.tsx` **NEW** · `src/app/(authenticated)/tools/quiz-schedule/page.tsx` (rebuilt) · `src/components/dashboard/SubjectQuizSchedule.tsx` **DELETED** |
| Docs | `docs/phase_7_1_implementation_report.md` **NEW** · `MASTER_ROADMAP.md` · `implementation_plan.md` · `task.md` · `walkthrough.md` |

## VERIFICATION

- **`verify_phase_7_1.py` — 26/26 PASS.** Complete canonical schedule vs
  timetable.json (1); BCS-054 Q3 resolved (2); cycles present, labs none (3);
  quiz_applicable exclusion (4); QUIZ_DAY calendar-only (5); 18 upcoming events
  (6); BCS-054 Q1/Q2 unchanged + Q3 window (7-9); lecture-only formula (10); L+T
  average formula (11); RECOVERABLE on real data (12); ELIGIBLE all-attended
  rollback (13); NOT_ELIGIBLE all-missed rollback (14); UNRESOLVED removed-date
  rollback (15); Criterion I (16); Criterion II (17); final OR combination (18);
  optimizer parity (19); UI analytics contract (20); labs 404 (21); per-user
  scoping (22); history intact, 89 records, none future-dated (23); quiz-day
  attendance canonical + surprise-quiz exactly-one-extra with byte-identical
  eligibility (24a/24b); exact baseline restoration (25).
- **Frozen regression:** `verify_phase_6_5.py` 23/23 · `verify_phase_6_6.py` 36/36
  · `verify_phase_6_7.py` 31/31 (with maintained 18-count assertions, documented
  in its docstring).
- **Static:** `python -m compileall backend/app backend/scripts` clean ·
  `npx tsc --noEmit` clean · ESLint on changed files 0 errors · `next build`
  exit 0 (14 static routes incl. `/tools/quiz-schedule`).

## DATABASE

- **Mutation (minimal, documented, reversible):** `quiz_schedules` BCS-054 ×
  cycle 3 → `date=2026-10-23`, `schedule_status=SCHEDULED`; then canonical
  `seed_academic_events.py` created the 18th QUIZ_DAY event (2026-10-23,
  BCS-054). No other table touched (no sessions, no attendance, no users,
  no subjects, no enrollments, no events beyond the seeded QUIZ_DAY).
- **New baseline (verified after every verifier run):** academic_events=18 ·
  class_sessions=684 (0 cancelled, 0 extra) · attendance_records=89 ·
  enrollments=18 · subjects=9 · quiz_schedules=18 (18 SCHEDULED) · users=30
  (1 ADMIN).
- **Reversal:** `UPDATE quiz_schedules SET date=NULL, schedule_status='UNRESOLVED'
  WHERE subject_id=<BCS-054 id> AND quiz_cycle_id=<cycle 3 id>;` then delete the
  QUIZ_DAY event for BCS-054 on 2026-10-23 (and restore the seed-script override
  if a fresh reseed must reproduce the old state).
- One-off migration script executed from temp (not committed):
  `resolve_bcs054_q3.py`.

## ARCHITECTURE

- Extends the **existing** eligibility engine additively (the documented
  extension point after the optimizer call, `docs/07_QUIZ_ENGINE.md`); no engine
  rewrite, no second math model. `optimize_attendance`/`meets_attendance_target`/
  `get_attendance_window` untouched.
- API extension is additive and backward-compatible (old fields unchanged;
  `is_eligible` meaning corrected per Q-D1).
- Dashboard service **unchanged** (frozen); its snapshot now truthful via the
  corrected `is_eligible`.
- Freeze boundaries respected: attendance engine, Phase 6 calendar engine +
  event synchronizer + event-session semantics, Track/History/Dashboard calc
  architecture, auth/JWT, schema unrelated to quiz schedule, Firebase, Phase 1
  design system — all untouched. Student event mutations remain admin-only
  (Part 16 of the authorization prompt).

## KNOWN LIMITATIONS

- **Q-D6 (raw-range vs teaching-day counting)** and **Q-D8 (overall
  denominator)**: unchanged, as scoped out of Phase 7.1.
- **Q-D7 (rule G — students add/remove events)** and **Q-D9 (quiz-day
  attendance without a session)**: unchanged by design (Phase 6 authz frozen;
  quiz-day attendance requires a session — canonical, verified).
- Historical one-off scripts (`migrate_extract.py`, `migrate_execute.py`,
  `verify_schema.py`, `expand_baseline.py`) still assert the old BCS-054 Q3
  UNRESOLVED invariant; they are documented as obsolete and were not run.
- The Quiz Eligibility page defaults to the Quiz I tab; it does not auto-select
  a cycle by date (no cycle date list is exposed by a single API call).
- With the schedule now complete, no live UNRESOLVED card exists in the current
  data; the variant renders only if a future cycle is genuinely unresolved.
- Browser/manual testing remains the user's responsibility (per the frozen
  verification policy).

## MANUAL TESTING CHECKLIST

1. Log in as admin `2401220100027` → Dashboard: Quiz Snapshot no longer shows
   6/6 Eligible; subjects needing attendance appear under attention (truthful).
2. Open **Quiz Eligibility** (`/tools/quiz-schedule`): title, policy banner,
   three cycle tabs; Quiz I selected by default.
3. **BCS-501 · Quiz I**: badge "Recoverable" (amber); Lecture 10/18 + 55.6%,
   Tutorial 1/6 + 16.7%, Average 36.1% vs Required 70%; View Calculation →
   Criterion I FAIL, Criterion II FAIL, Final Result NOT ELIGIBLE (Criterion I
   OR Criterion II), Must Attend Lecture 0 / Tutorial 5, Safe Skip Lecture 8 /
   Tutorial 0.
4. Switch **Quiz II / Quiz III** tabs — cards update per cycle (75% required).
5. **BCS-054 · Quiz III**: real window Sep 28 – Oct 22, quiz date Oct 23 2026,
   Recoverable — no more "Unresolved / TBD".
6. **No lab subjects** (BCS-551/552/553) appear anywhere on the page.
7. Log in as student `9999999999999` — all cards Recoverable with 0/… attended
   (no cross-user leakage).
8. Expand/collapse View Calculation on several cards; confirm loading skeletons
   on slow networks and per-card Retry when the backend is stopped.
9. Check `window_start/end`, quiz date, and percentages format correctly on a
   narrow window; verify dark theme contrast of status badges.
10. Verify dashboard still loads correctly (snapshot now shows truthful counts).

## NEXT PHASE

Phase 7.2 candidate scope (NOT started — requires product authorization):
Q-D6 teaching-day counting, Q-D8 overall denominator semantics, Q-D7 student
event-mutation capability (a product/security decision with its own freeze
review), and any further reference-UI polish (e.g., date-aware default cycle).
Any change must be its own phase with its own verifier, regression of 6.5/6.6/6.7
and 7.1, and this report's discipline.

**HARD STOP — Phase 7.1 complete. Do not start Phase 7.2 without explicit
authorization.**