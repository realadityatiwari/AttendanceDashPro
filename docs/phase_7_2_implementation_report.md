# Phase 7.2 — Quiz Eligibility Analytics Refinement

Implementation report (2026-08-15). Authorized scope: investigate and resolve the
four Phase 7.0 candidates (Q-D6 raw-range counting, Q-D8 attendance
denominator/pending treatment, Q-D7 mutation timing/eligibility conflict,
date-aware default Quiz tab) on the existing source-of-truth architecture — with
exactly ONE canonical eligibility calculation path, the reference UI frozen, and
full verification discipline.

---

## Phase 7.2 RESULT

**PASS** — 26/26 Phase 7.2 verification checks; frozen regression 6.5 (23/23),
6.6 (36/36), 6.7 (31/31), and 7.1 (26/26) all green; static gates green
(compileall, tsc --noEmit, ESLint, production build). No old assertion was
weakened; no Phase 6 frozen behavior changed.

---

## 1. Q-D6 — RAW-RANGE COUNTING: DECISION = NOT A DEFECT (documented + regression-proven)

**The question:** the legacy engine enumerated *effective teaching dates* in the
window and counted each subject's effective schedule per day; the backend counts
*raw non-cancelled sessions* in `[window_start, window_end]`
(`attendance_repo.get_subject_counts_between`). Can a raw date-range query count
sessions the canonical attendance/eligibility semantics would exclude?

**Trace (proven against the live DB):**
- `expand_baseline.py` materializes sessions **only on engine teaching days**
  (`if not day_info.is_teaching_day: continue`).
- The `EventSessionSynchronizer` (`event_session_service._desired_schedule`)
  returns an empty schedule on any non-working day: closures → every scheduled
  session on the date becomes `is_cancelled=True`; extras/SURPRISE_QUIZ are only
  materialized on working days; weekend projections are deleted when reverted.
- `get_subject_counts_between` (and `get_subject_counts_up_to_date`) exclude
  `is_cancelled` sessions (Phase 6.6 counting correction, frozen).
- `get_academic_day` sets `is_teaching_day = is_working_day`, so the session
  table is exactly the teaching-day-resolved effective schedule.

**Conclusion:** the raw-range query over non-cancelled sessions **is** the
teaching-day-resolved enumeration. Every counted session lies on an engine
teaching day; closures cancel (excluded); extras exist only on working days and
are genuine classes that must be counted. Switching the counts to a separate
teaching-day enumeration would create a *second* calendar-semantics model — the
exact duplicate-math the architecture forbids. The `teaching_days` figure in
`get_attendance_window` remains informational (not surfaced); it stays unused by
design.

**Implementation:** none to the counting path (unchanged). Regression coverage
added to `verify_phase_7_2.py`:
- check 1: for all 18 theory subject/cycle combos, every counted session lies on
  an engine teaching day and totals equal a teaching-day-resolved enumeration;
- check 2: a closure event cancels its day's sessions → excluded from the window
  (−1 lecture for BCS-054 Q3) and the cancelled day rejects attendance (409);
- check 3: an EXTRA_LECTURE on a working day materializes exactly one `is_extra`
  session and is counted in the window;
- check 4: a SURPRISE_QUIZ on a **non-working day** materializes **zero**
  sessions — the canonical event path cannot create a counted-but-excluded
  session, so raw-range counting can never diverge.

## 2. Q-D8 — OVERALL DENOMINATOR / PENDING: DECISION = RECORDED-ONLY (ERP/legacy), PENDING MADE EXPLICIT

**The question:** overall attendance = 71.43% (recorded-only: attended /
attended+missed) vs 46.51% (pending in denominator). Which is canonical?

**Trace (documented sources):**
- Legacy `computeCurrentOverallAttendance` (`js/attendance-engine.js:506-566`):
  `Σ attended_done / Σ completed` where completed = att + miss, **pending
  excluded** — "ERP overall attendance … Mirrors the SRMCEM / AKTU ERP formula".
