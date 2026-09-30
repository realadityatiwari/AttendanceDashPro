# REMEDIATION READINESS REPORT — AttendanceDashPro

**Phase:** 1 — Audit Report Reconciliation + Remediation Readiness
**Type:** READ-ONLY FORENSIC PASS (no code, DB, migration, seed, or config changes; no mutations; SELECT-only probes)
**Date:** 2026-09-29 (Asia/Kolkata)
**Input:** `docs/SYSTEM_FUNCTIONAL_BACKEND_AUDIT_REPORT.md` (system audit, 2026-09-29)
**Verification method:** every HIGH finding and every P0/P1 item re-verified against the current working tree (exact files/functions read); evidence claims re-tested against the live DB via the SELECT-only probe `backend/scripts/audit_ro_reconcile.py`; policy provenance re-traced through the project's own governance documents (`docs/18_ARCHITECTURE_DECISION_RECORDS.md` ADR-010, `docs/S4_PRODUCT_SPEC.md` §5, `docs/phase_7_0_quiz_eligibility_audit.md`, `docs/QUIZ_ELIGIBILITY_QC2_AUDIT_2026-09-09.md`, `docs/QUIZ_ELIGIBILITY_CALCULATION_AUDIT_2026-09-07.md`, `docs/phase_7_1_implementation_report.md`).
**DB state at verification:** alembic head `e2f3a4b5c6d7`; 5 users (one more than the audit snapshot — see §3.6), 452 orphaned ACADEMIC_EVENT notifications (re-confirmed), 18 active QUIZ_DAY events in strictly chronological order per scope, policies 70/75/75.

> **Read this first — the three headline reconciliations:**
>
> 1. **Severity counts reconciled to the inventory:** 0 CRITICAL · **5 HIGH** · **11 MEDIUM** · 8 LOW · 4 POTENTIAL. The executive summary's "13 MEDIUM" is a transcription error (§3.1).
> 2. **H-1 is downgraded from "CONFIRMED defect (HIGH)" to POLICY AMBIGUITY (MEDIUM):** the claim that the academic notice "ties 70% to the first criterion of Cycle I" is not supported by the project's own authoritative record of that notice (ADR-010 records per-cycle thresholds 70/75/75 with no per-criterion distinction). The two-criteria construct itself is a documented, owner-frozen product decision (S4 §5, Phase 7.3, commit `ed6c3e2`). What remains real: the per-criterion *formula* and the *window boundary* are interpretations of an external notice whose text is not in the repo, and the activity-relaxation framework is unmodeled. An owner decision list is provided (§9); the external notice text should be committed to the repo to close the provenance gap.
> 3. **M-6's "live-proven" evidence is retracted:** the probe shows user `7777777777777` (BCS-052/055 chooser) receives `first_quiz_date = 2026-08-24`, not None — their compulsory quiz subjects (BNC-501 08-24, BCS-501/502/503) carry earlier dates than every elective date, so the slot-unaware join still finds a date. The mechanism (slot-unaware join) is real and remains a genuine latent gap, but it is **not currently user-visible** with this dataset and is downgraded to a LOW latent-risk item with a corrected proof obligation.

---

## 1. Executive Summary

The system audit's architecture-level conclusions survive re-verification fully: one canonical elective resolver, one pooled attendance/eligibility math core, expected-timetable vs actual-occurrence separation, DB-authoritative RBAC, and atomic mutation chains are all real. No CRITICAL defect exists.

