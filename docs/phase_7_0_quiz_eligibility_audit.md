# Phase 7.0 — Quiz Eligibility & Schedule Reality Audit

**Status:** ✅ AUDIT COMPLETE — PASS (no implementation performed)
**Date:** 2026-08-15
**Mode:** READ-ONLY. No frontend/backend changes, no schema/migrations, no engines/events/API changes, no data seeding or mutation, no browser/E2E. DB access strictly SELECT. In-process engine execution only.
**Actor:** student `9999999999999` (primary), admin `2401220100027` (secondary — owns the only real attendance history).
**Predecessors:** Phases 6.0–6.7 COMPLETE & FROZEN (`4933ef3` = 6.5, `fb0131c` = 6.6; 6.7 verifier uncommitted).

---

## A. Scope & Constraints

1. Audit the **quiz eligibility path** end-to-end: `GET /api/v1/quiz-eligibility/{subject_code}/{quiz_cycle}` → `EligibilityService.get_quiz_eligibility` → `calendar_engine.get_attendance_window` → `attendance_repo.get_subject_counts_between` → `eligibility_engine.evaluate_quiz_eligibility` → `attendance_engine.meets_attendance_target` / `optimize_attendance`.
2. Audit the **schedule reality**: `quiz_schedules` (18 rows; 17 dated SCHEDULED, **BCS-054 Q3 UNRESOLVED**), `quiz_cycles` + `eligibility_policies`, `academic_events` (17 active QUIZ_DAY), `semesters` (V Semester 2026-07-15 → 2026-12-31).
3. Audit the **reference-UI data contract** (subject card: attended/total/% per lecture & tutorial, average %, required %, Criterion I / Criterion II / Final Result, eligible / not-eligible / recoverable, explanation) against what the backend can actually expose.
4. Audit **legacy parity**: `js/quiz-engine.js`, `js/attendance-engine.js`, `js/calendar-engine.js`, `js/ui.js` + docs 05/06/07/15, S4_PRODUCT_SPEC, ADR-010.
5. Compare against the **authoritative product rules (A–I)** provided by the user.
6. Report every discrepancy as **SOURCE A / SOURCE B / Current implementation / Product requirement / Decision required**. Never fix.

**Explicitly NOT done:** any write to the DB, any code change, any schema change, any commit.

---

## B. Dates & Frozen Baselines

- Audit performed against the working tree at commit `fb0131c` (Phase 6.6) + uncommitted `backend/scripts/verify_phase_6_7.py` + 4 tracking docs.
- Phase 6.7 freeze: 90/90 combined checks (23/23 + 36/36 + 31/31), baseline exact: events=17 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 · users=30 (1 ADMIN).
- Baseline re-verified at the start of this audit (see §T).

---

## C. Key References

| Reference | Location |
|---|---|
| Eligibility engine | `backend/app/engines/eligibility_engine.py` |
| Attendance engine | `backend/app/engines/attendance_engine.py` |
| Calendar engine (windows) | `backend/app/engines/calendar_engine.py:123` (`get_attendance_window`) |
| Eligibility service | `backend/app/services/eligibility_service.py` |
| Attendance repo (counts) | `backend/app/repositories/attendance_repo.py:40-71` |
| Quiz repo | `backend/app/repositories/quiz_repo.py` |
| Quiz endpoint | `backend/app/api/v1/endpoints/quiz.py` |
| Quiz models | `backend/app/models/quiz.py` (`ScheduleStatus`, `QuizCycle`, `EligibilityPolicy`, `QuizSchedule`) |
| Eligibility schema | `backend/app/schemas/attendance.py:66-88` |
| Dashboard quiz snapshot | `backend/app/services/dashboard_service.py:287-338` |
| Dashboard overall | `backend/app/services/dashboard_service.py:158-196` |
| Legacy quiz engine | `js/quiz-engine.js` (docs/07) |
| Legacy attendance engine | `js/attendance-engine.js` |
| Legacy calendar engine | `js/calendar-engine.js:674` (`getAttendanceWindow`), `:149` (`getQuizPolicy`) |
| Legacy UI cards | `js/ui.js:600-719` (`buildQuizSubjectCard`, summary card) |
| Product spec | `docs/S4_PRODUCT_SPEC.md:25-33` (eligibility rules incl. Criterion 1 OR Criterion 2) |
| ADR-010 | `docs/18_ARCHITECTURE_DECISION_RECORDS.md:133-139` (quiz windows) |
| Reference timetable | `timetable.json` (6 theory quiz-applicable + 3 lab subjects) |