- `S4_PRODUCT_SPEC.md §10` (Current vs Forecast): "Current Attendance: strictly
  defined as actual attended classes divided by actual class opportunities
  *that have already occurred*" — the current domain is recorded/conducted;
  forecast (pending-as-attended) is the separate explicit domain.
- Backend parity (Phase 7.0 audit §J): `_build_overall` = attended /
  (attended+missed), pending excluded from the current denominator but always
  counted and surfaced separately. History summary and subject
  current-percentages use the identical formula.
- The 46.51% figure is the *forecast-style* denominator — already modelled
  explicitly as the legacy `computeForecastOverallAttendance` / the subject
  `forecast_*_pct` fields.

**Conclusion:** recorded-only is the authoritative denominator (legacy + ERP +
S4 §10). Pending is **never converted to absent** — it is excluded from the
current denominator only, and is always counted and displayed separately.

**Implementation (treatment made explicit, no second formula):**
- No attendance formula changed anywhere. Dashboard `OverallSection` already
  exposes `attended`/`recorded`/`pending` and the Overall card renders
  "X attended · Y recorded · Z pending" (frozen surface untouched).
- **Quiz eligibility card** (the one surface that showed only attended/total/%):
  added a minimal, muted "· X pending" indicator on the Lecture and Tutorial
  rows so the pending treatment is explicit — the eligibility percentage counts
  every window session in its denominator (pending included, per the frozen
  eligibility formula), and pending is never silently treated as absent.
- Verifier checks 5–9 prove the semantics end-to-end: dashboard overall ==
  recomputed attended/recorded (and explicitly ≠ the pending-inclusive figure);
  history summary identical; subject summary exposes BOTH current (recorded-only)
  and forecast (pending-as-attended); quiz eligibility exposes missed+pending
  separately with attended+missed+pending == total; zero-record student overall
  is `null` (never a fabricated 0%).

## 3. Q-D7 — MUTATION / ELIGIBILITY TIMING: DECISION = B (INTENTIONAL PRODUCT RESTRICTION)

**The question:** the Phase 7.0 audit found the product rule G (students — not
admins — add/remove academic events) conflicts with the frozen Phase 6.5/6.6
admin-only event mutations. Is this (A) a real architectural inconsistency, (B)
an intentional product restriction, or (C) an audit ambiguity?

**Trace (correcting one framing):** *attendance* mutations are **student-scoped**
(authenticated user, enrollment-authorized 403, cancelled-session protected 409,
canonical `attendance_records` upsert) — students mark their own attendance; they
are not admin-only. What is admin-only is *event* mutation (POST/PATCH/DELETE
`/api/v1/events` → `require_admin`), a deliberate, frozen security decision
(backend role enforcement + frontend gating, `tools/events/page.tsx`). The
Phase 7.0 audit itself explicitly stated: "Do NOT change the frozen admin-only
behavior without an explicit decision." No product decision reversing it exists.
Eligibility is computed **read-time** from canonical records: a mutation
propagates to the next eligibility read immediately; window bounds are fixed by
the schedule; quiz-day sessions remain markable normal sessions; the Track UI
clamps navigation to today so future classes are not pre-markable (the API does
not independently gate future dates — documented latent observation, out of
scope, not a defect under the locked spec).

**Conclusion:** **B — intentional product restriction.** Rule G is a future
product capability (student-scoped event suggestions), not an architectural
inconsistency. The mutation path (who can mutate) is orthogonal to the
calculation path (canonical engines), so there is no timing inconsistency.

**Implementation:** none (frozen behavior preserved). Verifier checks 10–12
regression-prove the boundaries: student POST /events → 403; attendance on a
cancelled session → 409; attendance on a non-enrolled/unknown session → 403/404;
and a pending-class mutation propagates to the next eligibility read (lecture
percentage changes exactly as marked).

## 4. DATE-AWARE DEFAULT QUIZ TAB

The Quiz Eligibility page previously hardcoded the default tab to Quiz I. The
canonical schedule (18/18 SCHEDULED + dated) supports a deterministic,
date-aware choice, so the default is now derived from the authoritative schedule
— the frontend never recreates scheduling rules.