Of the five HIGH findings, re-verification confirms four as genuine defects/gaps with exact code evidence (H-2, H-3, H-4, H-5), **reclassifies H-1 as a policy ambiguity** (its central evidence claim — the notice's per-criterion reading — is not supported by the project's own ADR-010 record), and confirms H-6 as a real but **configuration-path-specific latent risk** that belongs in the inventory at MEDIUM/LOW severity (it was discussed in the audit's §R/§W but never inventoried — reconciled here as **H-6/L-9**).

One MEDIUM finding (M-6) had false live evidence; its mechanism stands but is downgraded to LOW latent risk. The remainder of the MEDIUM/LOW inventory re-verified as stated, with two cosmetic corrections noted (§3.5).

Implementation readiness: **P0 items H-2, H-4(1)(2)(3), H-5 are implementable immediately** (no policy input required, no DB schema change strictly required for the core fixes). **H-1 and H-3 are blocked on owner decisions** (documented, with options and consequences, in §9). The P1 invariant-hardening item (M-2/M-3) requires a guarded migration and should follow a decision on H-3 so the history semantics are settled before constraints harden the model.

## 2. Audit Scope

Re-verified in this pass (read-only):

- `backend/app/api/dependencies/deps.py` (get_current_user — H-2)
- `backend/app/services/refresh_token_service.py` (rotate — H-2 refresh path)
- `backend/app/api/v1/endpoints/auth.py` (login deactivation check, registration — H-2, L-2)
- `backend/app/engines/eligibility_engine.py` (threshold selection, `_evaluate_criterion`, `_combined_pct` dead code — H-1)
- `backend/app/repositories/quiz_repo.py` (`get_effective_quiz_dates_for_subjects._rank` — H-5, M-6)
- `backend/app/services/admin_quiz_service.py` (`update_quiz_schedule` validation — H-5)
- `backend/app/services/admin_student_service.py` (`correct_elective`, `set_student_status` — H-3, H-2, L-4)
- `backend/app/services/notification_service.py` + `notification_repo.py` (emit fan-out, `get_inbox` unbounded, sweep unscheduled — H-4)
- `backend/app/repositories/user_repo.py` + `backend/app/services/student_context_service.py` (`get_academic_context`, `_load_first_quiz_date` — M-6)
- `backend/app/core/config.py` (production guard, cookie settings — H-6), `docker-compose.prod.yml` (Caddy port 80 — H-6)
- `backend/app/services/admin_dashboard_service.py`, `admin_dashboard_repo.py`, `api/v1/endpoints/attendance.py`, `api/v1/endpoints/quiz.py` (M-1 clock sites)
- Governance docs for H-1 provenance (listed above); `timetable.json` (policies block)
- Live DB via `backend/scripts/audit_ro_reconcile.py` (9 SELECT-only probes: user/choice state, first_quiz_date replication + slot-resolved variant, event chronology, policies, notification integrity by kind and by user)

Not re-verified in depth (accepted from the system audit with spot checks): P2/P3 items (performance shapes, dead-code list, mojibake), the frontend contract details, and the admin N+1 list. None of these affect the P0/P1 remediation order.

## 3. Previous Report Reconciliation

### 3.1 A — Severity count mismatch

| Source | Count |
|---|---|
| §A Executive Summary | "5 HIGH and 13 MEDIUM" |
| §V Issue Inventory (authoritative) | 5 HIGH · 11 MEDIUM · 8 LOW · 4 POTENTIAL, with the explicit note: "(H-4's CLASS_REMINDER sub-gap counted within H-4; relaxation-framework absence counted within H-1)" |

**Reconciled:** the inventory is authoritative; the executive summary's "13 MEDIUM" is a transcription error. The two statements were reconciling different scopes (exec summary counted the CLASS_REMINDER and relaxation sub-gaps as separate items; the inventory deliberately bundles them). **Corrected counts: 0 CRITICAL · 5 HIGH · 11 MEDIUM · 8 LOW confirmed/likely + 4 POTENTIAL.** This report's final matrix (§10) preserves every finding.

### 3.2 B — H-6 inconsistency

H-6 (prod docker-compose/Caddy serves HTTP-only while `REFRESH_COOKIE_SECURE=True` + `SameSite=None` are mandatory) appears in the audit's §R and §W item 11 but never in the §V inventory. Re-verified facts:

- `docker-compose.prod.yml` caddy service exposes only port 80 with the comment "HTTP only in Phase 18A; TLS provisioned in a later phase."
- `app/core/config.py` production guard: `if not self.REFRESH_COOKIE_SECURE: raise ValueError(...)` — production *requires* Secure cookies, and `REFRESH_COOKIE_SAMESITE="none"` (cross-site Vercel↔Render architecture).
- Browsers reject `Secure` cookies over plain HTTP ⇒ on the compose/Caddy path, the cross-site refresh flow cannot complete until TLS exists. The Render (HTTPS) path is unaffected. No code change is implicated; it is a deployment gate.

**Reconciled:** H-6 is **valid, real, and previously un-inventoried**. Severity: **MEDIUM** (LATENT RISK — it blocks a specific deployment path, not the currently-documented primary Render path; there is no data exposure over the HTTP path because the refresh secret is not transmitted cross-site until a user refreshes, at which point the flow simply fails rather than leaking). It is entered into the final matrix as **H-6 (kept ID, reconciled severity MEDIUM)** with a cross-reference so the inventory gap is closed. It does **not** belong in P0.

### 3.3 C — H-4 scope split

H-4 bundled five distinct problems under one HIGH. Split into independent findings (each verified separately):

| New ID | Content | Status | Severity | Evidence |
|---|---|---|---|---|
| **H-4a** | Orphaned notification projections: 452/452 ACADEMIC_EVENT rows reference deleted (verifier-fixture) events; emitted to real users; deep links dead. | CONFIRMED DEFECT (data pollution) | HIGH | Probe: 452 orphans — owner 182 (all unread), `9999999999999` 182, `8888888888888` 88; all other kinds clean (0 orphans) |
| **H-4b** | Verifier/test-fixture hygiene: cleanup deletes events but not third-party notifications; any future verifier run re-pollutes. | CONFIRMED DEFECT (tooling) | MEDIUM | `after_event_mutation` fan-out design + verifier `finally` patterns (audit §M; mechanism re-read this pass) |
| **H-4c** | No retention policy + unbounded inbox read (`get_inbox` has no LIMIT; service has no cap). | ARCHITECTURE GAP | MEDIUM | `notification_repo.get_inbox` re-read this pass: unbounded select, newest-first only |
| **H-4d** | CLASS_REMINDER generation unreachable in production: builder exists but only the unscheduled callable sweep reaches it; no scheduler exists. | ARCHITECTURE GAP | MEDIUM | `notification_service` re-read: `_class_reminders` called only from `regenerate_user_notifications`; audit confirmed 0 live CLASS_REMINDER rows |
| **H-4e** | Missed-notification loss window: events created+deactivated between sweeps for offline users are never back-filled; no retry channel. | LATENT RISK | LOW | `after_event_mutation` skips `not event.active` |

The P0 backlog entry "H-4 notification orphans + retention" maps to **H-4a + H-4c** (one coherent remediation: purge + read-layer guard + retention/pagination); H-4b is a same-sprint verifier-hygiene task; H-4d is a separate product decision (is a scheduler wanted at all? — see §9 D-5); H-4e is accepted-risk documentation unless a scheduler lands.

### 3.4 D — P0/P1 ordering

The audit's P0 list order (H-4 → H-2 → H-1 → H-5 → H-3) is **not** dependency-optimal. Reconciled order (rationale in §7/§12):

1. H-2 (no dependencies; smallest risk; pure win)
2. H-4a/H-4c + H-4b (data cleanup is needed before invariant/constraint work so probe baselines stay clean)
3. H-5 (independent; changes read-model derivation before any new eligibility policy work)
4. H-1 (BLOCKED on owner decision D-1/D-2 — see §9)
5. H-3 (BLOCKED on owner decision D-3; also gates M-2/M-3 constraint hardening)
6. Then P1 items in the order of §12.

### 3.5 Cosmetic corrections to the audit (no finding changes)

- §D says "4 users"; at verification time the DB holds **5 users** (new `2401220999001` "UI Audit Runner", STUDENT, 9 enrollments, choices 052/055 — canonical). The audit's enrollment count (27 → now 36) and notification-unread figures drift accordingly. All structural conclusions unaffected.
- §D says user `8888888888888` has "ZERO enrollments" and (implicitly) no choices; it now has **2 choices (BCS-052/055) and 0 enrollments** — choices-without-enrollments is itself a mild invariant divergence worth one line in the M-2/M-3 remediation tests (a choice row without an ELECTIVE enrollment must not grant access to any read).
- §V totals line already noted the bundling; this report's matrix de-bundles explicitly (H-4a–e above).

### 3.6 Database drift disclosure

All probe numbers in this report are the live state at verification time (2026-09-29): 5 users / 36 enrollments / 10 choice rows / 452 orphaned ACADEMIC_EVENT notifications / 18 active quiz events / policies 70/75/75 / alembic head `e2f3a4b5c6d7`. Downstream remediation must re-baseline counts before/after any purge.

## 4. Corrected Severity Counts

| Severity | Previous (inventory) | Reconciled | Delta |
|---|---|---|---|
| CRITICAL | 0 | **0** | — |
| HIGH | 5 | **3** (H-2, H-3, H-4a) | H-1 → MEDIUM (policy ambiguity); H-5 → confirmed but effectively MEDIUM-HIGH boundary (kept HIGH, see matrix note) |
| MEDIUM | 11 | **14** (M-1..M-11 + H-1 + H-4b/H-4c + H-6) | +H-1 downgrade; +H-4 split creates 2 MEDIUM; +H-6 enters inventory |
| LOW | 8 | **10** (L-1..L-8 + M-6 downgrade + H-4e) | M-6 → LOW latent; H-4e LOW |
| POTENTIAL | 4 | 4 (P-1..P-4, unchanged) | — |

Totals: **0 CRITICAL · 3 HIGH · 14 MEDIUM · 10 LOW · 4 POTENTIAL** (H-5 retained at HIGH: mechanism CONFIRMED, trigger currently POTENTIAL — no out-of-order dates exist today; the final matrix marks status separately from severity so this is explicit. If the owner prefers severity to track *current* trigger probability, H-5 may be read as MEDIUM without any other change.)

## 5. HIGH Finding Re-verification

### H-1 — Quiz policy conflict → **POLICY/REQUIREMENT AMBIGUITY (MEDIUM)**

**Classification: POLICY AMBIGUITY.** The prior "CONFIRMED defect" classification is retracted.

**What was claimed:** the implementation applies Cycle I's 70% to *both* criteria while the notice "ties 70% to the first criterion of Cycle I."

**What re-verification found:**

- `eligibility_engine.evaluate_quiz_eligibility` (exact site): one `required` value is selected (`policy_thresholds['lecture_threshold']` if present, else `determine_quiz_threshold(quiz_cycle)` — 70/75/75) and passed to **both** `_evaluate_criterion` calls. Mechanism claim: **correct**.
- But the *normative* claim is not supported by the project's own sources:
  - **ADR-010** (`docs/18_ARCHITECTURE_DECISION_RECORDS.md`): "The official SRMCEM Attendance Criteria notice dated 14 July 2026 establishes cumulative but strict windows and varying target percentages **per quiz cycle** (Q1: 70%, Q2/Q3: 75%)." — thresholds are recorded **per cycle**, with **no per-criterion distinction anywhere**.
  - **S4_PRODUCT_SPEC §5** (updated 2026-09-26): "(Criterion 1 qualifies) OR (Criterion 2 qualifies) = Eligible. Both criteria use the pooled L+T count-level formula." The two-criteria construct is a **product decision**, and the S4 text was refreshed the day before the system audit — the owner actively reaffirmed it.
  - **Phase 7.3 freeze** (`QUIZ_ELIGIBILITY_CALCULATION_AUDIT_2026-09-07.md` §3): the Phase-7.1 "Criterion I = Lecture %" design was **superseded 2026-08-18 (commit `ed6c3e2`)**; both criteria = pooled average, differing only in window, is the project's *frozen, documented contract*.
  - **QC2 audit 2026-09-09** re-verified thresholds "ADR-010 explicitly → persisted 70/75/75 ✅" and recorded the two genuine ambiguities: (a) the **per-criterion formula is not specified in any in-repo source** — the notice itself was never committed; (b) the **inclusive previous-quiz-date boundary** is an interpretation with material guidance effects (worked example: exclusive reading would change BCS-501 Q2 Must-Attend from 3L+3T=75.0% to 4L+3T=78.57%).
- Seeded data: `eligibility_policies` = lecture_threshold 70/75/75 **and** combined_threshold 70/75/75 (both columns identical; `combined_threshold` never read by code).

**Conclusion:** the implementation faithfully implements the project's frozen contract; whether that contract faithfully implements the *external* notice is **unverifiable in-repo** because the notice text is not committed. "70% applies to both criteria in Cycle I" is therefore a property of the documented product decision, not a code defect. Residual true gaps, all policy-level:

1. The external notice text is not in the repo (provenance gap — should be committed, redacted of any private data, as `docs/source/notices/` or similar).
2. Per-criterion thresholds (if the notice does distinguish) are unimplementable without a schema/policy change (`combined_threshold` exists unused — the natural vehicle).
3. The activity-participation **relaxation framework** is unmodeled anywhere (this part of the original finding stands unchanged).
4. The inclusive-vs-exclusive previous-quiz-date boundary remains an interpretation (unchanged since 2026-09-07).

**Decision required:** §9 D-1 (threshold semantics), D-2 (boundary interpretation). D-3-adjacent: none. Until decided, **no code may change** — the current behavior is the documented contract.

**Exact code path (for the record):** `evaluate_quiz_eligibility` → `required = policy_thresholds['lecture_threshold']` (or `determine_quiz_threshold(cycle)` fallback 70/75/75) → identical `required` into `criterion_i = _evaluate_criterion(...)` and `criterion_ii = _evaluate_criterion(...)` → `passed = pooled_pct >= required` per criterion → `final_criterion.passed = ci.passed or cii.passed`.

### H-2 — Deactivated user keeps live-token access → **CONFIRMED DEFECT (HIGH)**

- Exact site: `deps.get_current_user` — after the user lookup (`if not user: 401`) there is **no `is_active` check**; the user object is returned regardless.
- Asymmetry confirmed: login blocks deactivated users (auth.py:114-119 → 403 "Account has been deactivated"), and `RefreshTokenService.rotate` blocks them (family revoked, error raised). But any access token issued *before* deactivation authorizes every student endpoint until expiry — `JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 480` (8h default).
- `set_student_status(is_active=False)` exists (admin_student_service) and changes only the flag.
- No token-version/invalidation channel exists in the JWT or DB.

**Verdict: previous report CORRECT.** Remediation is one guard clause; expected behavior: deactivated user with valid token → 401 (or 403) on the next request. No policy input required. (Severity note: blast radius is the student's *own* data — owner-scoped endpoints — plus nothing else; RBAC checks are DB-resolved per request so no privilege escalation is possible. It remains HIGH because deactivation is the account-kill switch and currently has an 8-hour tail.)

### H-3 — Elective correction re-attributes history → **CONFIRMED DEFECT mechanism / latent data (HIGH)**

- Exact site: `AdminStudentService.correct_elective` — swaps `StudentElectiveChoice.subject_id`, deletes the old ELECTIVE enrollment, adds the new one via `build_enrollment(student_id, new_subject, EnrollmentType.ELECTIVE)`; **zero interaction with `attendance_records`**; single `commit()`.
- Read-time attribution (all count queries) keys on the per-user choice join (`coalesce(TT.elective_slot, CS.elective_slot)` → chosen subject): after a correction, every historical mark on shared slot sessions instantly counts toward the **new** subject and vanishes from the old — both in history reads and in every percentage.
- "Immutable historical meaning" (roadmap) is violated by this operation.
- Mitigating live fact: only one choice-set per user exists in the DB; no correction has ever been executed — impact is latent.

**Verdict: previous report CORRECT** (mechanism CONFIRMED by code read this pass). **Decision required before implementation** (§9 D-3): freeze-old-attribution vs explicit re-basing with consent vs accept-and-document. Any fix touches history semantics — highest regression risk of all P0 items.

### H-4 — Notification orphans/pollution → **CONFIRMED DEFECT (HIGH), now split H-4a–e** (see §3.3)

- Exact sites: `NotificationService.after_event_mutation` (fan-out `emit()` per recipient — including real users for verifier-created fixture events), `NotificationRepository.get_inbox` (unbounded), verifier `finally` cleanups (delete events, not third-party notifications).
- Probe re-confirmation (exact numbers): **452 ACADEMIC_EVENT rows, 452 orphaned** (100% of the kind). Owner `2401220100027`: 182 rows/182 orphaned/189 total unread. `9999999999999`: 182/182/188. `8888888888888`: 88/88/88. New user `2401220999001`: 0 (registered post-pollution). All non-event kinds clean (2 QUIZ_APPROACHING, 3 ATTENDANCE_THRESHOLD, 9 MUST_ATTEND, 8 SAFE_SKIP — all live).
- Inbox read is unbounded (no limit/offset) — retention/pagination genuinely absent.

**Verdict: previous report CORRECT on substance; over-bundled.** Split as §3.3. P0 = H-4a (+H-4c). Verifier hygiene H-4b is a same-sprint companion (without it, the next verifier run recreates H-4a).

### H-5 — Quiz-cycle numbering instability → **CONFIRMED mechanism; trigger currently absent (HIGH)**

- Exact site: `QuizRepository.get_effective_quiz_dates_for_subjects._rank` — cycle number = `len(dates) + 1` over events ordered by `(start_date, id)`; `QuizSchedule.cycle`/`quiz_cycle_id` is never consulted at read time. `QuizSchedule` is the admin's plan; the event dates are the runtime authority (Phase 2 design).
- Mutation-side validation gap: `AdminQuizService.update_quiz_schedule` validates only semester bounds (`_validate_date_in_context`); **no cross-cycle ordering check** — an admin may set Q3's date before Q2's within the semester; the change commits and re-derives every read.
- Effect if triggered: eligibility windows, QUIZ_APPROACHING `occurrence_key = str(cycle)`, and dashboard cycle pick all silently rename; `quiz_schedules` labels diverge from reality; existing QUIZ_APPROACHING rows keyed by the old cycle number strand.
- Current data: probe shows **all 6 scopes strictly chronological** (BNC-501 08-24→09-14→10-09; BCS-501 08-27→09-17→10-12; BCS-502/503 similar; ELECTIVE_I 09-07→09-28→10-23; ELECTIVE_II 09-11→10-05→10-26). Positional cycle == schedule cycle everywhere today.

**Verdict: previous report CORRECT on mechanism; trigger is POTENTIAL.** Kept HIGH (systemic rename-on-edit across three surfaces is a bad failure mode; the fix is small), with status CONFIRMED-defect-mechanism / POTENTIAL-trigger. Remediation without policy input: validate date ordering across a subject's cycles at mutation time (and/or rank by schedule cycle with chronological tie-break). Note the second-order effect discovered this pass: QUIZ_APPROACHING occurrence keys are cycle numbers, so a rename also orphans/strands prior notification rows — the fix must account for it.

### H-6 — TLS/cookie deployment gate → **valid, previously un-inventoried (MEDIUM, LATENT RISK)**

Reconciled into the inventory at MEDIUM (analysis in §3.2). Not a code defect; a deployment-path gate with a documented later-phase TLS plan. Enter the matrix; schedule as a P2 deployment item (enable TLS before any HTTP-only production use).

## 6. P0/P1 Re-verification

### P0 items (audit backlog §W.1–5)

| # | Item | Still valid? | Files/functions (exact) | Migration? | Data cleanup? | API change? | Frontend? | Policy approval? | Independent? |
|---|---|---|---|---|---|---|---|---|---|
| 1 | H-4a orphans + H-4c retention | **Yes** (452 confirmed live) | `notification_repo.py` (get_inbox, new purge helper), `notification_service.py`, verifier cleanups | No (purge is DML on projections; retention may need a `created_at` index only) | **Yes** — one-time purge of orphaned rows | No (response shape unchanged; pagination optional/additive) | No | No (purge of dead projections) | Yes |
| 2 | H-2 deactivation guard | **Yes** | `deps.py::get_current_user` | No | No | No (status code only on a previously-successful path) | Optional (401 handling already exists in apiFetch) | No | Yes |
| 3 | H-1 policy reconciliation | **Reclassified** — POLICY AMBIGUITY | `eligibility_engine.py`, `eligibility_service.py`, policies seed, schema for per-criterion thresholds | Only if per-criterion columns chosen (combined_threshold exists) | No | Additive (per-criterion threshold in response) | QuizEligibilityCard already renders per-criterion values | **Yes — D-1/D-2** | Blocked |
| 4 | H-5 cycle-number stability | **Yes** (mechanism; trigger absent) | `admin_quiz_service.py::update_quiz_schedule` (+ create), optionally `quiz_repo._rank` | No | No | No | No | No (order-validation is uncontroversial; *ranking* change is owner-visible — recommend mutation-side validation only) | Yes |
| 5 | H-3 elective-history semantics | **Yes** (latent) | `admin_student_service.py::correct_elective` (+ possibly new re-basing helper) | Possibly (depends on chosen option) | Possibly (re-basing touches history) | No | No | **Yes — D-3** | Blocked; also gates M-2/M-3 |

### P1 items (audit backlog §W.6–9)

| Item | Still valid? | Notes from re-verification |
|---|---|---|
| M-2/M-3 invariant hardening | **Yes** | Read boundary at `user_repo.get_enrolled_subjects` (exact site confirmed — unfiltered join) + DB CHECKs/unique indexes. **Order after H-3 decision** (history semantics affect what the boundary must protect). New test from §3.5: choice-without-enrollment must not read. |
| M-1 clock unification | **Yes** | Sites confirmed this pass: `admin_dashboard_service.py` L45/L186/L225, `admin_dashboard_repo.py` L274/L289, `endpoints/attendance.py` L110, `endpoints/quiz.py` L56. (`eligibility_engine` L166-167 `date.today()` is a placeholder inside an UNRESOLVED return — cosmetic only, note in the fix.) Mechanical, low risk. |
| M-6 first_quiz_date slot resolution | **Mechanism yes; downgrade to LOW latent** | Probe **disproves** the live-evidence claim: `7777777777777` gets `2026-08-24` (compulsory quiz subjects predate electives). The join (`user_repo.get_academic_context`, `student_context_service._load_first_quiz_date`) is genuinely slot-unaware; a visible divergence requires a student whose *earliest* quiz date is elective-only — impossible while compulsory subjects always have earlier dates in this curriculum, but not schema-guaranteed. Fix remains one query swap to the canonical effective-dates helper; verify with a synthetic fixture, not the 777 account. |
| M-11 per-subject commencement | **Yes** | `_build_domain_subject` uses semester start; timetable.json carries per-subject commencementDate (legacy BNC-501 2026-07-20 documented as deliberately unused). Policy-adjacent: equivalent for this dataset (QC2 audit proof); owner sign-off recommended to keep it frozen-or-fixed (fold into D-2 discussion). |

## 7. Cross-Engine Dependencies (dependency graph)

```
FOUNDATION / POLICY (owner decisions — no code)
  D-1 per-criterion thresholds (Cycle I)      → blocks H-1 implementation
  D-2 window-boundary interpretation (+M-11 commencement stance) → blocks H-1 (and optional M-11)
  D-3 elective-history semantics              → blocks H-3, and shapes M-2/M-3 constraint design
  D-5 scheduler existence for CLASS_REMINDER  → blocks H-4d

DOMAIN MODEL / DATABASE
  M-3 guarded migration (CHECKs/uniques/indexes) ← depends on D-3 (what to constrain)
      and benefits from H-4a purge (clean baseline before constraint adds)

BACKEND ENGINE
  H-2 (deps guard)                — independent, first
  H-4a/H-4c purge+retention       — independent; before M-3 (clean baseline)
  H-4b verifier hygiene           — independent; immediately after H-4a (prevents re-pollution)
  H-5 mutation validation         — independent; before any H-1 policy change (stable labels first)
  H-1 per-criterion thresholds    — after D-1/D-2
  H-3 re-basing/freeze            — after D-3
  M-2 read boundary               — after D-3 (and with M-3)
  M-6 query swap                  — independent (LOW; bundle with M-1 batch)
  M-1 clock unification           — independent (bundle)

API CONTRACT
  H-1 additive response fields (if adopted); M-5 UNRESOLVED bucket (additive);
  inbox pagination (additive, with H-4c)

FRONTEND
  Only if H-1 adopted (QuizEligibilityCard already renders criterion values — minimal);
  M-5 bucket label; otherwise none

TESTS
  Each item carries its own plan (§8); regression suites run after each phase

DATA CLEANUP
  H-4a purge (once, before M-3); optional 888-choice/enrollment reconciliation (D-4 — actually
  a decision: leave as documented divergence or align)

DEPLOYMENT
  H-6 TLS gate (P2); M-8 worker posture documentation
```

Safe-to-parallelize set: **H-2, H-4a/c/b, H-5, M-1+M-6, M-5, L-1/L-2/L-5**. Sequential spine: D-1/D-2 → H-1; D-3 → H-3 → M-2/M-3 → indexes.

## 8. Test Coverage Gaps

Existing suites (DB-free, ~129 tests): pooled formula baselines, optimizer/practical safety, ERP-overall safety, deactivated-extra lifecycle, UI formula text, enrollment-invariant plan tests (Case A 054/058 vs Case B 052/055), sandboxed real-`register()` e2e. No `conftest.py`; DB-touching coverage lives in mutation-bearing verifier scripts (cannot run in CI; source of H-4b).

| Issue | Existing coverage | Missing tests (exact cases) | Where they should live |
|---|---|---|---|
| H-2 | none | deactivated user + valid JWT → 401 on student GET/POST; login-after-deactivation → 403 (exists only as endpoint code, untested); refresh-after-deactivation → family revoked; reactivation restores access | `backend/tests/test_auth_deactivation.py` (new; DB-free by monkeypatching `get_current_user`'s user lookup or via the sandboxed-e2e pattern of `test_registration_enrollment_e2e.py`) |
| H-4a/c | none | orphaned event-ref rows excluded/annotated by inbox read; retention cap behavior; pagination bounds; emit idempotency under repeated triggers (ON CONFLICT path) | `backend/tests/test_notification_projection.py` (new; repo-level with sqlite/pg-sandbox or pure-SQL-shape tests) |
| H-4b | none | verifier cleanup deletes third-party notifications (assert zero orphan rows after cleanup) | verifier-side self-check (each `verify_*.py` `finally` asserts 0 orphans) |
| H-5 | none (positional `_rank` untested) | out-of-order date edit → 409/422 at `update_quiz_schedule`; equal-date two cycles → deterministic rank; reorder does not rename notification keys (after fix) | `backend/tests/test_quiz_cycle_order.py` (engine-level `_rank` pure tests + mutation validation unit tests) |
| H-1 | engine formula tests exist (pooled); threshold selection untested | per-criterion thresholds when adopted (C-I 70 / C-II 75 in Cycle I); exact-threshold passes at 70.0 and 75.0; boundary day-prior cutoff; previous-quiz-date inclusive start; `exclude_quiz_day` | `backend/tests/test_eligibility_policy.py` (extend existing DB-free engine suites) |
| H-3 | plan-level elective divergence tests exist (chunk 16) | correction with existing attendance → old-subject history byte-identical (freeze option) or re-based exactly once (consent option); double-correction idempotence; choice-without-enrollment reads nothing | `backend/tests/test_elective_correction_history.py` (new; depends on D-3) |
| M-2/M-3 | enrollment-invariant plan tests (write side) | read-boundary rejection: COMPULSORY enrollment on elective-catalog subject; ELECTIVE without choice; choice slot mismatch; choice-without-enrollment | `backend/tests/test_enrollment_read_boundary.py` (new) |
| M-1 | none | `institution_today()` vs `date.today()` divergence at 18:30–24:00 IST (freeze clock; assert admin dashboard sessions-today and summary as_of use institution clock) | `backend/tests/test_clock_unification.py` (new, pure) |
| M-6 | none | synthetic fixture: student whose only quiz dates are elective-slot → first_quiz_date resolved via slot | extend `test_enrollment_invariant.py` or new `test_first_quiz_date.py` |
| Timezone/IST midnight (general) | none | window end = quiz−1 across IST midnight; attendance future-guard at 00:00 IST boundary | `backend/tests/test_institution_clock.py` |
| Authz boundaries | verifier-only | scoped-admin matrix (Head/Class/Subsection/Elective) as DB-free unit tests of `AuthorizationService` | `backend/tests/test_authorization_matrix.py` |

## 9. Owner Decision Log — Decisions Required Before Implementation

### D-1 — Quiz threshold semantics (Cycle I, per criterion)
- **Why it matters:** determines whether Cycle-I Criterion II (cumulative) passes at 70% or 75%; changes real eligibility verdicts and all guidance numbers.
- **Current implementation:** one threshold per cycle (70/75/75), applied to both criteria; `combined_threshold` column seeded (70/75/75) but never read.
- **Option A:** keep per-cycle thresholds for both criteria (status quo; matches S4 §5 as written and the Phase-7.3 frozen contract).
- **Option B:** per-criterion thresholds — Cycle I: C-I 70 / C-II 75; later cycles 75/75 (the system audit's reading of the notice).
- **Consequences:** A = no code change; B = schema/policy change (`combined_threshold` adoption or new columns), engine change, additive API fields, UI re-render, and every Cycle-I verdict re-derived.
- **Downstream systems affected:** eligibility engine/service, quiz_schedules policies seed, quiz eligibility API, QuizEligibilityCard, QUIZ_APPROACHING/MUST_ATTEND/SAFE_SKIP notification texts.
- **Prerequisite:** commit the official notice text (or its verbatim thresholds wording) into the repo so the decision is auditable.

### D-2 — Previous-quiz-date boundary (inclusive vs exclusive) + commencement stance
- **Why it matters:** materially changes Criterion-I windows and Must-Attend counts (worked example in QC2 audit: BCS-501 Q2 3L+3T=75.0% vs 4L+3T=78.57%).
- **Current implementation:** inclusive (window starts on previous quiz date; that date's ordinary classes count; quiz-day-shaped session excluded), commencement = semester start for all subjects; per-subject commencementDate in timetable.json deliberately unused (M-11).
- **Option A:** keep inclusive boundary + semester-start commencement (frozen interpretation; equivalent for this dataset — QC2-audit proof).
- **Option B:** exclusive boundary ("day after the previous quiz") and/or per-subject commencement threading.
- **Consequences:** A = none (document only); B = window function change + recomputation + per-subject commencement plumbing (M-11 implementation).
- **Downstream:** calendar_engine windows, eligibility engine, dashboard quiz snapshot, guidance texts.

### D-3 — Elective-correction history semantics (H-3)
- **Why it matters:** determines whether past attendance keeps its original subject attribution when a student's elective choice changes; touches the roadmap's "immutable historical meaning" principle.
- **Current implementation:** choice swap + enrollment swap only; history re-attributes instantly at read time.
- **Option A — freeze:** past records stay attributed to the old subject (e.g., snapshot old-subject attribution at correction time — per-record subject binding or outcome/annotation), future marks follow the new choice.
- **Option B — explicit re-basing:** correction requires an admin confirmation step; records are re-attributed to the new subject as an explicit, logged operation.
- **Option C — accept and document:** current behavior becomes the documented semantic (no code change).
- **Consequences:** A = most faithful to immutability; needs an attribution-persistence design (migration likely). B = simplest mental model for users but rewrites history by design (audit log required). C = zero effort; permanently accepts retroactive re-attribution.
- **Downstream:** attendance reads (history/track/dashboard/analytics), eligibility windows, subject percentages, admin student detail, M-2/M-3 constraint design.

### D-4 — User `8888888888888` divergence (choices without enrollments)
- **Why it matters:** the account holds ELECTIVE_I/II choices but zero enrollments; it is the last known invariant divergence and the standing "deferred inverse inconsistency."
- **Current implementation:** tolerated (documented in chunk 14/15; the account reads nothing).
- **Option A:** leave as documented divergence (no touch).
- **Option B:** align (add canonical enrollments or clear choices) as part of the H-4a cleanup batch.
- **Consequences:** A = none; B = small data operation, must follow the chunk-16 plan-based path if enrollments are added.
- **Downstream:** read-boundary tests (M-2), notification recipients (it already receives slot-event notifications via choice resolution — 88 orphan rows today).

### D-5 — Notification scheduler existence (H-4d)
- **Why it matters:** CLASS_REMINDERs are built but unreachable in production; a scheduler (or a trigger on session materialization) is a product decision about daily-notification behavior.
- **Option A:** add a scheduled sweep (cron/worker) for CLASS_REMINDER + missed-notification back-fill (also closes H-4e).
- **Option B:** event-triggered CLASS_REMINDERs only (emit when the synchronizer materializes tomorrow's sessions).
- **Option C:** drop CLASS_REMINDER from the product scope.
- **Consequences:** A = new infra component; B = no new infra, emits inside existing atomic sync (mind volume); C = remove dead builder.
- **Downstream:** notification engine, deploy topology (worker), push delivery volume.

*(Non-decisions, for clarity: H-2, H-4a/b/c, H-5 order-validation, M-1, M-2/M-3, M-5, M-6, M-7, and the L-batch require no owner input — they implement already-documented architecture.)*

## 10. Final Reconciled Issue Matrix

| ID | Finding | Previous Severity | Reconciled Severity | Status | Confidence | Needs Policy Decision | DB Change | API Change | Frontend Change |
|----|---------|-------------------|---------------------|--------|------------|-----------------------|-----------|------------|-----------------|
| H-1 | Cycle-I threshold applied to both criteria; relaxation unmodeled | HIGH | **MEDIUM** | POLICY AMBIGUITY | CONFIRMED (behavior) / retracted defect claim | **Yes (D-1, D-2)** | Optional (per-criterion columns) | Additive if adopted | If adopted |
| H-2 | Deactivated user keeps live-token access (8h) | HIGH | **HIGH** | CONFIRMED DEFECT | CONFIRMED | No | No | No | No |
| H-3 | Elective correction re-attributes history | HIGH | **HIGH** | CONFIRMED DEFECT (mechanism; latent data) | CONFIRMED | **Yes (D-3)** | Depends on option | No | No |
| H-4a | 452 orphaned ACADEMIC_EVENT notifications | HIGH | **HIGH** | CONFIRMED DEFECT (TEST DATA POLLUTION origin) | CONFIRMED | No | No (DML purge only) | No | No |
| H-4b | Verifier cleanup ignores third-party notifications | (in H-4) | **MEDIUM** | TEST DATA POLLUTION | CONFIRMED | No | No | No | No |
| H-4c | Unbounded inbox read; no retention | (in H-4) | **MEDIUM** | ARCHITECTURE GAP | CONFIRMED | No | Optional index | Additive pagination | No |
| H-4d | CLASS_REMINDER unreachable in production | (in H-4) | **MEDIUM** | ARCHITECTURE GAP | CONFIRMED | **Yes (D-5)** | No | No | No |
| H-4e | Missed-notification loss window | (in H-4) | **LOW** | LATENT RISK | CONFIRMED (by design) | No | No | No | No |
| H-5 | Cycle numbers re-derived chronologically; order-edit unguarded | HIGH | **HIGH** (mechanism) | CONFIRMED DEFECT (trigger POTENTIAL) | CONFIRMED | No (validation) / optional (ranking) | No | No | No |
| H-6 | HTTP-only prod compose vs mandatory Secure cookie | (not in inventory) | **MEDIUM** | LATENT RISK | CONFIRMED | No | No | No | No |
| M-1 | `date.today()` vs institution clock (6 sites) | MEDIUM | MEDIUM | CONFIRMED DEFECT | CONFIRMED | No | No | No | No |
| M-2 | No defensive enrollment read boundary | MEDIUM | MEDIUM | ARCHITECTURE GAP | CONFIRMED | No | Optional (with M-3) | No | No |
| M-3 | 9 academic rules application-enforced only | MEDIUM | MEDIUM | ARCHITECTURE GAP | CONFIRMED | Partially (D-3 shapes design) | **Yes (guarded migration)** | No | No |
| M-4 | Weekly bars exclude Saturday; weekly_pct includes | MEDIUM | MEDIUM | CONFIRMED DEFECT (latent) | CONFIRMED | No | No | No | No |
| M-5 | UNRESOLVED counted as not_eligible | MEDIUM | MEDIUM | CONFIRMED DEFECT | CONFIRMED | No | No | Additive | Label only |
| M-6 | first_quiz_date slot-unaware join | MEDIUM | **LOW** | CONFIRMED DEFECT (latent; live-evidence retracted) | CONFIRMED (mechanism) / retracted (live proof) | No | No | No | No |
| M-7 | 27 FK columns + class_sessions.date unindexed | MEDIUM | MEDIUM | ARCHITECTURE GAP | CONFIRMED | No | **Yes (migration)** | No | No |
| M-8 | In-process cache/limiter vs multi-worker | MEDIUM | MEDIUM | ARCHITECTURE GAP | CONFIRMED (design) | No | No | No | No |
| M-9 | Registration duplicates catalog validation | MEDIUM | MEDIUM | ARCHITECTURE GAP | CONFIRMED | No | No | No | No |
| M-10 | Seeder subject lookup ignores semester | MEDIUM | MEDIUM | CONFIRMED DEFECT (seed-time) | CONFIRMED | No | No | No | No |
| M-11 | Per-subject commencement ignored | MEDIUM | MEDIUM | POLICY AMBIGUITY (documented divergence) | CONFIRMED | Fold into **D-2** | No | No | No |
| L-1 | POST /attendance accepts PENDING | LOW | LOW | CONFIRMED DEFECT | CONFIRMED | No | No | No | No |
| L-2 | Registration broad except swallows 503 detail | LOW | LOW | CONFIRMED DEFECT | CONFIRMED | No | No | No | No |
| L-3 | Dead-code batch (§U list) | LOW | LOW | ARCHITECTURE GAP | CONFIRMED | No | No | No | No |
| L-4 | Subsection capacity check-then-set race | LOW | LOW | LATENT RISK | POTENTIAL | No | Optional constraint | No | No |
| L-5 | First-mark race → spurious 400 | LOW | LOW | CONFIRMED DEFECT | CONFIRMED | No | No | No | No |
| L-6 | GET /events over-exposure | LOW | LOW | LATENT RISK | POTENTIAL | Optional | No | No | No |
| L-7 | Frontend threshold coloring duplication | LOW | LOW | ARCHITECTURE GAP | CONFIRMED | No | No | Optional | Yes |
| L-8 | Event duplicate identity omits elective_slot | LOW | LOW | LATENT RISK | POTENTIAL | No | No | No | No |
| P-1 | Anchor+slot double attribution under dirty data | LOW/POTENTIAL | LOW | LATENT RISK | POTENTIAL | No | No | No | No |
| P-2 | Arbitrary session pick if >1 active | LOW/POTENTIAL | LOW | LATENT RISK | POTENTIAL | No | Closed by M-3 | No | No |
| P-3 | Optimizer pending conflates past-unmarked with future | LOW/POTENTIAL | LOW | LATENT RISK (documented simplification) | CONFIRMED (model) | Optional | No | No | No |
| P-4 | /sync client-set roll_number | LOW/POTENTIAL | LOW | LATENT RISK | CONFIRMED (code) | No | No | No | No |

No finding was silently removed. H-4 de-bundles into a–e; H-6 enters the inventory; H-1 and M-6 change severity/status with documented reasons; all others carry forward.

## 11. Implementation Specifications (confirmed P0/P1 issues)

Format: ISSUE → CURRENT BEHAVIOR → TARGET BEHAVIOR → AFFECTED FILES → AFFECTED SYMBOLS → DATA IMPACT → MIGRATION → API IMPACT → FRONTEND IMPACT → TEST PLAN → ROLLOUT RISK → DEPENDENCIES.

---

### SPEC-H-2 — Enforce deactivation on authenticated requests

**CURRENT BEHAVIOR:** `get_current_user` validates the JWT and loads the user; no `is_active` check. Deactivation blocks only login (403) and refresh (family revocation); a pre-deactivation access token authorizes all student endpoints up to 8h.
**TARGET BEHAVIOR:** after user load, `if not user.is_active: raise HTTPException(401, "Account is deactivated")` (401 so the frontend's existing refresh-then-fail flow signs the user out cleanly).
**AFFECTED FILES:** `backend/app/api/dependencies/deps.py`.
**AFFECTED SYMBOLS:** `get_current_user`.
**DATA IMPACT:** none.
**MIGRATION:** NO.
**API IMPACT:** NO (status codes on a previously-successful path only).
**FRONTEND IMPACT:** NO (apiFetch already handles 401 with a refresh retry then logout).
**TEST PLAN:** unit — deactivated user + valid JWT → 401 (student GET + POST); active user unchanged; login-after-deactivation → 403; refresh-after-deactivation → RefreshTokenError + family revoked (assert via service-level test); reactivation restores access. File: `backend/tests/test_auth_deactivation.py`.
**ROLLOUT RISK:** Low — one branch; no schema; deterministic.
**DEPENDENCIES:** none. **Ready to implement.**

---

### SPEC-H-4a/H-4c — Orphan purge + inbox retention/pagination

**CURRENT BEHAVIOR:** 452 ACADEMIC_EVENT rows reference deleted events (owner: 182 unread ghosts); `get_inbox` is unbounded; no retention cap or policy anywhere.
**TARGET BEHAVIOR:** (1) one-time purge: delete `notifications` rows whose `event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM academic_events WHERE id = event_id)`; (2) read-layer hardening: inbox read excludes (or annotates) rows with dead event refs so a future pollution cannot surface; (3) retention cap: e.g., hard delete read+dismissed rows older than N days and cap inbox at a bounded window (owner-tunable constant), plus LIMIT-paginated inbox query with additive response metadata.
**AFFECTED FILES:** `backend/app/repositories/notification_repo.py`, `backend/app/services/notification_service.py`, a one-time cleanup script under `backend/scripts/` (read-only audit pattern extended with the delete, run explicitly), optionally `backend/app/api/v1/endpoints/notifications.py` (pagination params).
**AFFECTED SYMBOLS:** `NotificationRepository.get_inbox`, `NotificationRepository.count_unread`, `NotificationService.get_notifications`; new: `purge_orphaned_event_notifications`, retention helper.
**DATA IMPACT:** deletes 452 dead projection rows (projections, not source facts — events are already gone; no academic data touched).
**MIGRATION:** NO schema change required; optional index on `notifications(user_id, created_at)` for pagination (bundle with M-7).
**API IMPACT:** additive only (pagination params + optional `total`/`has_more` fields).
**FRONTEND IMPACT:** none required (additive fields ignored by current consumers).
**TEST PLAN:** repo-level — purge deletes exactly dead-ref rows and no live ones (assert kind counts before/after using the probe's baseline); inbox excludes dead refs; retention respects read/dismiss state; pagination bounds (limit ≤ 200); emit-idempotency under repeated triggers. File: `backend/tests/test_notification_projection.py`.
**ROLLOUT RISK:** Low-Medium — the purge is irreversible DML; mitigate with a pre-purge count snapshot + backup dump, and run during a quiet window. Read-layer changes are low risk.
**DEPENDENCIES:** none (run before M-3's migration to keep baselines clean). **Ready to implement.**

---

### SPEC-H-4b — Verifier notification hygiene

**CURRENT BEHAVIOR:** verifier `finally` cleanups delete fixture events but not ACADEMIC_EVENT notifications already emitted to real users.
**TARGET BEHAVIOR:** every event-mutating verifier's cleanup also deletes notifications whose `event_id` is in the fixture set *for all users* (not only fixture users); a shared helper in the verifier harness enforces it; a self-check asserts zero orphans after cleanup.
**AFFECTED FILES:** all `backend/scripts/verify_*.py` that create events (the audit lists them; introduce `backend/scripts/_verifier_harness.py` helper).
**AFFECTED SYMBOLS:** verifier `finally` blocks; new harness function.
**DATA IMPACT:** cleanup-only.
**MIGRATION:** NO. **API IMPACT:** NO. **FRONTEND IMPACT:** NO.
**TEST PLAN:** harness self-check; one representative verifier run leaves zero orphan rows.
**ROLLOUT RISK:** Low. **DEPENDENCIES:** none; **run immediately after H-4a** (prevents re-pollution). **Ready to implement.**

---

### SPEC-H-5 — Cycle-date ordering validation at quiz mutation

**CURRENT BEHAVIOR:** `update_quiz_schedule`/`create_quiz_schedule` validate only semester bounds; effective cycle numbers are positional over chronologically ranked event dates, so an out-of-order date edit silently renames cycles across eligibility/notifications/dashboard.
**TARGET BEHAVIOR:** on any date-setting mutation, reject (`AdminQuizValidationError` → 422) a date that would make a subject's cycle dates non-chronological with respect to the subject's other scheduled cycles (compare against sibling `QuizSchedule` rows for the same subject/slot; equal dates also rejected as ambiguous). Ranking code optionally gains a defensive tie-break but stays event-authoritative.
**AFFECTED FILES:** `backend/app/services/admin_quiz_service.py`.
**AFFECTED SYMBOLS:** `AdminQuizService.update_quiz_schedule`, `AdminQuizService.create_quiz_schedule` (new shared `_validate_cycle_chronology(subject_id, slot, new_date, exclude_schedule_id)`).
**DATA IMPACT:** none (validation only; no existing rows violate chronology — probe-confirmed).
**MIGRATION:** NO. **API IMPACT:** NO (422 on a previously-accepted input).
**FRONTEND IMPACT:** none (422 surfaces as a form error).
**TEST PLAN:** unit — set Q3 date < Q2 → 422; equal dates → 422; moving Q2 later past Q3 → 422; semester-bounds still enforced; slot-scoped subjects validated against the slot's schedule set; existing chronological edits still pass. Files: `backend/tests/test_quiz_cycle_order.py` (+ engine `_rank` pure tests for dedup/rank stability).
**ROLLOUT RISK:** Low — validation-only; no data change.
**DEPENDENCIES:** none (do **before** H-1 policy work so labels are stable). **Ready to implement.**

---

### SPEC-H-1 — Per-criterion thresholds (BLOCKED on D-1/D-2)

**CURRENT BEHAVIOR:** one `required` per cycle applied to both criteria; `combined_threshold` seeded but unread; relaxation framework unmodeled; boundary/commencement interpretations frozen.
**TARGET BEHAVIOR (Option B of D-1 only):** per-criterion thresholds — populate and consume `combined_threshold` (or add `criterion_i_threshold`/`criterion_ii_threshold`); Cycle I 70/75, later cycles 75/75 per the owner's ruling; response carries per-criterion `threshold`; relaxation framework explicitly scoped as a separate backlog item (not silently bundled).
**AFFECTED FILES:** `backend/app/engines/eligibility_engine.py`, `backend/app/services/eligibility_service.py` (policy dict construction), `backend/app/models/quiz.py` (if new columns), seed source (`timetable.json` policies + seeding path), `backend/app/schemas/attendance.py` (CriterionResult already carries `threshold`; top-level fields additive).
**AFFECTED SYMBOLS:** `evaluate_quiz_eligibility`, `_evaluate_criterion`, `EligibilityPolicy`, `EligibilityService._build_domain_subject`/policy fetch.
**DATA IMPACT:** policy rows updated (values, not structure, if `combined_threshold` adopted).
**MIGRATION:** NO if `combined_threshold` is adopted (column exists); YES if new columns chosen. Backfill trivial; rollback possible.
**API IMPACT:** additive per-criterion threshold fields.
**FRONTEND IMPACT:** QuizEligibilityCard already renders per-criterion values; threshold labels update.
**TEST PLAN:** Cycle-I boundary tests for both criteria (70 vs 75 exact-pass/fail); later cycles 75/75; engine-fallback parity; notification text regeneration; regression: existing pooled-formula suites unchanged.
**ROLLOUT RISK:** Medium — changes Cycle-I verdicts (user-visible academic outcomes); requires owner sign-off on the exact matrix before merge.
**DEPENDENCIES:** **D-1 (+D-2 for boundary if the owner elects to change it); do after H-5** (stable cycle labels first).

---

### SPEC-H-3 — Elective-correction history semantics (BLOCKED on D-3)

**CURRENT BEHAVIOR:** `correct_elective` swaps choice+enrollment; historical AttendanceRecords remain on shared slot sessions and re-attribute to the new subject at read time.
**TARGET BEHAVIOR (per D-3 option):**
- *Freeze (A):* at correction time, persist old-subject attribution for existing records (design options: per-record subject binding column, or `occurrence_outcomes`-style attribution rows); reads honor frozen attribution; future marks follow the new choice.
- *Re-base (B):* explicit confirmation flow; records re-attributed exactly once; write an audit log row.
- *Accept (C):* document the semantics in S4/roadmap; no code change.
**AFFECTED FILES:** `backend/app/services/admin_student_service.py` (+ new attribution helper/service under `app/services/`), possibly `backend/app/models/attendance.py` (binding column) and a re-basing helper; audit-log table if B.
**AFFECTED SYMBOLS:** `AdminStudentService.correct_elective`; count-query join predicates in `AttendanceRepository` (frozen attribution must take precedence over choice join).
**DATA IMPACT:** option-dependent (backfill of attribution for existing records under A/B).
**MIGRATION:** UNKNOWN until option chosen (A: likely yes — attribution table/column + backfill; B: audit-log table; C: none). Rollback: additive in all designs.
**API IMPACT:** none (admin endpoint contract unchanged; possibly a confirmation flag for B).
**FRONTEND IMPACT:** confirmation dialog for B.
**TEST PLAN:** correction with existing attendance → old-subject history byte-identical (A) / re-based exactly once (B); idempotent double-correction; eligibility windows for both subjects after correction; no other student's data touched (chunk-16 snapshot pattern).
**ROLLOUT RISK:** High — touches history semantics for every future correction; must ship with the M-2/M-3 boundary work coordinated.
**DEPENDENCIES:** **D-3**; coordinates with M-2/M-3 (constraint design assumes settled semantics).

---

### SPEC-M-1 — Clock unification (P1)

**CURRENT BEHAVIOR:** 6 confirmed sites use `date.today()` (UTC on a UTC host): `admin_dashboard_service.py` L45/L186/L225, `admin_dashboard_repo.py` L274/L289, `endpoints/attendance.py` L110 (as_of fallback), `endpoints/quiz.py` L56 (semester_start fallback). Cosmetic 7th: `eligibility_engine.py` L166-167 placeholder inside the UNRESOLVED return.
**TARGET BEHAVIOR:** all resolved via `institution_today()`; the placeholder may use it too for consistency.
**AFFECTED FILES:** as listed.
**AFFECTED SYMBOLS:** `AdminDashboardService` internals, `AdminDashboardRepository` event queries, `get_attendance_summary`, quiz eligibility endpoint.
**DATA IMPACT:** none. **MIGRATION:** NO. **API IMPACT:** none (same fields, corrected values in the 18:30–24:00 IST window). **FRONTEND IMPACT:** none.
**TEST PLAN:** freeze-clock tests asserting institution-day selection at 23:59 IST vs 00:01 IST; admin dashboard `sessions_today` matches calendar service on the same instant.
**ROLLOUT RISK:** Very low. **DEPENDENCIES:** none. **Ready to implement.**

---

### SPEC-M-2/M-3 — Enrollment read boundary + DB invariant hardening (P1, after D-3)

**CURRENT BEHAVIOR:** `get_enrolled_subjects` joins enrollments unfiltered; 9 academic rules application-enforced only (enrollment-type↔slot, choice-slot validity, UNIQUE(subject,cycle) on quiz_schedules, single-active-session, timetable overlap, event dedup identity, QUIZ_DAY↔schedule sync, subsection capacity, registration structure assumptions).
**TARGET BEHAVIOR:** (1) read boundary — `get_enrolled_subjects` (and the context/enrollment loaders) filter to rows satisfying placement/session + type-vs-slot consistency; divergent rows are logged, never fabricated; (2) DB backstops in one guarded migration: CHECK enrollment-type-vs-catalog-slot, partial UNIQUE on `quiz_schedules(subject_id, quiz_cycle_id) WHERE active`, partial UNIQUE single-active `academic_sessions`, timetable overlap EXCLUSION constraint per (section, day), (optionally) choice-subject-slot FK-composite.
**AFFECTED FILES:** `backend/app/repositories/user_repo.py`, `backend/app/services/student_context_service.py` (loaders), one new migration, seeder/validation touchpoints only if they violate (verify first).
**AFFECTED SYMBOLS:** `UserRepository.get_enrolled_subjects`, `StudentContextService._load_enrollments/_load_elective_choices`; migration ops only.
**DATA IMPACT:** verify-no-violations pre-check required (current data is conformant except the 888 choice/enrollment divergence — D-4 first).
**MIGRATION:** YES (guarded: refuse-on-violation pattern per `c8d9e0f1a2b3` precedent; CONCURRENTLY for index adds in prod; reversible downgrade).
**API IMPACT:** none. **FRONTEND IMPACT:** none.
**TEST PLAN:** invariant verifier suite (write-side violations rejected at DB level); read-boundary unit tests (each divergence type); migration dry-run on a DB snapshot; 888-account behavior decided by D-4 beforehand.
**ROLLOUT RISK:** Medium — constraint additions can reject latent bad data on other environments; guarded pre-checks mandatory.
**DEPENDENCIES:** **D-3 (semantics), D-4 (888 account), H-4a purge (clean baseline)**.

---

### SPEC-M-6 — first_quiz_date slot resolution (P2 after downgrade)

**CURRENT BEHAVIOR:** `user_repo.get_academic_context` and `student_context_service._load_first_quiz_date` join events on `enrollment.subject_id` only; slot-unaware. Live impact currently nil (compulsory dates always earlier — probe-proven) but not schema-guaranteed.
**TARGET BEHAVIOR:** both queries resolve slot events via the student's choices (mirroring `QuizRepository.get_effective_quiz_dates_for_subjects` scope logic) — ideally by delegating to that canonical helper and taking `min(date)`.
**AFFECTED FILES:** `backend/app/repositories/user_repo.py`, `backend/app/services/student_context_service.py`.
**AFFECTED SYMBOLS:** `get_academic_context`, `_load_first_quiz_date`.
**DATA IMPACT:** none. **MIGRATION:** NO. **API IMPACT:** none. **FRONTEND IMPACT:** none.
**TEST PLAN:** synthetic fixture (student whose only quiz dates are elective-slot) → date resolves; non-chooser unchanged; chooser with both → min of all.
**ROLLOUT RISK:** Very low. **DEPENDENCIES:** none. **Ready to implement (bundle with M-1).**

---

### SPEC-M-7 — Index migration (P2, after M-3)

**CURRENT BEHAVIOR:** 27 FK columns + `class_sessions.date` unindexed (list in audit §D).
**TARGET BEHAVIOR:** guarded migration adding the indexes (`class_sessions.date` first, then FK set), CONCURRENTLY-safe ordering documented for prod.
**AFFECTED FILES:** one new migration.
**MIGRATION:** YES (additive; rollback = drop). **API/FRONTEND:** none. **DATA IMPACT:** none.
**TEST PLAN:** EXPLAIN probes before/after on the hot queries (dashboard window scan, inbox, eligibility windows); migration dry-run.
**ROLLOUT RISK:** Low. **DEPENDENCIES:** after M-3's migration (combine review, keep separate reversible ops).

## 12. Dependency-Aware Remediation Roadmap

### PHASE 1 — Policy / Domain Decisions (owner; no code)
- **Items:** D-1, D-2 (+M-11 stance), D-3, D-4, D-5; plus committing the official notice text into the repo (provenance).
- **Dependencies:** none. **Affected layers:** none (decisions). **Migration:** none. **Testing:** none.
- **Exit criteria:** each decision recorded with the chosen option in this report's decision log or an ADR.

### PHASE 2 — Core Backend / Data Integrity (immediately implementable)
- **Items:** H-2 (SPEC-H-2) → H-4a/H-4c (SPEC-H-4a/c) → H-4b (SPEC-H-4b) → H-5 (SPEC-H-5).
- **Dependencies:** none on Phase 1; H-4b strictly after H-4a; H-5 before any H-1 work.
- **Affected layers:** deps, notifications, quiz admin, verifier tooling. **Migration:** none. **Testing:** new suites per specs; run DB-free pytest + targeted verifier self-checks.
- **Independent bundle (same phase, any order):** M-1 + M-6 (clock + query swap), M-5 (UNRESOLVED bucket), L-1/L-2/L-5 (small correctness).

### PHASE 3 — Cross-Engine Corrections (post-decision)
- **Items:** H-1 (after D-1/D-2), H-3 (after D-3), then M-2/M-3 read boundary + guarded invariant migration (after D-3/D-4 and the H-4a purge), then M-7 indexes (after M-3), M-11 if D-2 elects change.
- **Dependencies:** as listed; M-2/M-3 is the phase's keystone.
- **Affected layers:** engines, services, repositories, models, migrations. **Migration:** YES (M-3, M-7; possibly H-3-A). **Testing:** invariant verifier suite + migration dry-runs + byte-identical history snapshots (H-3-A).

### PHASE 4 — Notifications / Infrastructure
- **Items:** H-4d (+H-4e) per D-5; M-8 multi-worker posture (Redis limiter or enforced single worker + documented cache semantics); push dispatch off the request path; batched `after_event_mutation` emission (adopt `upsert_many`); admin N+1 batching; request-ID logging; minimal admin-mutation audit log (roadmap chain); H-6 TLS gate before any HTTP-only production use.
- **Dependencies:** D-5 for H-4d; others independent.
- **Affected layers:** services, infra configs, new worker possibly. **Migration:** only if the audit-log table is added. **Testing:** trigger idempotency, limiter behavior, push isolation.

### PHASE 5 — Tests / Regression Hardening
- **Items:** the §8 gap list as named files: `test_auth_deactivation.py`, `test_notification_projection.py`, `test_quiz_cycle_order.py`, `test_eligibility_policy.py` (extend), `test_elective_correction_history.py`, `test_enrollment_read_boundary.py`, `test_clock_unification.py`, `test_institution_clock.py`, `test_authorization_matrix.py`; CI-enablement of the DB-free suites; verifier orphan self-checks.
- **Dependencies:** each suite depends on its fix landing (or documents current behavior until then).
- **Migration:** none. **Testing:** is the deliverable.

### PHASE 6 — Cleanup / Low-Priority Technical Debt
- **Items:** L-3 dead-code batch (`_combined_pct`, `require_admin`, `validate_selection` adoption-or-removal per M-9, `get_quiz_schedules_for_subject(s)`, `upsert_many` adoption-or-removal, legacy class-type aliases, `combined_threshold` per D-1 outcome, docstring-header fix on `e2f3a4b5c6d7`, mojibake, stray `backend/verify_phase_25_1.py` relocation, `get_db` consolidation); L-4 capacity lock; L-6 optional enrollment filter; L-7 backend variant field; L-8 slot in duplicate identity; P-2 (closed by M-3); P-4 (drop `/sync` roll_number write); M-9/M-10 de-duplication.
- **Dependencies:** several depend on D-1 outcome (`combined_threshold`) and M-9 direction.
- **Migration:** none. **Testing:** existing suites stay green.

## 13. Risks / Unknowns

1. **External notice provenance (H-1/M-11):** the official notice text is not in the repo; all policy interpretations trace to ADR-010's summary. Until the text is committed, D-1/D-2 cannot be closed with full confidence. *(Unknown, owner-resolvable.)*
2. **H-3 attribution design:** the freeze option's persistence shape (column vs attribution rows) interacts with the count-query join predicates; a wrong choice could double-count. Mitigation: byte-identical snapshot verification (chunk-16 pattern) as an acceptance gate. *(Design risk, bounded.)*
3. **Constraint migration on other environments:** M-3's CHECKs/uniques assume conformant data; non-local environments must run the guarded pre-check before upgrade. *(Operational risk, mitigated by refuse-on-violation pattern.)*
4. **Notification purge irreversibility:** H-4a deletes projection rows permanently; a pre-purge backup dump is required. *(Operational risk, mitigated.)*
5. **DB drift during remediation:** live data moved between the system audit and this pass (5th user appeared). All count-based acceptance criteria must re-baseline at execution time. *(Known, disclosed.)*
6. **Multi-worker semantics (M-8):** if the production deployment ever scales beyond one worker before the limiter/cache decision, rate limits and inbox freshness degrade silently. *(Deployment risk, documented.)*
7. **Could-not-verify items:** concurrency behaviors (L-4/L-5 races) were code-inspected only, per the no-mutation constraint; their POTENTIAL confidence stands.

## 14. Final Readiness Assessment

| Item | Status |
|---|---|
| **Ready to implement (no blockers)** | H-2, H-4a+H-4c (+H-4b companion), H-5, M-1, M-6, M-5, L-1, L-2, L-5 |
| **Blocked by policy decision** | H-1 (D-1/D-2), H-3 (D-3), H-4d (D-5), M-11 (D-2), M-2/M-3 partially (D-3/D-4 shape the constraints; the read-boundary half could proceed but should not precede the semantics decision) |
| **Blocked by insufficient evidence** | None — all P0/P1 mechanisms were verified to exact code sites this pass; the only evidence retraction (M-6 live proof) *downgraded* the item rather than blocking it |
| **Requires data migration planning** | M-3 (guarded invariant migration + pre-check), M-7 (index migration), H-3-option-A/B (attribution backfill), H-4a (irreversible purge — backup first) |
| **Requires architecture decision** | H-4d (scheduler vs trigger vs drop — D-5), M-8 (limiter/cache topology), audit-log introduction (Phase 4) |

**Overall:** the remediation program can start immediately on the ready list (Phase 2) without waiting for any owner input; the two highest-visibility academic-semantics items (H-1, H-3) are decision-gated by design, and their decision documents (§9) are complete enough that the owner can answer them directly.

*End of report.*