---

## D. Source-of-Truth Hierarchy (verified)

Authoritative (in order): **timetable/`class_sessions`** (actual classes) → **`quiz_schedules`** (quiz dates/status, via `QuizSchedule.date` + `schedule_status`) → **`semesters`** (commencement via section) → **`eligibility_policies`** (thresholds) → **canonical engines** (`calendar_engine` windows, `attendance_engine` counts/optimization, `eligibility_engine` evaluation) → **API** → **UI**. Nothing is computed in React (verified: quiz UI renders only backend fields; `MASTER_ROADMAP.md:405` "Do not move quiz calculations into React").

---

## E. Audit Result Summary

- **Formula verification (rule B):** PASS — combined rule `(Lecture% + Tutorial%)/2 ≥ threshold`, lecture-only when no tutorials (`attendance_engine.meets_attendance_target`, line 14; legacy `attendance-engine.js` `meetsAttendanceTarget` uses the same average with `Number.EPSILON` tolerance).
- **Practical exclusion (rule C):** PASS — eligibility counts only `L`/`T`; `P` is dropped in `eligibility_service.py:80-83` (and in the engine), while per-subject summary and overall attendance include `P`. 2-hour lab = one session (timetable expansion; no split).
- **Overall attendance (rule D):** PASS with documented semantics — overall = attended/(attended+missed) over **all** session types of enrolled subjects, cancelled excluded, pending excluded from the denominator (`dashboard_service._build_overall:158-196`). The phrase "total events" in rule D therefore means **recorded** events today (ERP-style "conducted"), not all scheduled events. If rule D intends pending-included totals, that is a **decision required**.
- **Quiz-day attendance (rule E):** PASS in current architecture — a QUIZ_DAY is a working day; its normal timetable sessions exist and attendance on them flows into overall (and into the NEXT cycle's window, since window N starts on the previous quiz date). No special quiz-day marker is needed. NOTE: if the quiz day has no scheduled session for that subject, there is **no attendance event at all** (attendance is session-based) — decision required if quiz-day attendance must be recorded regardless of timetable.
- **Surprise quizzes (rule F):** PASS — `SURPRISE_QUIZ` events materialize exactly one `is_extra` session (Phase 6.6/6.7 verified), which flows through the normal attendance pipeline into per-subject and overall counts, and into eligibility windows (counts include `is_extra` sessions; none exist in current data).
- **Student event mutations (rule G):** **DISCREPANCY** — product rule says students — not admins — add/remove events; the frozen Phase 6.5/6.6 system is **admin-only** for all event mutations (backend role enforcement + frontend gating, `tools/events/page.tsx:25-36,148-153`). See §Q-D7.
- **Calendar day detail (rule H):** PASS — calendar read model + daily/history endpoints expose the complete effective schedule (normal/extra/cancelled/events/quizzes) (`calendar_engine`, Phase 6.2/6.6 verified).
- **Never guess (rule I):** PASS — BCS-054 Q3 is surfaced as UNRESOLVED (no invented date); the profile first-quiz lookup requires `SCHEDULED` + non-null date.

**Headline behavioral finding:** with the current eligibility rule, **every resolved cycle of every theory subject reports `is_eligible = True`** for both traced users (because `pending > 0` ⇒ `is_eligible = is_reachable`, and every target is reachable by attending all pending classes) — even for the admin whose current averages are 15–55%. The legacy engine would label all of these "NEEDS ATTENDANCE". This is the #1 decision required (§Q-D1). The dashboard quiz snapshot therefore currently reports 6/6 "Eligible" (0 attention, 0 not-eligible) — misleading under the product definition of "currently meets the threshold".

---

## F. Quiz Cycle & Threshold Reality (DB, SELECT-only)

| Cycle | Label | `lecture_threshold` | `combined_threshold` | Legacy policy (timetable.json) |
|---|---|---|---|---|
| 1 | Quiz1 | **70.0** | 70.0 | 70 (ADR-010: SRMCEM notice 2026-07-14) |
| 2 | Quiz2 | **75.0** | 75.0 | 75 |
| 3 | Quiz3 | **75.0** | 75.0 | 75 |

- Engine fallback (`determine_quiz_threshold`) matches the DB values (70/75/75) — the service then overrides with the DB policy (`eligibility_service.py:58,101-103`). Consistent today.
- **D5:** `combined_threshold` from the DB is never read; the service sets `combined_threshold = lecture_threshold` whenever tutorials exist. If the two ever diverge, the combined criterion silently uses the wrong value.

---

## G. Quiz Schedule Reality (DB, SELECT-only)

- 18 `quiz_schedules` rows: 17 **SCHEDULED with dates** (2026-08-24 … 2026-10-26), 1 **UNRESOLVED (BCS-054 Q3, no date)**.
- All 6 theory subjects have Q1+Q2+Q3 dated except BCS-054 Q3.
- 17 active `academic_events`, **all QUIZ_DAY** (BCS-054 ×2, five others ×3), matching the 17 dated schedules (Phase 6.5 seeding integrity).
- No holiday/break/override events exist in the DB (no authoritative institutional dates — documented gap, Phase 6.5).
- Windows (ADR-010, both engines identical): **Q1** = [semester_start, quiz−1]; **QN>1** = [prev_quiz_date, quiz−1]. E.g. BCS-501 Q1 = [2026-07-15, 2026-08-26], quiz 2026-08-27; Q2 = [2026-08-27, 2026-09-16]. Note QN windows **include the previous quiz day** (sessions on that date count toward the next cycle).
- Commencement = **semester start** (2026-07-15) for every subject (`quiz.py:38-42` → section→semester; legacy uses per-subject `commencementDate`, e.g. BNC-501 2026-07-20). Minor drift, no behavioral impact today (session dates are the real grid).

---

## H. Eligibility Mathematics — Worked Traces (engine-in-process, real data)

Per-subject window counts = real `class_sessions` in [window_start, window_end], `is_cancelled=False`, status joined per user. Cancelled sessions are excluded (Phase 6.6); `P` counted but never used in eligibility; `is_extra` counted when present (0 today).

**Admin `2401220100027` — Quiz I windows (current averages):**

| Subject | Quiz | Window | L tot/att/miss/pend | L% | T tot/att/miss/pend | T% | Avg% | Target | engine is_eligible | deficits (L,T) | legacy verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BNC-501 | I | 07-15→08-23 | 11/3/3/5 | 27.3 | — | — | 27.3 | 70 | **True** | (5,0) | NEEDS ATTENDANCE |
| BCS-501 | I | 07-15→08-26 | 18/10/1/7 | 55.6 | 6/1/0/5 | 16.7 | 36.1 | 70 | **True** | (0,5) | NEEDS ATTENDANCE |
| BCS-502 | I | 07-15→08-30 | 20/9/2/9 | 45.0 | 7/4/1/2 | 57.1 | 51.1 | 70 | **True** | (2,2) | NEEDS ATTENDANCE |
| BCS-503 | I | 07-15→09-02 | 22/10/2/10 | 45.5 | 7/3/0/4 | 42.9 | 44.2 | 70 | **True** | (0,4) | NEEDS ATTENDANCE |
| BCS-054 | I | 07-15→09-06 | 23/8/4/11 | 34.8 | 8/2/2/4 | 25.0 | 29.9 | 70 | **True** | (7,4) | NEEDS ATTENDANCE |
| BCS-058 | I | 07-15→09-10 | 26/4/8/14 | 15.4 | 8/3/1/4 | 37.5 | 26.4 | 70 | **True** | (10,4) | NEEDS ATTENDANCE |

Quiz II/III windows contain only future sessions (0 attended, all pending) → reachable → `is_eligible=True`, deficits (5,3)/(6,3)/(6,4) etc. BCS-054 Q3 → engine placeholder (window=today, `is_eligible=False`, `policy_ambiguity_notes` set).

**Student `9999999999999`:** 0 attendance records; 129 sessions to-date all pending → identical shape (all `is_eligible=True`, all legacy "NEEDS ATTENDANCE").

**Overall (semester → today, rule D):**
- Admin: 129 sessions (0 cancelled, 0 extra), 60 attended / 24 missed / 45 pending → **71.43%** (recorded-only) vs **46.51%** (pending in denominator).
- Student: 0/0/129 → overall undefined (`null`) today.

**Optimizer sanity check (BCS-501 Q1, target 70):** attend all 5 pending tutorials (T=100%) → need L ≥ 40% → 8/18 = 44.4% ⇒ avg (44.4+100)/2 = 72.2 ✓ → optimum (0 L, 5 T), tie-broken to minimize total then minimize lectures — matches legacy `optimizeLive` selection rule.

---

## I. Criterion I / Criterion II

- **Product spec (S4_PRODUCT_SPEC.md:32-33):** "Evaluates routes logically: **(Criterion 1 qualifies) OR (Criterion 2 qualifies) = Eligible**"; exposes Lecture %, Tutorial %, Average %, Required %, Eligibility Status, Qualifying Criterion.
- **Current backend:** single combined criterion — `meets_attendance_target(L, T, target)` = average of L% and T% (or L% alone when no tutorials). There is **no dual-route OR**, and `EligibilityResult` exposes neither per-criterion PASS/FAIL nor a qualifying-criterion label.
- **Current legacy JS:** identical single combined rule (`computeQuizEligibility` → `meetsAttendanceTarget`); the legacy UI card shows Lecture/Tutorial/Average/Required + deficit — it does NOT render "Criterion I/II" either.
- Today the OR-vs-single divergence is theoretical (no subject has a lecture-only pass below the average), but the reference UI mandates Criterion I/II + Final Result, so the evaluation shape must be decided and, if dual-route, implemented. **Decision required (§Q-D3).**

---

## J. Overall Attendance Formula (rule D)

- `_build_overall`: overall% = Σ attended / Σ (attended+missed) over all enrolled subjects' sessions, all class types (L/T/P), cancelled excluded, pending excluded (denominator = "conducted/recorded"). Weekly strip and Today use the same semantics (`_aggregate_range`, `_build_weekly`, `_build_today`).
- Legacy `computeCurrentOverallAttendance` (`attendance-engine.js:518-566`): identical Σ att_done / Σ completed, pending excluded, subjects with zero conducted ignored.
- **Parity confirmed.** Only nuance: "total events" in rule D is interpreted as recorded events; pending events are excluded from both numerator and denominator. If the product wants pending-inclusive overall, that changes `_build_overall` and the legacy contract — decision required.

---

## K. Practical (Lab) Exclusion — Verified

- `eligibility_service.py:80-83`: counts dict contains only `L` and `T` keys; `P1/P2/P` map via `normalize_class_type` to `P` and are dropped before the engine runs.
- `eligibility_engine.py:58-59`: engine reads only `L`/`T` from the counts it is given.
- Lab subjects (BCS-551/552/553) have no quiz schedules → never evaluated.
- Per-subject summary (`compute_subject_stats`) and overall DO include practicals (rule C part 2: practicals count in overall) — confirmed: `attendance_engine.py:97-101` keeps `P`; overall aggregation includes all types.
- 2-hour lab = one attendance event (timetable `P1/P2` = single class per day per week; no duration splitting anywhere). PASS.

---

## L. Quiz-Day Attendance (rule E)

- QUIZ_DAY events are working days with **no session effect** (Phase 6.6/6.7 verified: calendar-only). The day's normal timetable sessions remain; attendance marked on them is a real attendance event for that subject and counts in overall and per-subject percentages.
- Window N starts on the previous quiz date, so that day's sessions also count toward the **next** cycle's eligibility window (ADR-010 boundary semantics, identical in both engines).
- Open nuance: attendance is session-based; a quiz day with no scheduled session for a subject produces no attendance event (no way to record "quiz attended" for overall). Decision required if the product wants quiz-day attendance as an independent event.

---

## M. Surprise Quiz (rule F)

- `SURPRISE_QUIZ` is a subject+class-type event (registry allows L/T); Phase 6.6 synchronizer materializes exactly one `is_extra` session per event; the attendance pipeline treats it like any class (mark → record → counts).
- `is_extra` sessions are included in eligibility window counts (no filter in `get_subject_counts_between`) and in overall — rule F ("surprise quizzes may be any day, representable without a fixed quiz date") is satisfied by the current model. Legacy doc 07 known-limitation #1 ("no surprise quiz handling") is **obsolete** for the backend architecture (Phase 6.6 fixed it at the session layer).
- No SURPRISE_QUIZ events exist in the current data.

---

## N. Event / Calendar Interaction (rules H, I)

- **Window bounds:** driven by `quiz_schedules` dates (authoritative); closure/override events do NOT shift windows. QUIZ_DAY events are calendar-only.
- **Counts vs teaching days (latent):** the backend counts **raw sessions in [window_start, window_end]** (`get_subject_counts_between`), not teaching-day-resolved dates; the engine's `teaching_days` figure is computed but unused (also flagged in `docs/phase_6_0_calendar_events_audit.md:242`). Today this is behaviorally identical to the legacy teaching-day grid because: closures cancel sessions (`is_cancelled` excluded — the legacy equivalent of "no class that day") and no non-closure day-disabling events exist. Any future event type that disables a day without cancelling sessions would diverge. Decision required (§Q-D6).
- **CLASS_CANCELLED:** cancels sessions → excluded from counts (409 on marking) — matches legacy (cancelled classes never counted).
- **Extras (EXTRA_LECTURE/TUTORIAL/PRACTICAL):** materialize one `is_extra` session each → counted in windows and overall (legacy: deltas applied to the day schedule — same effect). Parity.
- **Event mutations are ADMIN-only** (Phase 6.5 frozen) — conflicts with rule G. See §Q-D7.

---

## O. Frontend / Reference-UI Data Contract

Mandated subject card fields (from the reference UI): code, THEORY badge, name, eligibility status, **lecture attended/total/%**, **tutorial attended/total/%** (when tutorials), **average %**, **required %**, expandable "View Calculation" → **Criterion I, Criterion II, each criterion's value, PASS/FAIL, Final Result**, eligible / not-eligible / **recoverable**, meaningful explanation, quiz date, quiz cycle.

**Backend availability today:**

| Field | Available? | Where |
|---|---|---|
| subject code / name / THEORY badge | ✅ | `/subjects` + `category` (theory) |
| eligibility status (boolean) | ✅ | `EligibilityResult.is_eligible` (⚠ semantics per §Q-D1) |
| recoverable label | ❌ | derivable as `is_reachable && !is_eligible` (but today `is_eligible` conflates it) |
| lecture/tutorial attended & total (window-specific) | ❌ | not exposed by `GET /quiz-eligibility/...`; summary endpoint is semester-wide |
| lecture%/tutorial%/average% (window-specific) | ❌ | not exposed (legacy `optResult.lecturePercentage/tutorialPercentage/averagePercentage` have no backend equivalent) |
| required % | ✅ | `lecture_threshold` / `combined_threshold` |
| Criterion I / II values + PASS/FAIL + Final Result | ❌ | not modelled in `EligibilityResult` (`schemas/attendance.py:73-88`) |
| quiz date | ❌ | only `window_start`/`window_end` are returned; quiz date lives in `quiz_schedules` |
| explanation | ❌ | only `policy_ambiguity_notes` (unresolved cycles) |
| must-attend / safe-skip | ✅ | `optimization.lecture_deficit/tutorial_deficit/safe_skip_*` |

**Current UI** (`tools/quiz-schedule/page.tsx` + `SubjectQuizSchedule.tsx`) renders only: per-cycle window range, required %, must-attend/safe-skip, ambiguity notes. The dashboard `QuizSnapshotCard` shows next-quiz date, threshold, and eligible/attention/not-eligible counts (from `dashboard_service._build_quiz_snapshot`). The snapshot's "eligible" bucket is inflated by §Q-D1.

**Gap:** the reference UI cannot be implemented without backend additions (a window-bounded counts/percentages payload + criterion structure) — client-side recomputation is prohibited. This is the **Phase 7 implementation gap** (deferred; do not implement now).

---

## P. Legacy vs Backend Parity Summary

| Aspect | Legacy (JS) | Backend (Python) | Verdict |
|---|---|---|---|
| Window bounds (ADR-010) | `getAttendanceWindow` | `get_attendance_window` | ✅ identical |
| Teaching-day enumeration | `effectiveTeachingDates` grid | raw session range (latent, §N) | ⚠ equivalent today |
| Eligibility rule | avg of L/T (or L) vs target | `meets_attendance_target` | ✅ identical |
| Optimizer | `optimizeLive` exhaustive, tie → fewer lectures | `optimize_attendance` exhaustive, tie → fewer lectures | ✅ identical |
| eligible definition | `reachable && deficits==0` | `is_reachable` (when pending>0) | ❌ **DIVERGES** (§Q-D1) |
| Thresholds | `policies.quiz` 70/75/75 (default 75) | DB policies 70/75/75 | ✅ equal today |
| P exclusion from eligibility | counts L/T only in `getSubjectQuizOptimization` (P tracked but unused) | counts L/T only | ✅ |
| Overall % | Σ att / Σ completed (pending excluded) | Σ att / Σ recorded (pending excluded) | ✅ |
| % definitions | current = att/(att+miss); forecast = (att+pend)/tot | same in `compute_subject_stats` | ✅ |
| Lab subjects | `quizApplicable=false` → N/A card | service hardcodes `quiz_applicable=True` (relies on no schedules) | ⚠ drift (§Q-D4) |
| Surprise quiz | not evaluated (doc 07) | flows as `is_extra` session | ✅ superseded |

---

## Q. Open Questions & Discrepancies (SOURCE A / SOURCE B / implementation / decision)

- **Q-D1 (HEADLINE) — "Eligible" semantics.** SOURCE A (legacy `quiz-engine.js:49` + `docs/07:76`): eligible ⟺ reachable **AND** `lectureDeficit == 0 && tutorialDeficit == 0` (already above target even skipping all pending). SOURCE B (backend `eligibility_engine.py:69-74`): `pending > 0 ⇒ is_eligible = is_reachable`. Product requirement: the reference UI distinguishes **eligible / recoverable / not-eligible**, i.e. "eligible" should mean *currently meets the threshold* and "recoverable" should mean *reachable but not yet*. Current implementation reports `is_eligible=True` for every subject with any pending classes (all of them today) — the dashboard shows 6/6 "Eligible". **Decision required:** adopt legacy semantics (or a tri-state) so "eligible" means currently-qualified.
- **Q-D2 — Data contract for the reference UI.** SOURCE A (user requirement): subject cards expose window lecture/tutorial attended-total-%, average, Criterion I/II, Final Result, recovery state, explanation — from real backend outputs. SOURCE B (`EligibilityResult`): no counts/percentages/criteria/quiz-date fields. Current implementation: UI renders only window/threshold/deficits. **Decision required:** Phase 7 must extend the eligibility API payload (window-bounded counts + percentages + criterion structure + quiz date) — or an alternative single source — before the reference UI can be built.
- **Q-D3 — Criterion I OR Criterion II.** SOURCE A (`S4_PRODUCT_SPEC.md:32-33`): "(Criterion 1 qualifies) OR (Criterion 2 qualifies) = Eligible" with a Qualifying Criterion label. SOURCE B (both engines): a single combined average rule. Current implementation: average-only. **Decision required:** confirm dual-route semantics and what Criterion I/II mean exactly (e.g. I = lecture ≥ threshold, II = average ≥ threshold) so the UI can render per-criterion PASS/FAIL.
- **Q-D4 — quiz_applicable hardcoded.** SOURCE A (timetable.json/legacy): labs are `quizApplicable:false`. SOURCE B (`eligibility_service.py:47`): every subject forced `category="theory", quiz_applicable=True` (DB flag ignored). Current implementation: works only because labs have no schedules. **Decision required:** honor `subjects.quiz_applicable` in the domain subject construction.
- **Q-D5 — combined_threshold unused.** SOURCE A (DB): `eligibility_policies.combined_threshold` = 70/75. SOURCE B (`eligibility_service.py:102-103`): replaced with `lecture_threshold`. Current implementation: `combined_threshold` value never read. **Decision required:** keep both thresholds in the DB authoritative and use them in the (future) dual-criterion evaluation.
- **Q-D6 — Raw-window counting.** SOURCE A (legacy): counts enumerate effective teaching dates (holidays excluded). SOURCE B (`attendance_repo.get_subject_counts_between`): counts all non-cancelled sessions in the raw range. Current implementation: equivalent today (closures cancel sessions; no day-disabling non-closure events exist). **Decision required:** whether counts must be teaching-day-resolved for future event types, and whether `teaching_days` must be surfaced.
- **Q-D7 — Students add/remove events (rule G).** SOURCE A (product rule G): students — NOT admins — must add/remove academic events. SOURCE B (Phase 6.5 frozen + `tools/events/page.tsx` + backend role enforcement): event mutations are **admin-only** (students get 403 and a read-only notice). Current implementation: no student mutation path exists. **Decision required:** does rule G mean (a) students may create student-scoped event suggestions (new capability, future phase), (b) an admin gate is acceptable for now, or (c) the rule should be revisited with the product owner? Do NOT change the frozen admin-only behavior without an explicit decision.
- **Q-D8 — Overall "total events".** SOURCE A (rule D): overall = attended / total events **including** practicals. SOURCE B (both engines): attended / **recorded** events (pending excluded), practicals included in both numerator and denominator sets. **Decision required:** pending-inclusive denominator (46.51% vs 71.43% for the admin today) or recorded-only (current, ERP-style)?
- **Q-D9 — Quiz-day attendance without a session.** SOURCE A (rule E): quiz-day attendance is a real attendance event. SOURCE B (architecture): attendance exists only for `class_sessions`; a quiz day with no session for the subject records nothing. **Decision required:** record quiz-day presence as an event-independent attendance row, or accept session-based semantics?
- **Q-D10 — BCS-054 Q3.** UNRESOLVED (no date, no invention). Profile/dashboard/eligibility all handle it (min over SCHEDULED + non-null date; placeholder result with `policy_ambiguity_notes`). **Action:** Aditya must supply the date; nothing to change in code.

---

## R. Decisions Required (single list, for Aditya)

1. Q-D1 eligibility tri-state semantics (eligible / recoverable / not-eligible).
2. Q-D3 Criterion I/II definitions + OR-route rule + qualifying-criterion label.
3. Q-D2 Phase 7 eligibility API payload extension (window counts/percentages/criteria/quiz date).
4. Q-D4 honor `subjects.quiz_applicable`.
5. Q-D5 make DB `combined_threshold` authoritative.
6. Q-D6 teaching-day-resolved vs raw-range counting.
7. Q-D7 student event-mutation scope (rule G) vs frozen admin-only.
8. Q-D8 overall denominator (recorded vs all scheduled).
9. Q-D9 quiz-day attendance without a session.
10. Q-D10 BCS-054 Q3 date.

---

## S. Phase 7 Implementation Gap (documented, NOT implemented)

- Extend `EligibilityResult` (or add an endpoint) to expose: window-bounded `lecture {total, attended, pct}`, `tutorial {total, attended, pct}`, `average_pct`, `quiz_date`, `criterion I {value, pass}`, `criterion II {value, pass}`, `final_result`, `recoverable`, `explanation`; plus the tri-state status of Q-D1.
- Backend must compute (not React): consistent with the canonical engine chain (summary percentages already exist for semester-wide; window-bounded variants are new).
- Reference UI then renders the contract verbatim (subject cards + expandable "View Calculation").

---

## T. Verification Performed & DB Mutation Status

- **DB mutation status: NONE.** Every query was SELECT. No seeding, no writes, no transactions, no schema DDL. Trace scripts ran from the temp dir (`%TEMP%\opencode`), not the repo.
- Engine execution: in-process, read-only (calendar/attendance/eligibility engines imported and invoked with real data).
- Baseline re-verified: events=17 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quiz_schedules=18 · users=30 (1 ADMIN). Records detail: admin 84 + students 2/1/1/1; no future-dated records; statuses Attended ×64 / Missed ×25. Student `9999999999999`: 0 records.
- Static checks: `py_compile`-clean imports used by trace; frontend greps confirm presentation-only rendering; no hardcoded dates in `app/`.

---

## U. Commits & Working Tree

- Committed: `484484b` (calendar dashboard) → `c8838a9` (SWR hooks) → `c8eabe6` (pyc) → `4933ef3` (6.5) → `fb0131c` (6.6).
- Uncommitted at audit end: `backend/scripts/verify_phase_6_7.py` + 4 tracking docs (MASTER_ROADMAP / implementation_plan / task / walkthrough) — now joined by this audit doc. Recommended commit scope for the next commit: those 5 files + this document. **No commit made by the audit.**

---

## V. Next Steps (when authorized)

1. Obtain decisions Q-D1…Q-D10 from Aditya.
2. Phase 7 (implementation): eligibility payload extension (§S) + reference subject-card UI rendering the backend contract + tri-state status per Q-D1; verifier `verify_phase_7_1.py`; regression + baseline restore.
3. Phase 7.x: student event capability per Q-D7 decision.

---

## Y. HARD STOP

**Audit complete. No implementation was performed and no code was changed or committed.** All discrepancies are reported above for decision; the repository remains at the Phase 6.7 state plus documentation-only updates.