- **Backend (canonical source):** new read-only endpoint
  `GET /api/v1/quiz-eligibility/current-cycle` (student-scoped via enrollments).
  `EligibilityService.get_current_quiz_cycle(user_id)` resolves, from
  `quiz_schedules` alone (never invents dates):
  1. the cycle of the **next SCHEDULED quiz at/after today** (`basis:
     "next_upcoming"`); else
  2. the **highest-numbered resolved cycle** (`basis: "latest_resolved"`); else
  3. the documented fallback **Quiz I** with `has_schedule: false`,
     `quiz_date: null`, `basis: "fallback"`.
  This mirrors the dashboard quiz-snapshot pick exactly, so dashboard and page
  agree for the same user/cycle (verified: check 19).
- **Frontend:** `useCurrentQuizCycle()` SWR hook; the page initializes the active
  tab from the backend answer (`activeCycle = manual ?? currentCycle ?? 1`).
  Manual tab selection always wins; tab state is client-only and never mutates
  backend state; unresolved schedules still render UNRESOLVED (no fabricated
  dates — the cards render the backend contract verbatim).
- **Today (2026-08-15):** next upcoming quiz = BNC-501 Quiz I (2026-08-24) →
  default tab stays **Quiz I**; after the last Quiz I date passes it becomes
  Quiz II, then Quiz III, deterministically (verifier checks 13–15 prove all
  transitions, including latest_resolved and the no-schedule fallback, inside
  rollback transactions).

## 5. EXACT ELIGIBILITY CONTRACT AFTER PHASE 7.2

Unchanged from Phase 7.1 (the frozen canonical contract), plus one additive
read-only endpoint:

`GET /api/v1/quiz-eligibility/{subject_code}/{quiz_cycle}` → `EligibilityResult`
- `state` ELIGIBLE / RECOVERABLE / NOT_ELIGIBLE / UNRESOLVED; `is_eligible` =
  currently eligible; `recoverable`; `quiz_date` (None when unresolved);
  `window_start/end` (ADR-010); persisted `lecture_threshold`/`combined_threshold`/
  `required_percentage`; window `lecture`/`tutorial` ClassCounts
  (total/attended/missed/pending), `lecture_pct`/`tutorial_pct`/`average_pct`;
  Criterion I (Lecture %) and Criterion II (Combined average) with
  value/threshold/passed/explanation; `final_criterion` ("Criterion I OR
  Criterion II"); `optimization` (must-attend/safe-skip, byte-identical to the
  attendance engine); `explanation`; `policy_ambiguity_notes`; `subject_name`,
  `category`. Labs → 404 (`subjects.quiz_applicable` authoritative).

`GET /api/v1/quiz-eligibility/current-cycle` → `CurrentQuizCycle` (NEW)
- `quiz_cycle`, `quiz_label`, `quiz_date` (null when none), `has_schedule`,
  `basis` ("next_upcoming" | "latest_resolved" | "fallback").

The architecture remains exactly one path:
`sessions → quiz schedules → academic context/calendar → attendance counts →
eligibility engine → eligibility service → API → React`. No second formula, no
frontend eligibility math, no dashboard-specific math (dashboard code untouched;
its snapshot consumes the same `EligibilityResult`).

## 6. EXACT FILES CHANGED

| Layer | Files |
|---|---|
| Backend (app) | `app/schemas/attendance.py` (`CurrentQuizCycle` added) · `app/services/eligibility_service.py` (`get_current_quiz_cycle`, `UserRepository` injected) · `app/api/v1/endpoints/quiz.py` (`GET /current-cycle`, registered before the dynamic route) |
| Backend (scripts) | `scripts/verify_phase_7_2.py` **NEW** |
| Frontend | `src/types/api.ts` (`CurrentQuizCycle`) · `src/hooks/useApi.ts` (`useCurrentQuizCycle`) · `src/app/(authenticated)/tools/quiz-schedule/page.tsx` (date-aware default tab) · `src/components/quiz/QuizEligibilityCard.tsx` (pending indicator — Q-D8 explicitness; reference visual language otherwise untouched) |
| Docs | `docs/phase_7_2_implementation_report.md` **NEW** · `MASTER_ROADMAP.md` · `implementation_plan.md` · `task.md` · `walkthrough.md` |

**Untouched (hard boundaries):** attendance schema, database architecture, auth,
Firebase boundary, calendar engine semantics, `EventSessionSynchronizer`, event
mutations (admin-only), all engines' mathematics, Phase 6 frozen behavior,
dashboard service/schema (frozen), Phase 1 design system.

## 7. DATABASE MUTATIONS

**None.** All verification data was created inside rollback transactions or via
admin events that were deactivated and hard-deleted by the verifier; the exact
baseline (events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 ·
enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN) ·
max record date 2026-08-14) was asserted after every run. The authoritative
schedule remains 18/18 SCHEDULED and dated, including **BCS-054 Quiz III →
2026-10-23** (verified check 16).

## 8. VERIFICATION RESULTS

- **`verify_phase_7_2.py` — 26/26 PASS:** Q-D6 equivalence (18/18 combos), Q-D6
  closure exclusion + 409, Q-D6 extra counted, Q-D6 weekend-guard zero sessions;
  Q-D8 overall recorded-only + pending exposed (71.43% vs explicitly-not 46.51%),
  history identical, subject current-vs-forecast explicit, eligibility
  missed+pending explicit, zero-record student null; Q-D7 student 403, cancelled
  409, enrollment 403/404, mutation→eligibility immediacy; current-cycle admin
  Quiz I/2026-08-24/next_upcoming, student identical, all four date-aware
  transitions (Quiz I→II→III→latest_resolved→fallback) in rollback; BCS-054 Q3 =
  2026-10-23; UNRESOLVED only-when-genuinely-unresolved; labs 404;
  dashboard-snapshot == recomputed per-subject eligibility (snapshot cycle ==
  current-cycle); Track/History/Eligibility consistency; per-user isolation;
  exact baseline restoration.
- **Frozen regression:** `verify_phase_6_5.py` 23/23 · `verify_phase_6_6.py`
  36/36 · `verify_phase_6_7.py` 31/31 · `verify_phase_7_1.py` 26/26. No old
  assertion weakened (the Phase 6.7 17→18 maintenance from Phase 7.1 remains the
  only deliberate assertion change, previously documented).
- **Static:** `python -m compileall backend/app backend/scripts` clean ·
  `npx tsc --noEmit` clean · ESLint on changed frontend files 0 errors ·
  `next build` exit 0 (14 static routes incl. `/tools/quiz-schedule`).

## 9. UNRESOLVED ISSUES / KNOWN LIMITATIONS

- **Q-D9 (quiz-day attendance without a session)** — unchanged by design:
  attendance is session-based; a quiz day with no scheduled session for a subject
  records nothing. Documented in the Phase 7.0 audit; requires a product
  decision, out of Phase 7.2 scope.
- **Rule G (students add/remove events)** — intentionally NOT implemented
  (decision B); requires an explicit product decision and its own phase.
- The attendance mutation API does not itself reject future-dated sessions (the
  Track UI clamps to today). Documented latent observation; not a defect under
  the locked spec; out of scope.
- Browser/manual testing remains the user's responsibility (per the frozen
  verification policy).

## 10. CAN PHASE 7.2 BE FROZEN?

**Yes.** All four candidate items are resolved with documented decisions, 26/26
verification plus full frozen regression is green, the reference UI is
preserved, the database is at the exact baseline with no residue, and the
canonical single-path architecture is untouched (only additive).

## 11. RECOMMENDED NEXT PHASE

Phase 7.3 (or Phase 8 per the roadmap) — recommended candidate scope, each item
its own phase with its own verifier + full regression:
- **Q-D9** quiz-day attendance semantics (requires a product decision);
- **Rule G** student event-suggestion capability (product/security decision,
  its own freeze review);
- **Phase 8 — Attendance Analytics/Intelligence** (overall/subject analytics,
  forecasting, SAFE/WATCH/AT-RISK/CRITICAL risk states) on the existing canonical
  engines — the natural next roadmap phase.

**HARD STOP — Phase 7.2 complete. Do not start Phase 8 or any unrelated phase.
No commit was made.**
