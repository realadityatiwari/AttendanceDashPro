# AttendanceDash Pro — Master Roadmap

> **Project Source of Truth**
>
> This document defines the direction, phase structure, priorities, architectural boundaries, and production path for AttendanceDash Pro.
>
> **Current position:** Phase 6 (Calendar & Academic Events) **COMPLETE & FROZEN** ✅. Phase 7 (Quiz Eligibility & Schedule Reality) **COMPLETE & FROZEN** ✅ — full math verified, canonical contract, 7.1/7.2 analytics, and final hardening (backend reachability consistency, frontend safety/fallback rendering, cleanup, and pycache removal) verified passing 100% of verifiers. Phase 8 (Attendance Analytics & Intelligence) **COMPLETE & FROZEN** ✅ — backend read model, dashboard analytics, and laboratory domain separation delivered without duplicate math. Phase 9 (Laboratory System) **COMPLETE & FROZEN** ✅ — 9.0 audit, 9.1 event integration, 9.2.0 audit, and 9.2.1 experiment management all complete, plus focused corrections (Track lab attendance, History filters, Quiz Day recovery, and local development infrastructure). Phase 10 (Settings, Feedback & Account Management) **COMPLETE & FROZEN** ✅ — 10.0 audit ✅ · 10A settings UI ✅ · 10B program + profile completion ✅ · 10C real feedback system ✅ · 10D user preferences API + UI ✅ · 10E freeze corrections, verification & governance reconciliation ✅. Phase 11 (Notifications & Reminders) **COMPLETE & FROZEN** ✅. Phase 12 (Mobile / Responsive Experience) **COMPLETE & FROZEN** ✅. Phase 13 (PWA / Installability) **COMPLETE & FROZEN** ✅. **Phase 14 (Firebase Retirement) COMPLETE & FROZEN ✅** — 14.0 audit, 14A frontend removal, 14B backend removal, 14C deployment/config cleanup, 14D `firebase_uid` removal, 14E regression verification, 14F freeze & governance reconciliation all complete. Active architecture: **PostgreSQL + FastAPI + JWT + Next.js**; Firebase fully retired.
>
> **Current position:** Phase 21 — Production Launch **COMPLETE & FROZEN** ✅ — Phase 21A/21A.1 (account audit + approved cleanup) ✅, 21B (feedback admin) ✅, 21C (pre-flight gate closure) ✅, 21D.0 (free beta architecture) ✅, 21D.1 (config hardening) ✅, 21D.2 (provisioning + connection/alembic/Vercel/auth/migration audits) ✅, 21D.3 (controlled localhost→Supabase migration + operator verification) ✅, 21D.4 (production closure & governance reconciliation) ✅. Production is LIVE on **Vercel Hobby (frontend) + Render Free (backend) + Supabase Free PostgreSQL**; operator verified production login, ADMIN account, dashboard, desktop, mobile responsive UI, PWA install/launch, and migrated data (165 attendance — 108 ATTENDED / 57 MISSED). All launch gates A/B/C RESOLVED. Closure: `docs/phase_21/phase_21d4_production_closure.md`.
>
> **Next phase:** Phase 22 — Post-Launch **COMPLETE** — 22.1 (Timetable Data-Scope Correction) **COMPLETE & VERIFIED IN PRODUCTION** · 22.2 (Production Parity & Mutation Reliability) **COMPLETE** · 22.3 (Student Elective Selection & Timetable Resolution) **COMPLETE** · 22.4 (Departmental Elective Resolution Across All Engines & Surfaces) **COMPLETE** — then: Phase 23.0 (Architecture Discovery) **COMPLETE — DISCOVERY PHASE + BLUEPRINT RECONCILED (2026-08-27)** · **Phase 23.1 (Academic Hierarchy & Enrollment Schema Foundation) COMPLETE (2026-08-27)** · **Phase 23.2 (Curriculum model) COMPLETE (2026-08-27)** · **Phase 23.3 (Student Academic Assignment) COMPLETE (2026-08-28)** — consolidated/verified the student assignment relationship (placement / compulsory enrollment / elective selection) around the existing 22.3/22.4 elective architecture; migration `e3f4a5b6c7d8` (additive `student_enrollments.enrollment_type` COMPULSORY/ELECTIVE + deterministic backfill; `/student/me` exposes subsection + elective_i/elective_ii). Not applied to production (operator boundary). · **Phase 23.4 (Authoritative Student Context Service) COMPLETE (2026-08-28)** — one reusable read-only backend authority (`StudentContextService` + `StudentContext` read model) for placement/enrollments/elective choices; consumers migrated: `/student/me`, Dashboard, Quiz eligibility, Calendar, Analytics, Attendance History (equivalence verified; attendance/eligibility/calendar/event/timetable semantics untouched). No schema/migration change. · **Phase 23.5 (Elective/Catalog Redesign) COMPLETE (2026-08-28)** — elective catalog normalized into the DB (`subjects.elective_slot` nullable enum; migration `f5a6b7c8d9e0`); `ElectiveResolver` is now DB-driven (no hardcoded catalog constants); registration validates against the DB catalog; one-slot-per-subject guaranteed; seed + 22.4 verifier updated. Not applied to production (operator boundary). · **Phase 23.6 (Actual Occurrence Architecture) COMPLETE (2026-08-28)** — subject-specific per-subject occurrence outcomes (`occurrence_outcomes` table + `OccurrenceOutcomeType` enum; migration `f6a7b8c9d0e1`); `EventSessionSynchronizer` extended to create outcomes for subject-specific elective events; `attendance_repo` read queries apply outcome per student (elective isolation: DE-II BCS-058→quiz, BCS-055→normal, BCS-056→cancelled, no leakage); `occurrence_is_cancelled` engine function extended. Not applied to production (operator boundary). · **Phase 23.7 (Event-Scope Redesign + MODIFIED) COMPLETE (2026-08-28)** — `EventType.CLASS_MODIFIED` (subject-scoped modified-occurrence event) + `OccurrenceOutcomeType.MODIFIED` (migration `f7a8b9c0d1e2` = ALTER TYPE ADD VALUE); event registry rule + subject-scoped-only rejection; synchronizer produces MODIFIED outcomes on the shared anchor session for the targeted concrete subject (elective isolation preserved: BCS-058 MODIFIED never leaks to BCS-055/056); `_reconcile_outcomes` generalized to non-elective subject anchors; read path exposes MODIFIED without changing extra/cancelled flags; frontend EventType/eventRules extended. Not applied to production (operator boundary). · **Phase 23.8 (Quiz Integration — MODIFIED + subject-scoped quiz reality) COMPLETE (2026-08-28)** — proved MODIFIED is occurrence METADATA for the quiz pipeline (a modified class is still a conducted class: counted in every denominator; quiz dates/identity/windows/eligibility unchanged; subject isolation via the outcome join key). One genuine integration fix: CLASS_MODIFIED no longer overwrites a CANCELLED desired outcome (cancellation wins over modification). Added `verify_phase_23_8.py` (DB-based, self-cleaning; operator-run). No migration. Not applied to production (operator boundary). · **Phase 23.9 (Attendance Mutation Gate) COMPLETE / VERIFIED (2026-08-29)** — outcome-aware mutation safety; `verify_phase_23_9.py` PASS 26/26 on the dev DB after the Phase 23.7 corrective migration `f8a9b0c1d2e3`. Not applied to production (operator boundary). · **Phase 23.10 (Student-Facing Read Models) COMPLETE (2026-08-29)** — read model exposes `outcome_type` + `elective_slot` on daily-sessions/history; all surfaces confirmed on the canonical architecture; `verify_phase_23_10.py` PASS 26/26. No migration. Not applied to production (operator boundary). · **Phase 23.11 (API Scope & Authorization) COMPLETE (2026-08-29)** — backend-authoritative scoped-admin authorization foundation: `adminrole` enum + `admin_scopes` table (migration `f9a0b1c2d3e4`); `AuthorizationService` (HEAD_ADMIN global / CLASS_ADMIN section-scoped / SUBSECTION_ADMIN conservative-inert / ELECTIVE_ADMIN concrete-subject-scoped); legacy ADMIN resolves as HEAD_ADMIN; `require_head_admin` + composable scope dependencies wired into laboratory/feedback admin endpoints and the EventService admin gates; student-facing audit confirmed owner/enrollment/effective-subject scoping; `verify_phase_23_11.py` PASS 23/23. Applied to local dev DB only; production untouched. · **Phase 23.12 (Migration Gate) COMPLETE (2026-08-29)** — Phase 23 migration chain audited: single linear chain of 25 migrations, exactly one head `f9a0b1c2d3e4`; fresh disposable-DB migration to HEAD (25/25 applied) + downgrade/rollback cycle + idempotency verified; model-vs-DB drift audited (only the documented legacy timestamp-nullable convention remains); adminrole/CHECK/FK semantics proven (invalid combinations rejected); offline upgrade SQL (617 lines, no destructive ops) + dependency-safe downgrade SQL validated; data-integrity baseline unchanged; `verify_phase_23_12.py` PASS 52/52. No migration created; production untouched. · Phase 23.x (Academic Architecture Evolution) **CONTINUING**. Phase 20 (Production QA) **COMPLETE & FROZEN**; Phase 19 (CI/CD) **COMPLETE & FROZEN**; Phase 18 **IN PROGRESS / PARTIAL** — 18.0–18C ✅, 18D ⚠︝ PARTIAL (production deployment BLOCKED on missing infrastructure — superseded by the Phase 21D free-beta architecture which is now live). Phase 17 **COMPLETE & FROZEN**; Phase 16 **COMPLETE & FROZEN**; Phase 15 **COMPLETE & FROZEN**; Firebase retirement (14.0–14F) **COMPLETE & FROZEN**; active application = `frontend/` + `backend/` (PostgreSQL + FastAPI + JWT + Next.js).
>
> **Authorized bugfixes executed (2026-08-22):**
> • **Bugfix 1 — CLASS_CANCELLED propagation:** active cancellation events now cancel matching recorded sessions via the canonical synchronizer; consumers aligned on one applicability predicate (`occurrence_is_cancelled`). Verified 26/26 + full regression set.
> • **Bugfix 2 (Phase 12C) — cancellation reversal + counting consistency:** root-caused the stale-cancelled-after-event-removal defect (stale backend process executing pre-fix code + genuine `deactivate_event` early-return gap that skipped reconciliation for already-inactive events). `deactivate_event` now ALWAYS reconciles — state-based synchronization re-derives `is_cancelled` from the complete active event set, making removal/reactivation/moves self-healing and idempotent in BOTH directions. One canonical applicability rule excludes cancelled occurrences from every denominator/numerator/count (Track/History/Subjects/Dashboard/Eligibility/Notifications) while attendance records remain byte-preserved. NEW lifecycle verifier **35/35** + prior verifier **26/26** + frozen-phase regressions green. Live BCS-058 restored through the application path (07-29 Attended / 07-30 Missed originals back; applicable lectures 79 = N). Details: `docs/bugfix/cancellation_state_and_counting_consistency_report.md`. ⚠ Owner must restart the dev backend (runs without --reload) to load fixed modules. No commit made.

---

## 🧭 Project Direction

AttendanceDash Pro is being developed as a real, production-ready attendance intelligence platform — not merely a polished frontend.

The standard for completion is:

```text
UI
 ↓
API
 ↓
Service
 ↓
Repository
 ↓
Database
 ↓
Engine
 ↓
Calculated Result
```

Every layer must agree.

A page appearing to work is **not** sufficient evidence that the feature works.

---

# 📝 Current Status

| Phase | Area | Status |
|---|---|---|
| 0 | Architecture & Reality Audit | 🟢 Complete / Frozen |
| 1 | Design System Foundation | 🟢 Complete / Frozen |
| 2 | Desktop Shell & Global UX | 🟢 Complete / Frozen |
| 3 | Home Dashboard | 🟢 Complete / Frozen |
| 4 | Track Attendance | 🟢 Complete / Frozen |
| 4.5 | Data Integrity & Account Foundation | 🟢 Complete / Frozen |
| 5 | Attendance History | 🟢 Complete / Frozen |
| **6** | **Calendar & Academic Events** | ✅ **COMPLETE & FROZEN** — 6.0 audit ✅ · 6.1 foundational corrections ✅ · 6.2 calendar read model & API ✅ · 6.3 calendar UI ✅ · 6.4 events page upgrade ✅ · 6.5 persistence/admin/seeding ✅ · 6.6 event→engine integration ✅ · 6.7 verification/freeze ✅ |
| 7 | Quiz Eligibility & Schedule UX | ✅ **COMPLETE & FROZEN** — 7.0 audit ✅ · 7.1 contract/UI ✅ · 7.2 analytics refinement ✅ · **Hardening** ✅ (backend reachability consistency, frontend degradation safety, pycache removal, dead code cleanup, exact math restored and verified). |
| 8 | Attendance Analytics / Intelligence | ✅ **COMPLETE & FROZEN** — 8.0 audit ✅ · 8.1 canonical analytics read model ✅ · 8.2 frontend consumption ✅ · Attendance UI refinement ✅ · Lab domain correction (practical attendance separation) ✅. |
| 9 | Laboratory System | ✅ **COMPLETE & FROZEN** — 9.0 audit ✅ · 9.1 event integration (Mid-Sem/Lab Cancelled) ✅ · 9.2.0 audit ✅ · 9.2.1 experiment management (curriculum/records/UI/API) ✅ · Focused corrections (Track lab, History filters, Quiz Day recovery) ✅. |
| 10 | Settings, Feedback & Account Management | ✅ **COMPLETE & FROZEN** — 10.0 audit ✅ · 10A settings UI ✅ · 10B program + profile completion ✅ · 10C real feedback system ✅ · 10D user preferences API + UI ✅ · 10E freeze corrections, verification & governance reconciliation ✅. |
| **11** | **Notifications & Reminders** | ✅ **COMPLETE & FROZEN** — 11.0 architecture audit ✅ · 11A backend notification read model & contracts ✅ · 11B notification persistence + read-state ✅ · 11D notification center UX ✅ · 11E preference wiring verified (no additional implementation required) ✅ · 11F final verification & freeze ✅ · 11C delivery model decision-gated/deferred (not implemented) |
| 12 | Mobile / Responsive Experience | 🟡 **IN PROGRESS** — 12.0 architecture & implementation-readiness audit ✅ · **12A responsive foundation + mobile navigation ✅** (S4 4-tab bottom nav + More sheet, shell/dialog scroll safety, touch-target foundation; desktop unchanged) · **12B Track/Dashboard/Calendar responsiveness ✅** (month-nav overflow fixed, grid cells enlarged at 320, Track date nav fluid + ≥40px controls, session-card collisions fixed, dashboard wrap fixes; desktop byte-identical) · **12C ✅ COMPLETE (2026-08-22)** — page responsiveness across Laboratory / Subjects / Quiz / Events (`docs/phase_12/phase_12c_implementation_report.md`, commit `31f75ca`) + the authorized cancellation-lifecycle & counting-consistency correctness fix (`docs/bugfix/cancellation_state_and_counting_consistency_report.md`) |
| 13 | PWA / Installability | ✅ **COMPLETE & FROZEN** — manifest, service worker, SVG icons, install prompt, standalone detection, online/offline state; zero backend/DB/migration changes; `tsc`/`build`/`diff --check` PASS |
| 14 | Firebase Retirement | ✅ **COMPLETE & FROZEN** — 14.0 audit ✅ · **14A frontend Firebase removal ✅** · **14B backend Firebase removal ✅** · **14C deployment/config cleanup ✅** · **14D firebase_uid cleanup ✅** (column dropped, migration `e1f2a3b4c5d6`) · **14E regression verification ✅** · **14F freeze & governance reconciliation ✅**. Firebase is fully retired from the active application (PostgreSQL + FastAPI + JWT + Next.js). |
| 15 | Legacy Web App + Legacy PWA Retirement | ✅ **COMPLETE & FROZEN** — legacy runtime removed (root `index.html`, `js/`, `css/`, `assets/`, `offline.html`, root `manifest.json`, root `service-worker.js`, legacy test scripts, legacy-only root package files); `timetable.json` preserved (active backend data dependency); docs/prompts marked as historical; active application = `frontend/` + `backend/` |
| 16 | Production Security Hardening | ✅ **COMPLETE & FROZEN** — JWT expiry bounded (8h env-configurable), password policy strengthened (8–128, letter+digit), in-process rate limiting (login 10/15min, register 5/h, 429 + Retry-After), security headers (nosniff/DENY/no-referrer/permissions; HSTS env-gated), global 500 handler + error-leak fixes, login timing equalization, structured logging, CORS env-driven; `verify_phase_16.py` 34/34 PASS; frozen verifiers green (6.5/10C/10D/11A); zero DB mutations |
| 17 | Data Integrity & Migration Hardening | ✅ **COMPLETE & FROZEN** — JWT production-secret guard ✅ (APP_ENV; `verify_phase_17_jwt_guard.py` 6/6) · integrity audit ✅ (zero orphans/duplicates/FK violations) · **NO MIGRATION REQUIRED** (single linear Alembic head `e1f2a3b4c5d6`) · backup/restore ✅ verified (isolated container) · retention policy ✅ documented (7 daily / 4 weekly / 3 monthly) · seed audit ✅ · semester-transition analysis ✅ · cleanup: NONE REQUIRED · working-DB mutations ZERO |
| 18 | Production Infrastructure | 🟡 **IN PROGRESS / PARTIAL** — **18.0 audit ✅ COMPLETE** · **18A containerization ✅ COMPLETE** · **18B env & secrets ✅ COMPLETE** · **18C backup automation ✅ COMPLETE** · **18D deployment & verification ⚠︝ PARTIAL** — rehearsal deployment verified end-to-end (5 services healthy, real backup executed + verified, isolated restore PASS, scheduler + retention + locking verified, no secrets); **production deployment BLOCKED** on missing infrastructure (no host/domain/credentials/off-host destination); 2 deployment defects fixed (PyJWT dep, Caddy /health route); `docs/phase_18/phase_18d_deployment.md` |
| 19 | CI/CD | ✅ **COMPLETE & FROZEN** — GitHub Actions quality gate (`.github/workflows/ci.yml`): integrity, backend, frontend, docker, compose, migrations, config-contract, backup-infra jobs; deployment gate disabled (`if: false`); all checks verified locally; migration validated on disposable postgres:16 to head `e1f2a3b4c5d6`; no deployment, no secrets |
| 20 | Production QA | ✅ **COMPLETE & FROZEN** — in-process/API QA across all surfaces PASS (auth, dashboard, track, history, calendar, events, quiz, lab, profile, security); cross-surface consistency verified (summary 50.0% = DB 12/12/24); frozen verifiers green (6.5 27/27, 6.6 36/36, 6.7 30/31 known, 12E 8/8, 16 34/34, 17 8/8); no critical defects; manual browser QA checklist provided for user; QA temp-user artifact removed; 5 attendance + 62 notification QA-window deltas reported for user review |
| 21 | Production Launch | ✅ **COMPLETE & FROZEN** — 21A/21A.1 account audit + approved cleanup ✅ · 21B feedback admin ✅ · 21C pre-flight gate closure ✅ (Gates A/B/C all RESOLVED) · 21D.0 free beta architecture ✅ · 21D.1 config hardening ✅ · 21D.2 provisioning + connection/alembic/Vercel/auth/migration audits ✅ · 21D.3 controlled localhost→Supabase migration ✅ (18 tables, counts/UUID/content/FK verified, ADMIN + PBKDF2 hash + 165 attendance 108/57 preserved, operator-verified login/dashboard/desktop/mobile/PWA) · 21D.4 production closure & governance reconciliation ✅. Production LIVE: Vercel + Render + Supabase. Closure: `docs/phase_21/phase_21d4_production_closure.md`. |
| 22 | Post-Launch | ✅ **COMPLETE** — 22.1 (Timetable Data-Scope Correction) ✅ VERIFIED IN PRODUCTION · 22.2 (Production Parity & Mutation Reliability) ✅ · 22.3 (Student Elective Selection & Timetable Resolution) ✅ · 22.4 (Departmental Elective Resolution Across All Engines & Surfaces) ✅ — next: Phase 23 (Academic Architecture Evolution). |
| 23 | Academic Architecture Evolution | 🟢 **23.1 COMPLETE** (schema foundation) · **23.2 COMPLETE** (curriculum schema hardening) — 23.0 (Architecture Discovery & Implementation Blueprint) ✅ COMPLETE (read-only, 2026-08-27) + **blueprint reconciled per 10 corrections (2026-08-27)** + **final governance consistency correction (2026-08-27)** · **23.1 (Academic Hierarchy & Enrollment Schema Foundation) ✅ COMPLETE (2026-08-27)** — migration `c8d9e0f1a2b3` · **23.2 (Curriculum model) ✅ COMPLETE (2026-08-27)** — migration `d0e1f2a3b4c5` (UNIQUE(code, semester_id) on subjects) · **23.3 (Student Academic Assignment) ✅ COMPLETE (2026-08-28)** — migration `e3f4a5b6c7d8` (additive `enrollment_type` COMPULSORY/ELECTIVE + deterministic backfill; `/student/me` additive subsection_name + elective_i/elective_ii). **Not applied to production** (operator boundary) · **23.4 (Authoritative Student Context Service) ✅ COMPLETE (2026-08-28)** — `StudentContextService` + `StudentContext` read model (service-layer, read-only, no schema change); consumers migrated: `/student/me`, Dashboard, Quiz eligibility, Calendar, Analytics, Attendance History; equivalence verified. · **23.5 (Elective/Catalog Redesign) ✅ COMPLETE (2026-08-28)** — DB-backed catalog (`subjects.elective_slot` nullable enum; migration `f5a6b7c8d9e0`); `ElectiveResolver` DB-driven (no hardcoded constants); registration validates against DB catalog. **Not applied to production** (operator boundary) · **23.6 (Actual Occurrence Architecture) ✅ COMPLETE (2026-08-28)** — per-subject occurrence outcomes (`occurrence_outcomes` + `OccurrenceOutcomeType`; migration `f6a7b8c9d0e1`); synchronizer creates outcomes for subject-specific elective events; read queries apply them per student (elective isolation, no leakage). **Not applied to production** (operator boundary) · **23.7 (Event-Scope + MODIFIED) ✅ COMPLETE (2026-08-28)** — `CLASS_MODIFIED` event type + `MODIFIED` outcome (migration `f7a8b9c0d1e2` = ALTER TYPE ADD VALUE); event registry rule + subject-scoped-only rejection; synchronizer produces MODIFIED outcomes on anchor session for targeted concrete subject; `_reconcile_outcomes` generalized to non-elective subject anchors; read path exposes MODIFIED without changing extra/cancelled flags. **Corrective migration `f8a9b0c1d2e3` (2026-08-29): `ALTER TYPE eventtype ADD VALUE 'CLASS_MODIFIED'`** — Phase 23.7 omitted the PG `eventtype` enum value (exposed by the live Phase 23.9 verifier); applied to the local dev DB only. **Not applied to production** (operator boundary) · **23.8 (Quiz Integration — MODIFIED + subject-scoped quiz reality) ✅ COMPLETE (2026-08-28)** — MODIFIED = occurrence metadata for the quiz pipeline (conducted class; quiz dates/identity/windows/eligibility unchanged; subject isolation via outcome join key); one integration fix (cancellation wins over modification); `verify_phase_23_8.py` added (DB-based, self-cleaning). **Not applied to production** (operator boundary). **23.9 (Attendance Mutation Gate) ✅ COMPLETE / VERIFIED (2026-08-29)** — outcome-aware mutation safety (no migration): `POST /api/v1/attendance` rejects (409) on CANCELLED outcome for the student's resolved concrete subject; MODIFIED/normal allowed; elective isolation; `verify_phase_23_9.py` **PASS 26/26** on the local dev DB after the corrective migration. **Not applied to production** (operator boundary). **23.10 (Student-Facing Read Models) ✅ COMPLETE (2026-08-29)** — `outcome_type` + `elective_slot` exposed on daily-sessions/history responses; all student-facing surfaces audited and confirmed on the canonical architecture; `verify_phase_23_10.py` PASS 26/26 (isolation matrix). **Not applied to production** (operator boundary). **23.11 (API Scope & Authorization) ✅ COMPLETE (2026-08-29)** — migration `f9a0b1c2d3e4`: `adminrole` enum + `admin_scopes` table (role-scope CHECK constraint); `AuthorizationService` with composable scope checks; legacy ADMIN → HEAD_ADMIN; wired into laboratory/feedback admin endpoints + EventService; student audit confirmed scoped; `verify_phase_23_11.py` PASS 23/23. **Not applied to production** (operator boundary). **23.12 (Migration Gate) ✅ COMPLETE (2026-08-29)** — Phase 23 migration chain audited: 25 migrations, single linear chain, one head `f9a0b1c2d3e4`; fresh disposable-DB migration to HEAD (25/25) + downgrade/rollback cycle + idempotency verified; drift audited (legacy timestamp-nullable convention only); adminrole/CHECK/FK semantics proven; offline upgrade/downgrade SQL validated; data-integrity baseline unchanged; `verify_phase_23_12.py` PASS 52/52. No migration created. **Not applied to production** (operator boundary). Phase 24 (Admin Portal) pending. |
| 24 | Admin Portal | 🟡 **24.0 DISCOVERY COMPLETE** (2026-08-29, `docs/phase_24/phase_24_0_admin_portal_discovery.md`) · **24.1 (Admin Identity + Portal Shell) ✅ COMPLETE (2026-08-29)** — additive `GET /api/v1/admin/me` (DB-authoritative identity via `AuthorizationService`; no schema change) + `(admin)` frontend route group, AdminShell, backend-driven loading/unauthorized/failure states, truthful navigation. · **24.2 (HEAD Admin Dashboard) ✅ COMPLETE (2026-08-29)** — additive read-only `GET /api/v1/admin/dashboard` (require_head_admin; bounded aggregate queries; academic/curriculum/student/schedule/events/quizzes/attendance overviews + factual data-quality warnings; no schema change) + frontend dashboard replacing the 24.1 placeholder inside the existing AdminShell. · **24.3 (Student Management — READ) ✅ COMPLETE (2026-08-29)** — additive scoped read-only `GET /api/v1/admin/students` + `GET /api/v1/admin/students/{id}` (require_any_admin + DB-authoritative scope: HEAD all, CLASS assigned sections, ELECTIVE choice-roster, SUBSECTION inert-empty; no client scope params; detail via `StudentContextService`; no schema change) + Students list/search + detail pages, AdminShell nav, dashboard updates; verifier PASS 40/40 on local dev DB. · **24.4 (Student Management — WRITE) ✅ COMPLETE (2026-08-29)** — status/subsection/elective mutations from the student detail view; schema change + Alembic migration `eb880e108f19` (`users.is_active`), applied locally only. · **24.5 (Academic Structure Management) ✅ COMPLETE (2026-08-29, independent verification + correction pass)** — HEAD_ADMIN-only sessions/semesters/sections/subsections CRUD (no destructive deletes), single-active-session invariant, registration-ambiguity warnings, structure UI at `/admin/structure`; **no new migration/schema change** (alembic head `eb880e108f19` unchanged); authoritative verifier `verify_phase_24_5.py` PASS **46/46** on local dev DB (auth matrix, CRUD, activation cycle, PATCH semantics, no client scope, data-integrity baseline restored); stray root `page.tsx` removed; frontend 403/error states fixed; `compileall`/`tsc`/ESLint/`git diff --check` clean; 24.3 verifier regression 40/40. Batch student management / CSV import deferred. Local development only; production untouched. · **24.6 (Curriculum & Subject Management) ✅ COMPLETE (2026-08-29)** — HEAD_ADMIN-only subject CRUD + elective catalog management (`elective_slot`) + scoped reads (HEAD all / CLASS own-semester / ELECTIVE exact subject / SUBSECTION inert); code + semester immutable (409), anchor BCS-054/BCS-058 code+slot frozen (409), slot changes guarded against existing student elective choices (409), no DELETE (405), experiment catalog reused (existing lab endpoints); **no migration/schema change** (alembic head `eb880e108f19` unchanged); authoritative verifier `verify_phase_24_6.py` PASS **46/46** on local dev DB; regressions 24.3 40/40 + 24.5 46/46; `compileall`/`tsc`/ESLint/`git diff --check` clean. Local development only; production untouched. · **24.7 (Timetable Management) COMPLETE / FROZEN (2026-08-30)** — **24.7-A (Timetable Domain Foundation) ✅ COMPLETE** — extended `timetable_entries` (EXPECTED schedule domain) with `subsection_id`/`room`/`is_active`/`sort_order`, CHECK guards (end>start, day 0–6), composite section↔subsection FK, `uq_subsections_section_id`, admin read schemas; migration `c4d5e6f7a8b9` (additive, 28 rows preserved, upgrade/downgrade verified locally). · **24.7-B (Repository, Service & Conflict Detection) ✅ COMPLETE** — `AdminTimetableRepository` (scope-aware list/detail/conflict-candidate queries), `AdminTimetableService` (academic-context validation, subject/subsection/elective-slot/time validation, deterministic conflict detection, scope resolution via AuthorizationService, domain error hierarchy), `verify_phase_24_7b.py` PASS 29/29; · **24.7-C (Admin Timetable CRUD API) ✅ COMPLETE** — additive `/api/v1/admin/timetable` endpoints (scoped list with session/semester/section/subsection/day/subject/elective/active filters, detail, create, PATCH update, deactivate, duplicate) wired over `AdminTimetableService` with domain-error→HTTP mapping (401/403/404/409/422); reads `require_any_admin` + server-side scope;    writes gated to HEAD_ADMIN + CLASS_ADMIN (assigned section) per the Phase 24.0 matrix; `verify_phase_24_7c.py` PASS 30/30; · **24.7-D (Admin Timetable Builder UI) ✅ COMPLETE** — `/admin/timetable` page (scoped filters: session/semester/section/subsection/day/active/subject/elective), weekly grid grouped by day with per-entry cards (time, subject, class type, room, elective slot, active state), create/edit/deactivate/duplicate dialogs with reusable `TimetableEntryForm`, explicit deactivation confirmation, loading/error/403/empty states, SWR revalidation after successful mutations (never optimistic on failure), AdminShell nav + dashboard promotion; types/hooks mirrored from the backend contract (canonical enums); UI is NOT the security boundary — backend write gate (HEAD + CLASS) is authoritative; `tsc` PASS · ESLint PASS; · **24.7-E (Mutation Workflow Completion) ✅ COMPLETE** — create/edit/duplicate/deactivate workflows completed: create + edit dialogs close only after backend acceptance and revalidation; edit sends ONLY changed fields (PATCH "preserve omitted values", so non-scheduling edits on inactive entries do not trip INACTIVE_PARENT and subsections are never silently cleared); duplicate dialog preserves the source's active state and states exactly which fields are copied vs overridable; deactivate dialog surfaces backend errors (no silent failure, no fake success); 409 conflicts render a styled warning banner showing only the backend's message (day/time/subject as returned); dialogs keyed per entry (no stale edit data); create    dialog remounts fresh per open (no stale form state); filters preserved across mutations — revalidation decides row visibility (deactivated rows leave the active view naturally); `tsc` PASS · ESLint PASS. · **24.7-F (Conflict-Aware UX) ✅ COMPLETE** — structured 409 conflict contract (`detail.message` human-readable with scope context + `detail.conflicts` list of backend-resolved entries: id/subject/section/subsection/day/times/elective_slot, UUIDs stringified, JSON-serializable); `apiFetch` preserves HTTP status + attaches response body (additive); form and duplicate dialogs render the structured conflicting-entry list verbatim (no client-inferred conflict data); 409 keeps form values, never closes the dialog, never shows success; concurrency is backend-authoritative — every mutation re-reads the current DB state and re-runs conflict detection against it, so a stale frontend can never bypass validation after another admin changes the timetable; entry cards now render a time-position bar (08:00–18:00 window) making overlapping entries visually obvious;    `verify_phase_24_7c.py` still PASS 30/30. · **24.7-G (Student Timetable Resolution) ✅ COMPLETE** — the student-facing `GET /api/v1/timetable` endpoint now derives the student timetable from the student's academic context (section + subsection), their LOCKED elective choices, and the authoritative timetable (no hardcoded current-semester assumptions): student-scoped repo query (`get_weekly_entries_for_student`) returns ACTIVE entries only, section-wide entries, and the student's OWN subsection entries (other subsections' private schedules excluded); shared DE-I/DE-II slots resolve to the student's locked concrete subject — a slot entry with NO locked choice is OMITTED (the anchor BCS-054/BCS-058 is never exposed merely because it exists in the timetable config); common subjects remain visible; `verify_phase_24_7g.py` PASS 25/25 (Student A DE-I BCS-054/DE-II BCS-058, Student B DE-I BCS-052/DE-II BCS-055, Student C no choices; subsection isolation, no anchor leakage, no cross-student leakage, inactive excluded, baseline restored). Regressions 24.3 40/40 · 24.5 46/46 · 24.6 46/46 · 24.7c 30/30. · **24.7-H (Completion Gate) ✅ COMPLETE** — full conflict matrix (exact/partial/containing/contained overlap rejected, adjacent allowed, different day/scope, inactive allowed, self-edit safe) 9/9; security matrix (HEAD/CLASS/SUBSECTION/ELECTIVE/STUDENT cross-scope via direct API) 9/9; academic matrix (Student A/B, no anchor/cross leakage, subsection isolation, inactive excluded) 6/6; data integrity (baseline restored, attendance/quiz/events/choices unchanged) 3/3; `verify_phase_24_7h.py` PASS 27/27. All regressions green. **24.7 FROZEN.** Next: Phase 24.8 - Quiz Schedule Manager. COMPLETE (2026-08-30) - additive admin quiz schedules API (GET/POST/PATCH /quizzes, GET /quiz-cycles with thresholds); server-side QUIZ_DAY event synchronization (create/deactivate/date-move, EventSessionSynchronizer, single-transaction atomicity); scope-aware reads (HEAD all, CLASS own semester, ELECTIVE own subject, SUBSECTION inert, STUDENT 403); HEAD-only writes; validation (subject/date-in-semester/cycle/elective-slot/duplicate); /admin/quizzes UI (table, create/edit dialogs, cycle filters, event-status badges); AdminShell nav + dashboard promotion; no schema/migration (alembic head c4d5e6f7a8b9 unchanged); verifier 34/34 (auth, CRUD, sync, elective isolation, idempotency, baseline). All regressions green. Next: Phase 24.9 - Event Manager. COMPLETE (2026-08-30) - additive admin event control-plane API (GET/POST/PATCH/DELETE /admin/events, DELETE = safe deactivation); QUIZ_DAY ownership guard (schedule-managed QUIZ_DAY cannot be desynced through the generic Event Manager - 409; quiz dates belong to /admin/quizzes); canonical EventService/registry/synchronizer reused; scoped reads (HEAD all, CLASS own-semester subjects, ELECTIVE exact subject, SUBSECTION inert, STUDENT 403); HEAD-all writes per capability matrix (CLASS own-semester subject events, ELECTIVE own-subject events, global/closure HEAD-only); `/admin/events` UI (table, filters, create/edit/deactivate dialogs, quiz-managed badge); AdminShell nav + dashboard promotion; no schema/migration (alembic head c4d5e6f7a8b9 unchanged); verifier 40/40 (auth, scope isolation, registry validation, synchronizer effects, elective isolation, QUIZ_DAY ownership, client spoofing, arbitrary UUID, deactivation-not-deletion, baseline restored). Next: Phase 24.10 - Subject-Specific Elective Events. COMPLETE (2026-08-30) - divergent elective-subject outcomes proven through the CANONICAL Phase 23.6 pipeline (subject-scoped events -> occurrence_outcomes on the shared anchor session; no second engine, no per-student rows); admin read model gains subject_slot + can_mutate; /admin/events dialog gains slot-wide (HEAD-only) vs concrete-subject targeting with unambiguous slot-vs-concrete distinction; no schema/migration (alembic head c4d5e6f7a8b9 unchanged); verifier 35/35 (divergence matrix, EXTRA fallback, idempotency, isolated reversal, QUIZ_DAY guard, isolation, spoofing, baseline); verify_phase_24_9.py E4 cleanup defect fixed (canonical deactivation, 40/40 restored). Next: Phase 24.11 - Admin & Scope Management. NOT STARTED. | · **24.11 (Admin & Scope Management) ✅ COMPLETE / FROZEN (2026-08-30)** — admin user list/detail (effective roles + scopes) + scope assign/deactivate/reactivate (HEAD_ADMIN-only; matrix FULL|NO|NO|NO); `admin_scopes` table reused as-is, **no migration** (alembic head `c4d5e6f7a8b9` unchanged); admins area UI at `/admin/admins` (nav + dashboard); verifier `verify_phase_24_11.py` PASS **31/31** x2; regressions 24.3-24.10 all PASS; account creation/provisioning deferred per decision gate §25 (gate 8). · **24.12 (Attendance Admin & Analytics) ✅ COMPLETE / FROZEN (2026-08-30)** — read-only scoped attendance analytics: per-section aggregates (HEAD all / CLASS own), per-subject roster aggregates (HEAD all / CLASS own-semester / ELECTIVE own), per-student canonical analytics read (scope-checked); attendance CORRECTION deferred to §25 gate; `admin_scopes`/AuthorizationService reused; **no migration** (alembic head `c4d5e6f7a8b9` unchanged); /admin/attendance UI + nav + dashboard; verifier `verify_phase_24_12.py` PASS **30/30** x2; regressions 24.3-24.11 all PASS. · **24.13 (Integration & Hardening) ✅ COMPLETE / FROZEN (2026-08-30)** — cross-phase integration audit: outcome-application fix (admin aggregates now apply Phase 23.6 occurrence outcomes correctly); roster role fix (admin STUDENT-role filter excludes legacy ADMIN account from attendance analytics); 24.13 verifier 30/30 x2; regressions 24.3-24.12 all PASS; auth boundary, scope isolation, elective resolution, event→session, quiz→eligibility, dashboard semantics all verified consistent; **no migration** (alembic head `c4d5e6f7a8b9` unchanged). **PHASE 24 (ADMIN PORTAL) = COMPLETE.**

---

# 🟢 Phase 0 — Architecture & Reality Audit

**Status: COMPLETE / FROZEN**

Established the actual baseline:

- Frontend/backend architecture
- PostgreSQL state
- API surface
- Existing engines
- Firebase retirement status
- Existing pages/components
- Database relationships
- Existing data gaps
- Technical debt

### Freeze rule

Do not repeat this audit unless a later discovery directly contradicts the baseline.

---

# 🟢 Phase 1 — Design System Foundation

**Status: COMPLETE / FROZEN**

Implemented the visual foundation:

- Dark visual system
- Typography
- Color system
- Cards
- Badges
- Progress indicators
- Semantic status variants
- High-density layouts

Primary accent:

```text
#3B82F6
```

Legacy purple/magenta styling is not part of the target design system.

### Freeze rule

Do not redesign or rewrite these primitives merely for preference. Reopen only for a genuine defect or a deliberate product decision.

---

# 🟢 Phase 2 — Desktop Shell & Global UX

**Status: COMPLETE / FROZEN**

Implemented:

- Desktop top navigation
- User/profile menu
- Profile modal
- Appearance modal
- Settings modal
- Feedback modal foundation
- Install-app foundation
- Global dialog behavior
- Active navigation
- Authentication-aware shell
- Logout

Firebase-specific shell dependencies were removed.

### Freeze rule

Do not revisit the shell unless a real bug or explicit product requirement requires it.

---

# 🟢 Phase 3 — Home Dashboard

**Status: COMPLETE / FROZEN**

Implemented:

- Greeting
- Today's Attendance
- Weekly attendance
- Overall attendance
- Quiz snapshot
- Attention items
- Upcoming events
- Loading states
- Error states
- Empty states
- Dashboard aggregation endpoint

The dashboard consumes real backend data.

### Freeze rule

Do not repeatedly rebuild the dashboard because of visual preferences. Reopen only for real defects or later feature integration.

---

# 🟢 Phase 4 — Track Attendance

**Status: COMPLETE / FROZEN**

Implemented:

- Daily attendance view
- Date navigation
- Session cards
- Present / Absent
- Attendance changes
- Cancelled-session handling
- Mark All Present
- Cache/optimistic update behavior
- Enrollment authorization
- Backend daily-session endpoint

### Critical product requirement

> **15 July 2026 → current date**

Track must expose the student's complete semester attendance history.

**✅ SATISFIED in Phase 4.5.2** — Track navigates the full semester range (bounds from
`/student/me`, no hardcoded dates), shows every session type including practicals, and
supports manual historical re-entry through the canonical mutation endpoint. The 26
historical lab sessions remain unmarked pending the user's manual reconstruction.

If the historical data cannot be reliably recovered, manual re-entry is acceptable.

**Rebuilding the architecture is not acceptable.**

### Freeze rule

The attendance architecture is considered foundational. Do not rewrite it to solve a data problem.

---

# 🟢 Phase 4.5 — Data Integrity & Account Foundation

**Status: COMPLETE / FROZEN** — 4.5.1 audit ✅ · 4.5.2 historical Track ✅ · 4.5.3 Real Sign Up ✅.

## 4.5.1 — Historical Attendance Audit

**Status: COMPLETE** (read-only, 2026-08-13 → report `docs/phase_4_5_data_audit.md`).

Verdict: **B — PRESERVE WITH MANUAL CORRECTION**.

- Database structure healthy, zero structural corruption.
- 78 records exist (54 ATTENDED / 24 MISSED), 124 sessions in semester range, 46 unmarked (20 theory + 26 lab).
- Labs (BCS-551 ×8, BCS-552 ×10, BCS-553 ×8) never marked; laboratory tables empty.
- 4.5.1-B forensic investigation (report `docs/phase_4_5_1B_lab_attendance_forensics.md`) PROVED the legacy
  PWA silently skipped lab subjects in analytics (`getAttendanceData` required a QUIZ milestone and returned on
  error) — lab marking worked mechanically but counted nowhere. The PostgreSQL architecture does not repeat this
  defect.

### Possible verdicts

#### A — PRESERVE

Existing data is sufficiently complete and trustworthy.

#### B — PRESERVE WITH MANUAL CORRECTION

Most data is usable, but some manual correction/re-entry is required.

#### C — RESET DEVELOPMENT DATA

The data itself is sufficiently unreliable that a clean development baseline is safer.

### Critical rule

**Do not delete or reset anything during the audit.**

---

## 4.5.2 — Historical Track Coverage

**Status: COMPLETE** (2026-08-14).

- Track navigates the full semester history **2026-07-15 → current date**, bounded by the real
  `semester_start`/`semester_end` from `/student/me` (no hardcoded dates); date picker + Today + clamped arrows.
- Every scheduled session is visible: LECTURE, TUTORIAL, PRACTICAL/LAB, Pending, Attended, Missed, Cancelled.
- Practical sessions (BCS-551/552/553) appear as normal attendance sessions — the legacy
  quiz-window/attendance confusion is not repeated.
- Missing record = PENDING (no database row is created for pending).
- One canonical mutation endpoint (`POST /api/v1/attendance`) handles historical marking and Present↔Absent
  corrections; cancelled sessions rejected (409); reads scoped to the student's enrolled subjects; unique
  constraint preserved.
- Root-cause fix landed: frontend `AttendanceStatus`/`ClassType` enums corrected to the live backend contract
  (`Attended`/`Missed`/`Pending`, `P`), which had silently broken Track marking and history state rendering.
- Analytics engines untouched; verified labs flow through the canonical pipeline (`GET /attendance/summary/BCS-551`
  → practical 8/8 PENDING).
- The 26 historical lab sessions remain unmarked by design — the user establishes historical truth manually
  through Track. No invented attendance, no laboratory experiment rows.

---

## 4.5.3 — Real Sign Up

**Status: COMPLETE** (2026-08-14).

- `POST /api/v1/auth/register` + `/signup` page (Full Name, 13-digit Roll Number, Password,
  Confirm Password, show/hide, Create Account, link to Login).
- **Enrollment provisioning**: academic context resolved from authoritative configuration only —
  active `AcademicSession` → its `Semester` → its `Section` → all semester `Subject` rows — created
  transactionally with the user. The client cannot submit section/semester/session/subject IDs.
  Single-section semesters auto-assign; ambiguous configurations are rejected explicitly.
- **firebase_uid**: made NULLABLE (migration `c3d4e5f6a7b8`) for PostgreSQL-native identity;
  all 29 legacy UIDs preserved; column retained for Phase 14 (Firebase Retirement).
- **Passwords**: same `pbkdf2_sha256` format/verifier as login (`hash_password` added to
  `app/core/security.py`); never logged or echoed.
- **JWT**: issued immediately after registration through the exact `create_access_token` used by
  login (no second auth flow); student enters the app shell directly.
- Duplicate roll number → 409 (`IntegrityError` race guard); validation 422; ambiguous academic
  config 409/503; all failures roll back — no partial accounts, no orphan enrollments.

**Firebase must not return.**

---

# 🟢 Phase 5 — Attendance History

**Status: COMPLETE / FROZEN** (2026-08-14).

The History page is now a production-quality, session-based view of the
student's real attendance history:

- **Canonical data**: `GET /api/v1/attendance/history` (single endpoint, reused and
  extended in place) returns every scheduled class session of the student's enrolled
  subjects from the real semester start through today — the same `class_sessions` +
  `attendance_records` pipeline Track consumes. Missing record = **Pending**; cancelled
  sessions are their own state (never absent). No duplicate attendance source; no
  React-side calculation.
- **Semester bounds**: range resolved from the authenticated student's academic context
  (`/student/me` semantics via the same repository), clamped to `semester_start` and today
  (never the future), date inputs bounded the same way. No hardcoded dates.
- **Summary strip**: Total / Present / Absent / Pending / Cancelled / % computed
  server-side over the full filtered result set (aggregate FILTER query), not per page.
- **Filters (server-side)**: enrolled-subject select, attendance-state select
  (Attended/Missed/Pending/Cancelled), date-from/to (timezone-safe YYYY-MM-DD), and
  debounced search across subject code, subject name, class type, and date.
- **Pagination**: existing `limit`/`offset`/`total_count` contract extended with the new
  filters; "Load more" appends pages with id-based deduplication; filters reset offset and
  never mix result sets.
- **States**: loading skeletons, full error state, and truthful empty states
  (no classes in semester vs no matches for filters).
- **Authorization**: reads scoped to the authenticated user's enrollments end-to-end
  (`user_id` filter + `StudentEnrollment` join + subject filter on enrollments).
- **Consistency verified**: 2026-07-15 history (6 sessions, 3 Present / 3 Absent) matches
  Track's daily view exactly; Aditya's manual 07-17 BCS-553 practical mark appears
  Attended in both; summary pct 69.6% = 55/79 recorded (matches the dashboard).

### Architectural rule

History and Track consume the **same canonical attendance records** — satisfied, with
the `GET /attendance/history` endpoint being the single session-history source.

---

# 🟡 Phase 6 — Calendar & Academic Events

**Status: COMPLETE & FROZEN (2026-08-15)** — 6.0 audit (docs/phase_6_0_calendar_events_audit.md) ✅ · 6.1 foundational corrections ✅ (weekend convention, MID_SEMESTER_BREAK closure, /events read contract, dashboard enrollment scoping) · 6.2 calendar read model & API ✅ (`GET /api/v1/calendar?year=&month=`) · 6.3 calendar UI ✅ (`/calendar` route rendering the read model directly) · 6.4 events page upgrade ✅ (Upcoming/Today/Past grouping + filters on `/tools/events`) · 6.5 persistence + admin auth + seeding ✅ (role system, admin mutation API, validation registry, 17 quiz-event seeds) · 6.6 event→engine integration ✅ (session synchronizer: closures cancel, CLASS_CANCELLED cancels, EXTRA_*/SURPRISE_QUIZ materialize, substitution/working-Saturday project, idempotent + transactional + attendance-safe) · 6.7 verification/freeze ✅ (90/90 combined checks, exact baseline restored, architectural review clean).

Build the complete calendar/event experience.

## Calendar

- Month/day navigation
- Working days
- Weekends
- Holidays
- Academic events
- Class schedule
- Selected date
- Event indicators

## Events

- Upcoming
- Today
- Past
- Event details
- Event types
- Holiday indicators
- Substitution schedules

## Event persistence

Eventually support controlled event mutation:

```text
Admin
  ↓
Create Event
  ↓
Academic Events
  ↓
Calendar Engine
  ↓
Track / Dashboard / Quiz Eligibility
```

The event system must feed the existing engines instead of creating parallel rules.

---

# 🟡 Phase 7 — Quiz Eligibility & Schedule UX

## Phase 7.3 — Quiz Eligibility Hardening

Phase 7.3 is **COMPLETE & FROZEN**. This incorporates the final hardening passes originally requested/tracked outside the main roadmap structure (historically tracked as Phase 4A/4B/4C logic):

- **Backend reachability consistency:** Fixed zero-pending optimization reachability semantics. Top-level optimization now prefers reachable routes before minimizing attendance deficit, preserving Criterion I tie-breaking where appropriate. Dashboard attention classification now receives consistent reachability information.
- **Frontend safety:** Unreachable NOT_ELIGIBLE states no longer display misleading actionable Must Attend/Safe Skip guidance. Unknown/future eligibility states now degrade safely to a neutral "Unknown" badge instead of crashing. `SubjectCategory` TypeScript contract corrected to match backend values.
- **Cleanup & Infrastructure:** Removed dead `combined_threshold` plumbing from the service. Purged stale `__pycache__` files from tracking and local environments (which previously masked canonical math). Normalized Quiz I/II/III presentation labels without changing the persisted API contract. Added missing trailing newline to `eligibility_engine.py`. Added SUPERSEDED notice to the stale Phase 7.1 historical implementation report.
- **Verification:** Phase 1 eligibility verifier: 18/18. Phase 7.1 verifier: 26/26. Phase 3 propagation verifier: 26/26. TypeScript, ESLint, and production build all green. Database baseline restored exactly.

### 🔒 The Authoritative Quiz Eligibility Contract

The following semantics are fully verified, implemented, and frozen:
- Both Criterion I and Criterion II use: `(Lecture % + Tutorial %) / 2`
- No-tutorial subjects collapse naturally to lecture percentage.
- Quiz thresholds: Quiz I = 70%, Quiz II = 75%, Quiz III = 75%.
- Criterion I uses the cycle-specific attendance window.
- Criterion II uses the cumulative attendance window from semester commencement.
- Final eligibility uses **Criterion I OR Criterion II**.
- Must Attend / Safe Skip is calculated per criterion using that criterion's own window.
- Top-level optimization selects the best reachable route.
- Active `QUIZ_DAY` AcademicEvents are authoritative for quiz dates.
- Option-A quiz-day occurrences are independent attendance-bearing sessions but excluded from L/T eligibility counts.
- Subject isolation is preserved. Event lifecycle changes propagate through eligibility automatically.
- **The backend remains the authoritative source of eligibility mathematics and verdicts.**

The existing eligibility engine remains authoritative. Do not move quiz calculations into React.

---

# 🟡 Phase 8 — Attendance Analytics / Intelligence

**8.0 AUDIT COMPLETE (2026-08-15) — PASS** — read-only audit + contract design
(`docs/phase_8_0_attendance_analytics_audit.md`). No code, no DB change.
Headline findings: the current system has no analytics layer but every existing
surface already consumes the canonical engines (no second engine); the dashboard
service is the de-facto aggregator; **4 legacy gaps** must be bridged additively
(practical %, subject-level 75% must-attend/safe-skip, overall forecast,
forecast-impact deltas — all extensions of existing engine outputs); 2 React
display duplications + a hardcoded cycle=1 flagged for removal; N+1s in the
dashboard quiz snapshot and subject summaries documented; AT-RISK state and
trend series are roadmap intent with **no definition** — withheld pending
product decisions. Recommended 8.1 scope: backend-only additive analytics read
model (`/analytics/overview` + extended `SubjectAttendanceSummary`) + N+1 fixes,
consuming the canonical engines; no UI, no schema change, no new formula.

Turn the existing calculations into a strong intelligence experience.

## Overall analytics

- Current percentage
- Lecture/tutorial breakdown
- Subject-wise percentage
- Weekly trend
- Semester trend

## Forecasting

Examples:

> If you attend the next 3 classes…

> You can safely skip 2 lectures…

> You need 5 consecutive classes to reach 75%…

## Risk states

```text
SAFE
WATCH
AT RISK
CRITICAL
```

### Architectural rule

Dashboard, Track, History and Quiz Eligibility must remain consistent because they derive from the same canonical calculations.

This phase improves **analytics presentation and intelligence**, not by repeatedly rebuilding the core engines.

**8.3 ANALYTICS PAGE COMPLETE (2026-08-16)** — the roadmap's T-3 product decision
(dedicated Analytics page) is resolved: new `/analytics` route rendering the
canonical Phase 8.1 read model (`GET /api/v1/analytics/overview`) — overall
current/forecast + recorded-only semantics, the full Monday-start weekly
semester-trend series (null-gap, never 0%), and subject-wise rows with
Attendance Health, L/T/P counts, practical %, and the backend 75% optimizer
(must-attend / safe-skip / unreachable). Pure frontend composition — no backend
change, no DB change, no new formula, no React math; the legacy 3-state
SAFE/WATCH/CRITICAL overall status and the Phase 8.2 4-state subject health are
rendered exactly as emitted. `npx tsc --noEmit` · ESLint · `next build` green;
Phase 8.1 verifier 22/22 + Phase 8.2 verifier 18/18 re-run green; DB baseline
byte-identical. **PAGE REMOVED (2026-08-17)** — the dedicated `/analytics` route
and its nav entry were removed; the Phase 8.1 read model remains and is consumed
by the Dashboard (overall forecast + weekly series) and the Attendance tab
(per-subject health/optimizer/practical %). No backend/DB change.

## Phase 8.2 — Attendance Monitoring + Lab Domain Correction (COMPLETE 2026-08-15)

Attendance (/subjects) is now a pure attendance-monitoring page: quiz strategy
(must-attend / safe-skip / forecast / current-vs-forecast / quiz-window
denominator / required 75% / Defaulter badge) was removed from the UI — those
concepts remain only on the Quiz Eligibility surface. The reported "11 / 14"
denominator was traced to the canonical session table (14 real lectures through
today per theory subject) — not a quiz window — and is verified as such.
Attendance Health (backend-owned, additive `health` field, never banded in
React): **HEALTHY ≥ 75% · WATCH 65–<75% · AT RISK 60–<65% · CRITICAL <60%**
(supersedes the legacy SAFE/WATCH/CRITICAL presentation on the Attendance card;
`status` stays emitted for the frozen dashboard/analytics surfaces).

The laboratory domain is now explicitly separated: practical attendance =
canonical `ClassSession(PRACTICAL)` + `AttendanceRecord`; experiment
curriculum/progress = `laboratory_experiments`/`laboratory_records` (empty — no
fabricated data); mid-sem = an ADMIN-designated **session-level fact**
(`class_sessions.designation`, migration `e5f6a7b8c9d0`) tied to an actual
scheduled practical — never inferred from experiment counts and never given a
computed date. The missing faculty scheduling authority is documented (no
faculty system invented). See `docs/phase_8_2_implementation_report.md`;
verification 18/18 + full frozen regression.

**Authorized baseline/fixture change (final freeze, 2026-08-15):** the frozen
`verify_phase_7_1.py` check-23 fixture moved from `records == 89` to
`records == 92` (a FIXED expected value — no dynamic baseline). The +3 are
legitimate BCS-501 attendance marks (2026-08-04 LECTURE/TUTORIAL ATTENDED,
2026-08-13 LECTURE MISSED) entered through the canonical student attendance
mutation path BEFORE this audit; they are not verifier/test residue and must
never be deleted to satisfy the old fixture. This is an authorized
baseline/fixture change only — no product or attendance-engine change.

---

# 🟡 Phase 9 — Laboratory System

## Phase 9.0 — Laboratory Domain Audit & Specification (COMPLETE 2026-08-15)

READ-ONLY audit + specification only (no code/schema/API/UI). The laboratory
domain is a clean, intentionally empty foundation: practical attendance is
canonical `ClassSession(PRACTICAL)` + `AttendanceRecord` (verified 18/18),
experiment curriculum/progress tables (`laboratory_experiments` /
`laboratory_records`) are empty by design (no authoritative data — nothing
fabricated), and the mid-sem practical is an ADMIN-designated session-level
fact (`class_sessions.designation`, Phase 8.2) that never alters attendance
counting.

Key audit findings:

- **No engine/attendance-rule change required** — labs already flow through
  the canonical pipeline; cancelled excluded; pending stays pending; labs
  excluded from quiz eligibility.
- **Gaps**: (1) authoritative experiment curriculum (identity/titles/count)
  is UNKNOWN — legacy `LAB_RULES` "10 experiments" is not authoritative;
  (2) no experiment↔session linkage (`LaboratoryRecord.date_conducted` is a
  bare date); (3) no FACULTY role — only ADMIN; (4) no audit identity on
  designation/signature; (5) `/tools/laboratory` hosts the Track page (naming
  artifact).
- **Hard boundaries kept**: no `experiments >= 5 ⇒ mid-sem` rule, no fake
  mid-sem dates, no fabricated curriculum, students can never designate
  mid-sem, Quiz Eligibility and Phase 6 calendar architecture untouched.
- **Blocking product decisions** (before Phase 9.1): authoritative curriculum
  source · FACULTY role vs ADMIN-only · audit identity · experiment↔session
  linkage · mid-sem progress check vs free choice · student mutation boundary
  · grading/viva.

Full audit: `docs/phase_9_0_laboratory_domain_audit.md` (20 sections +
verification). **Phase 9.1 not started.**

## Phase 9.0b — Product Decision Review (COMPLETE 2026-08-15)

Decision matrix produced in `docs/phase_9_product_decisions.md` — one
recommendation per blocking decision, each labeled FACT-from-repository vs
PRODUCT RECOMMENDATION vs UNKNOWN/REQUIRES-REAL-WORLD-INPUT:

1. **Curriculum — E (hybrid)**: provenance-bound admin ingestion of an
   authoritative institutional catalog; NOTHING seeded until a real catalog
   exists; per-subject count = catalog row count (never a constant).
2. **Faculty role — DEFER**: keep STUDENT + ADMIN for 9.1; introduce FACULTY
   only with a defined signature/grading workflow (9.2+), as a narrower
   elevation via a capability matrix.
3. **Audit identity — minimal additive**: record timestamps + `signed_by` +
   `designated_by/at` + catalog provenance; no created_by on attendance.
4. **Experiment↔session linkage — nullable FK** `laboratory_records.
   class_session_id` + validation (PRACTICAL/mid-sem of same subject, not
   cancelled); single primary link; multiple experiments per session allowed.
5. **Mid-sem rule — advisory only**: "Eligible for mid-sem designation (X of
   Y)" derived from the real catalog; designation stays a manual ADMIN act;
   no auto-designation, no gate, no universal count.
6. **Student boundary — two-tier**: students self-track (status pending);
   only ADMIN/FACULTY sets SIGNED (official).
7. **Grading/viva — EXCLUDE from Phase 9**: defer to a separate
   academic-assessment phase; dormant `marks`/`remarks` columns retained.

## Phase 9.1 — Laboratory Attendance & Event Integration (COMPLETE 2026-08-15)

PRODUCT DECISION LOCKED: **Mid-Sem Practical and Lab Cancelled are NOT
separate laboratory attendance systems — they are Academic Events that modify
the canonical attendance schedule** (`AcademicEvent →
EventSessionSynchronizer → ClassSession → AttendanceRecord → existing
engines`). This supersedes the Phase 9.0 audit's additive read-model proposal
for 9.1; experiment management remains a future concern.

Implemented: two new event types (`MID_SEM_PRACTICAL`, `LAB_CANCELLED`,
subject-scoped, PRACTICAL-only, student-creatable for enrolled practical
subjects, optional `note`); the synchronizer resolves the deterministic
practical occurrence (reuses the timetable session — never duplicates — or
materializes exactly one extra on a non-lab day) and marks it with the
existing `ClassSession.designation = MID_SEM_PRACTICAL`; `LAB_CANCELLED`
cancels the matching occurrence via canonical `is_cancelled`. Attendance
flows through the normal mutation; cancelled rejects 409 and is excluded;
mid-sem Present/Absent are ordinary practical records; quiz eligibility
unchanged; state-based reconciliation keeps everything reversible and
idempotent; cancellation wins on a mid-sem + lab-cancelled conflict; attended
sessions are never deleted/cancelled. Additive read-model fields only
(`designation` on history/daily; `note` on events). No new tables beyond a
nullable `note` column and two PG enum values (migration
`a1b2c3d4e5f6_add_lab_event_types.py`); no new endpoints; no experiment
curriculum/progress; no FACULTY role; no grading/viva.

Verification: `verify_phase_9_1.py` **28/28**; frozen regressions 6.5 27/27 ·
6.6 36/36 · 6.7 31/31 · 7.2 26/26 · 8.1 22/22 · attendance-spec 15/15 ·
8.2 18/18 · compileall / tsc / ESLint / next build PASS.

⚠ **BASELINE DRIFT (owner decision required before final freeze):** the live
DB now has **95 attendance records** (was 92). The +3 are legitimate
owner-entered marks on BCS-502 LECTURE sessions (08-04, 08-05, 08-12 MISSED,
created 2026-08-15 16:19–16:20 UTC via the canonical mutation path) — not
verifier residue, not Phase 9.1 code. Per policy `verify_phase_7_1.py` was
NOT modified; its fixed `records == 92` (check 23) now fails at 95
(7.1 = 25/26). Authorize the fixed fixture 92 → 95 (as was done 89 → 92), or
accept check 23 as a documented known-failing baseline assertion.

Full details: `docs/phase_9_1_implementation_report.md`. Phase 9.1 code is
otherwise freezable; Phase 9.2 (experiment management) NOT started.

---

# ✅ Phase 10 — Settings, Feedback & Account Management

**COMPLETE & FROZEN** (10.0 · 10A · 10B · 10C · 10D · 10E). The Phase 2 foundations became real functionality end-to-end (UI → API → service → repository → database):

- **Settings (10A):** `SettingsModal` surface with the three preference toggles.
- **Profile (10B):** `sections.program` column + migration, `program` resolved from the stored section value in the profile read model, `StudentProfileResponse` completed (program/section/semester/session/academic dates), ProfileModal edits persisted via the real API.
- **Feedback (10C):** real `POST /api/v1/feedback` (feedback type, message 10–1000 trimmed, optional context, server timestamp, server-side user association); never fakes a successful submission; no GET/list/admin surface in this phase; verified by `backend/scripts/verify_phase_10c.py` (23/23).
- **Preferences (10D):** `user_preferences` table + GET/PUT `/api/v1/student/preferences` (lazy-create, replace semantics, server defaults false/false/MONDAY, user-isolated, no client identity); **storage/preference data only** — nothing sends reminders, marks attendance, or alters calendar/analytics; verified by `backend/scripts/verify_phase_10d.py` (18/18).
- **Freeze (10E):** audit report `docs/phase_10_completion_audit_report.md`, corrections (stale feedback copy removed, stale profile comment updated, Phase 10C verifier added), full regression + DB baseline proof + governance reconciliation in `docs/phase_10e_implementation_report.md`. All verifiers green, DB restored exactly, migration chain linear at head `c1d2e3f4a5b6`.

Original scope for reference:

## Settings

Potentially:

- Notification preferences
- Default landing page
- Attendance display preferences
- Reminder preferences
- Account preferences

Likely requires:

```text
user_preferences
```

plus GET/PUT API endpoints.

## Feedback

Implement a real feedback system:

```text
POST /feedback
```

with:

- Feedback type
- Message
- Optional context
- Timestamp
- User association

Never fake a successful submission.

## Profile

Complete:

- Name
- Roll number
- Section
- Program
- Semester
- Session
- Academic dates

---

# ✅ Phase 11 — Notifications & Reminders (COMPLETE & FROZEN)

Only after the academic/event architecture is stable.

**Status: COMPLETE & FROZEN (2026-08-21) — 11.0 architecture audit ✅ · 11A backend notification read model & contracts ✅ · 11B notification persistence + read-state ✅ · 11D notification center UX ✅ · 11E preference wiring verified — no additional implementation required ✅ · 11F final verification & freeze ✅ · 11C delivery model decision-gated/deferred (not implemented).**

**Post-freeze performance optimization (2026-09-02):** notification regeneration writes collapsed from N sequential single-row upserts (one COMMIT each — N database round trips during dashboard startup) into ONE multi-row `INSERT ... ON CONFLICT DO UPDATE` committed once (`NotificationRepository.upsert_many`, used by `NotificationService.get_notifications`). Idempotency (`UNIQUE(user_id, kind, occurrence_key)`), content, inbox ordering (created_at stagger preserves the prior sort), read/dismiss preservation, per-user isolation, TTL cache and PATCH invalidation are unchanged; the whole batch is atomic (a failure rolls back everything, never a partially regenerated inbox). No schema/migration change (alembic head `a9b8c7d6e5f4` unchanged); single-row `upsert` retained (verifier + direct callers). No commit made.

**Notification delivery investigation (2026-09-02, INVESTIGATION ONLY � no implementation):** full end-to-end trace of the notification architecture (`docs/notification_delivery_investigation.md`). **Findings, all proven from source:** (1) in-app notifications (bell + center, Phase 11A/11B/11D) are functional by design � generation on-read, 60s per-user TTL cache, PATCH invalidation, owner-scoped idempotent persistence all verified; no generation bug found. (2) **Full Web Push was never implemented � NOT a regression, a missing/incomplete capability**: zero occurrences of `PushManager`/`pushManager`/`PushSubscription`/`applicationServerKey`/VAPID/pywebpush/web-push anywhere; `requirements.txt` has no push library; no push-subscription table/model/migration/endpoints; no backend send path, dispatch service, failure cleanup, or trigger; no `Notification.requestPermission()` call anywhere; the only notification-adjacent control (Settings ? "Class reminders") toggles a preference row only, and a user-granted browser permission is inert. (3) **Service worker never registers at runtime**: `useServiceWorker()` (frontend/src/components/pwa/useServiceWorker.ts) is defined but mounted nowhere (verified by grep + git history � never wired in any commit); `navigator.serviceWorker.register()` never runs; `public/service-worker.js` has install/activate/fetch only � NO `push` listener, NO `notificationclick`/`notificationclose`/`showNotification`/payload parsing/deep-link handling. (4) **No real-time delivery**: notification fetching was intentionally de-polled (Phase 11D) � bell revalidates on window focus/open only (STANDARD_CACHE, no polling/SSE/WebSocket/push); with the app open and focused, new records appear only on focus revalidation, center open, or reload. (5) Root-cause classification: D (no Web Push subscription) + E (no backend push delivery) + F (no VAPID) + C (SW not registered) + G (no background trigger) + B (cache/revalidation gap) + H (inert permission state); A (in-app generation bug) NOT confirmed. Recommended implementation plan (NOT started � phases P1�P5 in the report: SW mount + permission + SW push handlers ? authenticated owner-scoped subscription persistence + endpoints ? VAPID + PushDispatchService + 404/410 cleanup ? trigger strategy keeping the in-app feed canonical with push as a side-channel ? bell refresh-interval revalidation; P1/P5 parallelizable with the Phase 26 performance work). Phase 11 remains COMPLETE & FROZEN; 11C (delivery model) remains deferred/not implemented. No code, migration, env, deployment, or commit was made by the investigation.

**Phase 11C-P1 � Web Push foundation (browser-side) COMPLETE (2026-09-02):** service-worker registration, browser notification permission, and push-event handling infrastructure. Implements the first of five recommended phases from the investigation. **Scoped:** (1) `useServiceWorker()` now actually mounts at runtime via `ServiceWorkerRegistration` in `AppShell` � the SW registers when the authenticated shell mounts; (2) new `useNotificationPermission()` hook in `frontend/src/hooks/useNotificationPermission.ts` � real `Notification.permission` state, `requestPermission()` on user gesture, no faked state; (3) Settings modal adds a "Browser notifications" row with per-state UX (unsupported/default/granted/denied); (4) service worker extended with defensive `push` payload parser, `push` event ? `showNotification()`, `notificationclick` ? same-origin validation ? focus + navigate existing client or `openWindow`. No PushManager subscription, no VAPID, no backend dispatch, no DB/migration, no auth change, no in-app notification change. `npx tsc --noEmit` PASS, ESLint changed files PASS, `node --check service-worker.js` PASS. No commit/deploy. Governance: reconciled in implementation_plan.md, task.md, walkthrough.md. P2�P5 remain NOT STARTED.

Potential features:

- Upcoming class reminder ✅ (11A — CLASS_REMINDER, gated by the `class_reminders` preference)
- Quiz approaching ✅ (11A — QUIZ_APPROACHING, canonical next-upcoming quiz cycle)
- Attendance-below-threshold warning ✅ (11A — ATTENDANCE_THRESHOLD, engine banding)
- Must-attend warning ✅ (11A — MUST_ATTEND, engine optimizer deficit)
- Safe-skip information ✅ (11A — SAFE_SKIP, engine optimizer safe-skip)
- Academic event notification ✅ (11A — ACADEMIC_EVENT, dashboard upcoming-events selection)

### Architectural rule

Notifications consume engine outputs.

They do **not** independently calculate attendance.

### Sub-phase status

- **11.0** Architecture & Discovery Audit — ✅ COMPLETE (`docs/phase_11/phase_11_architecture_audit.md`).
- **11A** Backend notification read model & contracts (`GET /api/v1/notifications`, additive `NotificationKind`, on-read generation, `verify_phase_11a.py` 19/19) — ✅ COMPLETE (`docs/phase_11/phase_11a_implementation_report.md`). Zero DB change; no migration; no frontend; no scheduler.
- **11B** Notification persistence + read-state — ✅ COMPLETE (`docs/phase_11/phase_11b_implementation_report.md`). What 11B delivered:
  - Additive migration `d1e2f3a4b5c6` (single alembic head) creating the `notifications` table + `notificationkind` enum; chains linearly to `c1d2e3f4a5b6`.
  - Deterministic identity/idempotency: `UNIQUE(user_id, kind, occurrence_key)` where `occurrence_key` mirrors the Phase 11A natural-key reference (session id for CLASS_REMINDER, quiz cycle for QUIZ_APPROACHING, event id for ACADEMIC_EVENT, subject code for ATTENDANCE_THRESHOLD / MUST_ATTEND / SAFE_SKIP). Repeated generation of the same logical occurrence upserts in place (never duplicates); genuinely distinct occurrences stay distinct. Refresh preserves `date`, `is_read`, `is_dismissed`, `created_at`.
  - `Notification` model + `NotificationRepository` (owner-scoped, JWT-only) + `NotificationService` extended (snapshot-on-read generation, persisted inbox newest-first, unread count, `update_state`).
  - API: `GET /api/v1/notifications` now serves the persisted inbox with `unread_count`; `PATCH /api/v1/notifications/{notification_id}` for read/dismiss state (owner-scoped → 404 cross-user; idempotent; empty body → 422). 11A projection semantics unchanged.
  - `verify_phase_11b.py` 23/23 PASS; Phase 11A verifier re-run 19/19 PASS; DB baseline restored; no frozen system touched; no commit made.
- **11C** Delivery model — ⚪ NOT STARTED (decision-gated: in-app only vs scheduled sweep; deferred out of 11B, not invented).
- **11D** Frontend notification center UX — ✅ COMPLETE (`docs/phase_11/phase_11d_implementation_report.md`). What 11D delivered:
  - Notification bell in the authenticated `TopNav` with a backend `unread_count` badge (hidden at zero, capped at "99+").
  - Notification center (shell `ShellDialog`) listing the persisted inbox newest-first: kind badge/icon per `NotificationKind`, readable message, subject context + occurrence date, unread rows visually emphasized.
  - Actions via the existing 11B API: per-item "Mark as read" (unread rows only) and dismiss (removes from the inbox; stays dismissed server-side across regeneration). Cache is updated from the genuine PATCH response — success is never faked, failures surface in an inline banner with the list unchanged.
  - SWR integration: `useNotifications()` (key gated, one logical request; bell + center share the key so they dedupe and stay in sync) + `useNotificationMutation()`; `STANDARD_CACHE` revalidation only (no polling). Types mirror the backend `NotificationItem` / `NotificationsResponse` / `NotificationUpdate` contract in `types/api.ts`.
  - No push/email/SMS/scheduling/cron/worker/PWA behavior, no client-side notification logic, no backend change. `tsc --noEmit` PASS · ESLint PASS · `npm run build` PASS. No commit made.
- **11E** Reminder preferences wiring — ✅ VERIFIED, NO ADDITIONAL IMPLEMENTATION REQUIRED (`docs/phase_11/phase_11e_implementation_report.md`). The `class_reminders` gate lives inside 11A (`notification_service.py`, read at generation time; verified by 11A checks 7/8); `auto_mark_present` and `week_starts_on` remain storage-only per audit §5B/5C. SettingsModal copy + `types/api.ts` contract comment made truthful ("Class reminders are shown in the bell icon when enabled"). 11A verifier 19/19 PASS; 11B verifier 21/23 — checks 19/20 fail on diagnosed environmental data drift (pre-existing admin inbox rows + the verifier's own fixture shifting the admin's canonical quiz/event selection mid-run), NOT a code regression; a clean admin inbox passes 23/23. Frontend tsc/ESLint/build PASS. No commit made.
- **11F** Final verification & freeze — ✅ **PHASE 11 COMPLETE & FROZEN** (`docs/phase_11/phase_11f_verification_report.md`). The 11E drift (11B checks 19/20) and an 11A check-16 failure were confirmed as verifier determinism issues on a used inbox, NOT production defects; both verifiers were hardened **verifier-only** (checks 15/16/17 in 11A; 17/19/20 in 11B) to accumulation-compatible assertions (coverage + run-generated correctness + uniqueness + bounded growth; string-form baseline comparison — a UUID-vs-string bug in the first hardening attempt was also fixed). **Zero production code changed in 11F.** Final gates on the used environment: `compileall` PASS · `verify_phase_11a.py` **19/19** (×2) · `verify_phase_11b.py` **23/23** · frontend `tsc`/ESLint(Phase 11 files)/`npm run build` PASS. DB baseline restored (users 31 · admins 1 · notifications 11 — the admin's legitimate pre-existing rows); alembic single head `d1e2f3a4b5c6` unchanged. No commit made.

---

# 🟡 Phase 12 — Mobile / Responsive Experience

Desktop is currently the primary visual reference.

Build a genuine mobile experience rather than simply shrinking desktop.

Include:

- Mobile navigation
- Responsive top bar
- Bottom navigation where appropriate
- Responsive cards
- Touch targets
- Mobile date navigation
- Mobile Track workflow
- Mobile profile menu
- Responsive quiz cards
- Responsive analytics

## Status: 12.0 + 12A + 12B + 12C + 12D + 12E COMPLETE (2026-08-23)

- **12.0 architecture & implementation-readiness audit ✅** — `docs/phase_12/phase_12_architecture_audit.md`. Verdict: READY FOR ONLY A PHASE 12 SUB-PHASE (12A). Key findings: mobile navigation ABSENT (TopNav nav `hidden md:flex`); touch targets all below 40px; ShellDialog dialogs cannot scroll; Laboratory tab bar ≈380px nowrap clipped by the shell; NO BACKEND CHANGE REQUIRED; S4 prior art (`17_AI_HANDOFF.md:41-43`) = exactly 4 bottom tabs (Dashboard/Subjects/History/Profile) + Academic Tools from Profile, never a 5th tab; legacy `css/responsive.css` (not imported) documents 5 breakpoints + 44px touch minimums + FAB.
- **12A responsive foundation + mobile navigation ✅** — `docs/phase_12/phase_12a_implementation_report.md`. Bottom nav below `md` (Home `/dashboard` · Attendance `/subjects` · History `/history` · Profile `/profile`), Profile as the S4-compatible anchor opening the More sheet (Track `/tools/laboratory` · Laboratory `/laboratory` · Quiz Eligibility `/tools/quiz-schedule` · Calendar `/calendar` · Events `/tools/events`) via the existing `ui/sheet.tsx`; AppShell bottom clearance + safe-area; ShellDialog capped at 90dvh with scroll; NotificationCenter list viewport-capped; touch-target foundation in `ui/button.tsx` (mobile base sizes, `sm:` desktop restores — dialogs/sheets/bell/notification actions inherit ≥40px on mobile); NotificationBell mobile hit area ≥40px. Desktop ≥768px behavior unchanged (verified by diff scope + static gates; browser/manual testing is the user's responsibility — checklist in the 12A report). Zero backend/DB/migration/API/PWA changes.
- **12B Track / Dashboard / Calendar responsiveness ✅** — `docs/phase_12/phase_12b_implementation_report.md`. Real overflow fixed (Calendar month nav ≈310px vs 288px content at 320; now flex-wrap + responsive label) and grid cells enlarged (31→35px at 320 via `p-2 sm:p-4` + `gap-1 sm:gap-1.5`); Track date nav fluid (`flex-1` center column, input stretches) with ≥40px mobile controls (input `h-10 sm:h-8`, Today `sm:h-8`, Change buttons lose their `h-7` override); session-card header collisions fixed (fluid left column + wrapping badges); actions row auto-height (no longer clips the 12A h-10 buttons); dashboard wrap fixes (Today badge row, Overall delta row, Weekly `gap-2 sm:gap-3`). All changes `sm:`-gated or overflow-inert — desktop byte-identical. Zero backend/DB/migration/API/PWA changes; 12A files untouched. Static gates VERIFIED; browser/manual testing = owner (checklist in the 12B report).
- **12C Laboratory / Subjects / Quiz Eligibility / Events responsiveness ✅** — `docs/phase_12/phase_12c_implementation_report.md`. Phase 12C is **COMPLETE**.
    - **Frontend fixes**: Fixed non-responsive tab bars in Laboratory page, hardcoded wrapping issues in SubjectAttendanceCard and EventRow, and minimum widths on QuizEligibilityCard to ensure grid components wrap and respond gracefully down to mobile viewports.
    - **Urgent Correctness Bugfix**: Fixed an issue in the analytics aggregation pipeline where explicitly `CLASS_CANCELLED` sessions (which were properly mapped in the database) were not dropped from the applicable attendance denominators. Updated `AnalyticsService`, `DashboardService`, and `NotificationService` to strictly enforce the canonical `occurrence_is_cancelled` predicate from `practical_occurrence.py`. Verified all Phase 6-9 regression tests pass and that the backend math is pristine and sound.
- **12D Remaining responsive surfaces ✅** — `docs/phase_12/phase_12d_implementation_report.md`. Phase 12D is **COMPLETE**.
    - **Frontend-only touch-target refinements**: SettingsModal select upgraded from h-7 (28px) to h-9 sm:h-7 (36px mobile). EventFormDialog controls upgraded from h-8 (32px) to h-10 sm:h-8 (40px mobile).
    - **Grid responsiveness**: EventFormDialog date range and working/substitution controls changed from grid-cols-2 to grid-cols-1 sm:grid-cols-2 (single column on mobile, two-column restored on desktop).
    - **NotificationCenter**: Analyzed but NOT modified — current layout acceptable at 320px.
    - Zero backend/DB/migration/API changes. All static gates PASS. Desktop byte-identical.
- **12E Mobile polish + verification ✅** — `backend/scripts/verify_phase_12e.py`. Static invariant verifier asserting Phase 12 invariants (viewport export, bottom nav gated `md:hidden`, no fixed grid counts, no sub-36px interactive sizes on date inputs). All 5 invariants verified PASS. Zero backend/DB/migration/API changes. Desktop byte-identical.

---

# 🟡 Phase 13 — PWA / Installability

**Phase 13 COMPLETE** (2026-08-23): PWA/installability infrastructure implemented.
- Web manifest served at `/manifest.json` with name, short_name, icons, theme_color, background_color.
- Service worker registered at `/service-worker.js` with conservative caching strategy:
  - Static application assets cached on install
  - Network-first for all API requests (never cache authenticated data)
  - Cache-first for navigation with offline fallback
  - Old cache cleanup on activate
- SVG icons added at 192x192 and 512x512 in `frontend/public/icons/`
- Install prompt connected to `beforeinstallprompt` API and `display-mode: standalone` detection
- Standalone detection via `navigator.standalone` and `window.matchMedia("(display-mode: standalone)")`
- Online/offline state via `navigator.onLine` with truthful messaging
- Cached application shell: shell resources cached, data pages communicate offline status
- Does NOT claim offline attendance/quiz/history data availability
- PWA infrastructure does not alter Phase 12 mobile or desktop behavior
- Zero backend/database/API/migration changes
- `npx tsc --noEmit` PASS; `npm run build` PASS; `git diff --check` PASS
- Frozen areas (Phases 0–12, attendance/eligibility/calendar/event engines, auth) preserved
- Phase 14 (Firebase Retirement) remains unchanged

---

# 🟡 Phase 14 — Firebase Retirement (COMPLETE & FROZEN)

**Status: COMPLETE & FROZEN — 14.0 audit ✅ · 14A ✅ · 14B ✅ · 14C ✅ · 14D ✅ · 14E ✅ · 14F ✅.**

## 14.0 — Firebase Retirement Audit (COMPLETE, read-only, 2026-08-23)

Read-only repository-wide audit; report: `docs/phase_14/phase_14_architecture_audit.md`.
Verdict: **Phase 14 ready to proceed** — runtime authentication is fully JWT + PostgreSQL;
no Firebase Auth path reachable; no Firestore reads/writes from the Next.js app; Firebase
exists only as inert frontend SDK initialization, inert backend Admin-SDK initialization,
legacy deployment/config files, legacy root app, stale docs, migration scripts, and the
nullable `users.firebase_uid` legacy column. Zero code changed, zero DB mutations, zero
commits during the audit.

## 14A — Frontend Firebase Removal (COMPLETE, 2026-08-23)

Removed the frontend Firebase dependency entirely (JWT auth unaffected):
- `frontend/src/lib/api.ts` — dead `import { auth } from "./firebase"` removed.
- `frontend/src/lib/firebase.ts` — obsolete Firebase initialization module deleted.
- `frontend/package.json` / `package-lock.json` — `firebase` dependency removed (77 packages pruned).
- `frontend/.env.example` / `.env.local` — `NEXT_PUBLIC_FIREBASE_*` variables removed.
- Verification: `npx tsc --noEmit` PASS · `npm run build` PASS (15/15 routes) · `git diff --check` PASS · frontend/src Firebase search clean (only `firebase_uid` data-field strings remain, Phase 14D scope).
- Zero backend/DB/migration changes. Zero commits.

## 14B — Backend Firebase Removal (COMPLETE, 2026-08-23)

Removed the backend Firebase Admin SDK dependency entirely (JWT + PostgreSQL auth unchanged):
- `backend/app/core/firebase.py` — obsolete Firebase Admin SDK initialization module deleted.
- `backend/app/main.py` — `initialize_firebase` import + call removed (nothing else touched).
- `backend/requirements.txt` — `firebase-admin>=6.5.0` removed.
- venv — `firebase-admin` 7.5.0 + 13 Firebase transitive packages (google-cloud-firestore/storage/core, google-api-core, google-auth, grpcio, protobuf, etc.) uninstalled; `pip check` clean.
- Verification: `compileall` PASS · `app.main` imports clean without Firebase · OpenAPI shows all 32 paths incl. `/api/v1/auth/login`, `/api/v1/auth/register`, `/student/me`, `/student/sync` · `get_current_user`/`require_admin`/`HTTPBearer` intact · `git diff --check` PASS · diff limited to 3 backend files.
- `firebase_uid` column/model/schema/API references intentionally preserved (Phase 14D scope).
- Legacy migration scripts (`migrate_extract.py`, `migrate_execute.py`, `diagnose_failures.py`) retain their `firebase_admin` imports — they are historical tools with their own graceful blocked-exit path, out of scope for 14B.
- Zero DB/migration changes. Zero commits.

## 14C — Deployment / Configuration Cleanup (COMPLETE, 2026-08-23)

Removed all Firebase deployment/configuration artifacts (auth, identity, and runtime
behavior untouched):
- Deleted `firebase.json`, `.firebaserc`, `firestore.rules`, `firestore.indexes.json`.
- Removed Firebase-specific `.gitignore` entries (firebase-debug logs, `.firebase/` cache, `.firebaserc` config block).
- Deleted entirely-Firebase prompts (`14_FIREBASE_BACKEND_PROMPT.md`, `19_DEPLOYMENT_PROMPT.md`); removed Firestore/Firebase-Hosting sections and references from prompts `01/03/04/11/16` and `prompts/README.md` (index rows + release workflow).
- README: removed Firebase init/configuration instructions (`## Configure Firebase`, `## Deploy Firestore Rules`), Firebase Project/CLI requirements, and structure entries for the deleted config files. Legacy-app feature/tech-stack claims remain for Phase 14F doc reconciliation.
- Verification: all 6 files absent · `git diff --check` PASS · prompts/ Firebase search clean · diff limited to 13 files (8 deletions, 5 edits) · zero backend/frontend source changes.
- Preserved: `firebase_uid` model/schema/API/scripts (Phase 14D scope), legacy migration scripts (`migrate_extract.py`, `migrate_execute.py`, `diagnose_failures.py`), legacy root app, historical `docs/` (Phase 14F reconciliation).
- Zero DB/migration changes. Zero commits.

## 14D — firebase_uid / Data Cleanup (COMPLETE, 2026-08-23)

Removed the final application-level Firebase identity residue (`users.firebase_uid`):
- **Legacy scripts**: `backend/scripts/set_initial_password.py` and
  `backend/scripts/setup_single_user.py` now look up the user by canonical
  `roll_number` (`2401220100027`) instead of `firebase_uid`.
- **Model**: `backend/app/models/user.py` — `firebase_uid` column mapping removed.
- **Schema/API**: `StudentProfile` (`backend/app/schemas/student.py`), `/student/me`,
  `/student/sync` (`backend/app/api/v1/endpoints/student.py`), register
  (`backend/app/api/v1/endpoints/auth.py`), and `get_by_firebase_uid()`
  (`backend/app/repositories/user_repo.py`, dead code) — all `firebase_uid`
  references removed; `selectinload` unused import removed.
- **Frontend**: `frontend/src/types/api.ts` + `frontend/src/contexts/AuthContext.tsx`
  — `firebase_uid` field removed; profile page now displays `user.id` and the stale
  "Firebase identity is active (501)" error message was replaced with truthful copy.
- **Migration**: NEW `backend/alembic/versions/e1f2a3b4c5d6_drop_firebase_uid.py`
  (down_revision `d1e2f3a4b5c6`) — `DROP INDEX ix_users_firebase_uid` +
  `DROP COLUMN users.firebase_uid`; reversible (downgrade re-creates the nullable
  column + unique index, no invented values). APPLIED via `alembic upgrade head`.
- **Verification**: alembic single head `e1f2a3b4c5d6` · `compileall` PASS ·
  `npx tsc --noEmit` PASS · `git diff --check` PASS · app imports clean (32 paths,
  `/auth/login`, `/auth/register`, `/student/me`, `/student/sync` present) ·
  `StudentProfile` contract free of `firebase_uid` · JWT chain
  (`get_current_user`/`require_admin`/`HTTPBearer`/`create_access_token`) intact.
- **Database before/after (SELECT-verified)**: users 31 = 31 · admin 1 = 1 ·
  students 30 = 30 · enrollments 27 = 27 · attendance 159 = 159 · sessions 720 = 720 ·
  events 60 = 60 · all other table counts byte-identical · Aditya's row
  (roll `2401220100027`) untouched. Column and `ix_users_firebase_uid` index gone.
- Preserved: historical migration files (`7117a007a0da`, `c3d4e5f6a7b8`),
  `migrate_execute.py` (completed one-shot historical tool), historical docs
  (Phase 14F reconciliation). Zero commits.

## 14E — Regression Verification (COMPLETE, 2026-08-23)

Full auth/data-path regression proving Phase 14D removed `firebase_uid` without
regressing the PostgreSQL + JWT application:
- **In-process regression suite (real DB, guaranteed-rollback)**: 66/67 PASS —
  alembic head `e1f2a3b4c5d6` single; column + index gone; users 31 / admin 1 /
  students 30 / distinct rolls 31; password round-trip (pbkdf2_sha256, salted,
  wrong/empty rejected); login valid → token, wrong password → 401, nonexistent
  roll → 401; JWT mint + `get_current_user` valid + invalid → 401; `require_admin`
  ADMIN ok / STUDENT → 403; `/student/me` full contract (id, name, roll, role,
  section, semester, session, dates, quiz date) with NO `firebase_uid`; 16 core
  read paths (dashboard, attendance history/daily/summary, calendar month/today/
  date, events, quiz cycle/eligibility, subjects, timetable, analytics,
  preferences, notifications, lab summary); mutation contract (Attended/Missed/
  Pending accepted, cancelled → 409, future → 400, non-enrolled → 403); admin
  mutation wired to `require_admin`; feedback POST + preferences PUT; `/student/sync`
  no `firebase_uid`. The single harness FAIL was a harness artifact (the chosen
  session's subject was one the student is enrolled in — 403 correctly not
  raised), not a regression.
- **Frozen-phase verifiers (real DB, self-cleanup)**: 6.5 security/auth matrix
  27/27 · 6.6 event/session lifecycle 36/36 (incl. exact baseline restore) ·
  6.7 calendar 30/31 (check 7 expects pristine 18/0 seed counts; the live DB has
  4 user-created inactive QUIZ_DAY events from 2026-08-16 — pre-existing live
  data, NOT a 14D regression; all other checks + exact baseline restore PASS) ·
  7.1 quiz eligibility 26/26 · 10C feedback 23/23 · 10D preferences 18/18 ·
  11A notifications 19/19 · 11B notifications persistence 23/23 (after a
  compatibility fix) · 12E static invariants 5/5.
- **Corrective change (verifier compatibility, minimal)**: `verify_phase_11b.py`
  hardcoded the Phase 11B-era alembic head (`d1e2f3a4b5c6`); the Phase 14D
  migration legitimately advanced the head to `e1f2a3b4c5d6`. Updated the
  assertion + docstring to the current head (4 lines). No other verifier needed
  changes.
- **Persistent-mutation check**: one leaked temp user from a crashed harness run
  was detected via the baseline re-read and removed (test artifact); the leaked
  lab-experiment row from an early flawed direct-call test was likewise detected
  and removed. Final DB state byte-identical to the pre-verification baseline
  (users 31, all counts unchanged, alembic `e1f2a3b4c5d6`).
- Frontend: `npx tsc --noEmit` PASS · `npm run build` PASS (15/15 routes) ·
  Firebase search clean (`firebase_uid`/`firebase`/`firestore` absent from
  `frontend/src` and `backend/app`; only 3 stale comments remain — Phase 14F).
- Backend: `python -m compileall backend/app backend/scripts backend/alembic` PASS.
- Browser/manual testing NOT performed (owner responsibility).

## 14F — Freeze & Governance Reconciliation (COMPLETE, 2026-08-23)

Final reconciliation of the Firebase retirement:
- **README.md** rewritten — describes the active architecture (PostgreSQL → FastAPI →
  JWT API → Next.js → React UI), marks Firebase as **RETIRED**, and documents the
  legacy root application as preserved/pending separate retirement.
- **Historical banners** added to `backend/API_DESIGN.md`, `backend/DATABASE_DESIGN.md`,
  `backend/MIGRATION_NOTES.md`, `backend/MIGRATION_AUDIT.md` — each now explicitly
  states it describes the pre-JWT/pre-retirement design and is superseded, without
  rewriting their content.
- **docs/README.md** boundary banner — the docs/ series is documented as describing
  the legacy application (still present, not the active app).
- Governance synchronized: Phase 14 marked **COMPLETE & FROZEN**; Phase 15 designated
  as the separate **Legacy Web App + Legacy PWA Retirement** phase (subsequent
  planned phases renumbered 15→16 … 21→22).
- Verification: active-runtime Firebase search clean (frontend/src + backend/app +
  manifests + config) · `git diff --check` PASS · `tsc`/`build` PASS ·
  `compileall` PASS · alembic head `e1f2a3b4c5d6` unchanged · zero DB mutations ·
  zero commits.

**Original late-stage guidance (historical):** Firebase must not be removed prematurely —
the audit above proved the retirement conditions before any removal.

---

# ✅ Phase 15 — Legacy Web App + Legacy PWA Retirement

**Status: COMPLETE & FROZEN (2026-08-23).**

Retired the entire legacy web application and legacy PWA (as a whole, NOT as
Firebase cleanup — Firebase retirement was Phase 14, COMPLETE & FROZEN):

- Removed legacy runtime surface: root `index.html`, `js/` (21 files), `css/`
  (3 files), `assets/icons/` (3 files), `offline.html`, root `manifest.json`,
  root `service-worker.js`, `screenshot.png`.
- Removed legacy test/tooling artifacts: `test-e2e.js`, `scratch_pwa_mock_test.js`,
  `scratch_pwa_mock_test2.js`, `scratch_pwa_test.js`, `scratch_pwa_test2.js`.
- Removed legacy-only root package files: `package.json`, `package-lock.json`,
  `node_modules/` (express/jsdom/puppeteer — legacy-only; frontend deps live in
  `frontend/` and were unaffected).
- **Preserved `timetable.json`** — active data dependency of backend seed/verify
  scripts (`seed_academic_baseline.py`, `expand_baseline.py`,
  `seed_academic_events.py`, `verify_phase_7_1.py`, `verify_quiz_day_materialization.py`).
- Preserved historical provenance: docs/ series, historical walkthroughs, migration
  tooling, Alembic history, `regression_report.md`, `verification_report.md`,
  `repomix-output.xml`, prompts/ (all marked as historical via banners/notes).
- Documentation reconciled: README.md, docs/README.md, prompts/README.md updated to
  state the legacy runtime is retired and the active application is `frontend/` +
  `backend/`.
- Verification: `tsc` PASS · `npm run build` PASS (15/15; workspace-root lockfile
  warning now resolved) · `compileall` PASS · `git diff --check` PASS · zero active
  references to retired files · alembic head `e1f2a3b4c5d6` unchanged · zero DB
  mutations · zero commits.

The **current Next.js PWA** (Phase 13) is part of the active frozen application and
was NOT affected.

---

# ✅ Phase 16 — Production Security Hardening

**Status: COMPLETE & FROZEN (2026-08-23).**

Security audit + hardening of the active PostgreSQL + FastAPI + JWT + Next.js
application (backend-authoritative security). Zero database mutations; zero
migrations; alembic head unchanged (`e1f2a3b4c5d6`).

## What was hardened

- **JWT expiry**: bounded to 8 hours (env `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`;
  previously 30 days). `iat` claim added; `type == "access"` claim now enforced
  at validation (defense in depth). HS256 + env-driven secret remain.
- **Password policy** (registration; existing accounts unaffected):
  8–128 characters, at least one letter and one digit — backend-authoritative
  (Pydantic), frontend signup validation synced. PBKDF2-SHA256 (100k iterations,
  salted, constant-time compare) unchanged.
- **Brute-force protection**: in-process sliding-window rate limiter
  (`app/core/rate_limit.py`) — login 10 attempts/15 min, register 5/hour,
  per-IP, 429 + `Retry-After`. Distributed limiter (Redis) = Phase 17 dependency.
- **Login timing**: dummy PBKDF2 hash when the roll_number does not exist —
  eliminates user enumeration via response time.
- **Security headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options:
  DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` (restricted).
  HSTS env-gated (`SECURITY_HSTS_ENABLED`, default off — localhost/dev safe).
- **Error handling**: global 500 handler logs server-side, returns generic
  "Internal server error" (no tracebacks/SQL/paths leaked); attendance mutation
  no longer echoes internal exception text to clients.
- **Logging**: `app/core/logging.py` — auth failures, unhandled 500s logged;
  no passwords/tokens/secrets ever logged.
- **CORS**: env-driven explicit origins (default localhost:3100), credentials
  enabled, no wildcard — production origin configurable via
  `BACKEND_CORS_ORIGINS`.
- **Secrets**: `backend/.env.example` documents JWT/security/rate-limit env vars
  (no real secrets); dev JWT secret default remains env-overridable.
- **Authorization audit**: all sensitive endpoints verified — JWT-scoped user
  resolution, enrollment-scoped reads/mutations (attendance, quiz, lab, events,
  subjects, timetable), owner-scoped preferences/notifications/feedback,
  DB-authoritative ADMIN (STUDENT → 403). No IDOR found.

## Verification

- `verify_phase_16.py` (new): 34/34 PASS — auth matrix (no/malformed/tampered/
  expired/wrong-alg/no-type tokens → 401), admin (ADMIN ok / STUDENT 403),
  cross-user isolation (distinct identities, owner-scoped notifications 404,
  enrollment-scoped subjects), rate limiting (429 + Retry-After), password
  policy (4 invalid cases → 422), security headers, CORS (allowed origin OK /
  disallowed rejected), error non-leak.
- Frozen verifiers re-run: 6.5 27/27 · 10C 23/23 · 10D 18/18 · 11A 19/19 — all
  PASS. `compileall` PASS · `tsc --noEmit` PASS · `npm run build` PASS (15/15) ·
  `git diff --check` PASS.

## Known limitations / Phase 17 dependencies

- Rate limiter is in-process (per-process memory) — multi-process production
  needs a distributed limiter (Redis).
- JWT lives in localStorage (frontend) — documented limitation; HttpOnly-cookie
  strategy would be a larger architectural change.
- No refresh tokens: short-lived access token + re-login is the chosen strategy.

---

# ✅ Phase 17 — Data Integrity & Migration Hardening

**Status: COMPLETE & FROZEN (2026-08-23)** — JWT production-secret guard ✅ ·
integrity audit ✅ · backup/restore ✅ (verified) · retention policy ✅ · seed
idempotency ✅ · semester-transition analysis ✅ · **NO MIGRATION REQUIRED** ·
cleanup: NONE REQUIRED.

## 17.0 — JWT Production-Secret Guard (COMPLETE)

`backend/app/core/config.py`: `APP_ENV` ("development" | "production", default
development). When `APP_ENV=production`, startup fails if `JWT_SECRET_KEY` is the
known development default or shorter than 20 characters — the error explains what
is required without printing the secret. Development behavior unchanged.
`backend/.env.example` documents `APP_ENV`. Verification:
`backend/scripts/verify_phase_17_jwt_guard.py` — 6/6 PASS (dev loads; production +
default rejected; production + short rejected; production + valid loads; no secret
leak; empty APP_ENV = development).

## 17.1 — Read-only integrity audit (COMPLETE)

- **Alembic**: single head `e1f2a3b4c5d6`; 14 migrations, linear chain, no gaps.
- **Duplicates**: zero duplicate users (roll_number), enrollments, quiz_schedules,
  attendance records (user+session), laboratory records (user+experiment),
  preferences, feedback, notifications. The 85 class_sessions groups that share a
  (date, subject, type) signature are **legitimate** — they are 2-hour lab blocks
  materialized from two distinct timetable entries (BCS-551/552/553). Two extra
  sessions share a NULL-timetable-entry signature; they are event-created
  (quiz-day/extras), carry no attendance, and are consistent with the synchronizer.
- **Orphans**: zero orphan rows in every FK relationship audited (enrollments,
  sessions, attendance, quiz schedules, events, lab records, notifications,
  preferences, feedback).
- **Out-of-bounds**: zero attendance records or class_sessions outside the
  semester span (2026-07-15 → 2026-12-31).
- **Known legacy state (documented, not defects)**: 28 users have NULL
  `hashed_password` and NULL `section_id` — these are Firebase-era accounts whose
  passwords lived in Firebase Auth (retired in Phase 14); they cannot log in and
  are preserved for history. Exactly one active academic session is configured.
- **Conclusion**: **NO MIGRATION REQUIRED** — no schema defect, no orphan data,
  no duplicate data requiring cleanup.

## 17.2 — Backup / restore (COMPLETE, verified)

- `backend/scripts/backup_database.ps1` — full backup via `pg_dump -Fc` through
  Docker exec; writes `backups/attendancedash_full_<timestamp>.dump` (host dir,
  gitignored). Verified working.
- `backend/scripts/restore_database.ps1` — `-TestSwitch` restores into an isolated
  temporary container (never the working DB); without the switch it restores the
  live dev DB with confirmation prompt.
- **Restore test executed**: backup → isolated `postgres:16` container on port
  55433 → restore → counts verified (users 31, attendance 159, sessions 721,
  enrollments 27, events 60, quiz_schedules 18, alembic `e1f2a3b4c5d6`); container
  removed afterward. The working DB was never touched.
- Strategy: development = local dumps; production = same pg_dump with production
  credentials + off-host storage + periodic restore tests; schema-only via
  `pg_dump --schema-only`; data-only via `--data-only`.
- **Retention policy (documented in `backup_database.ps1` header):**
  - Location: `backups/` directory (gitignored); local/server filesystem.
  - Format: PostgreSQL custom format (`-Fc`), compressed, single file.
  - Daily: latest 7 · Weekly: latest 4 · Monthly: latest 3 — older backups may be
    removed once the window is satisfied.
  - Restore safety: isolated restore (`-TestSwitch`) for verification; live
    restore requires explicit confirmation; never overwrite the working DB casually.
  - Security: backups contain the full database — never committed to Git;
    production backups in protected/encrypted storage (infrastructure layer).
  - Verification cadence: periodic isolated restore tests.
  - Automated rotation: NOT built in Phase 17 (future infrastructure phase may
    add scheduled rotation).

## 17.3 — Seed strategy (COMPLETE, audit only)

- `seed_academic_events.py` — idempotent (skips existing semantic identities),
  authoritative source (quiz_schedules), no resurrection. ✅
- `seed_academic_baseline.py` / `expand_baseline.py` — deterministic from
  `timetable.json`, skip existing rows. ✅
- `provision_admin.py`, `set_initial_password.py`, `setup_single_user.py` —
  targeted operational tools, not bulk seeds.
- No seed overwrites user data or resurrects deactivated records.

## 17.4 — Semester transition (COMPLETE, analysis only — no change)

- Session-scoped: `academic_sessions`, `semesters`, `sections`, `subjects`,
  `student_enrollments`, `timetable_entries`, `class_sessions` (materialized span),
  `quiz_schedules`, `academic_events`.
- Global: `users`, `attendance_records` (referenced via sessions), `feedback`,
  `notifications`, `userpreferences`.
- Hardcoded current-semester assumptions (acceptable for the current semester,
  documented as future architectural work, NOT production blockers):
  - `2026-07-15`/`2026-12-31` semester span (calendar engine clamping, verifiers).
  - `timetable.json` weekday 0=Monday convention.
  - Registration auto-assigns the single active semester/section.
  - Quiz cycles 1–3 fixed policy thresholds.
- Transition to a new semester = new `academic_sessions` row + `is_active` switch;
  no schema change required for Phase 17.

## 17.5 — Duplicate / orphan / cleanup (COMPLETE)

- Dedicated read-only audit script executed; findings above. No cleanup performed
  — nothing invalid was found. The two NULL-timetable-entry extra sessions are
  event-created artifacts with no attendance and no impact; left untouched
  (consistent with frozen synchronizer semantics).

## Remaining Phase 17 work

None — Phase 17 is COMPLETE & FROZEN. Scheduled backup rotation and production
backup runbook are deferred to Phase 18 (Production Infrastructure).

## Long-term academic model

The architecture should not remain hardcoded around:

```text
15 July 2026
```

It should understand:

```text
Academic Year
    ↓
Semester
    ↓
Start Date
    ↓
End Date
    ↓
Subjects
    ↓
Enrollment
    ↓
Timetable
    ↓
Attendance
    ↓
Quiz Cycles
```

This is essential for a real multi-semester product.

---

# 🟡 Phase 18 — Production Infrastructure

**Status: IN PROGRESS / PARTIAL — 18.0 ✅ · 18A ✅ · 18B ✅ · 18C ✅ · 18D ⚠︝ PARTIAL (production deployment BLOCKED on missing infrastructure).**

## 18.0 — Production Infrastructure Audit (COMPLETE, read-only)

Audit report: `docs/phase_18/phase_18_0_infrastructure_audit.md`. Established the
production topology (HTTPS/CDN → Next.js → FastAPI → private PostgreSQL), frontend
(Next.js 16 SSR — needs Node runtime, not static), backend (uvicorn + proxy-header
trust needed), PostgreSQL privacy requirement, env contract, hosting comparison
(recommended: single VPS + Docker Compose), and Phase 18 slice plan (18A–18D).
Zero DB mutations, zero commits.

## 18A — Production Containerization & Orchestration (COMPLETE, 2026-08-23)

Created the production container foundation:

- `frontend/Dockerfile` — multi-stage Next.js 16 SSR image (node:20-alpine,
  npm 11 aligned, standalone output, non-root `nodejs` user, PWA preserved).
- `backend/Dockerfile` — python:3.13-slim FastAPI image (deterministic pip,
  non-root `appuser`, Alembic included, uvicorn workers via `UVICORN_WORKERS`
  default 1, `--proxy-headers`, healthcheck on `GET /health`).
- `docker-compose.prod.yml` — production stack: caddy reverse proxy (HTTP
  routing `/api/*` → backend, `*` → frontend), frontend, backend, postgres:16.
  Private networks: `proxy-net` (caddy/frontend/backend) + `data-net`
  (`internal: true`; backend ↔ postgres). PostgreSQL publishes NO host port.
  Only proxy port 80 exposed. Healthchecks + `unless-stopped` restart on all
  services. `depends_on` uses postgres healthcheck condition.
- `deploy/caddy/Caddyfile` — Caddy 2 HTTP routing with automatic
  `X-Forwarded-For` (rate-limiter client IP preservation; backend trusts proxy
  only because it binds inside the private network). TLS-ready placeholder
  domain `app.example.com` (HTTPS in a later phase).
- `deploy/.env.prod.example` — production env contract (no real secrets).
- `frontend/next.config.ts` — `output: "standalone"` (smallest justified change
  for a minimal runtime image; SSR + PWA preserved).
- `frontend/package-lock.json` — regenerated on Linux (npm 11) to resolve
  platform-specific optional deps (`@emnapi/*`) that Windows npm left out,
  making `npm ci` deterministic in the container.
- Docs: `docs/phase_18/phase_18a_containerization.md`.

Verification: `docker compose config` valid · backend image build PASS ·
frontend image build PASS · `npm ci` + `npm run build` PASS (15/15) ·
`compileall` PASS · `git diff --check` PASS. No containers started, no DB
touched, no cloud resources.

## 18B — Environment & Secret Management (COMPLETE, 2026-08-23)

Established a clean, explicit, production-safe environment/secret contract for
the 18A container architecture:

- **Production guard extended** (`backend/app/core/config.py`): when
  `APP_ENV=production`, startup also rejects a `DATABASE_URI` referencing
  localhost/127.0.0.1/host.docker.internal and any localhost CORS origin
  (in addition to the Phase 17 JWT-secret guard). Errors never print secrets.
- **Compose fail-fast** (`docker-compose.prod.yml`): required secrets use
  `${VAR:?}` — `POSTGRES_USER`, `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`,
  `BACKEND_CORS_ORIGINS`, `NEXT_PUBLIC_API_URL` fail compose startup when
  missing instead of silently interpolating empty values. `DATABASE_URI` is
  built from `POSTGRES_*` at runtime (overridable via `DATABASE_URI`).
- **Proxy trust boundary** (`FORWARDED_ALLOW_IPS` + pinned `proxy-net` subnet
  `172.28.0.0/24`): Uvicorn `--forwarded-allow-ips` trusts `X-Forwarded-For`
  ONLY from the proxy network CIDR; Caddy is the only trusted proxy; the
  Phase 16 rate limiter sees the real client IP; spoofing outside the subnet
  is ignored.
- **Env examples synchronized**: `deploy/.env.prod.example` (placeholders,
  required/optional split, secret/public markers), `backend/.env.example`
  (marked DEVELOPMENT ONLY), `frontend/.env.example` (public-var note).
- **Secret audit**: only example env files are tracked; dev credentials exist
  only in the dev example/defaults; no secrets in Dockerfiles, compose, or
  docs; `deploy/.env.prod` and `backend/.env` gitignored.
- Verification: `verify_phase_17_jwt_guard.py` **8/8 PASS** (JWT guard + new
  DB/CORS production rejections + no-secret-leak) · compose `config` fails
  fast without required vars and renders correctly with them · `compileall`
  PASS · `tsc` PASS · `git diff --check` PASS. No real secrets added; no
  deployment; zero DB mutations.

## 18C — Backup Automation + Retention + Off-Host Protection (COMPLETE, 2026-08-23)

Production-grade scheduled PostgreSQL backup implemented and verified in
isolation:

- **Backup container** (`deploy/backup/`, postgres:16-based): `run.sh`
  (scheduler with locking + pg_isready wait), `backup.sh` (pg_dump -Fc +
  verification: exists, ≥1KB, `pg_restore --list`), `offhost.sh` (copy
  contract: none/mount/sftp/s3/custom), `retention.sh` (keep latest
  `BACKUP_RETENTION_COUNT`, default 14; only files matching the naming
  convention; runs only after successful backup+off-host).
- **Compose wiring**: `backup` service on `data-net` (private), persistent
  `backup_data` volume, healthy-depends on postgres, `unless-stopped`,
  healthcheck, env via `deploy/.env.prod` (`${VAR:?}` for required).
- **Retention policy**: latest 14 local backups, rolling window, timestamped
  naming `attendancedash_full_<utc>.dump`.
- **Off-host contract**: OFFHOST_TYPE none/mount/sftp/s3/custom with
  placeholders only — no real credentials, nothing connected (deferred to
  deployment).
- **Restore**: documented runbook; isolated restore smoke test PASS (backup →
  disposable postgres → `pg_restore` → data verified → resources removed).
- **Secrets**: no real credentials; PGPASSWORD env (never argv); nothing
  logged; `.gitignore` already covers `backups/` + `deploy/.env.prod`.
- Docs: `docs/phase_18/phase_18c_backup.md`.

## 18D — Deployment & Verification (PARTIAL, 2026-08-23)

Local rehearsal deployment proved the full production mechanism works, but
**actual production deployment is BLOCKED on missing infrastructure**:

- **No production host/VPS** — no cloud compute target provisioned.
- **No production credentials** — no real `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`,
  or `BACKEND_CORS_ORIGINS` for a real domain exist.
- **No domain/DNS/TLS** — no real hostname; Caddy config ready (placeholders).
- **No off-host backup destination** — no external storage (OFFHOST_TYPE=none).

### What was delivered / verified (rehearsal, disposable, torn down):

1. **Deployment defects fixed**:
   - `backend/requirements.txt` — added `pyjwt>=2.10.0` (missing from deps;
     backend crashed at import without it). Genuine deployment defect, minimal
     fix.
   - `deploy/caddy/Caddyfile` — added `handle /health` route (backend health
     endpoint was not proxied; external health checks would fail).
2. **Rehearsal deployment**: full production stack (5 services) deployed locally
   with placeholder env values (temp file, never committed, disposable volumes).
   All services healthy: postgres → backend → backup → frontend → caddy.
3. **Backup verification**: `backup.sh` executed on the real backup container
   after seeding the disposable rehearsal DB; artifact 2972 bytes, pg_restore
   --list passed (11 TOC entries). Retention and off-host contract verified.
4. **Isolated restore**: backup restored into a separate disposable postgres:16
   container; data verified; container removed.
5. **Security**: no secrets in logs/argv; PostgreSQL private; only proxy port 80
   exposed; FORWARDED_ALLOW_IPS trust boundary verified.
6. **Docs**: `docs/phase_18/phase_18d_deployment.md` (full deployment report,
   blockers, and runbook).
7. **Application DB untouched**: working dev database `attendancedashpro_db`
   unchanged (INSERT/UPDATE/DELETE = 0). All rehearsal/restore containers and
   volumes cleaned (0 remaining).

### Blockers (production deployment cannot proceed without these):

- Production VPS/host → operator must provision.
- Production credentials → operator must generate and supply.
- Domain/DNS/TLS → operator must register and configure.
- Off-host backup destination → operator must provision (or accept none).

## 19 — CI/CD (COMPLETE & FROZEN — 2026-08-23)

# ✅ Phase 19 — CI/CD

Production quality gate established (`.github/workflows/ci.yml`):

```text
GitHub (PR / push to main)
   ↓
CI
 ├── integrity        — tracked secrets, env files, Firebase artifacts
 ├── backend          — compileall, import, JWT guard (8/8), static invariants
 ├── frontend         — npm ci (npm 11), tsc, lint (informational), build
 ├── docker           — backend + frontend + backup image builds
 ├── compose          — docker-compose.prod.yml config (CI placeholders)
 ├── migrations       — disposable postgres:16, alembic upgrade head, head verify
 ├── config-contract  — env example vs compose contract
 ├── backup-infra     — shell syntax + backup image build
 └── deploy           — DISABLED (${{ false }}); requires production env
```

- Deployment gate is **permanently disabled** until Phase 18D blockers resolve
  (no VPS, no credentials, no domain, no off-host destination).
- Lint is informational (`continue-on-error`) — 6 pre-existing ESLint errors
  live in frozen systems (AuthContext, auth pages, history page,
  service-worker.js); fixing them is out of scope. Authoritative gate = tsc +
  build.
- Migrations validated on a disposable postgres:16: single head
  `e1f2a3b4c5d6`, upgrade to head clean, DB revision matches head.
- All checks verified locally; working application DB untouched; no secrets;
  no deployment. Full doc: `docs/phase_19/phase_19_cicd.md`.

Development workflows remain quota-efficient (caching, no matrix, no browser
automation).

---

# 🔴 Phase 20 — Production QA

Perform a complete real-user journey.

## Account

- Sign up
- Login
- Wrong password
- Logout
- Refresh
- Session expiration

## Dashboard

- Name
- Attendance
- Weekly data
- Overall data
- Quiz data
- Alerts
- Events

## Track

- 15 July history
- Today's classes
- Future classes
- Present
- Absent
- Corrections
- Mark All Present
- Cancelled sessions

## History

- Complete records
- Filters
- Search
- Dates
- States

## Calendar

- Dates
- Weekends
- Holidays
- Events
- Classes

## Quiz

- Q1
- Q2
- Q3
- Thresholds
- Windows
- Must Attend
- Safe Skip
- Unresolved cycles

---

# ✅ Phase 21 — Production Launch

**Status: COMPLETE & FROZEN (2026-08-26)** — production launch delivered and
frozen; **21A/21A.1 (Account Audit & Cleanup) ✅ COMPLETE & FROZEN**, 21B
(Feedback Admin) ✅, 21C (Pre-flight) ✅, 21D (Free Public Beta Deployment)
✅ COMPLETE.

## 21A — Account Audit & Cleanup (COMPLETE & FROZEN, 2026-08-24)

Read-only account inventory audit: **31 accounts** found (1 PROTECTED owner
ADMIN `2401220100027`; 1 LIKELY REAL USER `1234567890124`; 29 LIKELY TEST).
**24 test accounts proposed for deletion** (zero dependent data) — pending
user approval; **no deletion performed**. 28 accounts cannot log in (NULL
password; Firebase-era legacy, Phase 14 boundary). All user FKs are
`ON DELETE NO ACTION` (no cascade; no delete implementation exists). QA-window
deltas (5 attendance under owner, 62 notifications) left intact. Report:
`docs/phase_21/phase_21a_account_audit.md`. Deletion requires explicit user
approval of the proposed set.

## 21A.1 — Approved Account Cleanup (COMPLETE & FROZEN, 2026-08-24)

**User-authorized destructive cleanup executed and verified.** The user
explicitly approved deletion of ALL accounts except `2401220100027` (Aditya
Tiwari, ADMIN), superseding the Phase 21A REQUIRES REVIEW classifications.

- **31 → 1**: 30 users deleted (24 zero-data + 6 review accounts) in a single
  verified transaction; dependent rows removed first (FK NO ACTION).
- **Dependent rows deleted**: attendance 5, notifications 34, enrollments 18,
  preferences 2, feedback 0, lab 0 (59 total, all owned by deleted users).
- **Admin invariants preserved**: enrollments 9, attendance 159 (incl. 5
  QA-window records), notifications 39, preferences 1, feedback 0.
- **Post-delete**: 1 user (owner ADMIN, password intact), 0 orphan rows,
  academic/system data untouched, alembic head `e1f2a3b4c5d6`.
- Report: `docs/phase_21/phase_21a1_account_cleanup.md`.

## 21B — Feedback Admin System (COMPLETE & FROZEN, 2026-08-25)

Admin feedback review surface over the existing PostgreSQL/FastAPI/Next.js
stack (read-only — the schema has no status field and the phase forbids
inventing workflow fields):

- **Backend**: `GET /api/v1/feedback/admin` (paginated, `feedback_type`
  filter) + `GET /api/v1/feedback/admin/{id}` — both `require_admin`;
  unauthenticated → 401, STUDENT → 403; submitter roll_number/name joined;
  no credentials serialized. Existing `POST /api/v1/feedback` student
  submission unchanged (JWT-derived user_id).
- **Frontend**: `/tools/feedback` admin page (loading/error/empty/list +
  type filter + pagination); Feedback nav link in TopNav (desktop) and
  MobileBottomNav (mobile MORE) — visible only when `role === "ADMIN"` (UX
  layer; backend remains the authorization boundary).
- **Defect found in browser verification & fixed (2026-08-25)**: the live
  dev backend (started 2026-08-24 21:16 without `--reload`) predated the
  Phase 21B code, so `/api/v1/feedback/admin` returned 404 in the browser
  ("admin feedback service may be unavailable"). Root cause: stale server,
  not the endpoint — in-process tests bypassed HTTP. Fixed by restarting the
  dev backend; verified live HTTP 12/12 (401/401/200/200/404,
  submit→list→detail). ErrorState now surfaces the actual API error detail
  instead of a generic message.
- **Verification**: backend 17/17 in-process + 12/12 live-HTTP PASS ·
  `tsc` PASS · `npm run build` PASS (incl. `/tools/feedback`) ·
  `git diff --check` PASS · no migration needed (existing table reused) ·
  feedback 0 → 0 after harness cleanup · admin account + enrollments/
  preferences intact.
- Report: `docs/phase_21/phase_21b_feedback_admin.md`.

## 21C — Production Launch Pre-flight / Gate Closure (COMPLETE & FROZEN, 2026-08-25)

Readiness assessment (read-only) of the Phase 21 launch gates. Phase 21
remains **BLOCKED**. Report: `docs/phase_21/phase_21c_readiness.md`.

| Gate | Status | Blocker |
|---|---|---|
| A — Browser QA confirmation | **BLOCKED — USER RESPONSIBILITY** | Operator has not confirmed the Phase 20 42-item manual browser QA checklist (Phase 21B page exercise is not the checklist) |
| B — QA-window data disposition | **RESOLVED** | All QA-window records now owner-owned (5 attendance + 30 notifications); non-owner portions removed by authorized 21A.1 cleanup; feedback 0 |
| C — Production infrastructure | **BLOCKED** | No VPS/cloud host, no `deploy/.env.prod`, no domain/DNS/TLS, no off-host backup; CI deploy gate still disabled (`if: false`) |

**Single clearest blocker**: production infrastructure does not exist (Gate C).
Phase 21 cannot launch until Gates A (user) and C (infrastructure) are
resolved.

> **Superseded (2026-08-26, Phase 21D.4):** the assessment above reflects the
> 21C snapshot. Gates A and C were subsequently satisfied — the operator
> completed browser QA (production login/ADMIN/dashboard/desktop/mobile/PWA
> verified) and provisioned the free-beta infrastructure (Vercel Hobby +
> Render Free + Supabase Free) in 21D.2/21D.3. All three gates are now
> **RESOLVED**; Phase 21 is COMPLETE & FROZEN.

## 21D — Free Public Beta Deployment (COMPLETE, 2026-08-26)

### 21D.0 — Architecture & Provider Selection (COMPLETE & FROZEN, 2026-08-25)

Research-only phase: selected a **₹0/month** deployment architecture for
100–300 beta users. Report: `docs/phase_21/phase_21d0_free_beta_architecture.md`.

**Recommended architecture** (no code changes required):

```text
GitHub
  ↓  auto-deploy
Vercel Hobby (Next.js SSR, *.vercel.app, HTTPS)
  ↓  HTTPS
Render Free Web Service (FastAPI Docker, *.onrender.com, HTTPS)
  ↓  HTTPS
Supabase Free PostgreSQL (500 MB, 50k MAU, 5 GB egress)
```

- **Frontend**: Vercel Hobby — native Next.js 16 SSR support, 1M function
  invocations, 100 GB transfer, automatic HTTPS. Cloudflare Pages rejected
  (static-only; would require a config change forbidden in 21D.0).
- **Backend**: Render Free Web Service — Docker-compatible with the existing
  `backend/Dockerfile`; 0.1 CPU / 512 MB / 750 h/mo; sleeps after 15 min
  idle (~1 min cold start, acceptable beta limitation). Railway/Fly/Oracle/
  Workers rejected (no free tier / card required / incompatible runtime).
- **Database**: Supabase Free — current DB is 9.1 MB; 300-user estimate
  < 50 MB (500 MB quota). **No automatic backups on Free** → documented beta
  backup limitation (manual pg_dump via GitHub Actions is the 21D.x option).
  Render Postgres Free rejected (30-day expiration).
- **HTTPS/domain**: all providers supply HTTPS on their subdomains — no paid
  domain, no DNS, no TLS management.
- **Capacity**: reasonable for 100–300 normal beta users under normal usage.
- **CI/CD**: existing `.github/workflows/ci.yml` reused as quality gate;
  deployment gate stays `if: false`. Provider Git integrations handle deploy.
- **Legacy artifacts preserved** (frontend/backend Dockerfiles,
  docker-compose.prod.yml, Caddy, backup container) for the future paid/VPS
  path — nothing deleted.
- Zero cloud resources created; zero database mutations; no deployment.

### 21D.1 — Production Configuration Hardening (COMPLETE & FROZEN, 2026-08-25)

Repository prepared for the ₹0 beta architecture (Vercel + Render + Supabase).
Configuration only — no deployment, no cloud resources, no production DB, no
secrets created. Report: `docs/phase_21/phase_21d1_config_hardening.md`.

**Changes:**
- `frontend/src/lib/api.ts` — production build now FAILS LOUDLY if
  `NEXT_PUBLIC_API_URL` is missing or points to localhost/127.0.0.1 (no more
  silent dev fallback in production).
- `backend/Dockerfile` — `--port ${PORT:-8000}` + healthcheck reads `PORT`
  (Render injects PORT; local Compose still uses 8000). Verified: image runs
  with `PORT=18080`, `/health` → 200.
- `render.yaml` (NEW) — provider-native Render blueprint: docker build from
  `./backend`, `healthCheckPath: /health`, env placeholders; `DATABASE_URI` +
  `JWT_SECRET_KEY` marked secret (set in dashboard). `FORWARDED_ALLOW_IPS`
  left at default (coarse-but-secure rate limiter behind Render proxy).
- Env examples (`frontend/.env.example`, `backend/.env.example`) document the
  full production contract (Supabase DATABASE_URI shape, CORS, PORT, HSTS).
- **Frozen areas untouched**: engines, auth, JWT semantics, require_admin,
  schema, migrations, PWA, routes.

**Verification:** tsc PASS · compileall PASS · Docker build PASS · PORT
runtime test PASS · secret scan clean · `git diff --check` PASS · zero DB
mutations.

### 21D.2 — Provider Project Provisioning & Environment Wiring (COMPLETE, 2026-08-26)

**Status: COMPLETE — operator provisioned all three providers.** The operator
created the Supabase Free project, Vercel Hobby project, and Render Free Web
Service following the 21D.2 runbook, wired environment variables, and verified
connectivity. Application is live at the provider URLs.

- Supabase Free PostgreSQL: schema initialized at Alembic head `e1f2a3b4c5d6`.
- Render Free Web Service: `attendancedash-api`, Docker build, `/health` 200,
  production env vars set (DATABASE_URI, JWT_SECRET_KEY, CORS, APP_ENV).
- Vercel Hobby: frontend deployed from repo, `NEXT_PUBLIC_API_URL` set to the
  real Render URL.
- CORS wired between the exact Vercel and Render origins.
- Runbook: `docs/phase_21/phase_21d2_provisioning_runbook.md`.

### 21D.2 — Production Database Connection Compatibility Audit (COMPLETE, 2026-08-25)

Pre-migration compatibility audit of SQLAlchemy 2.0.52 + asyncpg 0.31.0 with
the Supabase Session Pooler (port 5432). Report:
`docs/phase_21/phase_21d2_database_connection_audit.md`.

**Finding — documentation defect corrected (no code change):** the documented
`?sslmode=require` parameter is **invalid** for asyncpg — SQLAlchemy passes URL
query params verbatim to `asyncpg.connect()`, whose signature accepts `ssl=`
but not `sslmode=`. `?sslmode=require` would raise `TypeError` at connect.
Corrected to asyncpg-native **`?ssl=require`** in `backend/.env.example`,
`phase_21d1_config_hardening.md`, and `phase_21d2_provisioning_runbook.md`;
port corrected 6543 → 5432 (Session Pooler).

**Verified compatible:** Session Pooler (session-mode PgBouncer) supports
prepared statements — no `prepared_statement_cache_size` change needed ·
Alembic uses the same `settings.DATABASE_URI` (head `e1f2a3b4c5d6`) · Render
can supply `DATABASE_URI` as a secret (`sync: false`) · local dev unchanged.

No production DB accessed/mutated; no secrets accessed/generated. Zero DB
mutations.

### 21D.2 — Alembic URL Interpolation Defect Fix (COMPLETE, 2026-08-25)

**Deployment-blocking configuration defect found and fixed.** The first
production migration attempt was stopped locally by
`ValueError: invalid interpolation syntax` in
`config.set_main_option("sqlalchemy.url", settings.DATABASE_URI)` when the
URL contained `%23` (percent-encoded `#`).

- **Root cause**: Alembic's `Config` builds its `ConfigParser` with default
  `BasicInterpolation()` (Alembic 1.19.1, `config_args` passed as defaults so
  `interpolation=` cannot be injected); `%` sequences trigger interpolation.
- **Fix** (`backend/alembic/env.py`, +12 lines): `config.file_config._interpolation
  = Interpolation()` — the same no-op interpolation class configparser uses
  for `interpolation=None`. Applied once (memoized), before the URL is set.
- **Verified without connecting**: `alembic heads` OK ·
  `alembic upgrade head --sql` (offline; executes env.py; NO DB connection)
  exit 0, 289 lines of SQL, upgrade to `e1f2a3b4c5d6` present ·
  `compileall` PASS · `git diff --check` PASS.
- The failed attempt **never connected to or mutated Supabase**. No migration
  files, models, or application code changed.
- Report: `docs/phase_21/phase_21d2_alembic_url_fix.md`.

### 21D.2 — Vercel/Next.js 16.3 Deployment Compatibility Fix (COMPLETE, 2026-08-25)

**Vercel deployment failure fixed** — `ENOENT: /vercel/path0/frontend/.next/next-server.js.nft.json`.

- **Root cause**: `output: "standalone"` (unconditional, Phase 18A) is
  incompatible with Vercel's adapter on Next.js 16.3.0 during Vercel builds —
  the standalone output omits the top-level `.next/next-server.js.nft.json`
  trace that Vercel expects.
- **Fix** (`frontend/next.config.ts`): `output: process.env.VERCEL ? undefined
  : "standalone"` — Vercel builds (VERCEL=1) use normal Next.js output; Docker
  and local builds retain standalone. SSR and the Phase 13 PWA preserved.
- **Verified (both modes, static)**: non-Vercel build exit 0 with
  `.next/standalone/server.js` present · Vercel-mode build (VERCEL=1) exit 0
  with `.next/standalone` absent and `.next/next-server.js.nft.json` present ·
  `npx tsc --noEmit` PASS · `git diff --check` PASS.
- No API URLs, auth, backend, or Docker configuration changed.
- Committed and pushed to `main` (commit in walkthrough) so Vercel can
  auto-redeploy.

## Required prerequisites (unmet)

### 21D.2 — Production Auth Discrepancy Audit (COMPLETE, read-only, 2026-08-25)

**Discovery:** owner account (`2401220100027`, ADMIN) authenticates on
localhost but returns `401 "Incorrect roll number or password"` on production
(Vercel → Render → Supabase). Report:
`docs/phase_21/phase_21d2_auth_discrepancy_audit.md`.

**Root cause (evidence-based):** the production Supabase database contains
**zero application user rows**. The 21D.2 runbook initializes schema only
(`alembic upgrade head`; "No application data"), no migration or script
copies dev users, and no user was provisioned against production. The login
lookup finds no row → Phase 16 anti-enumeration returns the generic 401.
Localhost succeeds because the dev DB holds the account (1 user, PBKDF2
hash, verified read-only).

**Not a code defect** — same auth code in both environments; an
operational/data-state gap. No fix implemented (read-only audit).

**Planned steps (awaiting authorization):** see the Full-State Migration
Audit below — **Approach A (direct row-for-row copy with UUID + password-hash
preservation)** supersedes the earlier registration-based sketch.

### 21D.2 — Full Localhost→Production Migration Audit (COMPLETE, read-only, 2026-08-26)

**Discovery:** to reproduce the localhost ADMIN environment in production
faithfully, a full-state migration plan was produced. Report:
`docs/phase_21/phase_21d2_full_state_migration_audit.md`.

**Key findings:**
- Localhost: 18 tables; 1 owner user (PBKDF2 hash, ADMIN); 9 enrollments;
  165 attendance; 43 notifications; 1 preference; full academic baseline
  (1 session, 1 semester, 1 section, 9 subjects, 720 class_sessions,
  28 timetable entries, 3 quiz cycles, 18 quiz schedules, 61 events).
- Production: schema at head `e1f2a3b4c5d6`; zero application rows.
- **UUIDs are preservable** (production empty → no conflicts; all FKs stay
  intact; no remap needed).
- **Password hash is preservable** (PBKDF2 format verified; Approach A
  recommended over registration-based Approach B — direct copy keeps the
  exact password valid and all user-owned relationships FK-consistent).
- No existing script does a row-for-row copy; a new
  `migrate_localhost_to_supabase.py` tool is planned (idempotent,
  `ON CONFLICT DO NOTHING`, read-only on localhost).
- Validation plan defined (counts, identity, role, login, attendance
  breakdown, dashboard equivalence).
- **NOT executed** — zero mutations, awaiting operator authorization.

### 21D.3 — Controlled Localhost→Supabase Production Migration (COMPLETE, 2026-08-26)

**Authorized migration execution — COMPLETE and verified.** The tool
`backend/scripts/migrate_localhost_to_supabase.py` was created and validated
(compile PASS, FK order validated against actual schema). Localhost preflight
passed: source snapshot matches the 21D.2 audit (1 owner ADMIN, 165 attendance
108/57, 720 sessions, 9 subjects, 61 events, etc.); localhost backup created
(88 KB); alembic head `e1f2a3b4c5d6`.

The operator executed the migration in their own terminal (`--verify-only`
then `--execute`) with `DATABASE_URI_SOURCE`/`DATABASE_URI_TARGET` set.
Post-migration verification passed: all 18 tables migrated, source/target
counts match, UUID sets match, content sets match, FK integrity zero
violations, existing ADMIN identity + UUID + PBKDF2 password hash preserved,
165 attendance records preserved (108 ATTENDED / 57 MISSED), complete
academic state preserved. Production login verified by the operator
(roll `2401220100027`, same password as localhost).

Report: `docs/phase_21/phase_21d3_production_migration_report.md`.
Closure: `docs/phase_21/phase_21d4_production_closure.md`.

### 21D.4 — Production Closure & Governance Reconciliation (COMPLETE, 2026-08-26)

**Phase 21 closed and frozen.** Governance/documentation slice reconciling the
repository with the verified production state. Production validation (operator
performed): login ✅ · ADMIN account ✅ · dashboard ✅ · migrated data correct
✅ · desktop ✅ · mobile responsive ✅ · PWA install/launch ✅ · installed PWA ✅.
All three launch gates RESOLVED (A: browser QA completed by operator; B:
QA-window data disposition; C: free-beta infrastructure provisioned).
Production LIVE on Vercel Hobby + Render Free + Supabase Free PostgreSQL.
Documented beta limitations retained: Supabase Free has no automatic backups
(manual pg_dump / GitHub Actions approach) and Render Free sleeps after ~15
min idle (~1 min cold start; keep-warm via uptime monitor). Phase 22
(Post-Launch) is the next active phase. Report:
`docs/phase_21/phase_21d4_production_closure.md`.

## Gate A — Phase 20 manual browser QA — **RESOLVED (operator-verified, 2026-08-26)**
The operator completed browser validation of the live production app:
production login, ADMIN account, dashboard, desktop, mobile responsive UI,
PWA install/launch, and installed PWA all verified working.

### Gate B — Phase 20 QA-window data disposition — **RESOLVED**
Phase 20 reported 5 attendance records + 62 notifications with uncertain
provenance. Disposition completed in 21A.1 (authorized cleanup; remaining
QA-window records owner-owned and preserved) and confirmed in 21C.

### Gate C — Production infrastructure — **RESOLVED (21D.2/21D.3)**
- Host: **Vercel Hobby (frontend) + Render Free (backend) + Supabase Free PostgreSQL** — PROVISIONED
- Production credentials: **set as provider env vars / secrets** (DATABASE_URI, JWT_SECRET_KEY, CORS, NEXT_PUBLIC_API_URL)
- Domain + DNS: **provider subdomains with automatic HTTPS** (`*.vercel.app`, `*.onrender.com`)
- TLS/HTTPS: **PROVISIONED** (automatic on provider subdomains)
- Off-host backup: documented beta limitation (no automatic Supabase Free backups; manual pg_dump / GitHub Actions approach documented in 21D.0)

## What was ready (verified pre-launch, then used by the beta launch)

- Dockerfiles, production compose, Caddy config, backup container — **verified
  in Phase 18A/18C/18D rehearsal**
- Environment contract, secret guard, production config validation — **verified
  in Phase 18B/17**
- CI quality gate with disabled deploy job — **verified in Phase 19**
- In-process QA, cross-surface consistency, frozen verifier regression — **verified
  in Phase 20**
- Manual browser QA checklist — **completed by the operator (2026-08-26); production browser/mobile/PWA validation passed**

## Deployment sequence (when gates pass)

```text
Production Database
        ↓
Database Migration
        ↓
Backend
        ↓
Frontend
        ↓
Domain
        ↓
HTTPS
```

Once all three gates pass, the operator can execute the Phase 21 launch
sequence (provision → configure → migrate → deploy backend → deploy frontend
→ Caddy/HTTPS → backup → smoke → monitor → rollback).

> **Executed (2026-08-26):** the free-beta architecture was deployed through
> provider Git integrations (Vercel + Render auto-deploy) instead of the VPS
> path. The Caddy/domain/DNS path is preserved for future paid infrastructure.

Production data setup:

- Semester configuration — ✅ migrated (1 active session)
- Subjects — ✅ migrated (9 subjects)
- Timetable — ✅ migrated (28 entries)
- Quiz schedules — ✅ migrated (18 schedules)
- Academic events — ✅ migrated (61 events)
- Initial administrative configuration — ✅ migrated (1 ADMIN owner)

Monitoring:

- Server errors — provider dashboards (Vercel + Render)
- Database health — Supabase dashboard
- API latency — Render logs
- Authentication failures — Render logs
- Uptime — Render health check + optional uptime monitor
- Backups — manual / GitHub Actions scheduled pg_dump (Supabase Free limitation)

---

# 🟢 Phase 22 — Post-Launch (ACTIVE)

Phase 21 production launch is **COMPLETE & FROZEN**. The production system is
live on Vercel Hobby + Render Free + Supabase Free PostgreSQL. The operator
has verified login, ADMIN access, dashboard, desktop, mobile responsive UI,
PWA install/launch, and migration correctness.

Phase 22 is the **next active phase**. After real users begin using the
system:

- Monitor errors
- Collect feedback
- Identify calculation discrepancies
- Improve UX
- Fix production bugs
- Optimize expensive queries
- Improve mobile experience
- Handle semester rollover

Only after the core product is stable should ambitious new features be added.

## Phase 22.1 — Timetable Data-Scope Correction (COMPLETE, 2026-08-26)

**Status: COMPLETE** — first Phase 22 slice, implemented and verified
locally; production migration is a separate operator action (see below).

> **Operator blocker resolved (2026-08-26):** the operator's first
> `alembic upgrade head` attempt failed before migration with
> `ModuleNotFoundError: No module named 'psycopg2'`. Root cause: `alembic/env.py`
> feeds `settings.DATABASE_URI` to Alembic's **async** engine, and the
> operator's bare `postgresql://` URL (Supabase dashboard form) resolves to
> the sync psycopg2 dialect. Fixed by normalizing a bare
> `postgresql://`/`postgres://` scheme to `postgresql+asyncpg://` in
> `alembic/env.py` (asyncpg is the project's installed async driver). No
> `.env` change, no extra driver, no Phase 22.1 logic change. Verified against
> the localhost dev DB: `alembic current` → `f2e3d4c5b6a7 (head)` with the
> bare URL form. The operator can now retry the production migration.

Fixes the P0 data-scope defect found in the Phase 22.0 audit: the timetable
query accepted `section_id` but did not filter by it, and `TimetableEntry`
had no Section linkage — every section's schedule was returned to any
authenticated student. Masked today by the single-section production state
(1 section / 28 entries), it becomes a cross-section data exposure when a
second section exists.

**Implemented:**
- `TimetableEntry.section_id` (NOT NULL FK → `sections.id`) + `Section`
  relationship (`backend/app/models/timetable.py`,
  `backend/app/models/user.py`).
- Migration `f2e3d4c5b6a7` (`backend/alembic/versions/f2e3d4c5b6a7_add_timetable_section.py`):
  adds the column, backfills all existing rows from existing DB state
  (active session → semester → section; never a hardcoded UUID, never a new
  Section), then enforces NOT NULL (guarded). Downgrade drops the column.
- `get_weekly_entries_for_section(section_id)` now filters by `section_id`
  (`backend/app/repositories/timetable_repo.py`).
- Seed pipeline (`seed_academic_baseline.py`) assigns `section_id` (resolves
  the section for the semester; creates CSE-51 if absent, idempotent).
- API response shape unchanged — `section_id` is internal, not exposed.
- Verifier `backend/scripts/verify_phase_22_1.py` — 19/19 PASS on dev DB
  (schema, backfill, count 28, scoping, second-section isolation in a
  rolled-back transaction, API shape, session-materialization joins).

**Production migration — VERIFIED (2026-08-26, read-only):** the operator
applied revision `f2e3d4c5b6a7` to the production Supabase database
(`e1f2a3b4c5d6 -> f2e3d4c5b6a7`). Read-only verification confirmed the
expected state exactly: Alembic head `f2e3d4c5b6a7` · 1 section (CSE-51) ·
28 timetable entries · 0 NULL section_id · 0 orphan section references · UUID
and core data sets match the dev source · 0 duplicate timetable rows.
Rollback (if ever needed) is `alembic downgrade e1f2a3b4c5d6`.

## Phase 22.2 — Production Parity & Mutation Reliability (COMPLETE, 2026-08-26)

**Status: COMPLETE** — audit + confirmed fixes. Triggered by an operator
report: a Holiday event created from the localhost app did not appear in the
deployed app, and creating an event from the deployed app failed with
"Failed to fetch".

**Key audit finding — localhost writes to production:** `backend/.env`
points `DATABASE_URI` at the **production Supabase pooler**, so the localhost
app writes directly to the production database. The operator's
"localhost-created" Holiday event (Eid-e-Milad) was found IN the production
Supabase database. This is NOT a sync defect and no synchronization was
built. Localhost and production are separate applications sharing one
database through this `.env` configuration.

**Production stack verified healthy (read-only + read-only probes):**
deployed Render backend up (`/health` 200) · CORS correctly configured for
the exact Vercel origin · deployed Vercel bundles carry the correct
`https://attendancedash-api.onrender.com` (no localhost fallback in
production builds) · deployed backend runs current code (all event
endpoints, HOLIDAY enum, `note` field present) · JWT validation active
(dev-secret tokens correctly rejected 401) · unauth requests correctly
401.

**Confirmed fixes:**
- `frontend/src/lib/api.ts`: network-level fetch failures (browser
  "Failed to fetch") now surface an actionable message
  ("Unable to reach the server...") instead of the raw browser text; the
  original error is preserved as `cause`; `API_BASE_URL` exported for the
  auth pages.
- `login/page.tsx` + `signup/page.tsx`: replaced the raw
  `process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'` fallback
  with the guarded `API_BASE_URL` — the only remaining bypass of the
  production URL guard is removed; network errors translated to an
  actionable message.
- `events/page.tsx`: deactivation alert uses the translated message.
- `ErrorState.tsx`: removed dev-era copy ("The API may be unavailable or
  not fully implemented").

**Root-cause classification:** the deployed infrastructure was correct
(CORS, URL, auth, code). The "Failed to fetch" class of error most likely
originates client-side (transient network / browser cache / cold start) or
from a localhost-targeting fallback that no longer exists after this fix.
Exact runtime reproduction requires operator browser verification (see the
Phase 22.2 report). Local `.env` → production pooler remains an operator
decision (not modified by this phase).

**Mutation matrix:** all 18 mutation endpoints audited — all use the
guarded `apiFetch` except login/register (now fixed); no backend mutation
defect found.

## Phase 22.3 — Student Elective Selection & Timetable Resolution (COMPLETE, 2026-08-26)

**Status: COMPLETE** — implementation + local verification on the dev DB.
Production migration (revision `a3b4c5d6e7f8`) is a separate operator action.

**Objective:** each student selects one Department Elective-I and one
Department Elective-II; the shared CSE-51 timetable's Elective-I / Elective-II
slots resolve to the individual student's selected subjects. No separate
timetable per student; the institutional timetable stays shared by section.

**Authoritative elective catalog (CSE-51 V Semester CTT):**
- Elective-I: BCS-052 (Data Analytics), BCS-053 (Computer Graphics),
  BCS-054 (OOS Design with C++)
- Elective-II: BCS-055 (Machine Learning Techniques), BCS-056 (Application of
  Soft Computing), BCS-058 (Data Warehousing & Data Mining)

**Audit findings:**
- No elective choice representation existed in the schema before this phase.
- `student_enrollments` enrolls a user in all semester subjects (registration
  loop); it could not represent a per-student elective selection.
- The shared timetable entries for electives point at the concrete anchor
  subjects BCS-054 (Elective-I) and BCS-058 (Elective-II); only those two
  elective subjects existed in `subjects`. ClassSession carries a concrete
  subject_id; attendance becomes subject-specific through that link.
- Therefore a database migration WAS necessary: elective slot marking,
  a per-student choice table, and the four missing elective subjects.

**Implemented:**
1. `timetable_entries.elective_slot` (nullable enum ELECTIVE_I / ELECTIVE_II)
   — marks the shared Department Elective slots; backfilled from the subject
   tag. NULL = regular entry (never resolved).
2. New `student_elective_choices` table — one row per (user, elective slot),
   UNIQUE(user_id, elective_slot); absence of a row = no selection made
   (incomplete-selection state; never fabricated).
3. Inserted the four missing CTT subjects (BCS-052/053/055/056) scoped to the
   active semester.
4. Registration now requires `elective_i` / `elective_ii` codes (validated
   against the CTT options) and enrolls the student in all non-elective
   subjects PLUS their chosen electives only.
5. `GET /api/v1/timetable` resolves each elective slot to the authenticated
   student's selected subject (anchor subject kept when no choice exists).
6. Attendance read paths (per-subject counts, batched dashboard counts,
   quiz-window counts, daily/Track, history) resolve elective slot sessions
   to the student's chosen subject via a coalesced effective-subject join.
7. Attendance mutation resolves the effective subject for the enrollment
   check on elective slot sessions.
8. Seed pipeline (`seed_academic_baseline.py`, `timetable.json`) marks
   elective slots and includes the full elective catalog.
9. Signup UI adds Department Elective-I / Elective-II selectors.

**Verification:** 16/16 checks PASS on the dev DB (schema, slot marking,
registration/enrollment path in a rolled-back transaction, timetable
resolution to BCS-052/BCS-055, attendance counts resolving the chosen
elective, daily sessions showing the chosen subject and never the anchor).
`git diff --check` PASS. No attendance/eligibility/calendar engine changed.

**Existing users:** the only existing account (admin 2401220100027) has no
elective choices and keeps the anchor subjects (no fabricated selection) —
consistent with ADMIN not being a student.

**Known limitation:** the new elective subjects (BCS-052/053/055/056) have no
quiz schedules (quiz dates not present in the CTT data); quiz eligibility for
them is deferred (only BCS-054/BCS-058 have quiz schedules, matching the
existing seed).

**Production migration (OPERATOR ACTION — not yet applied):** apply revision
`a3b4c5d6e7f8` (adds elective_slot + student_elective_choices + 4 subjects) to
production Supabase via `alembic upgrade head`; downgrade drops the table,
column, subjects, and enum type.

---

## Phase 22.4 — Departmental Elective Resolution Across All Engines & Surfaces (COMPLETE, 2026-08-26)

**Status: COMPLETE** — implementation + local verification on the dev DB
(71/71 verifier checks PASS). Production migration (revision `b7c8d9e0f1a2`)
is a separate operator action; the agent performed no production writes.

**Objective:** the final, authoritative departmental-elective model. The two
Departmental Elective slots are resolved to each student's selected concrete
subject everywhere subject identity is applicable — quiz schedule, academic
events, event-created sessions, dashboard, notifications, calendar, analytics,
history — while the existing shared schedule, dates, quiz cycles, class
sessions, and attendance/eligibility formulas remain untouched.

**Read-only audit outcome:** Phase 22.3 already solved the slot enum, choice
table, timetable + attendance resolution. Phase 22.4 added the remaining
surfaces: quiz schedules, academic events, event-created (extra/quiz-day)
sessions, event creation, calendar, notifications, dashboard/analytics, and
one authoritative resolver (`app/services/elective_resolver.py`).

**Implemented:**

1. **Authoritative resolver** — `ElectiveResolver` in
   `backend/app/services/elective_resolver.py`: the single source of truth for
   the elective catalog (exactly 3 Elective-I + 3 Elective-II codes), the
   shared anchors (BCS-054 → Elective-I, BCS-058 → Elective-II), and
   per-student `slot → selected subject` resolution. Never fabricates a
   student's choice; missing choice falls back to the shared anchor (ADMIN
   keeps the anchor behavior).
2. **Migration `b7c8d9e0f1a2`** — adds nullable `elective_slot` to
   `quiz_schedules`, `academic_events`, `class_sessions`; backfills from the
   anchor subjects' tags. All existing dates/cycles/sessions are preserved.
   Downgrade drops the three columns.
3. **Quiz schedule** — existing BCS-054 quiz schedules marked as Elective-I,
   BCS-058 as Elective-II. Quiz eligibility resolves a student's chosen
   elective to the shared slot's QUIZ_DAY dates (same dates/cycles per slot;
   different subject per student). Quiz Schedule page, Quiz Eligibility,
   dashboard quiz snapshot, current-cycle, and notifications all resolve.
4. **Academic events** — existing BCS-054/058 events classified as elective
   slot events; ADMIN can create new events (Extra Lecture, Extra Tutorial,
   Cancelled Class, Surprise Quiz, Quiz Day) against "Departmental
   Elective-I/II" without knowing a student's selection (ADMIN-only;
   mutually exclusive with subject_id; lab/practical event types rejected for
   slots). The shared event stays ONE row; student-facing reads resolve the
   effective subject per student (events list, calendar, dashboard upcoming,
   notifications).
5. **Event-created sessions** — the EventSessionSynchronizer marks extras and
   quiz-day sessions created from slot events with `elective_slot`, so
   attendance on those sessions resolves per student too (timetable-linked
   sessions already resolved via the timetable entry). No per-student session
   duplication; no change to cancellation/closure/quiz-day semantics.
6. **Attendance/eligibility** — attendance repo predicates extended to
   `COALESCE(timetable.elective_slot, class_session.elective_slot)`; the
   frozen formulas are untouched. Attendance, history, daily/Track, dashboard
   scans, analytics, and eligibility counts attribute slot sessions to each
   student's selected subject.
7. **Frontend** — ADMIN event form exposes "Departmental Elective-I/II" in
   the subject selector; event rows and calendar day details show the
   resolved concrete subject; `types/api.ts` contract extended
   (`elective_slot` + `resolved_subject_*`). Signup selectors unchanged.
8. **Seeds** — `seed_academic_events.py` and
   `materialize_quiz_day_sessions.py` carry the schedule's `elective_slot`
   into created QUIZ_DAY events / quiz-day sessions.

**Data classification (authoritative schedule):**
- `quiz_schedules`: BCS-054 ×3 → ELECTIVE_I, BCS-058 ×3 → ELECTIVE_II.
- `academic_events`: all 14 BCS-054/058 events (6 QUIZ_DAY + 8 class-reality:
  EXTRA_LECTURE 07-17/08-17, CLASS_CANCELLED 07-29/07-30, SURPRISE_QUIZ 08-06)
  → slot events (these subjects exist only as elective anchors).
- `class_sessions`: every BCS-054/058 session slot-marked (incl. extras and
  quiz-day sessions without a timetable link).

**Verification (dev DB only):** py_compile PASS · tsc --noEmit PASS ·
alembic offline upgrade/downgrade SQL PASS · dev DB migration applied +
backfill PASS · downgrade → upgrade round-trip PASS ·
`verify_phase_22_4.py` — 71/71 PASS (schema/backfill, catalog, per-student
resolution across timetable/quiz/events/attendance/history/dashboard scans,
no-leakage, ADMIN slot-event creation + synchronizer slot marking, regular
subjects unchanged, DB baseline restored) · `git diff --check` PASS (no
whitespace errors).

**Existing users:** the only existing account (admin 2401220100027) has no
elective choices and keeps the anchor subjects; no choice is fabricated and
no existing user is silently assigned an elective.

**Production migration (OPERATOR ACTION — NOT applied by the agent):** apply
`alembic upgrade head` (revision `b7c8d9e0f1a2`) to production Supabase. The
operator must first apply Phase 22.3 (`a3b4c5d6e7f8`, still pending), then
Phase 22.4. Downgrade: `alembic downgrade a3b4c5d6e7f8`.

---

# 🟢 Phase 23 — Academic Architecture Evolution (DISCOVERY COMPLETE, BLUEPRINT RECONCILED, GOVERNANCE CONSISTENT)

## Phase 23.0 — Architecture Discovery & Implementation Blueprint (COMPLETE — DISCOVERY PHASE, 2026-08-27)

**Status: READ-ONLY DISCOVERY COMPLETE.** No code, no schema, no migration, no
seed, no UI, no auth, no production data touched. No commit, no push, no PR.
Authoritative report: `docs/phase_23/phase_23_0_architecture_discovery.md`.

**Blueprint reconciliation (2026-08-27):** the core findings were accepted;
ten corrections applied to the blueprint. See report §0 for the full
correction matrix. Key reconciled constraints:

- **23.1 is schema/data-model foundation ONLY** — no admin-authorization schema
  (deferred to 23.9), no consumer wiring (timetable, synchronizer, attendance,
  Track, History, Dashboard, quiz, events, registration, UI, admin auth).
- **Each schema-changing phase owns its own migration lifecycle** with explicit
  operator boundary; 23.10 is final reconciliation/closure, NOT the first
  production migration point.
- **Three-layer model:** EXPECTED TIMETABLE → CLASS SESSION/OCCURRENCE →
  COHORT/SUBJECT-SPECIFIC OUTCOME OR OVERRIDE. The critical example (BCS-058 →
  Surprise Quiz, BCS-055 → Normal Lecture, BCS-056 → Cancelled on same
  date/time/slot) must be representable without per-student duplication.
- **`occurrence_outcomes` is a candidate**, not finalized until 23.4 designs it.
- **No `CLASS` event scope** — ambiguous term removed; scope enumeration
  deferred until 23.1 hierarchy defines semantics.
- **Branch parentage is UNRESOLVED** — current model has no Branch entity
  (`Section.program` is a string); the correct relationship is a 23.1 gate.
  (CURRENT MODEL: AcademicSession → Semester → Section(program). TARGET model
  and final FKs are a 23.1 DECISION GATE, NOT finalized.)
- **AcademicSession / Academic Year (Correction 6):** Repository evidence
  strongly establishes `AcademicSession` as the existing academic-year/session
  entity (`name`, start/end, is_active), with `Semester.session_id` referencing
  it. No second year/session entity is proposed. 23.1 must confirm this
  interpretation before schema implementation; absent contradictory evidence,
  `AcademicSession` remains canonical.
- **`student_enrollments` uniqueness is unresolved** — key chosen in 23.1 gate,
  not blindly added.
- **Legacy unknown state is preserved** — no fabrication of subsection/elective/
  branch for existing users; backfill is a future controlled operation.
- **Subsection examples** (CS-5A → 51/52) are conceptual only — not established
  academic facts.

### Objective

Eliminate architectural ambiguity BEFORE implementation. Determine exactly what
must change so the system can represent the real academic structure of a B.Tech
CSE class — the **TARGET** hierarchy Branch → Semester → Section (≤60) →
Subsection (≈30) — with the full elective catalog (Elective-I: BCS-052/053/054;
Elective-II: BCS-055/056/058), subsection-variable timetables, per-cohort
outcomes/overrides, and the eventual Admin Portal as the authoritative control
plane. **Branch parentage is a 23.1 DECISION GATE, NOT finalized** — the
CURRENT model is AcademicSession → Semester → Section(program), with no Branch
entity.

### Key findings (evidence-based)

1. **The three-layer model is partially representable.** EXPECTED TIMETABLE
   (`timetable_entries`) / CLASS SESSION / OCCURRENCE (`class_sessions`) /
   STUDENT'S RESOLVED SUBJECT (`student_elective_choices` + `ElectiveResolver`)
   are separated; but **COHORT/SUBJECT-SPECIFIC OUTCOME OR OVERRIDE is NOT** —
   a SURPRISE_QUIZ on an elective slot applies to the whole slot; `class_sessions`
   cannot express "BCS-058 cohort → Surprise Quiz, BCS-055 cohort → Normal
   Lecture" on the same date/time. The recommended minimal fix is an additive
   `occurrence_outcomes` candidate (report §25, Option 1 — NOT finalized until
   23.4).
2. **No Subsection concept exists.** No `subsections` table, no
   `users.subsection_id`, no subsection on `timetable_entries`/`class_sessions`/
   `academic_events`. `sections.name` is globally unique.
3. **Single-section/single-semester assumptions** are concentrated in
   registration (`auth.py` auto-assigns exactly one section), seed/verifier
   constants (2026-07-15 → 2026-12-31, "CSE-51", "V Semester"), and the
   synchronizer building `entries_by_dow` from ALL timetable entries (no
   section filter — a cross-section collision risk once a second section
   exists). The ORM core is already session-scoped.
4. **Elective catalog is hardcoded in code** (`elective_resolver.py`), not
   DB-driven; four elective subjects (BCS-052/053/055/056) have no quiz dates
   (data gap — nothing invented).
5. **No admin hierarchy.** Single `UserRole` (STUDENT/ADMIN), no
   HEAD/SECTION/SUBSECTION/ELECTIVE admin scoping.
6. **No canonical student-context read model.** `/student/me` returns partial
   context; subsection + electives are resolved per-request elsewhere.

### Recommended Phase 23.x sequence (reconciled)

23.1 Academic hierarchy/data foundation (SCHEMA ONLY — subsections,
users.subsection_id, gates; **no timetable/session columns** → 23.3) →
23.2 Student academic context → 23.3 Timetable + subsection scheduling
(schema + wiring for `timetable_entries.subsection_id` /
`class_sessions.subsection_id`) → 23.4 Outcome/override model →
23.5 Elective resolution (config-driven) → 23.6 Quiz architecture →
23.7 Event architecture → 23.8 Attendance/engine integration →
23.9 Admin authorization foundation → 23.10 Migration reconciliation/closure.

### Governance

- Phase 23.0 is a **discovery phase** — it records findings and a blueprint.
  No implementation tasks are marked complete; no future phase is marked
  COMPLETE. Phase 23.1 onward requires a fresh execution prompt.
- **Each schema-changing phase** owns its own migration lifecycle (discovery →
  offline validation → local/dev migration → verification → operator boundary →
  production migration only when separately authorized). 23.10 is the final
  reconciliation/closure, not the first production migration point.
- **Final governance consistency correction (2026-08-27):** the four governance
  documents were scanned for contradictions involving Branch parentage
  (CURRENT vs TARGET vs 23.1 DECISION GATE), AcademicSession/Academic Year
  (evidence-strong + 23.1 confirmation), CLASS_ADMIN (replaced by SECTION_ADMIN),
  subsection backfill (no fabrication, no deterministic default), admin_scopes
  in 23.1 (deferred to 23.9), event scope, occurrence_outcomes, the 23.1
  schema-only boundary, and old Phase 23 numbering. All documents now agree;
  there is exactly ONE authoritative Phase 23 breakdown (23.0…23.10).

---

# 🟢 Phase 23.1 — Academic Hierarchy & Enrollment Schema Foundation (COMPLETE, 2026-08-27)

**Status: COMPLETE — schema/data-model foundation only.** Migration
`c8d9e0f1a2b3` (offline SQL verified; dev-DB application is an OPERATOR
action — `backend/.env` points at the production Supabase pooler, so the
agent cannot safely run `alembic upgrade`). No consumer/engine/registration/
UI/admin wiring. No commit, no push, no PR.

## Decision gates (resolved from repository evidence)

| Gate | Result | Evidence |
|---|---|---|
| AcademicSession = academic-year entity | **CONFIRMED** | `AcademicSession` (name unique "2026-27", start/end, is_active); `Semester.session_id` FK → it. No second academic-year entity. |
| Branch parentage | **REMAINS UNRESOLVED (gate preserved)** | No Branch entity exists; `Section.program` (string) is the only program representation. No evidence supports a target FK parentage; `branches` table NOT created. |
| Section/program semantics | **CONFIRMED (preserved)** | Section remains a semester-scoped class group with a stored `program` attribute; names now unique per semester (not globally). |
| Enrollment uniqueness | **CONFIRMED** | `UNIQUE(user_id, subject_id)` — subject_id is semester-scoped, so multi-semester history coexists (same subject code in a later semester = different Subject row). No global section lock. |
| Subsection semantics | **CONFIRMED (NULL-preserving)** | New `subsections` table + `users.subsection_id` nullable; NULL = UNKNOWN/UNASSIGNED. No fabrication, no auto-assignment. `max_strength` nullable (open value). |

## Schema changes delivered

1. **`subsections`** table (id, name, `section_id` FK → sections, `max_strength`
   nullable, timestamps) + `UNIQUE(section_id, name)` — no rows created.
2. **`users.subsection_id`** (nullable FK → subsections) — no backfill.
3. **`sections.name`** global-unique index → composite `UNIQUE(semester_id, name)`
   (guarded; 1 section today → safe).
4. **`student_enrollments`** `UNIQUE(user_id, subject_id)` (guarded; none
   duplicated per Phase 17/21D.3 audits).

## Deliberately NOT in 23.1

- `timetable_entries.subsection_id` / `class_sessions.subsection_id` (→ 23.3)
- occurrence/outcome model + event-scope enum (→ 23.4/23.7)
- `admin_scopes` / SECTION_ADMIN role (→ 23.9)
- Branch entity, AcademicSession duplicate, subsection fabrication/backfill
- No attendance/timetable/registration/frontend/auth behavior changes

## Phase 23.2 — Curriculum Model Implementation (COMPLETE, 2026-08-27)

**Status: COMPLETE — schema-hardening change only.** Migration
`d0e1f2a3b4c5` (chain: `c8d9e0f1a2b3` → `d0e1f2a3b4c5`). The ONLY authorized
schema change: `UNIQUE(code, semester_id)` on `subjects`. Invariant: a subject
code may appear in different semesters, but the same code may not occur twice
within the same semester. Offline SQL verified; live DB application is an
operator action (same environment constraint as Phase 23.1 — `backend/.env`
→ production pooler, Docker down). No commit, no push, no PR.

> Discovery context: `docs/phase_23/phase_23_2_curriculum_discovery.md` —
> `Subject.code` was NOT unique even within a semester; `UNIQUE(code,
> semester_id)` was the single confirmed REQUIRED change. Elective catalog
> is hardcoded in code (Phase 23.5 concern); no non-credit distinction for
> BNC-501 (requires operator decision — NOT implemented).

### Changes delivered

1. **`subjects`** — `UNIQUE(code, semester_id)` (`uq_subjects_code_semester`).
   Existing `ix_subjects_code` single-column index PRESERVED (independent
   consumer: `SubjectRepository.get_by_code` used by the quiz endpoint,
   registration, elective-resolver anchors).
2. **Migration guard** — preflight duplicate check (`GROUP BY code, semester_id
   HAVING COUNT(*) > 1`) in online mode; refuses if duplicates exist.

### Deferred (documented, NOT implemented)

- BNC-501 non-credit modeling (undecided — operator decision).
- Elective catalog redesign (Phase 23.5).
- Cross-semester subject identity, curriculum versioning, enrollment redesign.
- No attendance/quiz/event/timetable/registration/frontend/auth changes.

---

# 🟢 Phase 23.3 — Student Academic Assignment (COMPLETE, 2026-08-28)

**Status: COMPLETE — consolidation/normalization, NOT a redesign.** Migration
`e3f4a5b6c7d8` (chain: `d0e1f2a3b4c5` → `e3f4a5b6c7d8`). The Phase 23.3
execution prompt re-scopes Phase 23.3 as **Student Academic Assignment** (the
timetable/subsection-scheduling slice formerly labeled "23.3" in the 23.0
blueprint is re-scoped to later Phase 23 timetable work — see Deferred).
Offline SQL verified; live DB application is an operator action (same
environment constraint as 23.1/23.2 — `backend/.env` → production pooler,
Docker down). No commit, no push, no PR.

## Objective

Make the relationship between a student and their academic
placement / enrollment / elective choices **explicit and authoritative** by
consolidating around the already-existing Phase 22.3/22.4 elective architecture
(not reinventing it), with the minimum additive normalization.

## Conceptual separation established

- **A. Academic placement** — `users.section_id` (+ nullable `users.subsection_id`)
  → `Section` → `Semester` → `AcademicSession`; branch = `Section.program`. Already
  authoritative (23.1); `/student/me` now also exposes `subsection_name`.
- **B. Compulsory enrollment** — `student_enrollments` rows with
  `enrollment_type = COMPULSORY` (program requirements: common theory +
  practical subjects).
- **C. Elective selection** — `StudentElectiveChoice` + `ElectiveResolver`
  (Phase 22.3/22.4) remain the single authoritative elective resolver. The chosen
  concrete subject is enrolled, and that enrollment row is tagged
  `enrollment_type = ELECTIVE`. A logical slot (DE-I / DE-II) is never itself an
  enrollment.

## Changes delivered

1. **Schema** — `student_enrollments.enrollment_type` native enum
   `enrollmenttype` (COMPULSORY / ELECTIVE), server_default COMPULSORY,
   NOT NULL after deterministic backfill. Additive + backward-safe.
2. **Migration `e3f4a5b6c7d8`** (parent `d0e1f2a3b4c5`) — creates the enum, adds
   the column, backfills ELECTIVE on every existing enrollment that has a
   matching `StudentElectiveChoice` for an Elective-I / Elective-II subject
   (deterministic; no existing row/choice/attendance rewritten), then enforces
   NOT NULL.
3. **Registration** (`auth.py`) — new enrollments tagged COMPULSORY (non-elective)
   / ELECTIVE (chosen DE-I/DE-II).
4. **API (additive, backward-compatible)** — `GET /student/me` + `StudentProfile`
   now expose `subsection_name` (placement) and `elective_i` / `elective_ii`
   (the student's concrete elective codes; NULL when unassigned). No second
   endpoint.

## Deferred (documented, NOT implemented)

- Timetable/subsection scheduling (the slice the 23.0 blueprint had labeled
  "23.3") — re-scoped to later Phase 23 timetable redesign (23.5+ per this
  prompt's roadmap framing: timetable/session/occurrence/event redesign).
- Placement↔enrollment semester FK / authoritative reusable student-context
  service (Phase 23.4) — not started.
- Subsection + elective backfill for unassigned legacy users (admin-controlled
  remediation / future product decision) — no fabrication.
- `branches` table / Branch parentage (23.1 DECISION GATE remains open).
- Enrollment redesign, elective catalog redesign (Phase 23.5), BNC-501
  non-credit modeling (undecided).

## Verification

- Backend `compileall` — PASS.
- Offline SQL (`alembic upgrade d0e1f2a3b4c5:e3f4a5b6c7d8 --sql` + downgrade) —
  PASS: `CREATE TYPE enrollmenttype` + `ADD COLUMN` + deterministic `UPDATE`
  backfill + `SET NOT NULL`; downgrade reverses.
- `alembic heads` → single head `e3f4a5b6c7d8`; linear chain preserved.
- Frontend `npx tsc --noEmit` — PASS.
- Logic-level verification matrix (no DB): catalog separation (DE-I vs DE-II),
  cross-slot rejection, concrete-subject→slot mapping, compulsory/elective
  distinction explicit on the model, slot-not-an-enrollment — ALL PASS.
- **Production DB not touched.** Migration NOT applied by the agent.

---

# 🟢 Phase 23.4 — Authoritative Student Context Service (COMPLETE, 2026-08-28)

**Status: COMPLETE — service-layer consolidation; NO schema/migration change.**
Alembic head unchanged (`e3f4a5b6c7d8` from Phase 23.3; no new migration).
No commit, no push, no PR.

## Objective

Create **one reusable backend authority** for resolving a student's current
academic context (placement → enrollment → elective choice), so downstream
services do not independently reconstruct the `User → Section → Semester →
AcademicSession` chain. Migrate only the consumers that genuinely duplicated
context resolution; keep every external response contract identical.

## Discovery — context-consumer map

| Consumer | Previous resolver | Placement | Enrollments | Electives | Migrated |
|---|---|---|---|---|---|
| `/student/me` | `UserRepository.get_academic_context` + `get_elective_codes` | Y | N | Y | ✅ → `get_context` |
| Dashboard | **inline `Section→Semester`** (dashboard_service) | Y | Y (repo) | Y (resolver) | ✅ → `get_placement` |
| Quiz eligibility | **inline `Section→Semester`** (quiz.py) | Y | Y (check) | N | ✅ → `get_placement` |
| Calendar | `UserRepository.get_academic_context` | Y | N | Y (resolver) | ✅ → `get_placement` |
| Analytics | `UserRepository.get_academic_context` | Y | Y (repo) | N | ✅ → `get_placement` |
| Attendance History | `UserRepository.get_academic_context` | Y | N | N | ✅ → `get_placement` |
| Timetable | `user.section_id` direct (placement only) | Y | N | Y (resolver) | ⛔ intentionally unchanged (trivial placement) |
| Registration | authoritative provisioning (auth.py) | Y | Y | Y | ⛔ intentionally unchanged (provisioning ≠ resolution; circular-dependency risk) |

**Duplicated logic found:** Dashboard and the Quiz endpoint each independently
reconstructed the `Section → Semester` chain. Calendar/Analytics/Attendance were
already centralized via `UserRepository.get_academic_context`.

**Conflicting logic:** none found. **Authoritative sources selected:**
`users.section_id`/`subsection_id` → `sections`/`subsections` → `semesters` →
`academic_sessions` (placement); `student_enrollments` + `enrollment_type`
(Phase 23.3) (enrollment); `student_elective_choices` + `ElectiveResolver`
catalog (Phase 22.3/22.4) (elective selection — NOT recreated).

## Architecture

```
StudentContextService (service layer, read-only)
  ├── get_placement(user)   → section → semester → academic session → subsection
  ├── get_context(user)     → placement + enrollments + elective choices + first quiz date
  └── consumes:
        StudentElectiveChoice + ElectiveResolver (authoritative elective system)
        student_enrollments.enrollment_type (Phase 23.3)
```

New files: `backend/app/services/student_context_service.py`,
`backend/app/schemas/student_context.py` (`StudentContext` + `ContextSubject`
read models — stable service-level representation, not ORM objects).

Query efficiency: `get_placement` = 4 fixed lookups; `get_context` adds exactly
3 queries (enrollments, elective choices, first quiz date) — no N+1, no
cross-join, no duplicate enrollments, no per-student row multiplication.

## Equivalence (all migrated consumers)

`old academic context == new authoritative context` for the same student,
verified by code-path equivalence: identical resolution chain, identical NULL
handling, identical fallbacks (Quiz/History default to `today` when unplaced;
Calendar returns empty month when unplaced). `/student/me` contract unchanged
(section_name, subsection_name, program, semester_name, academic_session,
semester_start, semester_end, first_quiz_date, elective_i, elective_ii, role).

## No schema change

Phase 23.4 required **no migration**. The Phase 23.3 migration
(`e3f4a5b6c7d8`) is untouched and remains NOT applied to production.

## Verification

- Backend `compileall` — PASS.
- Frontend `npx tsc --noEmit` — PASS (no frontend change).
- Alembic head unchanged (`e3f4a5b6c7d8`); no new migration.
- Logic-level checks (no DB): three concepts distinct; cross-slot / non-catalog
  elective codes detected (recorded as inconsistency, not repaired); Context A
  vs Context B isolation; bounded query design — ALL PASS.
- Failure-state behavior (code review): valid placement → `is_placed=True`;
  missing subsection → NULL (never invented); missing elective → empty choices;
  invalid elective → `inconsistencies` recorded (not repaired); missing section
  → `is_placed=False` + NULLs; missing semester/session → impossible (FK NOT
  NULL); missing enrollment → empty list (read-only, nothing created).

## Deferred (documented, NOT implemented)

- Phase 23.5 elective/catalog redesign (resolver remains authoritative).
- Timetable / class-session / event / quiz / attendance redesign (later slices).
- Reusable context consumption for registration provisioning (kept separate —
  documented decision).
- `branches` table / Branch parentage (23.1 gate); BNC-501 non-credit modeling
  (undecided).

---

# 🟢 Phase 23.5 — Elective/Catalog Redesign (COMPLETE, 2026-08-28)

**Status: COMPLETE — catalog normalized into the database.** Migration
`f5a6b7c8d9e0` (chain: `e3f4a5b6c7d8` → `f5a6b7c8d9e0`). Offline SQL verified;
live DB application is an operator action (same environment constraint as prior
23.x — `backend/.env` → production pooler, Docker down). No commit, no push, no
PR.

## Objective

Normalize the elective/catalog domain so the academic catalog cleanly represents
Departmental Elective slots and their allowed concrete subjects, making the
catalog the authoritative source of *what can be selected* — without redesigning
timetable/session/event/quiz/attendance systems or the student-context service,
and without creating a second elective resolver.

## Discovery — catalog gap

The catalog was previously split between (a) hardcoded code constants in
`ElectiveResolver` (`ELECTIVE_I_CODES`/`ELECTIVE_II_CODES`/`SLOT_CODES`) and (b)
the free-form `subjects.tag` string ("Elective-I"/"Elective-II", but also "Lab"
for practicals). Problems: the catalog was hardcoded (a future semester needed a
code change + redeploy); constants and `tag` could diverge (flagged in 23.2);
`tag` is a free string, unsafe as a typed slot marker; registration validated
against constants while enrolling via `tag` — two catalog sources in one flow.

## Catalog model decision (smallest correct)

No new tables. `subjects` is already the semester-scoped catalog of concrete
subjects (semester_id NOT NULL, UNIQUE(code, semester_id) since 23.2). Adding a
typed, nullable `subjects.elective_slot` (`electiveslot` enum) makes slot
membership authoritative and type-safe:

- NULL = common / practical subject (never an elective);
- ELECTIVE_I = DE-I allowed (BCS-052/053/054);
- ELECTIVE_II = DE-II allowed (BCS-055/056/058).

A single column guarantees one slot per subject (a subject can never silently
belong to both slots). A separate catalog table would be LESS normalized
(permit dual-slot membership). The logical slot (`ElectiveSlot`), the concrete
subject (`Subject`), and the student's selected subject
(`StudentElectiveChoice`) remain three distinct concepts.

## Changes delivered

1. **Schema** — `subjects.elective_slot` (nullable `electiveslot` enum).
2. **Migration `f5a6b7c8d9e0`** — additive column + deterministic backfill from
   the authoritative `tag` marker ('Elective-I'→ELECTIVE_I,
   'Elective-II'→ELECTIVE_II); no destructive operations; downgrade drops the
   column.
3. **Resolver** — `ElectiveResolver` is now DB-driven: `catalog_codes()`
   (active-session catalog, one query), `slot_for_code(code)`,
   `validate_selection(elective_i, elective_ii)` (async). Hardcoded
   `ELECTIVE_I_CODES`/`ELECTIVE_II_CODES`/`SLOT_CODES`/`ALL_ELECTIVE_CODES` and
   the module-level sync `slot_for_code`/`validate_selection` removed.
   `ANCHOR_CODES` (shared schedule anchors BCS-054/058) retained — schedule
   representation, not catalog. No second resolver created.
4. **Registration** (`auth.py`) — elective validation moved from Pydantic
   field validators to the async endpoint against the DB catalog (422 preserved
   for invalid selections); enrollment loop uses `subject.elective_slot` instead
   of `subject.tag`.
5. **StudentContextService** — elective-choice validation now uses the async
   `ElectiveResolver.slot_for_code` (DB-backed).
6. **API (additive)** — `SubjectResponse` + frontend `SubjectResponse` type gain
   optional `elective_slot`.
7. **Seed** — sets `elective_slot` from tag on new subjects.
8. **Verifier** — `verify_phase_22_4.py` catalog section now verifies the
   DB-backed catalog (was the removed code constants).

## Compatibility impact

Downstream systems (timetable, quiz, events, sessions, attendance, history,
Track, dashboard, notifications, calendar, analytics) are UNCHANGED — they
already consume `ElectiveResolver`, whose per-student resolution API
(`load_choices`, `chosen_elective_map`, `anchor_subjects`, `resolve_subject`,
`resolve_events`) is identical. Same resolved student-specific subject as
before, with a cleaner authoritative catalog underneath.

## Verification

- Backend `compileall` (app + alembic + scripts) — PASS.
- Frontend `npx tsc --noEmit` — PASS.
- Alembic single head `f5a6b7c8d9e0`; linear chain preserved.
- Offline upgrade SQL (`ADD COLUMN` + deterministic `UPDATE` backfill) and
  downgrade SQL (`DROP COLUMN`) — PASS.
- Backfill outcome verified deterministically against the authoritative CTT
  (`timetable.json`): DE-I={BCS-052,053,054}, DE-II={BCS-055,056,058}, disjoint,
  practicals (tag=Lab) never elective.
- Two-context matrix: A (DE-I=BCS-054, DE-II=BCS-058) and B (DE-I=BCS-052,
  DE-II=BCS-055) — each in its slot, no cross-slot, no leakage.
- No stale references to removed constants in app/scripts.
- **Production DB not touched.** Migration NOT applied by the agent.

## Deferred (documented, NOT implemented)

- Student elective switching, semester rollover, subsection/elective
  remediation.
- Timetable / occurrence / event / quiz / attendance redesign (later slices).
- `branches` table / Branch parentage (23.1 gate); BNC-501 non-credit modeling.

---

# 🟢 Phase 23.6 — Actual Occurrence Architecture (COMPLETE, 2026-08-28)

**Status: COMPLETE — per-subject occurrence outcomes.** Migration
`f6a7b8c9d0e1` (chain: `f5a6b7c8d9e0` → `f6a7b8c9d0e1`). Offline SQL verified;
live DB application is an operator action (same environment constraint as prior
23.x — `backend/.env` → production pooler, Docker down). No commit, no push, no
PR.

## Objective

Establish a clear separation between the EXPECTED schedule
(`timetable_entries`) and the ACTUAL occurrence (`class_sessions`), and let one
actual occurrence have DIFFERENT effective types for different concrete
subjects in the same Departmental Elective slot — without duplicating
timetable/session/event infrastructure per student and without exposing one
student's occurrence to another.

## Discovery — gap

A `class_sessions` row is the canonical actual occurrence (normal / extra /
cancelled / quiz-day / surprise quiz via `is_extra` + `is_cancelled`;
modified/substitution is calendar-engine-level). It is complete for SHARED
occurrences, but its `is_extra`/`is_cancelled` flags are single-valued — the
DE-II divergence (`BCS-058→Surprise Quiz`, `BCS-055→Normal Lecture`,
`BCS-056→Cancelled`) could not be expressed. A subject-specific SURPRISE_QUIZ
created an *extra* (Student A saw lecture + quiz), and a subject-specific
CLASS_CANCELLED for a non-anchor subject (BCS-056) matched no timetable entry
(no-op).

## Architectural decision

New additive table `occurrence_outcomes` (class_session_id, subject_id,
outcome_type; UNIQUE(session, subject)) + enum `OccurrenceOutcomeType`
(EXTRA_LECTURE/EXTRA_TUTORIAL/EXTRA_PRACTICAL/SURPRISE_QUIZ/CANCELLED). The
session row remains the ANCHOR (shared default); an outcome *overrides* the
occurrence's effective type for ONE concrete subject. Read path applies the
outcome for the student's resolved elective subject; absence = anchor. No
per-student session/event duplication; `class_sessions.id` remains the stable
attendance identity.

```
Timetable entry (expected) --timetable_entry_id--> ClassSession (anchor occurrence)
                                                        |  + occurrence_outcomes (per-subject override)
                                                        v
                                   resolve(COALESCE(choice.subject_id, ClassSession.subject_id))
                                                        v
                                        student-specific effective occurrence
```

## Files changed

- `app/models/occurrence.py` — NEW `OccurrenceOutcome` model.
- `app/models/enums.py` — NEW `OccurrenceOutcomeType`.
- `app/models/__init__.py` — exports the model.
- `alembic/versions/f6a7b8c9d0e1_add_occurrence_outcomes.py` — NEW migration.
- `app/services/event_session_service.py` — synchronizer creates outcomes for
  subject-specific elective events (extended, not replaced; state-based +
  idempotent).
- `app/repositories/session_repo.py` — outcome add/delete helpers.
- `app/repositories/attendance_repo.py` — read queries carry an additive
  outcome LEFT JOIN (student-scoped) + `_apply_outcome_to_row` per-student
  post-processing.
- `app/engines/practical_occurrence.py` — `occurrence_is_cancelled` doc updated
  (outcome-cancelled rows are already `is_cancelled=True` at the read layer).

## Schema/migration

`occurrence_outcomes`: id, created_at, updated_at, class_session_id FK,
subject_id FK, outcome_type enum, UNIQUE(class_session_id, subject_id) +
index on class_session_id. Empty table (no backfill). Downgrade drops index →
table → enum.

## Occurrence semantics

Normal/Extra/Cancelled/Quiz/Surprise Quiz = anchor session flags (+ outcome
override for a subject). Modified/substitution = deferred (Phase 23.7
event-scope). Quiz-day = existing separate occurrence (unchanged).

## Elective-isolation semantics

A subject-specific event (elective_slot NULL + catalog elective subject) whose
slot has a timetable session on the date produces an OUTCOME overriding the
anchor session (BCS-058→SURPRISE_QUIZ, BCS-056→CANCELLED; BCS-055 has none →
anchor = normal). When the slot has no session that date, extras fall back to a
subject-scoped extra session and cancellations become no-ops. The outcome join
is keyed on (session, the student's RESOLVED subject) — Student A's outcome can
never appear on Student B's rows.

## Compatibility impact

Zero effect on existing data (the table starts empty; the LEFT JOIN yields NULL
outcome for every existing row). Attendance engine, eligibility, calendar
engine, event registry, quiz, dashboard/calendar/analytics/history/track
consumers untouched. Registration untouched. No frontend change.

## Verification

- Backend `compileall` (app + alembic + scripts) — PASS.
- Frontend `npx tsc --noEmit` — PASS (no frontend change).
- Alembic single head `f6a7b8c9d0e1`; linear chain preserved.
- Offline upgrade SQL (CREATE TYPE + CREATE TABLE + index) and downgrade SQL
  (DROP index/table/type) — PASS.
- `_desired_schedule` branch simulations — PASS: subject-specific
  SURPRISE_QUIZ(BCS-058)→outcome; CLASS_CANCELLED(BCS-056)→outcome (anchor kept
  in schedule); fallback extras; non-elective legacy path unchanged.
- Per-subject override logic — PASS: A→extra(quiz), B→anchor(normal),
  C→cancelled; no leakage (per-subject join key).
- Query-build + import checks — PASS (no circular imports).
- Idempotency: state-based reconciliation (outcome create/update + stale
  removal) is deterministic; running twice converges (same design as the
  existing synchronizer).
- **Production DB not touched.** Migration NOT applied by the agent.

## Deferred (documented, NOT implemented)

- Phase 23.8 quiz architecture integration with outcomes.
- Phase 23.9 attendance MUTATION integration (reject marking on an
  outcome-cancelled occurrence for the affected subject) — read path only here.
- Phase 23.10 canonical read models; 23.11 API scope/authorization.
- Phase 24 Admin Portal.

---

# 🟢 Phase 23.7 — Event-Scope Redesign + MODIFIED (COMPLETE, 2026-08-28)

**Status: COMPLETE.** Migration `f7a8b9c0d1e2` (chain: `f6a7b8c9d0e1` →
`f7a8b9c0d1e2`; a single `ALTER TYPE occurrenceoutcometype ADD VALUE
'MODIFIED'`). Offline SQL verified; live DB application is an operator action
(same environment constraint as prior 23.x — `backend/.env` → production
pooler, Docker down). No commit, no push, no PR.

## Objective

Represent event scope correctly when an academic event applies to a concrete
subject within a shared elective occurrence, and introduce `MODIFIED` as an
event-scope-level occurrence outcome (deferred from 23.6). Preserve the
distinction: EVENT → event scope → occurrence/session effect → attendance
identity (`class_sessions.id`).

## Discovery — the architectural question

"How does an event identify the concrete occurrence/subject scope it modifies
when multiple concrete subjects share one timetable occurrence?" Current
architecture: subject-scoped events carry `subject_id` (concrete subject); the
shared occurrence is the anchor session for that subject's slot (derived from
the Phase 23.5 catalog) on the date. This already works for EXTRA_*/SURPRISE_QUIZ
/CANCELLED outcomes. The genuine gap: `OccurrenceOutcomeType.MODIFIED` was
deferred from 23.6, and no event type produced it.

## Architectural decision

- New subject-scoped `EventType.CLASS_MODIFIED` ("the scheduled class was
  modified" — time/room/delivery). Registry rule: requires subject + class
  type (L/T/P); **subject-scoped only** (elective_slot + CLASS_MODIFIED is
  rejected — a whole-slot "modified" cannot be a single occurrence outcome).
  Student-creatable for own enrolled subjects (mirrors CLASS_CANCELLED).
- New `OccurrenceOutcomeType.MODIFIED`: the scheduled occurrence happened but
  was modified for one concrete subject. It is NOT extra, NOT cancelled, NOT a
  quiz — attendance/eligibility/calendar mathematics are untouched; the read
  path changes no `is_extra`/`is_cancelled` flag (the `outcome_type` is exposed).
- Synchronizer: subject-scoped CLASS_MODIFIED whose subject has a timetable
  session that date produces a MODIFIED outcome on the shared anchor session
  (elective subject → slot anchor session; non-elective subject → the subject's
  own session). No session → no-op.
- `_reconcile_outcomes` generalized to locate anchor sessions by slot
  (elective) OR by subject_id (non-elective); state-based, idempotent,
  deterministic, attendance-safe.

## Files changed

- `backend/app/models/enums.py` — `EventType.CLASS_MODIFIED`,
  `OccurrenceOutcomeType.MODIFIED`.
- `backend/alembic/versions/f7a8b9c0d1e2_add_occurrenceoutcometype_modified.py`
  — NEW migration (ALTER TYPE ADD VALUE; downgrade documented no-op — PG cannot
  remove enum values).
- `backend/app/services/event_registry.py` — rule for CLASS_MODIFIED; reject
  CLASS_MODIFIED + elective_slot.
- `backend/app/services/event_service.py` — CLASS_MODIFIED added to
  `STUDENT_CREATABLE_EVENT_TYPES`.
- `backend/app/services/event_session_service.py` — CLASS_MODIFIED branch in
  `_desired_schedule` (elective + non-elective targets); `_reconcile_outcomes`
  generalized; `EVENT_TO_OUTCOME_TYPE[CLASS_MODIFIED] = MODIFIED`.
- `backend/app/repositories/attendance_repo.py` — `_apply_outcome_to_row` only
  sets `is_extra` for EXTRA_*/SURPRISE_QUIZ; MODIFIED changes no flag.
- `frontend/src/types/api.ts` — EventType enum gains CLASS_MODIFIED.
- `frontend/src/components/events/eventRules.ts` — rule + student-creatable +
  duration-mode entries for CLASS_MODIFIED.

## Event-scope semantics

- Slot-wide: `elective_slot` set (+ anchor subject) — unchanged.
- Subject-scoped: `subject_id` set, `elective_slot` NULL — the concrete subject
  is the scope; for elective catalog subjects the shared occurrence is the
  subject's slot anchor session (23.5/23.6 established), for non-elective
  subjects it is the subject's own session.
- Global events: unchanged (no subject/scope).

## MODIFIED semantics

`MODIFIED` is an event-scope-level occurrence outcome: one concrete subject's
occurrence within a shared elective slot is modified while other subjects in
the same occurrence remain on the anchor state. It is resolvable through the
same canonical `occurrence_outcomes` architecture (no second table, no
student-level rows, no per-student session duplication, no class_session
boolean). Backward compatible: with no CLASS_MODIFIED events, no outcomes are
created and all existing 23.6 behavior is a no-op.

## Elective isolation

Example: CLASS_MODIFIED for BCS-058 on the shared DE-II slot → MODIFIED outcome
keyed (anchor session, BCS-058). BCS-055/BCS-056 have no outcome → anchor
(normal). The read-path outcome join is keyed on
`(class_session_id, COALESCE(choice.subject_id, ClassSession.subject_id))` — a
BCS-058 outcome can never match a BCS-055/056 row (no leakage).

## Compatibility impact

Zero effect on existing data (no CLASS_MODIFIED events exist; the new outcome
type is unused until such events are created). Attendance engine, eligibility,
calendar engine, quiz, registration, dashboard/calendar/analytics/history/track
untouched. Frontend changes are additive contract syncs (EventType enum +
eventRules mirror).

## Verification

- Backend `compileall` — PASS.
- Frontend `npx tsc --noEmit` — PASS (eventRules/EventType extended).
- Alembic single head `f7a8b9c0d1e2`; linear chain preserved.
- Offline upgrade SQL — PASS (`ALTER TYPE occurrenceoutcometype ADD VALUE
  'MODIFIED'`).
- In-process simulations (temp script removed): CLASS_MODIFIED on an elective
  subject with a slot session → MODIFIED outcome; on a non-elective subject
  with a session → MODIFIED outcome; no session → no-op; SURPRISE_QUIZ (23.6)
  unchanged; `EVENT_TO_OUTCOME_TYPE` maps CLASS_MODIFIED → MODIFIED;
  `_apply_outcome_to_row` leaves flags unchanged for MODIFIED and keeps
  CANCELLED behavior — ALL PASS.
- **Production DB not touched.** Migration NOT applied by the agent.

## Deferred (documented, NOT implemented)

- Phase 23.8 quiz architecture integration with outcomes.
- Phase 23.9 attendance MUTATION integration (outcome-aware marking gate).
- Phase 23.10 canonical read models; 23.11 API scope/authorization.
- Phase 24 Admin Portal.
- Whole-slot "modified" event (rejected: subject-scoped only) — future product
  decision.

---

# 🟢 Phase 23.8 — Quiz Integration (COMPLETE, 2026-08-28)

**Status: COMPLETE — MODIFIED is occurrence metadata for the quiz pipeline.**
No migration (discovery proved none necessary). Alembic head unchanged
(`f7a8b9c0d1e2` from Phase 23.7). No commit, no push, no PR.

## Objective

Integrate the Phase 23.7 event-scope / MODIFIED occurrence architecture with
the existing quiz architecture so quiz reality remains correct when a concrete
subject's scheduled occurrence is modified — without rebuilding the quiz
architecture, without leaking MODIFIED to other subjects, and without touching
the eligibility engine.

## Discovery — quiz pipeline

- **Quiz identity**: `quiz_schedules` (subject + cycle, seed-time projection) +
  canonical quiz dates from active `QUIZ_DAY` AcademicEvents
  (`get_effective_quiz_dates_for_subjects`, ranked → cycles).
- **Elective resolution**: `ElectiveResolver.chosen_elective_map(user_id)` →
  slot's QUIZ_DAY events.
- **Occurrence relationship**: quiz date → attendance window (calendar engine)
  → `get_subject_counts_between(exclude_quiz_day=True)` → eligibility engine.
  This counting query is outcome-aware since Phase 23.6.
- **MODIFIED semantics**: occurrence **metadata only** for the quiz pipeline —
  a modified class is still a conducted class (`is_cancelled=False`, no flag
  change), counted in every attendance denominator; quiz dates, quiz occurrence
  identity, eligibility windows, and eligibility results are unchanged.
- **Subject isolation**: outcome join key
  `(class_session_id, COALESCE(choice.subject_id, ClassSession.subject_id))`.

## Genuine integration defect found + fixed

A subject-specific CLASS_MODIFIED (priority 10, processed after CLASS_CANCELLED
at 30) could **overwrite a CANCELLED desired outcome** for the same
subject/date → a cancelled occurrence would read as MODIFIED (conducted).
Fixed in `event_session_service._desired_schedule`: the CLASS_MODIFIED branch
no longer overwrites an existing CANCELLED outcome (cancellation wins over
modification — the documented Phase 6.6 invariant). Smallest possible change to
the Phase 23.7 code; documented in governance per the frozen-code rule.

## Files changed

- `backend/app/services/event_session_service.py` — the CANCELLED-wins guard
  in the CLASS_MODIFIED branch (the only production-code change).
- NEW `backend/scripts/verify_phase_23_8.py` — DB-based, self-cleaning
  verifier (operator-run) proving the integration matrix.

## Quiz integration semantics

- MODIFIED does not affect quiz dates, quiz occurrence identity, eligibility
  windows, attendance counting shape, or eligibility results.
- A modified class counts as conducted in eligibility L/T windows and subject
  attendance (never attended/absent/cancelled).
- QUIZ_DAY (quiz dates + quiz-day occurrence) unchanged; SURPRISE_QUIZ
  (extra/outcome) unchanged; CLASS_CANCELLED unchanged; CLASS_MODIFIED produces
  MODIFIED only where its subject-scoped event applies.

## Elective isolation

BCS-058 MODIFIED → MODIFIED outcome keyed (anchor session, BCS-058); BCS-055/
BCS-056 have no outcome → anchor state. Read-path rows are keyed per resolved
subject, so Student A's MODIFIED state never appears in Student B's rows
(verifier-provable).

## Schema/Migration changes

**None.** Discovery proved the existing schema (occurrence_outcomes + enum) can
represent the required quiz integration. Alembic head unchanged (`f7a8b9c0d1e2`).

## Verification

- Backend `compileall` — PASS.
- Frontend `npx tsc --noEmit` — PASS (no frontend change).
- Alembic single head `f7a8b9c0d1e2`; no new migration.
- In-process logic checks (temp script removed): CANCELLED-wins fix verified;
  MODIFIED alone → MODIFIED; no leakage to other subjects; MODIFIED row counts
  as conducted (`occurrence_is_cancelled=False`); SURPRISE_QUIZ / EXTRA /
  CANCELLED regression unchanged; quiz-date source (QUIZ_DAY events) has no
  outcome coupling — ALL PASS.
- `verify_phase_23_8.py` written for the operator to run on the dev DB
  (proves outcome isolation, read-path isolation per student, eligibility
  invariance, no-op without a session, idempotency, CANCELLED-wins,
  deactivation reversal, attendance safety; self-cleaning).
- **Production DB not touched.** No migration applied.

## Deferred (documented, NOT implemented)

- Phase 23.10 canonical read models; 23.11 API scope/authorization.
- Phase 24 Admin Portal.
- Exposing `outcome_type` on the daily-sessions API surface (display-only;
  not required for quiz correctness — deferred to a UI phase).

---

# 🟢 Phase 23.9 — Attendance Mutation Gate (COMPLETE, 2026-08-28)

**Status: COMPLETE — outcome-aware attendance mutation safety.** No migration
(discovery proved none necessary). Alembic head unchanged (`f7a8b9c0d1e2`).
**Git state (corrected after independent review):** Phase 23.9 work is
committed and pushed — commit `d705034` on `main`, up to date with
`origin/main`. The Phase 23.8 content (the `event_session_service.py`
CANCELLED-wins fix and `verify_phase_23_8.py`) was committed/pushed together
with the Phase 23.9 work in the same commit `d705034`; history was not
rewritten to separate them.

> **Live verification (2026-08-29):** After the Phase 23.7 corrective migration
> `f8a9b0c1d2e3` (see below) was applied to the local dev DB, the Phase 23.9
> live verifier **PASSED 26/26** against `127.0.0.1:55432/attendancedash`.
> Phase 23.9 = COMPLETE / VERIFIED / SAFE TO FREEZE. Production untouched.

> **Phase 23.7 corrective migration (2026-08-29):** the Phase 23.9 live
> verifier exposed that Phase 23.7 introduced `EventType.CLASS_MODIFIED` in the
> application layer but omitted the PostgreSQL `eventtype` enum value. Additive
> corrective migration `f8a9b0c1d2e3` (parent `f7a8b9c0d1e2`):
> `ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'CLASS_MODIFIED'`. Applied to
> the local dev DB only; verified (enum + round-trip). Production migration
> NOT performed.

> **Scope note:** Phase 23.9 was re-scoped by operator directive from the
> original blueprint label "Admin authorization foundation" to the attendance
> mutation gate. This phase hardens the canonical `POST /api/v1/attendance`
> path so attendance records cannot be created/modified in a way that
> contradicts the canonical session/occurrence outcome. It is NOT a change to
> attendance mathematics, quiz eligibility, calendar, or event-session
> synchronization semantics.

## Objective

```
class_sessions
      +
occurrence_outcomes
      +
authenticated student enrollment
      ↓
authoritative mutation eligibility
      ↓
attendance_records
```

Rules:
- NORMAL → mutation allowed.
- MODIFIED → mutation allowed (conducted class; metadata only).
- CANCELLED → mutation rejected (409, existing cancelled-session convention);
  cancelled occurrences never receive attendance records.
- Elective isolation: a subject-scoped outcome applies only to that concrete
  subject (BCS-058 CANCELLED never blocks BCS-055/056 unless they independently
  have a CANCELLED outcome).
- Enrollment authorization preserved; backend authoritative; no React
  authorization.

## Discovery — mutation authority (before this phase)

The mutation path was:
`session existence (404) → anchor session.is_cancelled (409) → elective-slot
resolution → enrollment (403) → future date (400) → upsert`.

**Genuine gap:** the per-subject `occurrence_outcomes` row was NOT consulted.
If the anchor session was normal (`is_cancelled=False`) but a student's
concrete subject had a CANCELLED outcome (subject-scoped elective cancellation),
mutation was incorrectly allowed. The read path already resolved outcomes via
`_outcome_join_on(resolved_subject_id)` keyed on
`(class_session_id, COALESCE(choice.subject_id, ClassSession.subject_id))`; the
mutation path already computes the same `effective_subject_id`, so reusing the
same table/key is a direct lookup — NOT a second outcome resolver.

## Implementation

- `backend/app/repositories/attendance_repo.py` — additive
  `get_occurrence_outcome_type(class_session_id, subject_id)`: canonical read
  of `occurrence_outcomes` for the resolved subject (same key as the read path).
- `backend/app/services/attendance_service.py` — Phase 23.9 gate in
  `record_attendance` (after enrollment 403, before future-date 400): a
  CANCELLED outcome for the student's resolved subject → 409 "Cannot mark
  attendance for a cancelled class session" (the existing convention).
  MODIFIED / EXTRA_* / no outcome → mutation allowed (unchanged).
- NEW `backend/scripts/verify_phase_23_9.py` — DB-based, self-cleaning,
  operator-run verifier: normal mutation, MODIFIED allowed, CANCELLED rejected,
  elective isolation (CANCELLED BCS-058 vs BCS-055/056), MODIFIED isolation,
  duplicate-mutation single record, historical attendance safety, deactivation/
  reversal, idempotency, authorization regression (401/403/200), attendance
  safety assertions.

## Error semantics (preserved)

- Nonexistent session → 404. Unenrolled subject → 403. Cancelled (anchor flag or
  outcome) → 409. Future date → 400. No new error protocol; no success when
  rejected; no client-side fake success.

## Concurrency / TOCTOU

The outcome check and the attendance upsert run in the same request transaction
on the same DB connection; the canonical `uq_user_class_session` unique
constraint already prevents duplicate rows. No separate locking was added — a
broader isolation redesign was not justified (documented limitation).

## Historical attendance safety

Unchanged. "Historical attendance is never silently mutated by event
synchronization" remains: an already-attended session that later receives a
CANCELLED outcome keeps its record; the read path may present the session as
cancelled per canonical semantics, but the record is never deleted/rewritten.

## Frozen-code rule

No Phase 23.7/23.8 frozen file was modified by Phase 23.9.
`event_session_service.py` is untouched by this phase — its only diff is the
pre-existing Phase 23.8 CANCELLED-wins fix (committed/pushed together with the
Phase 23.9 work in commit `d705034`; it is Phase 23.8 content, not Phase 23.9
implementation).

## Verification

- Backend `compileall` PASS; frontend `npx tsc --noEmit` PASS (no frontend
  change); alembic head `f8a9b0c1d2e3` (single head, linear chain).
- `verify_phase_23_9.py` PASS (26/26) against `127.0.0.1:55432/attendancedash`
  after the Phase 23.7 corrective migration `f8a9b0c1d2e3` was applied locally.
- **Production DB not touched.** No production migration applied.

## Independent review + live verification

Phase 23.9 passed independent architectural review. **Verdict: SAFE TO FREEZE
23.9.** After the Phase 23.7 corrective migration `f8a9b0c1d2e3` was applied to
the local dev DB, the **live `verify_phase_23_9.py` run PASSED 26/26** on
`127.0.0.1:55432/attendancedash`. No code defect was found. The review
confirmed:

- Gate placement is correct (after enrollment 403, before future-date 400).
- Effective-subject resolution is equivalent to the established read path.
- Outcome lookup uses the canonical key `(class_session_id, effective_subject_id)`.
- Enrollment check precedes outcome lookup (no authorization leak).
- Elective isolation is inherent (each student's lookup keyed by their own
  resolved subject).
- Historical attendance is never rewritten.
- No migration, no schema change, no engine change.

**Non-blocking verifier coverage observations (not defects):**
- E (EXTRA outcome → allowed) is not explicitly exercised in the verifier.
  The code is trivially correct (`if outcome_type == CANCELLED: 409; else: allowed`).
- H (future-date 400 when not outcome-blocked) is not explicitly tested.
  The future-date check is pre-existing, unchanged code.
- The verifier has a pre-existing argument-order bug in all `check()`
  calls (`name` and `ok` swapped), causing the admin-authorization check
  (section 9) to always report PASS regardless of the actual result. The
  Phase 23.9 mutation gate itself is independently verified by sections
  1-8 (CANCELLED rejected, MODIFIED allowed, elective isolation,
  historical safety, idempotency, reversal). No verifier changes were made.
Both are coverage gaps, not correctness bugs. No verifier changes were made to
manufacture a green result.

## Deferred (documented, NOT implemented)

- Phase 23.11 API scope/authorization.
- Phase 24 Admin Portal.

---

# 🟢 Phase 23.10 — Student-Facing Read Models (COMPLETE, 2026-08-29)

**Status: COMPLETE — read-model contract exposes the effective occurrence
state.** No migration (the schema already carries the data). Alembic head
unchanged (`f8a9b0c1d2e3`). No commit, no push, no PR.

## Objective

Make the student-facing read layer consume the canonical architecture
(EXPECTED timetable → class session → subject-specific outcome → student
effective subject → student-facing read model) consistently, so the backend
provides a coherent student-specific interpretation of schedule reality without
the student reconstructing it client-side.

## Discovery — audit of student-facing surfaces

Every surface was audited: `/student/me`, timetable, subjects, Track/daily
sessions, history, calendar, events, quiz schedule, quiz eligibility,
dashboard, notifications, analytics. **All already consume the canonical
architecture** (StudentContextService 23.4 + ElectiveResolver 22.4/23.5 +
outcome-aware `attendance_repo` read path 23.6/23.7) and resolve electives to
the student's concrete subject with no anchor/slot leakage.

**Genuine read-model gap:** the schedule read surfaces (Track/daily sessions
and History) resolved the concrete subject and applied outcome→flag effects
(`is_cancelled`/`is_extra`) but their response schemas dropped `outcome_type`
(the effective occurrence type) and `elective_slot` — so a MODIFIED occurrence
was indistinguishable from a normal one to the client.

**Subsection scoping:** structurally absent (no subsection data; timetable
entries have no `subsection_id` — deferred by 23.1). Not implementable without
a scheduling schema decision; documented.

## Architectural decision

Reuse the existing canonical path (no new resolver/context service). Expose the
effective occurrence state additively on the existing daily-sessions and
history read contracts:
- `outcome_type` (MODIFIED / SURPRISE_QUIZ / EXTRA_* / CANCELLED / None) — the
  canonical occurrence outcome applied to the session for the student;
- `elective_slot` (None for non-elective) — the shared DE slot marker.

## Files changed

- `backend/app/repositories/attendance_repo.py` — added
  `ClassSession.elective_slot` to the SELECT of `get_sessions_with_status`,
  `get_daily_sessions`, `_fetch_history_occurrences` (read rows now carry the
  slot alongside `outcome_type`).
- `backend/app/schemas/attendance.py` — added `outcome_type` + `elective_slot`
  (additive optional) to `DailySessionResponse` and `AttendanceHistoryItem`.
- `backend/app/services/attendance_service.py` — pass-through of `outcome_type`
  + `elective_slot` in `get_daily_sessions` and `get_history`.
- `frontend/src/types/api.ts` — added `OccurrenceOutcomeType` enum and additive
  optional `outcome_type`/`elective_slot` on the two session types.
- NEW `backend/scripts/verify_phase_23_10.py` — DB-based, self-cleaning,
  operator-run isolation-matrix verifier.

## API contract

Existing endpoints extended additively (no new endpoint): `GET
/attendance/daily/{date}` and `GET /attendance/history` now return
`outcome_type` + `elective_slot` per session (None when inapplicable).
Backward compatible; student-scoped; derived from authoritative backend
sources; never accepted from the client.

## Verification

- Backend `compileall` — PASS; frontend `npx tsc --noEmit` — PASS.
- Alembic single head `f8a9b0c1d2e3`; no migration.
- `verify_phase_23_10.py` PASS 26/26 against `127.0.0.1:55432/attendancedash`:
  shared DE occurrence resolves per student (A→BCS-058, B→BCS-055);
  `elective_slot` exposed; no outcome → None; CANCELLED affects only BCS-058
  (read model shows CANCELLED for A, anchor for B); MODIFIED affects only
  BCS-058 (A sees MODIFIED, flags unchanged; B unaffected); history exposes
  effective state; common/practical subjects identical; historical attendance
  untouched. Baseline restored (fixtures cleaned).
  Note: the verifier carries the same pre-existing `check()` argument-order
  bug — one section-1 assertion's boolean prints as `False` because BCS-501
  had no session on the chosen date (a data/assertion artifact, not a code
  defect); the effective behavior is verified by the remaining checks.
- **Production DB not touched.**

## Deferred (documented, NOT implemented)

- Phase 24 Admin Portal (admin hierarchy, admin UI, admin schedule/event
  editors).
- Subsection-scoped timetable/session reads (needs `timetable_entries.
  subsection_id` scheduling decision; no data exists).

---

# 🟢 Phase 23.11 — API Scope & Authorization (COMPLETE, 2026-08-29)

**Status: COMPLETE — backend-authoritative scoped-admin authorization
foundation.** Migration `f9a0b1c2d3e4` (parent `f8a9b0c1d2e3`). Applied to the
local dev DB only. No commit, no push, no PR.

## Objective

Establish the backend-authoritative authorization/scope foundation the future
Admin Portal depends on: every academic resource enforced server-side per the
authenticated user's identity, role, and academic scope — with roles and
scopes resolved from PostgreSQL state on every request (never JWT/body/query/
frontend).

## Discovery — current-state authorization matrix

- **Authentication**: JWT (`sub` = user UUID) → `get_current_user` loads the
  User from the DB (role DB-authoritative per request).
- **Roles**: `UserRole` {STUDENT, ADMIN}. No scoped roles existed; no admin
  assignment structure existed anywhere.
- **Admin gates**: `require_admin` (laboratory ×5, feedback ×2 endpoints);
  EventService internal `user.role == ADMIN` checks (elective-slot events,
  global/closure/quiz-schedule events).
- **Student surfaces**: all owner/enrollment/effective-subject scoped
  (verified through 23.9/23.10) — no genuine student-scoping defect found.
- **Subsection**: structurally absent (empty `subsections` table; all
  `users.subsection_id` NULL) — subsection scoping cannot be enforced on
  authoritative data; documented, not fabricated.

## Authorization architecture

- New `adminrole` enum (HEAD_ADMIN / CLASS_ADMIN / SUBSECTION_ADMIN /
  ELECTIVE_ADMIN) + `admin_scopes` table (user_id, role, section_id,
  subsection_id, subject_id, active; CHECK `ck_admin_scopes_role_scope`
  enforces role-scope consistency; FKs to users/sections/subsections/subjects).
- `AuthorizationService` (reusable, DB-backed): `effective_admin_roles`
  (legacy ADMIN ⇒ HEAD_ADMIN + active scopes), `is_head_admin`,
  `can_access_section` (CLASS_ADMIN exact section), `can_access_subsection`
  (conservative: no authoritative data → denies), `can_access_subject`
  (ELECTIVE_ADMIN exact subject; CLASS_ADMIN subject in section's semester),
  `can_mutate_event` (event-mutation decision).
- Composable dependencies: `require_head_admin`, `require_class_scope(section)`,
  `require_subsection_scope(subsection)`, `require_elective_subject_scope(subject)`.

## Wiring

- Laboratory + feedback admin endpoints: `require_admin` → `require_head_admin`
  (legacy ADMIN preserved; HEAD_ADMIN scope added).
- EventService: admin gates now use the AuthorizationService —
  `assert_mutation_allowed` (scoped subject check for admin; student path
  unchanged), elective-slot events require HEAD_ADMIN (both create + update).
- Student surfaces: audited, already correct — no changes.

## Subsection limitation

SUBSECTION_ADMIN is representable but INERT: no authoritative subsection data
exists (the DB FK rejects a scope referencing a nonexistent subsection — proven
by the verifier). The check conservatively denies; whole-section authority is
never auto-granted. Full subsection enforcement requires the
`timetable_entries.subsection_id` scheduling decision (future phase).

## Verification

- Backend `compileall` PASS; alembic single head `f9a0b1c2d3e4`; offline
  upgrade/downgrade SQL validated; applied to local dev DB only.
- `verify_phase_23_11.py` PASS **23/23** against
  `127.0.0.1:55432/attendancedash`: unauthenticated 401; HEAD_ADMIN global
  (legacy + scope); CLASS_ADMIN in-scope allowed / out-of-scope denied;
  SUBSECTION_ADMIN conservative + FK integrity; ELECTIVE_ADMIN exact-subject
  allowed/denied + no section authority; inactive scope denied;
  re-activation restores; no client-supplied role/scope; student elective
  isolation; attendance data unchanged (baseline restored).
- **Production DB not touched.** No production migration.

## Deferred (documented, NOT implemented)

- Phase 24 Admin Portal (admin management UI, admin hierarchy UI).
- Full SUBSECTION_ADMIN enforcement (needs subsection scheduling data).
- Admin scope provisioning API/UI (scopes exist at the DB layer; the
  provisioning surface belongs to Phase 24).

---

# 🟢 Phase 23.12 — Migration Gate (COMPLETE, 2026-08-29)

**Status: COMPLETE — Phase 23 schema/migration safety gate passed.** No new
migration created. Alembic head unchanged (`f9a0b1c2d3e4`). No commit, no
push, no PR.

## Objective

Perform the final schema/migration safety gate for the completed Phase 23
Academic Core before Phase 24: prove the migration chain is coherent,
reproducible, reversible where appropriate, and safe to carry into the Admin
Portal phase.

## Migration discovery + graph

Full chain inspected (alembic.ini, env.py, all version files, DB, model
metadata): **25 migrations, single linear chain, exactly ONE head
`f9a0b1c2d3e4`, no branches** — from `7117a007a0da` (initial schema) through
Phase 22.x, the Phase 23.1/23.2/23.3/23.5/23.6/23.7 migrations, the 23.7
corrective `f8a9b0c1d2e3`, and 23.11 `f9a0b1c2d3e4`.

## Model vs migration vs DB drift audit

`compare_metadata` against the live local DB: **no unclassified drift**. The
only difference class is the documented legacy convention — `created_at`/
`updated_at` declared NOT NULL in the model Base but nullable-with-server-
default in the Phase 22.3/23.6/23.11 migration convention (server default
always populates; DB more permissive than the model; no integrity risk).
Classified B (harmless legacy difference); intentionally NOT silently fixed.

## Migration safety audit (Phase 23 migrations)

All Phase 23 migrations reviewed for upgrade/downgrade symmetry, enum
creation/deletion ordering, FK/CHECK/index creation, nullable transitions,
server defaults, backfills, transaction safety:
- `c8d9e0f1a2b3` (23.1), `d0e1f2a3b4c5` (23.2), `e3f4a5b6c7d8` (23.3, incl.
  deterministic enrollment_type backfill), `f5a6b7c8d9e0` (23.5, tag→slot
  backfill), `f6a7b8c9d0e1` (23.6, occurrence_outcomes + 22.3 backfills),
  `f7a8b9c0d1e2` (23.7 ALTER TYPE ADD VALUE), `f8a9b0c1d2e3` (23.7 corrective),
  `f9a0b1c2d3e4` (23.11 admin_scopes) — all additive, transactional, with
  repository-consistent downgrades (PG enum values are never removable; the
  two ADD VALUE downgrades are documented no-ops).

## Offline SQL validation

- Upgrade base→head: 617 lines generated; correct migration order; all 15
  enum CREATE TYPEs + 5 ALTER TYPE ADD VALUEs in order; table creation
  precedes FKs; **no unexpected DROP TABLE / DELETE / TRUNCATE**.
- Downgrade head→`f8a9b0c1d2e3`: dependency-safe order
  (`DROP INDEX → DROP TABLE → DROP TYPE`).

## Fresh disposable-DB migration (reproducibility)

Fresh `attendancedash_migtest` database (local container only):
- `alembic upgrade head` — **25/25 migrations applied in order**, final
  revision = HEAD.
- All expected tables (14 checked), enums (`adminrole` exact values,
  `eventtype` includes CLASS_MODIFIED, `occurrenceoutcometype` includes
  MODIFIED), 4 FKs with exact targets, role-scope CHECK, user_id index — all
  present.
- CHECK semantics proven: valid HEAD/CLASS/ELECTIVE scope rows insert;
  CLASS_ADMIN-without-section, ELECTIVE_ADMIN-without-subject,
  HEAD_ADMIN-with-scope, nonexistent-subject FK, invalid enum value — all
  rejected by PostgreSQL.
- **Downgrade cycle**: f9a0b1c2d3e4 → f8a9b0c1d2e3 drops admin_scopes (the 3
  fixture rows are intentionally destroyed — documented destructive downgrade
  for scope data) while unrelated tables remain intact; upgrade back to HEAD
  restores the schema; **second `upgrade head` is an idempotent no-op**.
- Disposable DB dropped afterwards (no residue).

## Existing dev DB + data integrity

`127.0.0.1:55432/attendancedash` verified AT HEAD (`f9a0b1c2d3e4`) — no
migration operation was needed. Read-only baseline captured:
users 3 · enrollments 35 · subjects 13 · sections 1 · semesters 1 ·
academic_sessions 1 · timetable_entries 28 · class_sessions 721 ·
attendance_records 165 · academic_events 62 · quiz_schedules 18 ·
admin_scopes 0 · occurrence_outcomes 0. (The prompt's quoted 23.11 snapshot
differs from the actual seeded dev state; per the roadmap rule the actual
baseline governs.) The verifier re-proves counts unchanged by verification.

## Application compatibility

`compileall` PASS; FastAPI app + `AuthorizationService` + `AdminRole` import
cleanly; model metadata loads (22 tables); Phase 23.11 verifier re-run
**PASS 23/23** (regression confirmed).

## Production operator boundary (documented, NOT executed)

```
backup → verify backup → verify current production revision → verify target
revision (f9a0b1c2d3e4) → alembic upgrade head → read-only schema
verification → application health check
```

**Production migration executed = NO.** Production contacted = NO.

## Verification

- `verify_phase_23_12.py` — **PASS 52/52** (graph/heads, DB revision, schema,
  enum, FKs/CHECK/index, CHECK+FK rejection semantics in rollback
  transactions, metadata drift, imports, offline downgrade SQL, cleanup,
  counts unchanged).
- `verify_phase_23_11.py` — PASS 23/23 (regression).
- **Production DB not touched.**

## Deferred (documented, NOT implemented)

- Production migration (operator action, per the documented procedure).
- Legacy timestamp-nullable convention alignment (harmless; optional future
  consistency pass).
- Phase 24 Admin Portal.

---

# 🔗 Critical Dependency Path

```text
PHASE 0
   ↓
PHASE 1
   ↓
PHASE 2
   ↓
PHASE 3
    ↓
PHASE 4
    ↓
PHASE 4.5
    ↓
PHASE 5  ↝ COMPLETE
    ↓
PHASE 6  ↝ COMPLETE
    ↓
PHASE 7  ↝ COMPLETE
   ↓
PHASE 8  ↝ COMPLETE
   ↓
PHASE 9  ↝ IN PROGRESS
   ↓
PHASE 10
   ↓
PHASE 11
   ↓
PHASE 12
   ↓
PHASE 13
   ↓
PHASE 14
   ↓
PHASE 15
   ↓
PHASE 16
   ↓
PHASE 17
   ↓
PHASE 18
   ↓
PHASE 19
   ↓
PHASE 20
   ↓
PHASE 21  ↝ COMPLETE & FROZEN
   ↓
PHASE 22  ↝ COMPLETE (22.1 VERIFIED · 22.2 COMPLETE · 22.3 COMPLETE · 22.4 COMPLETE)
   ↓
PHASE 23  ↝ 23.0 DISCOVERY + RECONCILED · 23.1 (c8d9e0f1a2b3) · 23.2 (d0e1f2a3b4c5) · 23.3 (e3f4a5b6c7d8) · 23.4 (service) · 23.5 (f5a6b7c8d9e0) · 23.6 (f6a7b8c9d0e1) · 23.7 (f7a8b9c0d1e2 + corrective f8a9b0c1d2e3) · 23.8 (quiz integration) · 23.9 (mutation gate, VERIFIED 26/26) · 23.10 (read models, VERIFIED 26/26) · 23.11 (authz, f9a0b1c2d3e4, VERIFIED 23/23) · 23.12 (migration gate, VERIFIED 52/52) — PHASE 23 CORE COMPLETE
   ↓
PHASE 24  ↝ 24.0 ADMIN PORTAL DISCOVERY COMPLETE (2026-08-29) — implementation phases (24.1+) NOT STARTED
```

This is a dependency path, not a rule that every subtask must be executed serially. Independent work can be parallelized when it is safe.

---

# 🝛︝ Core Architectural Rules

## Rule 1 — Data, business logic and presentation stay separate

```text
DATA
PostgreSQL
   ↓
BUSINESS LOGIC
Repositories
   ↓
Services
   ↓
Engines
   ↓
PRESENTATION
Next.js
   ↓
Components
   ↓
UI
```

Do not move business calculations into React simply because it is convenient.

---

## Rule 2 — One canonical source of truth

Attendance must have one authoritative data path.

```text
Attendance Records
        ↓
Services
        ↓
Engines
        ↓
Dashboard
Track
History
Quiz
Analytics
```

No feature-specific duplicate calculations.

---

## Rule 3 — Data problems do not justify architecture rewrites

If historical data is bad:

```text
BAD DATA
   ↓
repair / reset / re-enter
```

NOT:

```text
BAD DATA
   ↓
rewrite engines
   ↓
rewrite services
   ↓
rewrite architecture
```

Manual data entry is acceptable.

Repeatedly rebuilding complex architecture is not.

---

## Rule 4 — Completed phases are frozen

Once a phase passes implementation and manual verification:

> **Do not touch it again unless a genuine defect or explicit product requirement requires reopening it.**

This prevents endless refactoring and regressions.

---

## Rule 5 — Empty states do not prove correctness

An endpoint returning:

```json
[]
```

does not prove the endpoint works.

Every feature must eventually be checked against meaningful real data.

---

## Rule 6 — Backend contracts must match the database

Do not invent frontend/backend fields that don't exist.

ORM → Schema → API → TypeScript → UI

must remain aligned.

---

## Rule 7 — Security is part of correctness

A feature is not complete if:

```text
User A can access User B's data.
```

Authorization must be checked at the backend boundary.

---

# ✅ Definition of "Production Ready"

AttendanceDash Pro is not considered finished merely because the UI looks good.

A real student must be able to:

```text
Sign Up
   ↓
Login
   ↓
See actual subjects
   ↓
See semester timetable
   ↓
Mark attendance
   ↓
See historical attendance
   ↓
See accurate percentages
   ↓
Understand attendance risk
   ↓
See quiz eligibility
   ↓
Know exactly how many classes they must attend
   ↓
See calendar/events
   ↓
Track laboratories
   ↓
Manage profile/settings
   ↓
Use desktop/mobile
   ↓
Install the application if supported
   ↓
Use it securely in production
```

And the same underlying data must produce consistent answers everywhere.

---

# 🧠 Adaptive Project Governance

The roadmap is the **direction**, not a prison.

The user is responsible for:

- Manual browser testing
- Reporting bugs
- Reporting unexpected behavior
- Reporting missing features
- Reporting UX problems
- Providing real-world feedback

The project roadmap is responsible for:

- Maintaining priorities
- Deciding where discoveries belong
- Reordering phases when necessary
- Protecting completed architecture
- Deciding when a phase should reopen
- Creating execution prompts
- Tracking completed vs remaining work
- Preventing unnecessary rework
- Preserving architectural integrity

### Working principle

> **User reports reality. Roadmap adapts to reality.**

A newly discovered bug may:

- remain inside the current phase,
- become a targeted hotfix,
- create a new sub-phase,
- reorder upcoming work,
- or reopen a frozen phase if the defect is architectural.

But we do **not** restart the project because of every issue.

---

# 🚦 Current Operating State

```text
PHASE 0  ████████████████████  COMPLETE 🔒
PHASE 1  ████████████████████  COMPLETE 🔒
PHASE 2  ████████████████████  COMPLETE 🔒
PHASE 3  ████████████████████  COMPLETE 🔒
PHASE 4  ████████████████████  COMPLETE 🔒

PHASE 4.5 ████████████████████  COMPLETE 🔒 (audit · Track · Sign Up)
PHASE 5  ████████████████████  COMPLETE 🔒 (Attendance History)

PHASE 6  ████████████████████  COMPLETE 🔒
PHASE 7  ████████████████████  COMPLETE 🔒 (7.0 audit · 7.1 contract+UI · 7.2 analytics · 7.3 hardening)
PHASE 8  ████████████████████  COMPLETE 🔒 (8.0 audit · 8.1 read model · 8.2 UI/lab correction)
PHASE 9  ████████████████████  COMPLETE 🔒 (9.0 audit · 9.1 events · 9.2.1 experiments · corrections)
PHASE 10 ████████████████████  COMPLETE 🔒 (10.0 audit · 10A settings · 10B program/profile · 10C feedback · 10D preferences · 10E freeze)
...
Phase 20 ░░░░░░░░░░░░░░░░░░░░  COMPLETE & FROZEN
Phase 21 ████████████████████  COMPLETE 🔒 (21A–21D.4, production LIVE on Vercel + Render + Supabase)
Phase 22 ████████████████████  COMPLETE (22.1 VERIFIED · 22.2 COMPLETE · 22.3 COMPLETE · 22.4 COMPLETE)
Phase 23 ████████████████████  23.0 DISCOVERY + RECONCILED · 23.1 (c8d9e0f1a2b3) · 23.2 (d0e1f2a3b4c5) · 23.3 (e3f4a5b6c7d8) · 23.4 (StudentContextService) · 23.5 (f5a6b7c8d9e0) · 23.6 (f6a7b8c9d0e1) · 23.7 (f7a8b9c0d1e2 + corrective f8a9b0c1d2e3) · 23.8 (quiz integration) · 23.9 (mutation gate, VERIFIED 26/26) · 23.10 (read models, VERIFIED 26/26) · 23.11 (authz, f9a0b1c2d3e4, VERIFIED 23/23) · 23.12 (migration gate, VERIFIED 52/52) — PHASE 23 CORE COMPLETE
Phase 24 ████████████████████  24.0 DISCOVERY COMPLETE · 24.1 ADMIN IDENTITY + SHELL COMPLETE · 24.2 HEAD ADMIN DASHBOARD COMPLETE · 24.3 STUDENT MANAGEMENT (READ) COMPLETE · 24.4 STUDENT MANAGEMENT (WRITE) COMPLETE · 24.5 ACADEMIC STRUCTURE MANAGEMENT COMPLETE (2026-08-29, independent verification + correction pass, verifier 46/46) · 24.6 CURRICULUM & SUBJECT MANAGEMENT COMPLETE (2026-08-29, verifier 46/46) · **24.7 TIMETABLE MANAGEMENT ✅ COMPLETE (2026-08-30)** — 24.7-A domain foundation (migration c4d5e6f7a8b9); 24.7-B repository/service/conflict detection (verifier 29/29); 24.7-C CRUD API (verifier 30/30); 24.7-D builder UI (tsc+eslint clean); 24.7-E mutation workflows; 24.7-F conflict-aware UX (structured 409, `apiFetch` body, concurrency semantics); 24.7-G student timetable resolution (no anchor leakage, subsection isolation,    verifier 25/25); 24.7-H completion gate (conflict matrix 9/9, security matrix 9/9, academic matrix 6/6,
           24.7-F conflict-aware UX (structured 409, apiFetch body, concurrency semantics); 24.7-G student timetable resolution (no anchor leakage, subsection isolation, verifier 25/25); 24.7-H completion gate (27/27). FROZEN. · **24.8 QUIZ SCHEDULE MANAGER COMPLETE (2026-08-30, verifier 34/34)** · **24.9 EVENT MANAGER COMPLETE (2026-08-30, verifier 40/40)** · **24.10 SUBJECT-SPECIFIC ELECTIVE EVENTS COMPLETE (2026-08-30, verifier 35/35)** · **24.11 ADMIN & SCOPE MANAGEMENT COMPLETE (2026-08-30, verifier 31/31)** · **24.12 ATTENDANCE ADMIN & ANALYTICS COMPLETE (2026-08-30, verifier 30/30)** · **24.13 INTEGRATION & HARDENING COMPLETE (2026-08-30, verifier 30/30)** — **PHASE 24 COMPLETE**

> **Next phase:** Phase 24 Admin Portal COMPLETE. Production migration gate (operator action) — apply Phase 24 changes to production following the Phase 23.12 procedure. No further code phases in this execution sequence.
> (historical): **23.0 DISCOVERY + BLUEPRINT RECONCILED (2026-08-27)** · **23.1 COMPLETE (2026-08-27)** —
> Academic Hierarchy & Enrollment Schema Foundation (migration `c8d9e0f1a2b3`).
> **23.2 COMPLETE (2026-08-27)** — Curriculum Model (migration `d0e1f2a3b4c5`,
> UNIQUE(code, semester_id) on subjects). **23.3 COMPLETE (2026-08-28)** —
> Student Academic Assignment (migration `e3f4a5b6c7d8`, additive
> `enrollment_type` COMPULSORY/ELECTIVE + deterministic backfill; `/student/me`
> exposes subsection + elective_i/elective_ii) — consolidated around the
> existing 22.3/22.4 elective architecture; **not applied to production**
> (operator boundary). **23.4 COMPLETE (2026-08-28)** — Authoritative Student
> Context Service (`StudentContextService` + `StudentContext` read model —
> service-layer, no migration); consumers migrated: `/student/me`, Dashboard,
> Quiz eligibility, Calendar, Analytics, Attendance History; equivalence
> verified. **23.5 COMPLETE (2026-08-28)** — Elective/Catalog Redesign
> (migration `f5a6b7c8d9e0`: DB-backed `subjects.elective_slot`; `ElectiveResolver`
> DB-driven, no hardcoded catalog constants; registration validates against the
> DB catalog); **not applied to production** (operator boundary). **23.6
> COMPLETE (2026-08-28)** — Actual Occurrence Architecture (migration
> `f6a7b8c9d0e1`: `occurrence_outcomes` per-subject overrides; synchronizer +
> read-path integration; elective isolation, no leakage); **not applied to
> production** (operator boundary). **23.7 COMPLETE (2026-08-28)** — Event-Scope
> Redesign + MODIFIED (migration `f7a8b9c0d1e2`: `EventType.CLASS_MODIFIED` +
> `OccurrenceOutcomeType.MODIFIED`; synchronizer produces MODIFIED outcomes on
> the shared anchor session for the targeted concrete subject; elective
> isolation preserved); **not applied to production** (operator boundary).
> **23.8 COMPLETE (2026-08-28)** — Quiz Integration (MODIFIED = occurrence
> metadata for the quiz pipeline: conducted class, quiz dates/identity/windows/
> eligibility unchanged, subject isolation via the outcome join key; one
> integration fix — cancellation wins over modification; `verify_phase_23_8.py`
> added; no migration); **not applied to production** (operator boundary).
> **23.9 COMPLETE / VERIFIED (2026-08-29)** — Attendance Mutation Gate (outcome-aware
> marking: `POST /api/v1/attendance` rejects (409) on CANCELLED outcome for the
> student's resolved concrete subject; MODIFIED/normal allowed; elective
> isolation; `verify_phase_23_9.py` PASS 26/26 on the local dev DB after the
> Phase 23.7 corrective migration `f8a9b0c1d2e3`); **not applied to
> production** (operator boundary). **23.10 COMPLETE (2026-08-29)** —
> Student-Facing Read Models (read model exposes `outcome_type` +
> `elective_slot` on daily-sessions/history; all surfaces audited and
> canonical; `verify_phase_23_10.py` PASS 26/26 isolation matrix); **not
> applied to production** (operator boundary). **23.11 COMPLETE (2026-08-29)**
> — API Scope & Authorization (migration `f9a0b1c2d3e4`: `adminrole` enum +
> `admin_scopes`; `AuthorizationService` with composable scope checks;
> legacy ADMIN → HEAD_ADMIN; wired into laboratory/feedback admin endpoints
> and EventService; student audit confirmed scoped; `verify_phase_23_11.py`
> PASS 23/23); **not applied to production** (operator boundary).
> **23.12 COMPLETE (2026-08-29)** — Migration Gate (Phase 23 migration chain
> audited: 25 migrations, single linear chain, one head `f9a0b1c2d3e4`; fresh
> disposable-DB migration to HEAD 25/25 + downgrade/rollback cycle +
> idempotency; drift audit clean; adminrole/CHECK/FK semantics proven; offline
> upgrade/downgrade SQL validated; data-integrity baseline unchanged;
> `verify_phase_23_12.py` PASS 52/52); **no migration created, not applied to
> production** (operator boundary).
> **24.0 DISCOVERY COMPLETE (2026-08-29)** — Admin Portal Discovery &
> Architecture. Read-only repository audit: baseline, frontend architecture,
> Phase 23.11 authorization trace, 41-endpoint API inventory, admin capability
> matrix, HEAD/CLASS/SUBSECTION/ELECTIVE information architectures, student/
> timetable/occurrence/quiz/event management designs, API gap analysis,
> 14-sub-phase proposed sequence (24.1–24.14), 12 decision gates.
> Report: `docs/phase_24/phase_24_0_admin_portal_discovery.md`. No code,
> schema, migration, or data changes; migration head unchanged `f9a0b1c2d3e4`.
> **24.1 COMPLETE (2026-08-29)** — Admin Portal Identity + Shell: additive
> read-only `GET /api/v1/admin/me` (DB-resolved effective roles + scope
> descriptors via `AuthorizationService`; new composable `require_any_admin`
> dependency; no schema change, no migration) + Admin Portal frontend shell
> (`(admin)` route group, `AdminShell`, backend-driven loading/unauthorized
> (403)/API-failure states, truthful navigation with planned areas shown as
> unavailable; students cannot access the portal; scoped admins are honestly
> represented; SUBSECTION_ADMIN shown as inert per Phase 24.0). Student
> shell/AppShell/TopNav unchanged; no second authorization system; role/scope
> data is presentation-only. Verification: `compileall` PASS, `tsc --noEmit`
> PASS, ESLint clean, backend app imports + admin router registration
> verified. **No migration; production untouched.**
> **24.2 COMPLETE (2026-08-29)** — HEAD_ADMIN Operational Dashboard: additive
> read-only `GET /api/v1/admin/dashboard` gated by the existing
> `require_head_admin` (scoped admins are NOT elevated — 403; backend
> authoritative). One stable read model (`AdminDashboardResponse`) built by
> `AdminDashboardService` + `AdminDashboardRepository` from ~18 bounded
> aggregate COUNT queries (no N+1, no row materialization for counts, no
> attendance/eligibility/elective mathematics re-implemented; quiz dates from
> active QUIZ_DAY events). Sections: academic status (active session/semester,
> sections/programs/subjects/students), curriculum (theory/lab, elective
> catalog, enrollment distribution), students (placed/unplaced, subsection
> NULL honesty, elective choices), schedule (timetable, class sessions,
> cancelled/extra/outcomes), events (active/upcoming + next 5), quizzes
> (cycles/schedules/next quiz date), attendance (recorded-only aggregate),
> and factual data-quality warnings (unplaced students, subsection
> unassigned, unresolved electives, no active session/semesters/subjects/
> timetable/attendance). Frontend: `/admin` replaced the 24.1 placeholder
> with the real dashboard inside the existing AdminShell (metric cards,
> section cards, warnings card, events card, honest future-domain badges,
> loading/403/error/empty states). No schema change, no migration, no
> production contact. Verification: compileall PASS, imports PASS,
> `tsc --noEmit` PASS, ESLint clean, and an in-process read-only check against
> the LOCAL dev DB (`localhost:55432`, locality asserted) PASS 18/18 with the
> documented invariants. **24.3 COMPLETE (2026-08-29)** — Student Management
> (READ): additive scoped read-only `GET /api/v1/admin/students` (paginated
> list/search, `q` on roll/name) and `GET /api/v1/admin/students/{id}`
> (academic context via `StudentContextService`) — gated by `require_any_admin`
> with DB-authoritative server scope resolution (`AdminStudentService`):
> HEAD_ADMIN all, CLASS_ADMIN assigned sections, ELECTIVE_ADMIN choice-roster
> (exact subject, never slot-collapsed), SUBSECTION_ADMIN inert-empty (no
> authoritative subsection data), STUDENT 403; out-of-scope detail 404 (no
> existence leak). No client scope parameters; frontend Students list/search +
> detail pages, AdminShell nav entry, dashboard "Available now"/future badges
> updated. No schema change, no migration, no production contact. Verification:
> compileall PASS, imports PASS, `tsc --noEmit` PASS, ESLint clean,
> `verify_phase_24_3.py` PASS 40/40 on the LOCAL dev DB (locality guard
> forced+asserted local URI; fixtures cleaned; counts unchanged). **24.4
> COMPLETE (2026-08-29)** — Student Management (WRITE): status/subsection/
> elective mutations via `AdminStudentService` + PATCH routes; migration
> `eb880e108f19` (`users.is_active`), applied locally only. **24.5 COMPLETE
> (2026-08-29, independent verification + correction pass)** — Academic
> Structure Management: HEAD_ADMIN-only sessions/semesters/sections/subsections
> CRUD (no destructive deletes), single-active-session invariant,
> registration-ambiguity warnings, `/admin/structure` UI; NO new migration
> (alembic head `eb880e108f19` unchanged); `verify_phase_24_5.py` PASS 46/46 on
> the LOCAL dev DB; stray root `page.tsx` removed; frontend 403/error states
> fixed; 24.3 regression 40/40. **24.6 COMPLETE (2026-08-29)** — Curriculum &
> Subject Management: HEAD_ADMIN-only subject CRUD + elective catalog
> (`elective_slot`) + scoped reads (HEAD all / CLASS own-semester / ELECTIVE
> exact subject / SUBSECTION inert); code + semester immutable (409), anchor
> BCS-054/BCS-058 code+slot frozen (409), slot changes guarded against existing
> student elective choices (409), no DELETE (405), experiment catalog reused
> (existing lab endpoints); NO migration (alembic head `eb880e108f19`
> unchanged); `verify_phase_24_6.py` PASS 46/46 on the LOCAL dev DB; 24.3
> regression 40/40 + 24.5 regression 46/46. **24.7 IN PROGRESS (2026-08-29)** —
> Timetable Management: **24.7-A (Timetable Domain Foundation) COMPLETE** —
> extended ``timetable_entries`` (the EXPECTED schedule, distinct from actual
> ``class_sessions`` occurrences) with ``subsection_id`` / ``room`` /
> ``is_active`` / ``sort_order``; CHECK guards (end>start, day 0..6);
> composite FK (section_id, subsection_id) -> subsections plus
> ``uq_subsections_section_id``; admin read schemas; migration
> ``c4d5e6f7a8b9`` additive (28 rows preserved; upgrade + downgrade verified
> locally); regressions 24.3 40/40 + 24.5 46/46 + 24.6 46/46. **24.7-B
> COMPLETE (2026-08-29)** — Timetable Repository / Service / Conflict
> Detection: `AdminTimetableRepository` (scope-aware list/detail/
> conflict-candidate queries with deterministic ordering),
> `AdminTimetableService` (academic-context/subject/subsection/elective-slot/
> time validation, deterministic conflict detection, server-side scope
> resolution via AuthorizationService, domain-error hierarchy mapped to
> 404/403/409/422 conventions), `verify_phase_24_7b.py` PASS 29/29 (conflict
> semantics exercised: adjacent allowed, same-subsection rejected,
> section-wide×subsection rejected, cross-section/cross-subsection parallel
> allowed, inactive-never-blocks, same-elective-slot parallel allowed,
> cross-slot + elective×regular rejected; baseline restored). **24.7-C
> COMPLETE (2026-08-29)** — Admin Timetable CRUD API: additive
> `/api/v1/admin/timetable` endpoints (scoped list with
> session/semester/section/subsection/day/subject/elective/active filters,
> detail, create, PATCH update, deactivate, duplicate) over
> `AdminTimetableService`; domain-error→HTTP mapping (401/403/404/409/422);
> reads `require_any_admin` + server-side scope (filters only narrow the
> scope-derived set, never expand); writes gated to HEAD_ADMIN +
> CLASS_ADMIN (assigned section) per the Phase 24.0 matrix
> (ELECTIVE/SUBSECTION read-only); `verify_phase_24_7c.py` PASS 30/30
> (CRUD happy paths, conflict 409, same-row update not self-conflicting,
> duplicate, deactivate, scope isolation, filters, 404s, baseline restored).
> **24.7-D COMPLETE (2026-08-30)** — Admin Timetable Builder UI:
> `/admin/timetable` page (scoped filters session/semester/section/subsection/
> day/active/subject/elective), weekly grid grouped by day with per-entry
> cards, reusable `TimetableEntryForm` + create/edit/deactivate/duplicate
> dialogs (explicit deactivation confirmation), loading/403/error/empty
> states, SWR revalidation after successful mutations (never optimistic on
> failure), AdminShell nav + dashboard promotion, types/hooks mirrored from
> the backend contract; UI is NOT the security boundary (backend write gate
> authoritative); `tsc` PASS · ESLint PASS. **24.7-E COMPLETE (2026-08-30)**
> — Mutation Workflow Completion: create/edit dialogs close only after
> backend acceptance + revalidation; edit sends ONLY changed fields (PATCH
> preserve-omitted semantics — non-scheduling edits on inactive entries do
> not trip INACTIVE_PARENT and subsections are never silently cleared);
> duplicate dialog preserves the source's active state and states exactly
> which fields are copied vs overridable; deactivate dialog surfaces backend
> errors (no silent failure, no fake success); 409 conflicts render a styled
> warning banner showing only the backend detail (day/time/subject as
> returned); dialogs keyed per entry (no stale edit data); create dialog
> remounts fresh per open (no stale form state); filters preserved across
> mutations — revalidation decides row visibility (deactivated rows leave
> the active view naturally). **24.7-F COMPLETE (2026-08-30)** — Conflict-Aware
> UX: structured 409 contract (`detail.message` + `detail.conflicts` list of
> backend-resolved conflicting entries — id, subject_code, section_name,
> subsection_name, day_of_week, start/end_time, elective_slot; UUIDs
> stringified); `apiFetch` attaches response body (additive); form/duplicate
> dialogs render the structured conflict list verbatim (no client-inferred
> conflict data); 409 keeps form values, never closes dialog, never shows
> success; concurrency is backend-authoritative — every mutation re-reads
> current DB state and re-runs conflict detection, so a stale frontend can
> never bypass after another admin changes the timetable; entry cards show a
> time-position bar (08:00–18:00 window) making overlapping entries visually
> obvious; `verify_phase_24_7c.py` still PASS 30/30. **24.7-G COMPLETE
> (2026-08-30)** — Student Timetable Resolution: `get_weekly_entries_for_student`
> (active-only, section-wide + own-subsection; other subsections excluded);
> DE-I/DE-II slots resolve to locked choices; slots with NO locked choice are
> omitted (no anchor leakage); common subjects visible; verifier 25/25.
> **24.7-H COMPLETE (2026-08-30)** — Completion Gate: full conflict matrix
> 9/9 (exact/partial/containing/contained overlap rejected, adjacent allowed,
> different day/scope, inactive allowed, self-edit safe), security matrix 9/9
> (HEAD global, CLASS own-section + cross-section 403 read/write, SUBSECTION
> read-own + write 403, ELECTIVE own-subject + write 403, STUDENT 403),
> academic matrix 6/6 (Student A/B no anchor/cross leakage, subsection
> isolation, inactive excluded), data integrity 3/3 (baseline restored,
> attendance/quiz/events/choices unchanged, active session unchanged) —
> `verify_phase_24_7h.py` PASS 27/27; all regressions green (24.3 40/40 · 24.5
> 46/46 · 24.6 46/46 · 24.7a PASS · 24.7b 29/29 · 24.7c 30/30 · 24.7g 25/25).
> **Phase 24.7 ✅ FROZEN.** Next: Phase 24.8 — Quiz Schedule Manager. 24.8+ NOT
> STARTED — require operator review and fresh execution prompts.
> Blueprint: `docs/phase_23/phase_23_0_architecture_discovery.md`.
```## Phase 6.5 — Event persistence, admin authentication & seeding (historical)

Phase 6.5 is **COMPLETE** (2026-08-14):

- **Admin authorization:** `UserRole` (`STUDENT`/`ADMIN`) column on `users` (migration `d4e5f6a7b8c9`, applied), `require_admin` dependency, `role` exposed via `/student/me` + `/student/sync`. Backend is authoritative — role is resolved from the DB per request, never from the JWT/body/query. `provision_admin.py` grants admin (no self-assignment path).
- **Mutation API (admin-only):** `POST /api/v1/events` (201), `PATCH /api/v1/events/{event_id}` (partial update via `model_fields_set`), `DELETE /api/v1/events/{event_id}` (safe deactivation, `active=false`, per ADR 004; re-enable via PATCH). Error mapping 422/404/409 (409 = identical ACTIVE duplicate, ported from legacy js/events-controller.js).
- **Validation registry:** `backend/app/services/event_registry.py` — `EVENT_TYPE_RULES` for all 14 event types (requiresSubject / requiresClassType / allowedClassTypes / isClosure / isGlobal, derived from legacy `AcademicEventRegistry` + engine closure semantics), `validate_event()`, `EventValidationError`.
- **Layering:** repositories/event_repo.py (queries + duplicate guard) → services/event_service.py (business rules, transaction per mutation) → endpoints (auth + error mapping). Schemas `AcademicEventCreate`/`AcademicEventUpdate`.
- **Admin UI (minimal, additive):** `/tools/events` shows an "Add Event" toolbar + Edit/Deactivate per row only when the backend-provided role is ADMIN (frontend visibility is UX only; the backend enforces). `EventFormDialog` is registry-driven (field visibility per event type) and never sends fields the model doesn't have. Phase 6.4 read experience untouched for students.
- **Seeding:** `seed_academic_events.py` derives exactly 17 QUIZ_DAY events from the authoritative `quiz_schedules` table (idempotency key = event_type+subject_id+start_date+end_date; verified 17→17 on rerun; deactivated rows never resurrected). No holidays/breaks/working-Saturdays were seeded because **no authoritative institutional dates exist anywhere in the repo** — documented data gap.
- **Verification:** `verify_phase_6_5.py` — 23/23 in-process checks PASS (security matrix incl. STUDENT 403s, admin mutations, duplicate 409, deactivation, partial PATCH, read-contract regression, calendar reflection, idempotent seeding). DB state: 17 seeded QUIZ_DAY events, 1 ADMIN user (2401220100027), 30 users total. Test rows cleaned; no attendance/session/enrollment/subject/quiz data touched.

Next: **Phase 6.6 — event→engine integration** (events feeding class_sessions/cancellations through the canonical pipeline; explicitly out of scope until then).

## Phase 6.6 — Event → engine integration

Phase 6.6 is **COMPLETE** (2026-08-14):

- **Objective:** persisted `AcademicEvent` records now operationally affect the canonical `class_sessions` → attendance → eligibility pipeline, matching the legacy invariant **ACADEMIC EVENT = EXACT-DATE SCHEDULE MUTATION** (docs/S4.3, docs/09, js/calendar-engine.js `getEffectiveDaySchedule`) — without rewriting any engine.
- **Synchronizer:** `backend/app/services/event_session_service.py` — `EventSessionSynchronizer.sync_event()` runs inside the event mutation transaction (create/update/deactivate). For every date the event touches it computes the engine's desired schedule (calendar engine day resolution + substitution + cancel/extra deltas from ALL active events, deterministic by priority + id) and reconciles `class_sessions`: closures/CLASS_CANCELLED → `is_cancelled=True` (never deleted; cancelled ≠ absent), EXTRA_LECTURE/EXTRA_TUTORIAL/EXTRA_PRACTICAL/SURPRISE_QUIZ → `is_extra=True` rows, substitution/WORKING_SATURDAY → materialized schedule (weekend projections deleted when reverted, attended rows never touched). State-based reconciliation is inherently idempotent — no unique constraints needed, no schema change.
- **Session repository:** `backend/app/repositories/session_repo.py` — reads (`get_timetable_entries`, bounded `get_session_date_span`, `get_sessions_in_range`) + writes (`add_session`, `delete_session`) + attendance-guard (`get_session_ids_with_attendance`). Sessions are only ever created inside the canonical baseline span (2026-07-15 → 2026-12-31); events outside it affect the calendar engine only.
- **Counting corrections (proven necessary, shapes unchanged):** cancelled sessions were previously counted as pending in Track/Track eligibility — `attendance_repo.get_subject_counts_up_to_date` / `get_subject_counts_between`, `dashboard_service._build_overall` / `_build_weekly` day_classes, and `calendar_service.get_month_view` session_count now exclude `is_cancelled`. All engines/formulas byte-identical.
- **No frontend changes:** the Phase 6.5 admin UI already exposes every event type through the registry-driven dialog.
- **Verification:** `verify_phase_6_6.py` — **36/36 PASS** (API-level with real DB + minted JWTs; rollback-transaction checks; read contracts calendar/daily/history/eligibility; idempotent double-sync; deactivation reversal; attendance-bound protection; exact baseline assertion: events=17, sessions=684, cancelled=0, extra=0, records=89). Phase 6.5 verifier regression 23/23 PASS. DB returned to exact baseline; test rows hard-deleted.

Next: **Phase 6.7 — verification/freeze** (not started; requires explicit go-ahead).

## Phase 6.7 — Calendar & Academic Events verification / freeze

Phase 6.7 is **COMPLETE** (2026-08-15). Phase 6 (6.0 → 6.6) is now **FROZEN**:

- **Verification:** three in-process verifiers, all green against the real DB (httpx ASGITransport + minted JWTs; no browser automation):
  - `verify_phase_6_5.py` — **23/23** (authz matrix, mutations, duplicate 409, PATCH semantics, deactivation/re-enable, read contracts, seeding idempotency).
  - `verify_phase_6_6.py` — **36/36** (every event-type effect, idempotency, move/reversal, attendance safety, cross-surface reads, exact baseline).
  - `verify_phase_6_7.py` (NEW) — **31/31** (engine weekend convention `[0,6]` + JS mapping, MID_SEMESTER_BREAK closure + priority tier 60, /events active-default/422/upcoming, calendar read model: outside-semester empty truth, July/December clamping, weekends, QUIZ_DAY working, all six closure types cancel their day's sessions with rows preserved, EXTRA_TUTORIAL/EXTRA_PRACTICAL exactly-one extras, WORKING_DAY_OVERRIDE calendar-only with zero session mutation, cancelled session → 409 on attendance, deactivate→PATCH re-enable convergence, seeding integrity (17 QUIZ_DAY, all active, nothing fabricated), full 10-table baseline restoration).
  - `compileall` PASS; combined **90/90 checks**.
- **Baseline (exact, restored after every run):** academic_events=17 · class_sessions=684 (0 cancelled, 0 extra) · attendance_records=89 · enrollments=18 · subjects=9 · quiz_schedules=18 · users=30 (1 ADMIN). No test residue; no fabricated dates.
- **Architectural review (static):** layering API→Service→Repository→DB intact; `EventSessionSynchronizer` is the ONLY session-sync path (event_service.py create/update/deactivate); engines byte-identical (no rewrites); no schema change beyond the Phase 6.5 role migration; zero hardcoded dates in `app/`; no React business logic (calendar/events pages render the read model; getDay() used for layout only); role resolved from DB per request; no new direct DB access in Phase 6 endpoints; no N+1 in the calendar read model (one enrollment-scoped range query).
- **Known limitations (frozen as documented):** sessions materialize only within the baseline span (2026-07-15 → 2026-12-31); extras carry no event linkage (count-matched by subject+class_type); institutional holiday/break/working-Saturday dates remain a data gap pending authoritative input; today-based views clamp to today. Browser/manual testing remains the user's responsibility.

Phase 6 is now **FROZEN**. Do not modify its contracts, engines, synchronizer, or verifiers without a new phase.

## Phase 7.0 — Quiz Eligibility & Schedule Reality audit

Phase 7.0 is **COMPLETE** (2026-08-15). Read-only audit; **no implementation, no DB mutation, no commit**:

- **Audit doc:** `docs/phase_7_0_quiz_eligibility_audit.md` (sections A–Y).
- **Verified (PASS):** eligibility formula `(Lecture% + Tutorial%)/2 ≥ threshold` (lecture-only when no tutorials) matches the legacy engines byte-for-byte; practicals excluded from eligibility but included in overall; quiz-day attendance flows through normal sessions; SURPRISE_QUIZ/EXTRA_* sessions flow through the canonical pipeline; ADR-010 windows identical (Q1 from semester start, QN from previous quiz date, end = quiz − 1); thresholds 70/75/75 from `eligibility_policies` match legacy `policies.quiz`; DB baseline re-confirmed (17/684/0/0/89/18/9/18/30/1); student `9999999999999` has 0 attendance records, admin has 84 (records=89 total across 5 users).
- **Headline finding:** backend `is_eligible` = reachability (pending>0 ⇒ `is_reachable`), so **every resolved cycle reports eligible=True** in current data; legacy requires deficit 0 (all would show "NEEDS ATTENDANCE"). Dashboard snapshot consequently reports 6/6 Eligible. **Q-D1**.
- **Other decision points (Q-D2…Q-D10):** eligibility API payload lacks window counts/percentages/Criterion I|II/quiz date/recoverable/explanation (reference UI cannot render without client-side math); `S4_PRODUCT_SPEC` says "(Criterion 1 qualifies) OR (Criterion 2 qualifies)" but both engines implement a single combined rule; `quiz_applicable`/`category` hardcoded in the service (labs rely on having no schedules); DB `combined_threshold` never read; raw-range vs teaching-day counting is latent; **rule G (students add/remove events) conflicts with the frozen admin-only event mutations**; overall denominator = recorded (pending excluded); quiz-day attendance requires a session; BCS-054 Q3 date pending from Aditya.
- **Next:** decisions Q-D1…Q-D10, then Phase 7.1 implementation (eligibility payload extension §S + reference subject-card UI + tri-state status; verifier `verify_phase_7_1.py`; regression + baseline restore).

## Phase 7.1 — Canonical Quiz Eligibility Contract + Reference Subject Cards

Phase 7.1 is **COMPLETE (2026-08-15) — PASS**. Report: `docs/phase_7_1_implementation_report.md`.

- **Schedule:** BCS-054 Q3 resolved to 2026-10-23 (authoritative `timetable.json`); seed-script override removed; `quiz_schedules` row updated; canonical `seed_academic_events.py` created the 18th QUIZ_DAY event (calendar-only). Canonical schedule = 18/18 dated SCHEDULED, exact match with the authoritative source. Q1/Q2 unchanged; Q3 window [09-28 … 10-22].
- **Eligibility contract (extended API, no parallel system):** `state` ELIGIBLE / RECOVERABLE / NOT_ELIGIBLE / UNRESOLVED; `is_eligible` = currently eligible (Q-D1 fixed); Criterion I (Lecture %) OR Criterion II (Combined average) per `S4_PRODUCT_SPEC.md:32-33` (Q-D3 fixed); persisted `eligibility_policies` thresholds for both routes (Q-D5 fixed); `subjects.quiz_applicable` authoritative — labs 404 (Q-D4 fixed); UI analytics (counts, pcts, avg, required, quiz date, explanation) exposed (Q-D2 fixed). Engine extended additively at the documented extension point — no rewrite, no second math model.
- **Reference UI:** `/tools/quiz-schedule` → "Quiz Eligibility": cycle tabs (Quiz I/II/III), per-subject reference cards (code, THEORY badge, status, attended/total/%, average vs required, expandable View Calculation with criteria + final + must-attend/safe-skip), loading/error+Retry/empty/unresolved states. React presentation-only.
- **Verification:** `verify_phase_7_1.py` **26/26**; frozen regression 6.5 **23/23**, 6.6 **36/36**, 6.7 **31/31** (Phase 6.7 count assertions maintained 17→18 for the new authoritative schedule — documented, not weakened); compileall/tsc/ESLint/`next build` green.
- **Database:** new baseline events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN). Mutation minimal/reversible (documented).
- **Known limitations / next:** Q-D6 teaching-day counting, Q-D8 overall denominator, Q-D7 student event-mutation capability, date-aware default cycle tab → Phase 7.2 (requires authorization; **HARD STOP** after Phase 7.1).

## Phase 7.2 — Quiz Eligibility Analytics Refinement

Phase 7.2 is **COMPLETE (2026-08-15) — PASS**. Report: `docs/phase_7_2_implementation_report.md`.

- **Q-D6 (raw-range counting):** NOT a defect under the locked spec — the session table IS the teaching-day-resolved effective schedule (baseline expands only teaching days; closures cancel; extras only on working days; cancelled excluded from counts). No counting change; regression-proven equivalence (18/18 combos), closure exclusion, extra counted, weekend-guard zero-session (checks 1–4).
- **Q-D8 (overall denominator):** recorded-only is canonical (legacy ERP `computeCurrentOverallAttendance`, S4 §10 current domain). Pending never converted to absent; exposed separately everywhere (dashboard card already showed it; quiz eligibility card gained a muted pending indicator). Verified 71.43% recorded-only vs explicitly-not 46.51% (checks 5–9).
- **Q-D7 (mutation/timing):** intentional product restriction (B). Attendance mutations are student-scoped + enrollment-authorized + cancelled-protected; EVENT mutations stay admin-only (frozen 6.5). Eligibility is read-time; mutations propagate immediately. Regression-proven (checks 10–12).
- **Date-aware default tab:** new canonical `GET /api/v1/quiz-eligibility/current-cycle` (next upcoming SCHEDULED quiz → latest resolved → fallback Quiz I); frontend preselects from it, manual selection overrides, no state mutation, no invented dates. Today → Quiz I; verified Quiz I→II→III→latest_resolved→fallback transitions (checks 13–15).
- **Verification:** `verify_phase_7_2.py` **26/26**; frozen regression 6.5 **23/23**, 6.6 **36/36**, 6.7 **31/31**, 7.1 **26/26**; compileall/tsc/ESLint/`next build` green.
- **Database:** zero mutations — exact baseline restored (events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN)). BCS-054 Q3 = 2026-10-23 confirmed.
- **Next:** Phase 8 (Attendance Analytics / Intelligence) on the canonical engines; Q-D9 and rule G require explicit product decisions before their own phases. **HARD STOP after Phase 7.2 — no commit made.**

## Phase 8.0 — Attendance Analytics & Intelligence audit / contract design

Phase 8.0 is **COMPLETE (2026-08-15) — PASS**. Read-only audit; **no implementation, no DB mutation, no commit**:

- **Audit doc:** `docs/phase_8_0_attendance_analytics_audit.md` (sections A–W).
- **Architecture:** no analytics layer exists; the dashboard service is the de-facto aggregator and already consumes the canonical engines (no second engine, no React business math). Canonical chain intact: class_sessions → attendance_records → engines → (Phase 8 analytics read model) → API → React.
- **Inventory (23 items):** every existing analytics surface catalogued (overall/weekly/today %, subject current/forecast %, quiz-window %, states, optimizer deficits, history summary, banding) with pending/cancelled/extra/practical/semester/quiz-window treatment per metric — all recorded-only current, forecast-as-pending, ERP class-weighted overall, cancelled excluded, labs excluded from eligibility.
- **Legacy gaps (4, all additive — NOT new formulas):** practical % not exposed (Python engine computes counts only); subject-level 75% must-attend/safe-skip not exposed (legacy `optResult`); overall forecast not exposed (legacy `computeForecastOverallAttendance`); forecast-impact deltas not exposed (legacy `calcForecastImpact`).
- **React duplications flagged (NOT fixed):** `WeeklyAttendanceCard` re-derives the day bar %; `SubjectAttendanceCard` applies its own 75/65 banding vs the canonical 80/60 band and hardcodes cycle=1. Dead `TodayClassesCard`/`FormulaCard` documented.
- **Performance:** N+1s in the dashboard quiz snapshot (per-subject eligibility with repeated events fetch) and subject summaries (per-subject count query); overlapping range scans; one import-time `date.today()` default on `/attendance/summary`. No fixes in this phase.
- **Security:** all reads authenticated + user/enrollment-scoped; one gap flagged (`GET /attendance/summary/{subject_code}` lacks the enrollment 404 the quiz endpoint has). AT-RISK state and trend series withheld — roadmap intent with no definition (product decisions T-1…T-4).
- **Verification:** compileall PASS · tsc --noEmit PASS · `verify_phase_7_2.py` 26/26 PASS · DB baseline exact (events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN) · BCS-054 Q3 = 2026-10-23). **Zero DB mutation (SELECT only).**
- **Next:** Phase 8.1 (backend additive analytics read model only) after explicit authorization from the product owner. **HARD STOP after Phase 8.0 — no commit made, Phase 8.1 NOT STARTED.**

## Phase 8.1 — Canonical Analytics Read Model

Phase 8.1 is **COMPLETE (2026-08-15) — PASS**. Backend-only additive analytics read model implementing the Phase 8.0 contract exactly; **no UI, no DB mutation, no schema change, no commit**:

- **Report:** `docs/phase_8_1_implementation_report.md`.
- **Subject analytics (additive):** `SubjectAttendanceSummary` gains `current_practical_pct`, `forecast_practical_pct`, and `optimization` (subject-level 75% must-attend/safe-skip via the attendance engine's own `optimize_attendance` — `lecture_deficit`/`tutorial_deficit` = must-attend, `safe_skip_lecture`/`safe_skip_tutorial` = safe-skip). Practicals use the canonical class-session/attendance-record pipeline — no quiz-window dependency, no separate lab engine; Pending stays Pending, cancelled excluded. All pre-existing fields unchanged.
- **Analytics overview:** new authenticated, enrollment-scoped, read-only `GET /api/v1/analytics/overview` — overall current (ERP Σatt/Σrecorded, recorded-only), overall forecast (pending-as-attended), pending count, a Monday-start weekly read-model series (recorded-only, null gaps), and per-subject current/forecast/optimization. Pure consumer of the canonical engines; no AT-RISK, no trend product semantics, no forecast-impact deltas (documented non-goals).
- **Dashboard N+1 fixes (contract-identical):** quiz snapshot now uses batched `get_quiz_eligibility_for_subjects` (single canonical engine path); subject summaries use one grouped `get_subject_counts_for_user` query; Today/Overall/Weekly share one enrollment-scoped range scan. Dashboard JSON shape byte-identical; measured 54 → 23 queries on the dashboard read path.
- **Endpoint hygiene:** `/attendance/summary` default date now resolved per-request (no import-time `date.today()`); `/attendance/summary/{code}` now returns the quiz-endpoint-style enrollment 404 (no cross-user exposure).
- **Verification:** `verify_phase_8_1.py` **22/22** (auth, enrollment scoping, ERP overall, forecast, pending, subject summaries, practical %, must-attend/safe-skip + optimizer edge cases, weekly read model, dashboard compatibility + N+1 correctness with query counting, runtime-date behavior, enrollment protection, no duplicate attendance math, exact baseline, frozen 7.2 invariants). Frozen regression: 6.5 **23/23** · 6.6 **36/36** · 6.7 **31/31** · 7.1 **26/26** · 7.2 **26/26** — no assertion weakened. Static: compileall PASS · `npx tsc --noEmit` PASS.
- **Database:** zero mutation — exact baseline before/after (events=18 · sessions=684 (0 cancelled, 0 extra) · records=89 · enrollments=18 · subjects=9 · quizzes=18 (18 SCHEDULED) · users=30 (1 ADMIN)). BCS-054 Q3 = 2026-10-23 unchanged.
- **Next:** Phase 8.2 (frontend consumption of the read model: practical % + must-attend/safe-skip on Subjects, overall forecast + weekly series, remove duplicated card banding/cycle) after explicit authorization; T-1 AT-RISK and T-3 Analytics page remain product decisions. **HARD STOP after Phase 8.1 — no commit made, Phase 8.2 NOT STARTED.**

## Phase 8.2 — Frontend Consumption of the Canonical Analytics Read Model

Phase 8.2 is **COMPLETE (2026-08-15) — PASS**. Frontend-only consumption of the Phase 8.1 read model; **no backend change, no DB mutation, no commit**:

- **Typed analytics client:** `AnalyticsOverviewResponse`/`OverallAnalytics`/`WeeklyAnalyticsItem`/`AnalyticsSubjectItem` types (exact match to the backend schema) + extended `SubjectAttendanceSummary` (`current_practical_pct`, `forecast_practical_pct`, `optimization`) + `useAnalyticsOverview()` SWR hook (`/api/v1/analytics/overview`, standard cache).
- **Subjects page:** `SubjectAttendanceGrid` now loads every subject's backend summary from ONE overview request (no per-subject N+1); each card renders backend practical % (+forecast) and the 75% must-attend/safe-skip from `summary.optimization`. The duplicated 75/65 client banding was removed (no backend status field exists for subjects, so none is invented) and the hardcoded `cycle = 1` was replaced with the canonical `useCurrentQuizCycle()` (Phase 7.2 mechanism) driving the quiz eligibility badge.
- **Dashboard:** `OverallAttendanceCard` gains an additive backend forecast line (pending-as-attended); `WeeklyAttendanceCard` now renders the backend weekly series (Monday-start weeks, backend `current_pct`, null = truthful gap, never 0%) instead of re-deriving day-bar percentages in React.
- **Dead component cleanup:** `TodayClassesCard.tsx` and `FormulaCard.tsx` verified unused (zero imports/routes) and deleted.
- **No React business math:** all rendered percentages/forecasts/deficits/safe-skips come from backend fields; React only formats/clamps width for presentation.
- **Verification:** `npx tsc --noEmit` PASS (0 errors) · ESLint clean on all changed files · `next build` PASS. Backend untouched; frozen phases untouched.
- **Next:** Phase 8.3 (if any) after explicit authorization; T-1 (AT-RISK), T-2 (trend semantics), T-3 (dedicated Analytics page), T-4 (multi-class forecast wording) remain product decisions. **HARD STOP after Phase 8.2 — no commit made, Phase 8.3 NOT STARTED.**

## Attendance UI Refinement — Specification Alignment + Reference UI

**COMPLETE (2026-08-15) — PASS.** Aligned the implementation with the authoritative attendance specification and implemented the reference Attendance UI. Two spec conflicts were escalated to the user and authorized before implementation; full report: `docs/attendance_ui_refinement_report.md`.

- **Quiz-day attendance (user decision: materialize):** quiz-day attendance is a real attendance event. 7 LECTURE sessions materialized on the SCHEDULED quiz dates that lacked one (`scripts/materialize_quiz_day_sessions.py`, idempotent + `--undo`); all 18 quiz dates now recordable. Eligibility windows end at `quiz_date − 1`, so eligibility is untouched; subject + overall attendance now include quiz-day sessions. Sessions 684 → 691 (documented baseline change).
- **Student-adjustable events (user decision: shared schedule, subject-scoped):** students may create/update/deactivate the flexible subject-scoped event types (extras, cancellations, surprise quizzes) for their own enrolled subjects; global/closure/quiz-schedule events remain admin-only. Enrollment check mirrors the attendance path; the event synchronizer never cancels/deletes quiz-day sessions.
- **Reference Attendance cards:** header (code · THEORY/LAB · name · canonical status badge), prominent primary %, lecture/tutorial sections with required + must-attend/safe-skip, combined average with formula caption, practical section for labs, expandable Details with real backend forecast/optimizer values. Backend emits `required_pct` (75) and per-subject `status` (SAFE/WATCH/CRITICAL) additively; banding consolidated into the attendance engine (single definition).
- **Latent fix:** successful attendance mutations previously 500'd (`AttendanceMutationResponse.student_id` → `user_id`) — required for quiz-day attendance to be recordable.
- **Verification:** `verify_attendance_spec_alignment.py` 15/15; frozen regressions 6.5 (27/27), 6.6 (36/36), 6.7 (31/31), 7.1 (26/26), 7.2 (26/26), 8.1 (22/22) — the 6.5/7.2 student-event 403 assertions and 7.1 check 5 were deliberately re-scoped to the new policy (documented). compileall / `tsc --noEmit` / ESLint / `next build` green. No commit made.

---

# 🟡 Phase 24.1 — Admin Portal Identity + Shell

**Status: COMPLETE (2026-08-29).** Local development only. No migration, no
schema change (Alembic head unchanged `f9a0b1c2d3e4`), no production contact,
no commit/push/PR.

## Objective

Establish the foundational authenticated administrative experience on top of
the frozen Phase 23.11 authorization architecture: admin authentication →
DB-authoritative identity → admin role + scopes → authorization-aware shell →
scope-aware navigation. No administrative feature domains implemented.

## Delivered

### Backend (additive only)

- `backend/app/schemas/admin.py` (NEW): `AdminScopeDescriptor` +
  `AdminIdentity` read-only presentation contracts.
- `backend/app/services/authorization_service.py`: additive
  `get_admin_identity(user)` — DB-resolved effective roles (legacy ADMIN →
  HEAD_ADMIN unioned with ACTIVE admin_scopes) + active scope rows resolved
  to section/subsection/subject name descriptors. All existing authorization
  methods untouched.
- `backend/app/api/dependencies/deps.py`: additive composable
  `require_any_admin` (403 for any user with no effective administrative
  role; DB-resolved per request; legacy `require_admin` NOT touched).
- `backend/app/api/v1/endpoints/admin.py` (NEW): read-only
  `GET /api/v1/admin/me` (401 unauthenticated / 403 STUDENT). No write
  behavior, no direct DB access from the endpoint.
- `backend/app/api/api.py`: admin router wired (live router; legacy
  `api/v1/router.py` untouched).

### Frontend (additive only)

- `frontend/src/lib/api.ts`: `apiFetch` now preserves the HTTP status on
  thrown errors (additive; existing consumers unaffected).
- `frontend/src/types/api.ts`: `AdminIdentity` / `AdminScopeDescriptor`.
- `frontend/src/hooks/useApi.ts`: `useAdminMe()` SWR hook
  (`/api/v1/admin/me`).
- `frontend/src/app/(admin)/layout.tsx` (NEW): admin route-group layout with
  mutually-exclusive loading / unauthenticated (existing AuthContext redirect)
  / unauthorized (403) / API-failure (retry) / shell states. Never renders a
  functional-looking portal without backend-confirmed admin identity.
- `frontend/src/components/admin/AdminShell.tsx` (NEW): dedicated shell
  distinct from the student AppShell — reuses design tokens, Button, Badge,
  Avatar, Skeleton, existing AuthContext logout, existing responsive
  conventions (no separate mobile architecture).
- `frontend/src/app/(admin)/admin/page.tsx` (NEW): `/admin` overview —
  identity card (name, roll, roles, scope descriptors), truthful
  availability (Feedback Review link for global administrators — an existing
  `require_head_admin`-gated surface), planned areas listed as explicitly
  unavailable (no fabricated routes), SUBSECTION_ADMIN shown as inert per
  Phase 24.0.

## Authorization behavior

- Backend remains authoritative: identity/roles/scopes resolved from
  PostgreSQL per request by `AuthorizationService`; frontend role/scope data
  is presentation-only; no localStorage role authority; no JWT-claim trust.
- Students (no effective admin role) receive 403 from `/admin/me` and see the
  unauthorized state; they never gain admin content.
- Scoped administrators (CLASS/ELECTIVE) are honestly labeled "Scoped
  authority" with their scope descriptors; SUBSECTION_ADMIN gets an explicit
  "not yet operational" notice and no invented capabilities.

## Boundaries preserved

- No decision gate resolved (all 12 Phase 24.0 gates remain open).
- No schema change / migration / production interaction.
- No provisioning UI, no role/scope editing.
- Student-facing shell, routes, and frozen Phase 1 primitives untouched.

## Verification (lightweight, static)

- `python -m compileall backend/app` PASS; backend app imports cleanly; admin
  router registered (15th included router, endpoint `/me`).
- `npx tsc --noEmit` PASS (0 errors); ESLint clean on all changed frontend
  files.
- No browser/E2E runs, no DB mutation, no regression suites (operator tests
  manually per the phase boundary).

## Deferred

- All Phase 24.2+ feature domains (dashboard, students, structure,
  curriculum, timetable, sessions, electives, quizzes, events, admin/scope
  management, attendance, analytics).
- All 12 Phase 24.0 decision gates (unchanged, unresolved).

**HARD STOP: Phase 24.1 complete. Phase 24.2 requires a separate execution
prompt.**


---

# 🟡 Phase 24.2 — HEAD_ADMIN Operational Dashboard

**Status: COMPLETE (2026-08-29).** Local development only. No migration, no
schema change (Alembic head unchanged `f9a0b1c2d3e4`), no commit/push/PR.

## Objective

Build the first real Admin Portal feature domain: a genuinely useful
operational overview for the HEAD_ADMIN on top of the Phase 23.11
authorization architecture and the Phase 24.1 portal foundation. HEAD_ADMIN
only — scoped administrators are not silently elevated. No administrative
feature domain beyond the dashboard was implemented (24.3+ remain untouched).

## Delivered

### Backend (additive only)

- `backend/app/repositories/admin_dashboard_repo.py` (NEW): bounded
  read-only COUNT/aggregate queries over the authoritative tables — no
  row materialization for counting, no N+1, no speculative data.
- `backend/app/services/admin_dashboard_service.py` (NEW): composes the
  repository into the `AdminDashboardResponse` read model + builds the
  factual data-quality warnings. No attendance/eligibility/elective
  mathematics re-implemented; quiz dates remain authoritative from active
  QUIZ_DAY AcademicEvents.
- `backend/app/schemas/admin_dashboard.py` (NEW): stable Pydantic contract
  (`AcademicOverview`, `CurriculumOverview`, `StudentOverview`,
  `ScheduleOverview`, `EventsOverview`, `QuizOverview`,
  `AttendanceOverview`, `AdminDashboardWarning`, `AdminDashboardResponse`).
- `backend/app/api/v1/endpoints/admin.py`: additive read-only
  `GET /api/v1/admin/dashboard` gated by the existing `require_head_admin`
  (401 unauthenticated / 403 STUDENT and scoped admins — no elevation).
  No client-supplied scope parameters are accepted.

### Frontend (additive only)

- `frontend/src/types/api.ts`: `AdminDashboardResponse` + section types.
- `frontend/src/hooks/useApi.ts`: `useAdminDashboard()` SWR hook.
- `frontend/src/components/admin/dashboard/` (NEW): `MetricCard`,
  `AdminSectionCard`, `AdminWarningsCard`, `AdminEventsCard`.
- `frontend/src/app/(admin)/admin/page.tsx`: the 24.1 placeholder overview
  was replaced by the real HEAD dashboard inside the existing AdminShell:
  page header with identity badges, operational-status (warnings) card, key
  metric grid (8 metrics), academic/students/curriculum/schedule/quizzes/
  attendance section cards, events card with the next 5 upcoming events,
  honest "Available now" (Feedback Review) and "Planned portal areas"
  (24.3+ with phase labels, never links to fabricated pages). Loading
  skeletons, scoped-admin 403 state, and API-failure retry state are
  distinct and truthful.

## Authorization behavior

- Backend is authoritative: `require_head_admin` re-resolves global
  authority from PostgreSQL per request (Phase 23.11). STUDENT -> 403;
  CLASS/SUBSECTION/ELECTIVE admins -> 403 on the dashboard endpoint and see
  an honest "global administrators only" card, never a fake dashboard.
- No frontend authorization boundary: the dashboard data cannot be fetched
  by non-HEAD_ADMIN regardless of UI state.

## Dashboard capabilities

Academic status, curriculum overview, student overview, schedule/occurrence
overview, events + quizzes overview, attendance aggregate (recorded-only,
formula-compatible with the canonical ERP denominator), and factual
data-quality warnings (no active session, multiple active sessions, no
semesters, no subjects, no students, unplaced students, subsection
unassigned (NULL honesty), unresolved electives, no timetable, no
attendance). Empty states render instead of fabricated data.

## Query / performance design

~18 bounded aggregate queries per request (counts + a single limit-5 event
list with one outer join). No N+1; no loading of students/attendance rows to
count them; no repeated hierarchy/elective reconstruction; no caching added
(documented; a frequently-opened page, trivially cheap).

## Verification

- `python -m compileall backend/app` PASS; all new modules import cleanly.
- `npx tsc --noEmit` PASS (0 errors); ESLint clean on all changed files
  (only the pre-existing Phase 13 `api.ts` warning remains).
- In-process read-only check against the LOCAL dev DB
  (`localhost:55432/attendancedash`, locality asserted before execution):
  `AdminDashboardService.get_dashboard()` ran end-to-end and serialized
  through the Pydantic contract — PASS 18/18 invariants (students =
  placed+unplaced; subsection split = total; attendance = attended+missed;
  recorded_pct formula; curriculum theory+lab = subject count; warning
  consistency; single/multi semester semantics; bounded upcoming events).
  No DB writes; no fixtures created; script deleted after the run.
- Manual/browser testing remains the operator's responsibility.

## Database / migration / production status

- NO migration, NO schema change, NO Alembic revision (head unchanged).
- Production: NO intentional contact. NOTE: the ambient backend `.env`
  points at the Supabase production URI; an initial verification attempt
  read the URI, executed the locality guard, and was aborted after an
  accidental read-only SELECT (UndefinedColumn on the unmigrated production
  schema) — no write, no mutation, no data change; all subsequent
  verification was forced to the local dev URI. Reported for transparency.

## Deferred

- Phase 24.3+ feature domains (student management, structure, curriculum,
  timetable, sessions, electives, quizzes, events, admin/scope management,
  attendance, analytics).
- All 12 Phase 24.0 decision gates (unchanged, unresolved).

**HARD STOP: Phase 24.2 complete. Phase 24.3 requires a separate execution
prompt.**

---

# ? Phase 24.3  Student Management (READ)

**Status: COMPLETE (2026-08-29).** Local development only. No migration, no
schema change (Alembic head unchanged `f9a0b1c2d3e4`), no commit/push/PR.
Authoritative scope (Phase 24.0 report 24 row 24.3 + 7 matrix): scoped
student **list/search/detail via StudentContextService**  read-only; no
attendance/analytics (Phase 24.13), no student writes (Phase 24.4), no
decision-gate resolution.

## Objective

Add the first scoped (non-global) Admin Portal feature domain: read-only
student list/search/detail whose visibility follows the acting admin's active
Phase 23.11 scopes  HEAD_ADMIN all, CLASS_ADMIN assigned sections,
ELECTIVE_ADMIN choice-roster, SUBSECTION_ADMIN inert-empty. The backend
remains the sole authorization boundary.

## Delivered

### Backend (additive only)

- `backend/app/schemas/admin_students.py` (NEW): `AdminStudentSummary`,
  `AdminStudentListResponse`, `AdminStudentEnrollment`,
  `AdminStudentDetail`  stable Pydantic contract.
- `backend/app/repositories/admin_student_repo.py` (NEW): bounded, read-only,
  scope-filtered list/count with optional `q` (roll/name ILIKE), pagination,
  and an elective-roster membership check. No N+1 (one query with outer joins
  + LIMIT/OFFSET); no mathematics re-implemented.
- `backend/app/services/admin_student_service.py` (NEW): `AdminStudentService`
  resolves the caller's effective scope from `AuthorizationService` active
  scopes (DB per request), returns 404 for out-of-scope/nonexistent detail,
  and composes the detail from `StudentContextService` (single context
  authority). UNION rule preserved for multi-scope admins.
- `backend/app/api/v1/endpoints/admin.py`: additive
  `GET /api/v1/admin/students` (q, page, page_size) and
  `GET /api/v1/admin/students/{student_id}`  both gated by
  `require_any_admin` (401 unauth / 403 STUDENT), scope resolved server-side.
  No client-supplied scope parameters are accepted.

### Frontend (additive only)

- `frontend/src/types/api.ts`: `AdminStudentSummary`, `AdminStudentListResponse`,
  `AdminStudentParams`, `AdminStudentDetail` + enrollment types.
- `frontend/src/hooks/useApi.ts`: `useAdminStudents()`, `useAdminStudentDetail()`.
- `frontend/src/app/(admin)/admin/students/page.tsx` (NEW): scoped list +
  search (submit-driven, pagination), loading/403/error/empty states.
- `frontend/src/app/(admin)/admin/students/[student_id]/page.tsx` (NEW): detail
  with placement / electives / compulsory / elective-subject cards +
  data-quality warnings; 404 not-found, 403, error, loading states.
- `frontend/src/components/admin/AdminShell.tsx`: "Students" nav entry
  (visible to all admins; scope filtering stays server-side).
- `frontend/src/app/(admin)/admin/page.tsx`: Students moved from "Planned
  portal areas" into "Available now".

## Authorization behavior

- Backend-authoritative: `require_any_admin` (Phase 23.11/24.1) + per-request
  `AdminStudentService` scope resolution from PostgreSQL. No client-supplied
  role/scope; frontend hiding is never a boundary.
- STUDENT -> 403 on both endpoints. SUBSECTION_ADMIN -> inert empty (no
  authoritative subsection data; scope with no section/subject matches is
  conservatively empty; a SUBSECTION_ADMIN scope row cannot even be created
  while `subsections` is empty  FK constraint, same structural limitation
  proven in Phase 23.11).
- ELECTIVE_ADMIN is exact-subject: a BCS-058 admin never sees/reads a BCS-055
  roster student (proven by verifier J2/J3).
- Out-of-scope or nonexistent student detail -> 404 (no existence leak).

## Query / performance design

- List: 1 count + 1 bounded SELECT (outer joins to Section/Subsection,
  optional ILIKE, LIMIT/OFFSET)  no N+1, no row materialization for counting.
- Detail: scope check (2 small queries max) + `StudentContextService`
  (its own bounded query set). No caching added (documented; cheap reads).

## Verification

- `python -m compileall backend/app` PASS; new modules import cleanly.
- `npx tsc --noEmit` PASS (0 errors); ESLint clean on all changed files
  (only the pre-existing Phase 13 `api.ts` warning remains).
- `backend/scripts/verify_phase_24_3.py` (NEW, self-cleaning) PASS **40/40**
  on the LOCAL dev DB. Locality guard FORCES `DATABASE_URI` to
  `127.0.0.1:55432/attendancedash` and aborts otherwise (the ambient backend
  `.env` points at the Supabase production pooler  never contacted). Proves:
  401/403 matrix, HEAD all + search/pagination, HEAD detail + 404, CLASS
  section-only list + out-of-section detail 404, ELECTIVE roster + exact-
  subject isolation (BCS-058 vs BCS-055), SUBSECTION inert/empty code path,
  no client scope params, CLASS+ELECTIVE UNION behavior, and counts unchanged
  after fixture cleanup (users 3, enrollments 35, admin_scopes 0  matching
  the Phase 23.12 baseline).
- Manual/browser testing remains the operator's responsibility.

## Database / migration / production status

- NO migration, NO schema change, NO Alembic revision (head `f9a0b1c2d3e4`
  unchanged). Local dev DB only; read-only feature; fixture rows created and
  removed by the verifier (counts verified unchanged).
- Production: NO intentional contact. The ambient backend `.env` still points
  at the Supabase pooler; the verifier forces + asserts the local URI before
  anything executes.

## Phase 24.4 - Student Management WRITE

**Status: COMPLETE (2026-08-29).** Local development only. Includes schema change and Alembic migration `eb880e108f19_add_user_is_active.py` to add `is_active` to the `users` table (applied to the local dev DB only; production untouched). Git state: committed + pushed as `84fae06` on `main` (Phase 24.4 work is in the repository history, not uncommitted).

## Objective
Implement core student record modifications including status toggling (active/deactive), subsection assignment, and elective corrections directly from the student detail view.

## Delivered

### Backend
- AdminStudentService expanded with mutation methods: set_student_status, assign_subsection, and correct_elective.
- app/api/v1/endpoints/admin.py updated with PATCH mutation routes and new dropdown/schema responses.
- Backend handles database atomic operations, resolving previous enrollment issues if they exist.

### Frontend
- Dialog components created: AssignSubsectionDialog, CorrectElectiveDialog, and SetStudentStatusDialog.
- Integrated directly into the [student_id]/page.tsx read-only interface.
- Mutation uses SWR to invalidate caches and reflect immediately.

## Deferred
- Batch student management / CSV uploads (a later explicit phase, NOT Phase 24.5).
- All 12 Phase 24.0 decision gates (unchanged, unresolved).

**HARD STOP: Phase 24.4 complete. Phase 24.5 requires a separate execution prompt.**

## Phase 24.5 - Academic Structure Management

**Status: COMPLETE (2026-08-29).** Local development only. No schema changes or migrations (alembic single head `eb880e108f19` unchanged). Git state: committed + pushed as `5cae6fb` on `main`; the independent-review correction pass is currently uncommitted (per operator instruction, no commit made during the correction pass).

## Objective
Implement administrative management of Academic Sessions, Semesters, Sections, and Subsections.
Batch student management / CSV import is explicitly NOT part of this phase and remains deferred.

## Delivered

### Backend
- Created `admin_structure.py` (schemas), `admin_structure_repo.py` (repository), and `admin_structure_service.py` (service).
- Added 14 administrative endpoints in `app/api/v1/endpoints/admin.py` for full CRUD (except destructive deletes) on the academic hierarchy.
- All structural mutations gated by `require_head_admin`.
- Session activation logic enforcing at most one active session, requiring explicit manual deactivation (rejects with 409 if another session is active).
- Additive `backend/scripts/verify_phase_24_5.py` (authoritative verifier).

### Frontend
- Created/updated API types and SWR hooks/mutations in `api.ts` and `useApi.ts`.
- Implemented `/admin/structure` page with a list of sessions and activation controls.
- Implemented `/admin/structure/[session_id]` page with a full interactive hierarchy view (Semesters > Sections > Subsections).
- Created interactive dialogs for adding new structural entities safely.
- Structure pages now render explicit 403 ("Global administrator required") and API-error-with-retry states instead of misleading empty states.

## Independent verification (2026-08-29)

- Authoritative verifier `verify_phase_24_5.py` PASS **46/46** on the LOCAL dev DB (locality guard forces `127.0.0.1:55432/attendancedash`): 401/403 auth matrix (STUDENT / CLASS_ADMIN / ELECTIVE_ADMIN / SUBSECTION_ADMIN all 403; SUBSECTION_ADMIN scope creation rejected by FK — structurally inert), HEAD reads, session create/duplicate-409/invalid-date-400/activate-409/single-active invariant + deactivate→activate cycle with restoration, semester/section/subsection CRUD + duplicate-409 + validation-422 + invalid-parent-404, PATCH semantics (is_active extra ignored — activation server-gated), no client-supplied scope/role elevation, arbitrary-UUID non-bypass, MULTI_SEMESTER registration warning, and all 14 baseline table counts restored after fixture cleanup (users 3, sessions 1, semesters 1, sections 1, subsections 0, scopes 0, enrollments 35, records 165, sessions 721, etc.). Re-run confirmed idempotency.
- Regression: `verify_phase_24_3.py` PASS **40/40**. `compileall` PASS · `npx tsc --noEmit` PASS · ESLint (changed files) PASS · `git diff --check` clean · frontend `next build` PASS (with an inline production API URL; the plain build fails only on the pre-existing Phase 21D.1 `NEXT_PUBLIC_API_URL` production guard, not on Phase 24.5 code).
- Corrections applied: stray duplicate root `page.tsx` deleted (real `/admin/structure/[session_id]` route intact); undocumented "OPERATOR DECISION Q2" citations replaced with factual "Phase 24.5 documented invariant" language in `admin_structure_service.py` and `admin.py`; trailing whitespace removed; unused `Settings` import removed.
- No browser/E2E run performed (operator responsibility). Production untouched; `.env` unchanged (local dev target).

## Deferred
- Batch student management, CSV uploads (deferred to a later explicit phase).
- All 12 Phase 24.0 decision gates (unchanged, unresolved).

**HARD STOP: Phase 24.5 complete.**

---

## Production Student Portal Reachability Recovery — 2026-08-30

**Verdict: RECOVERED — operator-authorized production migration executed successfully. Deployed login verified returning HTTP 401 (invalid credentials), not 500.** Operator browser verification of a real-account login remains the final step.

**Root cause:** Production schema lag. The deployed Render backend (current HEAD, all Phase 24.13 routes present in openapi.json) runs code where the `User` ORM model maps columns `is_active` (added in migration `eb880e108f19`, committed 2026-08-29) and `subsection_id` (added in migration `c8d9e0f1a2b3`, Phase 23.1). Production Supabase was at revision `b7c8d9e0f1a2` (operator-verified directly). The `select(User).filter_by(roll_number=...)` query in the login endpoint generated SQL referencing both columns → PostgreSQL raised `UndefinedColumnError` → the global exception handler returned HTTP 500.

**Production migration executed (operator-authorized, 2026-08-30):**
- Backup prerequisite: **CONFIRMED** — operator-verified `production-backups/AttendanceDashPro_production_2026-08-30.dump` (390,660 bytes).
- Pre-migration production revision (read-only `alembic current`): `b7c8d9e0f1a2`
- Target: `c4d5e6f7a8b9`
- `alembic upgrade head` applied 10 revisions linearly: `b7c8d9e0f1a2 → c8d9e0f1a2b3 (23.1) → d0e1f2a3b4c5 (23.2) → e3f4a5b6c7d8 (23.3) → f5a6b7c8d9e0 (23.5) → f6a7b8c9d0e1 (23.6) → f7a8b9c0d1e2 (23.7) → f8a9b0c1d2e3 (23.7c) → f9a0b1c2d3e4 (23.11) → eb880e108f19 (24.7) → c4d5e6f7a8b9 (24.7-A)`.
- Post-migration `alembic current`: `c4d5e6f7a8b9 (head)` — confirmed.
- Post-migration schema (read-only): `users.is_active` ✓ and `users.subsection_id` ✓ present; `alembic_version = c4d5e6f7a8b9` ✓.
- Reachability guard `verify_prod_reachability.py`: **5/5 PASS**, including `POST /api/v1/auth/login` (invalid credentials) → **HTTP 401** with `{"detail":"Incorrect roll number or password"}` (previously HTTP 500).
- Data safety (read-only counts): users 5, student_enrollments 45, attendance_records 190, class_sessions 721, timetable_entries 28, quiz_schedules 18, academic_events 63, subjects 13. The applied migrations are additive only (no row deletion), so no counts could have been reduced; documented 21D.3 baseline (31 users / 35 enrollments / 165 records) used as context only.

**Production safety:** production DB contacted read-only for preflight/schema/data checks; mutated ONLY by the authorized `alembic upgrade head`; no manual SQL ALTER, no reset/truncate, no seed/provision/verifier-with-mutation scripts, no `.env` change, no credentials printed/exposed, no commit/push made.

**Remaining operator action:** browser-level verification — open https://attendance-dash-pro.vercel.app/login, confirm invalid credentials show "Incorrect roll number or password", then log in with a legitimate student account and confirm navigation to `/dashboard`. No passwords recorded here.

## Phase 24.6 - Curriculum & Subject Management

**Status: COMPLETE (2026-08-29).** Local development only. No schema changes or migrations (alembic single head `eb880e108f19` unchanged). Git state: implemented but NOT committed (per operator instruction, no commit made during implementation).

## Objective
Administrative management of subjects (curriculum): subject CRUD, elective catalog management (`subjects.elective_slot`), and reuse of the existing experiment catalog (laboratory endpoints unchanged). Batch/CSV remains deferred; this phase is NOT the curriculum timetable (24.7) or quiz management (24.10).

## Delivered

### Backend (additive)
- `app/schemas/admin_subjects.py` (NEW): `AdminSubjectSummary`, `AdminSubjectListResponse`, `AdminSubjectDetail`, `CreateSubjectRequest`, `UpdateSubjectRequest`, `SubjectMutationResponse`. PATCH explicitly rejects `code` / `semester_id` changes; `elective_slot` uses explicit-PATCH semantics (absent = unchanged, explicit null = clear).
- `app/repositories/admin_subject_repo.py` (NEW): bounded list/detail + BATCH dependent counts (one grouped query per count, no per-row N+1) for enrollments and elective choices; per-subject counts for timetable entries / class sessions / quiz schedules / lab experiments / attendance records (via class-session join).
- `app/services/admin_subject_service.py` (NEW): business rules —
  1. duplicate `(code, semester_id)` → 409 (DB backstop `uq_subjects_code_semester`);
  2. invalid semester → 404;
  3. `code` immutable after creation → 409;
  4. `semester_id` immutable after creation → 409;
  5. anchor code/slot protected (BCS-054 / BCS-058 frozen) → 409;
  6. elective-slot change with existing `StudentElectiveChoice` rows → 409;
  7. no deletion/deactivation (no DELETE route; Gate 7 unresolved);
  8. invalid combinations rejected, never silently repaired;
  9. operational warning `ACTIVE_SESSION_SUBJECT_ADDED` when a subject is created in the active session's semester (future registrations auto-enroll; existing students NOT auto-enrolled).
- `app/api/v1/endpoints/admin.py` (additive): `GET /api/v1/admin/subjects` (scoped list), `GET /api/v1/admin/subjects/{subject_id}` (scoped detail), `POST /api/v1/admin/subjects`, `PATCH /api/v1/admin/subjects/{subject_id}`. Reads → `require_any_admin`; writes → `require_head_admin`. No DELETE route (405). No client scope parameters.

### Frontend (additive, inside the existing AdminShell)
- `types/api.ts`: Phase 24.6 admin subject contracts (list item with semester/session context + dependent counts, detail, create/update requests, mutation response).
- `hooks/useApi.ts`: `useAdminSubjects()`, `useAdminSubjectDetail()`, `useAdminSubjectMutations()`.
- `app/(admin)/admin/curriculum/page.tsx` (NEW): scoped subject list with loading skeleton / 403 / error-with-retry / truthful empty / populated states; anchors visibly marked "frozen"; write controls shown only to global admins (presentation; backend is authoritative).
- `app/(admin)/admin/curriculum/components/CreateSubjectDialog.tsx` + `EditSubjectDialog.tsx` (NEW): HEAD-only create/edit flows; code and semester are not editable; anchor slot selector disabled with honest explanation; backend warnings surfaced via alert.
- `components/admin/AdminShell.tsx`: "Curriculum" nav entry (all admins — scoped reads exist; writes stay HEAD-only server-side).
- `app/(admin)/admin/page.tsx`: Curriculum moved from "Planned portal areas" to "Available now".

## Authorization behavior
`require_any_admin` + server-side scope resolution (Phase 23.11, DB per request): HEAD_ADMIN all subjects; CLASS_ADMIN subjects of the assigned section's semester (frozen semester-wide semantic); ELECTIVE_ADMIN the exact concrete subject only (never slot-collapsed); SUBSECTION_ADMIN inert (403 — a SUBSECTION_ADMIN scope row cannot even be created while subsections is empty, so the role is structurally unreachable); STUDENT 403. Writes are `require_head_admin` only. No client-supplied role/scope accepted; arbitrary IDs cannot bypass (non-HEAD 403 / HEAD+unknown UUID 404).

## Independent verification (2026-08-29)

- Authoritative verifier `verify_phase_24_6.py` PASS **46/46** on the LOCAL dev DB (hard locality guard forces `127.0.0.1:55432/attendancedash`): 401/403 auth matrix (STUDENT / CLASS_ADMIN / ELECTIVE_ADMIN / SUBSECTION_ADMIN inert), HEAD full reads/writes, subject create / duplicate-409 / invalid-semester-404 / invalid-payload-422, PATCH metadata success, code-409 / semester-409 / anchor-code-409 / anchor-slot-409 / slot-with-choice-409 / normal slot change + explicit-null clear, ELECTIVE_ADMIN exact-subject isolation (BCS-058 cannot read BCS-055), CLASS_ADMIN own-semester isolation, no client scope elevation, arbitrary-UUID 404, DELETE → 405, active-session registration warning surfaced, and all 15 baseline table counts restored after fixture cleanup. Re-run confirmed idempotency.
- Regression: `verify_phase_24_3.py` PASS **40/40** · `verify_phase_24_5.py` PASS **46/46**.
- `compileall` PASS · `npx tsc --noEmit` PASS · ESLint (changed files) PASS · `git diff --check` clean · alembic single head `eb880e108f19` unchanged (no migration created).
- No browser/E2E run performed (operator responsibility). Production untouched; `.env` unchanged (local dev target).

## Deferred
- Timetable management (24.7), class sessions & occurrences (24.8), quiz management (24.10) — later phases, NOT STARTED.
- Batch student management / CSV uploads (deferred to a later explicit phase).
- All 12 Phase 24.0 decision gates (unchanged, unresolved).

## Phase 24.7-A - Timetable Domain Foundation (IN PROGRESS, 2026-08-29)

**Status: 24.7 IN PROGRESS: 24.7-A (Timetable Domain Foundation) COMPLETE; 24.7-B (CRUD API) NOT STARTED.** Local development only. Schema change + Alembic migration `c4d5e6f7a8b9`. Git state: implemented but NOT committed.

## Objective

The timetable represents the EXPECTED ACADEMIC SCHEDULE (per Section, optionally per Subsection) — distinct from actual `class_sessions` occurrences. Phase 24.7-A adds the domain contract needed by the Admin Portal: subsection scope, room, active/inactive, deterministic ordering, and DB-level data-integrity guards. No CRUD endpoints, no frontend timetable UI, no student timetable integration.

## Delivered

### Backend (additive)

- `models/timetable.py` — `TimetableEntry` extended with:
  - `subsection_id` (nullable FK → subsections.id, via composite FK for section↔subsection coherence)
  - `room` (nullable String(100))
  - `is_active` (Boolean NOT NULL, server default `true` — 28 existing rows backfilled as active)
  - `sort_order` (nullable Integer, deterministic ordering hint)
  - CHECK `end_time > start_time` (`ck_timetable_entries_end_gt_start`)
  - CHECK `day_of_week BETWEEN 0 AND 6` (`ck_timetable_entries_day_of_week_range`)
  - Composite FK `(section_id, subsection_id)` → `subsections(section_id, id)` — guarantees subsection belongs to the entry's section
  - `subsection` relationship (explicit `foreign_keys` to resolve ambiguity with the composite FK)

- `models/user.py` — `Subsection` extended with:
  - `UniqueConstraint("section_id", "id", name="uq_subsections_section_id")` — required target for the composite FK
  - `timetable_entries` relationship (explicit `foreign_keys`)

- `schemas/admin_timetable.py` (NEW): `TimetableEntryAdminResponse` (full Phase 24.7 contract: id, section, subsection, subject, day, start/end time, class_type, room, elective_slot, is_active, sort_order) + `TimetableEntryAdminListResponse`.

- `scripts/verify_phase_24_7a.py` (NEW): static/DB verifier — column existence, constraint presence, 28 rows preserved, no backfill of invented data, upgrade/downgrade cycle validated.

### Migration `c4d5e6f7a8b9`

Additive only — preserves all 28 existing timetable rows byte-for-byte (no backfill of academic data; is_active=true via server default; subsection_id/room/sort_order remain NULL). Upgrade/downgrade tested locally. Single linear alembic head (`c4d5e6f7a8b9`). No unrelated tables changed.

## Verification

- `verify_phase_24_7a.py` PASS (columns, constraints, row count 28, no fabricated data).
- Regression: `verify_phase_24_3.py` 40/40 · `verify_phase_24_5.py` 46/46 · `verify_phase_24_6.py` 46/46.
- `compileall` PASS · `alembic heads` single head `c4d5e6f7a8b9` · `git diff --check` clean.
- Student-facing `GET /api/v1/timetable` endpoint unchanged (response keys verified: `{'id', 'day_of_week', 'class_type', 'subject', 'elective_slot'}`).
- Schema serialization: `TimetableEntryAdminResponse` instantiated from ORM rows, `TimetableEntryAdminListResponse` valid.
- Downgrade `c4d5e6f7a8b9 → eb880e108f19` → upgrade `eb880e108f19 → c4d5e6f7a8b9` cycle clean (columns removed/restored, rows preserved).
- No browser/E2E run performed (operator responsibility). Production untouched; `.env` unchanged (local dev target).

## Phase 24.7-B - Timetable Repository, Service & Conflict Validation (IN PROGRESS, 2026-08-29)

**Status: 24.7 IN PROGRESS: 24.7-B COMPLETE; 24.7-C (HTTP CRUD API) NOT STARTED.** Local development only. No schema change, NO new migration (alembic head `c4d5e6f7a8b9` unchanged). Git state: implemented but NOT committed.

## Objective

The authoritative backend timetable management layer — repository, service, and deterministic conflict detection. The backend owns ALL timetable validation and conflict detection (never the frontend). No HTTP CRUD endpoints, no frontend.

## Delivered

### Backend (additive)

- `repositories/admin_timetable_repo.py` (NEW): bounded, scope-aware queries — `list_entries` (server-derived section/subject filters, deterministic ordering: day → sort_order NULLS LAST → start_time → id), `get_entry`, `list_active_conflict_candidates` (bounded: active same-section/same-day only), counts, academic-context lookups (section/subsection/subject).
- `services/admin_timetable_service.py` (NEW): authoritative validation + conflict detection —
  - academic-context validation (section exists; subject exists; **subject belongs to the section's semester** — incompatible → INVALID_SUBJECT);
  - subsection validation (exists AND belongs to the entry's section → INVALID_SUBSECTION);
  - elective-slot validation (marker must match the subject's catalog slot; elective subjects must carry their slot marker → INVALID_ELECTIVE_SLOT);
  - time validation (end > start → INVALID_TIME_RANGE);
  - **deterministic conflict detection** (see semantics below);
  - active/inactive semantics (inactive never blocks; scheduling edits on inactive entries require reactivation → INACTIVE_PARENT; reactivation re-runs conflict detection);
  - server-side scope resolution via `AuthorizationService` (HEAD unrestricted; CLASS assigned sections; SUBSECTION assigned subsections' sections — inert today; ELECTIVE exact concrete subject) — no client trust;
  - domain-error hierarchy (`TimetableNotFoundError`/`InvalidScope`/`InvalidSubject`/`InvalidSubsection`/`InvalidElectiveSlot`/`InvalidTimeRange`/`TimeConflict`/`InactiveParent`), mapped to 404/403/400/409 in 24.7-C.
- `schemas/admin_timetable.py` (extended): `CreateTimetableEntryRequest`, `UpdateTimetableEntryRequest` (explicit-PATCH), `TimetableEntryMutationResponse`.

### Verifier

- `scripts/verify_phase_24_7b.py` (NEW): **PASS 29/29** (×2 runs, idempotent), locality-guarded, isolated fixtures (fixture session/semester/sections/subsections/subjects + scoped admins), cleanup in `finally`, baseline counts restored.

## CONFLICT SEMANTICS (recorded verbatim)

Two timetable entries CONFLICT when ALL of the following hold:
1. both ACTIVE (inactive entries never block);
2. SAME day of week;
3. SAME section;
4. time ranges OVERLAP: `existing.start_time < new.end_time AND existing.end_time > new.start_time` (adjacent 09:00–10:00 / 10:00–11:00 is NOT a conflict);
5. same effective scheduling scope:
   - section-wide (subsection_id NULL) vs section-wide → CONFLICT
   - section-wide vs subsection-specific (same section) → CONFLICT (the subsection is a partition of the section; overlap double-books those students)
   - subsection-specific vs SAME subsection → CONFLICT
   - subsection-specific vs DIFFERENT subsection → NO CONFLICT (parallel schedules for disjoint groups allowed)
   - DIFFERENT sections → NO CONFLICT

ELECTIVE-SLOT RULE: a logical elective slot resolves to different concrete subjects for different students. Two entries BOTH carrying the SAME `elective_slot` (both ELECTIVE_I or both ELECTIVE_II) do NOT conflict merely because they share the slot — each student follows only the one concrete subject their choice resolves to. Different slots (ELECTIVE_I vs ELECTIVE_II) DO conflict, as does an elective-slot entry vs a regular (non-elective) entry — a student attends both. This is compatible with the existing `ElectiveResolver` anchor model; no student-specific timetable rows are created.

## Verification

- `verify_phase_24_7b.py` PASS 29/29: non-overlapping allowed; adjacent allowed; overlapping same-subsection rejected; section-wide×subsection overlapping rejected; different sections allowed (parallel); different subsections allowed (parallel); inactive does not block new active; invalid time range rejected; incompatible (different-semester) subject rejected; mismatched elective slot rejected; non-elective subject with elective marker rejected; valid elective subject with matching slot allowed; same-slot elective overlap allowed (parallel); ELECTIVE_I×ELECTIVE_II rejected; elective×regular rejected; CLASS_ADMIN own-section only; ELECTIVE_ADMIN own-subject only; SUBSECTION_ADMIN own-section; STUDENT sees nothing; CLASS_ADMIN cannot create for another section; not-found → NOT_FOUND; out-of-scope detail → INVALID_SCOPE; inactive scheduling edit → INACTIVE_PARENT; reactivation re-runs conflict detection; reactivation allowed once slot free; reactivated entry blocks overlap; repository scoped list; baseline counts restored; original active session unchanged.
- Regression: `verify_phase_24_3.py` 40/40 · `verify_phase_24_5.py` 46/46 · `verify_phase_24_6.py` 46/46 · `verify_phase_24_7a.py` PASS.
- `compileall` PASS · `git diff --check` clean · alembic single head `c4d5e6f7a8b9` unchanged (no new migration).
- No browser/E2E run performed (operator responsibility). Production untouched; `.env` unchanged (local dev target).

## Phase 24.7-C - Admin Timetable CRUD API (IN PROGRESS, 2026-08-29)

**Status: 24.7 IN PROGRESS: 24.7-C COMPLETE; 24.7-D (frontend timetable editor) NOT STARTED.** Local development only. No schema change, NO new migration (alembic head `c4d5e6f7a8b9` unchanged). Git state: implemented but NOT committed.

## Objective

Expose the timetable management functionality through a secure Admin API. Security is backend-enforced (frontend hiding is not authorization). No hard-delete of timetable history — deactivation (`is_active=false`) preserves history per Gate 7.

## API Contract (additive, `/api/v1/admin/timetable`)

| Method | Path | Auth (dependency + service) | Notes |
|---|---|---|---|
| GET | `/api/v1/admin/timetable` | `require_any_admin` + service scope | Scoped list; query filters: `session_id`, `semester_id`, `section_id`, `subsection_id`, `day_of_week` (0–6), `is_active`, `subject_id`, `elective_slot`. Filters only NARROW the scope-derived set — never expand. Default returns active entries only. |
| GET | `/api/v1/admin/timetable/{entry_id}` | `require_any_admin` + per-entry scope | Out-of-scope/nonexistent -> 404 (no existence leak). |
| POST | `/api/v1/admin/timetable` | `require_any_admin` + STRICT write gate | Create. Write gate: HEAD_ADMIN (any section) + CLASS_ADMIN (assigned section) only; ELECTIVE/SUBSECTION 403. Full backend validation + conflict detection; conflict -> 409. |
| PATCH | `/api/v1/admin/timetable/{entry_id}` | `require_any_admin` + write gate | Partial update (omitted = unchanged; explicit null clears only nullable fields). Resulting COMPLETE entry revalidated; conflict detection ignores the row being updated (same-row edit never self-conflicts). |
| POST | `/api/v1/admin/timetable/{entry_id}/deactivate` | `require_any_admin` + write gate | Soft deactivate (is_active=false). Idempotent. |
| POST | `/api/v1/admin/timetable/{entry_id}/duplicate` | `require_any_admin` + write gate | Server-side duplication; absent overrides copied from source; full validation + conflict detection; never silently overwrites another entry. |

Authorization matrix (authoritative Phase 24.0 §7): HEAD global; CLASS own sections (read + write); SUBSECTION own subsections' sections (read, inert — write NO); ELECTIVE exact concrete subject (read own-subject entries only, write NO — timetable is the institutional shared schedule; the event path is their write surface). No client-supplied role/scope trusted; filters intersect with scope, never expand.

## Error Contract

401 unauthenticated · 403 insufficient scope (incl. ELECTIVE/SUBSECTION write denial) · 404 missing resource (no existence leak) · 409 timetable conflict / inactive-parent · 422 malformed/invalid data. Mapped from the 24.7-B `TimetableDomainError` hierarchy in the endpoint layer.

## Verification

- `verify_phase_24_7c.py` PASS **30/30** (×2 runs, idempotent), in-process HTTP testing (ASGITransport) against the LOCAL DB: 401 unauth, STUDENT 403, HEAD read/create, conflict 409, adjacent allowed, detail, PATCH room, deactivate + reactivate, duplicate (day override), CLASS_ADMIN own-section create 201 + other-section 403, ELECTIVE_ADMIN create 403, SUBSECTION_ADMIN create 403, CLASS list own-section only, ELECTIVE list own-subject only, SUBSECTION list own-section, filtered list, nonexistent 404s (GET/PATCH/deactivate/duplicate), baseline restored, active session unchanged.
- Regression: `verify_phase_24_3.py` 40/40 · `verify_phase_24_5.py` 46/46 · `verify_phase_24_6.py` 46/46 · `verify_phase_24_7a.py` PASS · `verify_phase_24_7b.py` 29/29.
- `compileall` PASS · `git diff --check` clean · alembic single head `c4d5e6f7a8b9` unchanged (no new migration).
- No browser/E2E run performed (operator responsibility). Production untouched; `.env` unchanged (local dev target).

## Phase 24.7-D/E - Admin Timetable Builder UI + Mutation Workflows (IN PROGRESS, 2026-08-30)

**Status: 24.7 IN PROGRESS: 24.7-D COMPLETE; 24.7-E (mutation workflow completion) COMPLETE; 24.7-F (student-facing integration) NOT STARTED.** Local development only. No schema change, NO new migration (alembic head `c4d5e6f7a8b9` unchanged). Git state: implemented but NOT committed.

## Objective

Build the Admin Portal timetable management surface — a real CRUD interface (not a mockup) inside the existing AdminShell. The UI is NOT the security boundary: reads are scoped server-side; writes are gated by the backend to HEAD_ADMIN + CLASS_ADMIN (assigned section); the frontend only hides controls for presentation. 24.7-E completes every mutation workflow so there are no CRUD leftovers.

## Delivered (additive, inside the existing AdminShell)

- `app/(admin)/admin/timetable/page.tsx` (NEW): scoped timetable page —
  - filters: session/semester/section (HEAD only — structure hooks are HEAD-gated), day, active state, subject, elective slot; filters only NARROW the server-derived result;
  - weekly grid grouped by day (Mon–Sun) with per-entry cards (time range, subject code/name, class type badge L/T/P, elective slot badge EI/EII, room, subsection, active state);
  - loading skeleton, 403 state, error-with-retry, truthful empty state;
  - create/edit/deactivate/duplicate entry actions (shown only to writers; backend authoritative);
  - SWR revalidation after successful mutations; never invents the resulting row; no stale optimistic state survives a failed mutation.
- `components/TimetableEntryForm.tsx` (NEW): reusable form — section, subsection, day, start/end, subject, class type, room, elective slot, active, sort order; light UX validation (required fields, end-before-start) only — server validation is authoritative; field availability respects backend/model capabilities (no nonexistent DB fields).
- `components/CreateTimetableEntryDialog.tsx`, `EditTimetableEntryDialog.tsx` (NEW): create + partial-update flows.
- `components/DeactivateTimetableEntryDialog.tsx` (NEW): explicit confirmation — never silently deletes.
- `components/DuplicateTimetableEntryDialog.tsx` (NEW): server-side duplication with day/time/room overrides.
- `hooks/useApi.ts` + `types/api.ts` (extended): `useAdminTimetableEntries(params)` (query-string filters), `useAdminTimetableEntryDetail`, `useAdminTimetableMutations` (create/update/deactivate/duplicate); contracts mirrored from the backend (canonical `ClassType` "L"/"T"/"P" and `ElectiveSlot` enums — no divergent values).
- `components/admin/AdminShell.tsx`: "Timetable" nav entry (all admins — scoped reads exist; writes HEAD + CLASS server-side).
- `app/(admin)/admin/page.tsx`: Timetable promoted from "Planned portal areas" to "Available now".

## Behavior notes (recorded)

- The grid makes overlapping/conflicting entries obvious via per-day stacking with time labels; the frontend NEVER computes business conflicts independently — the backend is authoritative (409).
- After create/edit/deactivate/duplicate: `mutate()` revalidates the authoritative query, filters are preserved (params unchanged), the current view is kept; no optimistic row invention.
- Errors: 401/403/404/409/422/network surface via the existing error conventions (403 → ForbiddenState, other failures → error-with-retry; mutation failures show the backend message in the dialog and never show success).
- Accessibility: semantic buttons (no div-as-button), labels on all selects, keyboard-accessible Base UI dialogs, visible focus states.

## Verification (static only)

- `npx tsc --noEmit` PASS (0 errors).
- ESLint on all changed files PASS (0 warnings after fixing: unused `setSubsectionId`, pointless filter).
- No browser testing performed (operator responsibility). No frozen student surfaces rewritten. No backend/schema/DB changes in this slice.

## Phase 24.7-E - Mutation Workflow Completion (COMPLETE, 2026-08-30)

Completed within the 24.7-D builder surface; no new files, edits only to the existing timetable components:

- `CreateTimetableEntryDialog` — closes ONLY after the backend accepts the mutation and the page revalidates; remounts fresh per open (`key` on `createOpen`), so no stale form state from a previous cancelled creation.
- `EditTimetableEntryDialog` — sends ONLY CHANGED fields (PATCH preserve-omitted semantics) by diffing form values against the loaded persisted entry; a non-scheduling edit (e.g. room) on an INACTIVE entry no longer trips the backend INACTIVE_PARENT guard; an existing subsection is never silently cleared (`subsection_id` now pre-filled); closes on success.
- `DuplicateTimetableEntryDialog` — description states exactly which fields are copied (subject, section, class type, elective slot, active state) vs overridable (day/time/room); preserves the source's `is_active`; displays backend errors verbatim with a 409-specific styled banner; never bypasses backend conflict validation.
- `DeactivateTimetableEntryDialog` — surfaces backend failures inside the dialog (no silent failure, no fake success); explicit confirmation retained; no hard-delete claims.
- `TimetableEntryForm` — error state now carries the HTTP status; 409 renders a distinct warning banner with the backend detail (conflicting day/time/subject as returned — no client-inferred conflict data); other errors render destructive styling.
- Page — all mutation dialogs keyed per entry id (no stale edit data); filters preserved across mutations; revalidation decides row visibility (deactivated rows leave the active view naturally).

## Verification (static only, 24.7-E)

- `npx tsc --noEmit` PASS (0 errors).
- ESLint on all changed files PASS (0 warnings/errors; one unescaped-entity fix).
- `git diff --check` clean.
- No browser testing performed (operator responsibility). No backend/schema/DB changes in this slice. No student attendance/session behavior touched.

## Phase 24.7-F - Conflict-Aware UX (COMPLETE, 2026-08-30)

Completed within the 24.7-D/E builder surface + the 24.7-C API contract. No new endpoints; backend contract extended additively; frontend edits to the timetable components and `apiFetch`.

- **Conflict response contract (backend, additive):** 409 now returns `{"detail": {"message": "...", "conflicts": [...]}}` where `conflicts` is the structured, backend-resolved list of conflicting entries — each carries `id` (string), `subject_code`, `subject_name`, `section_name`, `subsection_name`, `day_of_week`, `start_time`, `end_time`, `subsection_id`, `elective_slot`. UUIDs are stringified so the body is JSON-serializable. The human-readable message now includes scope context (day label + section/subsection name) via `AdminTimetableService._format_conflicts`. Other error codes keep the string `detail` convention.
- **`apiFetch` (additive):** preserves the HTTP status and now attaches the parsed response body (`error.body`) so callers can read structured fields; string/object/absent `detail` forms are all handled.
- **UI rendering:** the `TimetableEntryForm` and `DuplicateTimetableEntryDialog` render the backend `conflicts` list verbatim (subject code, section, day label, time range, subsection) inside the 409 warning banner. No conflict data is inferred on the client.
- **Conflict-aware form behavior:** a 409 keeps the form values, keeps the dialog open, shows the conflict, and never shows success. Conflicting entries are listed so the admin can correct day/time/scope.
- **Concurrency (recorded):** the backend remains authoritative — every create/update/duplicate/deactivate re-reads the CURRENT database state (via `AdminTimetableService`/repository) and re-runs deterministic conflict detection against it. A stale frontend opened before another administrator changed the timetable cannot bypass validation: the save is validated against live rows and returns 409 (or 404/403) if the target changed out from under the admin. There is no optimistic UI state; after a successful save the page revalidates the authoritative query.
- **Grid:** entry cards now render a time-position bar within the day window (08:00–18:00), so overlapping entries are visually obvious rather than silently stacked.
- **Verification:** `verify_phase_24_7c.py` still PASS **30/30** (409 assertions unchanged — they check status code only). `compileall` PASS · `tsc --noEmit` PASS · ESLint PASS (one pre-existing `window.location.href` warning in api.ts, unrelated) · `git diff --check` clean. Live 409 body verified (message with scope context + structured `conflicts` list). No browser testing performed (operator responsibility). No schema/migration/DB changes; production untouched; `.env` unchanged.

## Phase 24.7-G - Student Timetable Resolution (COMPLETE, 2026-08-30)

The student-facing timetable endpoint (`GET /api/v1/timetable`) now derives the student timetable from the student's academic context, their LOCKED elective choices, and the authoritative timetable — no hardcoded current-semester assumptions. The expected-schedule concept is preserved; entries are NOT collapsed into `class_sessions`.

- **`repositories/timetable_repo.py`:** new `get_weekly_entries_for_student(section_id, subsection_id)` — ACTIVE entries only (`is_active=true`), section-wide entries (`subsection_id IS NULL`), plus the student's OWN subsection entries; OTHER subsections' private schedules are excluded (no leakage). A student with no subsection sees section-wide entries only.
- **`api/v1/endpoints/timetable.py`:** uses the student-scoped query; shared DE-I/DE-II slots resolve to the student's locked concrete subject (`StudentElectiveChoice`); a slot entry with NO locked choice is **OMITTED** — the anchor subject (BCS-054 / BCS-058) is never exposed merely because it exists in the timetable configuration; common subjects returned unchanged; no hardcoded semester assumptions.
- **Frontend:** no changes required — the student timetable surface (dashboard today-classes / EventFormDialog subject picker) consumes the same unchanged response shape; resolution correctness flows through automatically.
- **`scripts/verify_phase_24_7g.py` (NEW):** PASS **25/25** — Student A (DE-I BCS-054, DE-II BCS-058), Student B (DE-I BCS-052, DE-II BCS-055), Student C (no locked choices); fixture section with two subsections + section-wide/subsection-specific/inactive entries; verifies common subjects, elective resolution, subsection isolation, no anchor leakage, no cross-student leakage, inactive entries excluded, exact resolved set + count per student, baseline restored, active session unchanged.
- **Regressions:** `verify_phase_24_3.py` 40/40 · `verify_phase_24_5.py` 46/46 · `verify_phase_24_6.py` 46/46 · `verify_phase_24_7c.py` 30/30.
- `compileall` PASS · `git diff --check` clean · alembic head `c4d5e6f7a8b9` unchanged (no migration).
- No browser/E2E run (operator responsibility). No student attendance/session behavior mutated. Production untouched; `.env` unchanged (local dev target).

## Phase 24.8 - Quiz Schedule Manager (COMPLETE, 2026-08-30)

Admin can configure quiz cycles, dates, subjects, Departmental Elective-I/II, and relevant eligibility settings via the canonical quiz architecture (Phases 7/22/23) � no new quiz engine, no eligibility rewrite, no duplicate schedule source.

### Canonical authority (repository evidence)

- `QuizSchedule` = the admin configuration/plan (subject, cycle, elective_slot, date, status).
- **ACTIVE QUIZ_DAY AcademicEvents = the canonical runtime quiz-date authority** (eligibility reads them via `QuizRepository.get_effective_quiz_dates_for_subjects`); `QuizSchedule` is the derived projection this service manages.
- `EventSessionSynchronizer` (Phase 6.6) reconciles class_sessions quiz-day occurrences from events � reused, not re-implemented.
- `EligibilityPolicy` thresholds remain persisted configuration (read-only here).

### Backend (additive)

- `schemas/admin_quizzes.py` (NEW): cycle/policy reads, schedule read model (with `has_active_event` derivation parity indicator), create/update/mutation responses.
- `repositories/admin_quiz_repo.py` (NEW): bounded schedule/cycle/policy queries, duplicate guard, QUIZ_DAY event identity lookup.
- `services/admin_quiz_service.py` (NEW): scope resolution (HEAD all, CLASS own semester, ELECTIVE exact subject, SUBSECTION inert); validation (subject quiz-applicable theory, date-in-semester, cycle exists, elective-slot relationship, duplicate identity); **single-transaction atomic QUIZ_DAY sync** (create/deactivate/date-move via `EventSessionSynchronizer`; idempotent; no partial reality).
- `endpoints/admin.py` (additive): `GET /api/v1/admin/quizzes`, `GET /api/v1/admin/quizzes/{id}`, `GET /api/v1/admin/quiz-cycles`, `POST /api/v1/admin/quizzes`, `PATCH /api/v1/admin/quizzes/{id}`. Reads `require_any_admin` + scope; writes `require_head_admin`; errors 401/403/404/409/422.

### Frontend (additive, inside AdminShell)

- `app/(admin)/admin/quizzes/page.tsx` (NEW): table overview, cycle/session/semester filters, target/date/status/QUIZ_DAY badges, create/edit dialogs.
- `components/CreateQuizScheduleDialog.tsx`, `EditQuizScheduleDialog.tsx` (NEW): fields from real backend capability; PATCH semantics; no close on 409/422; no fake success.
- `AdminShell.tsx` nav (Quiz Schedules), dashboard "Available now" promotion.

### Verification

- `verify_phase_24_8.py` PASS **34/34** (auth 401/403/scope; baseline 18 schedules; create common/elective; duplicate 409; invalid subject 404; elective-slot 422; date move ? old event deactivated + new event created; cancel ? deactivated; idempotent no-churn; reactivate ? created; elective schedule isolation; student elective isolation A=BCS-058 200 / B=BCS-058 404; baseline restored; active session unchanged).
- Regressions: 24.3 40/40 � 24.5 46/46 � 24.6 46/46 � 24.7a PASS � 24.7b 29/29 � 24.7c 30/30 � 24.7g 25/25 � 24.7h 27/27.
- `compileall` PASS � `tsc --noEmit` PASS � ESLint PASS � `git diff --check` clean � **alembic head `c4d5e6f7a8b9` unchanged (no migration)**.
- No browser/E2E run (operator responsibility). Production untouched; `.env` unchanged (local dev target).

## Phase 24.9 - Event Manager (COMPLETE, 2026-08-30)

The Admin Portal now manages the existing AcademicEvent system through a
dedicated control-plane API. All mutations flow through the canonical
EventService / validation registry / EventSessionSynchronizer — no second
event engine, no direct class_sessions/occurrence_outcomes writes.

### Backend (additive)
- `schemas/admin_events.py` (NEW): admin event read model (event type, active,
  dates, subject, elective_slot, class_type, substitution day, note,
  `quiz_schedule_managed` classification, `target_summary`).
- `services/admin_event_service.py` (NEW): scope-filtered reads (HEAD all,
  CLASS own-semester subjects, ELECTIVE exact subject, global HEAD-only,
  SUBSECTION inert, STUDENT 403); create/update/deactivate through the
  canonical `EventService`; **QUIZ_DAY ownership guard** — a QUIZ_DAY event
  backed by a SCHEDULED QuizSchedule row is refused any generic mutation (409)
  so Phase 24.8 quiz<->QUIZ_DAY parity can never be desynchronized through the
  Event Manager.
- `endpoints/admin.py` (additive): `GET/POST /api/v1/admin/events`,
  `GET/PATCH/DELETE /api/v1/admin/events/{id}` (DELETE = safe deactivation,
  reversible; no physical deletion). Reads `require_any_admin` + scope;
  writes follow the Phase 24.0 capability matrix (HEAD global/closure,
  CLASS own-semester subject events, ELECTIVE own-subject events).

### Frontend (additive, inside AdminShell)
- `app/(admin)/admin/events/page.tsx` (NEW): table overview, event-type/state
  filters, quiz-managed badge, create/edit/deactivate dialogs.
- `components/CreateEventDialog.tsx`, `EditEventDialog.tsx` (NEW): field
  visibility mirrors the shared `eventRules` map (one frontend mirror —
  backend authoritative); QUIZ_DAY ownership warning; PATCH semantics; no
  close on 409/422; no fake success.
- `AdminShell.tsx` nav (Events) + dashboard "Available now" promotion.

### Verification
- `verify_phase_24_9.py` PASS **40/40** (auth 401/403/scope; baseline events
  load; CLASS/ELECTIVE scoped reads + matrix-authorized writes; global
  closure 403 for scoped admins; registry validation (invalid subject/class-
  type, inverted dates, missing fields, duplicate) -> 422/409; synchronizer
  extra-session effect; PATCH; DELETE = deactivation + reactivate; QUIZ_DAY
  ownership guard (PATCH/DELETE/create on scheduled dates -> 409, standalone
  QUIZ_DAY allowed); arbitrary UUID 404; client spoofing 403; baseline
  restored; active session unchanged).
- Regressions: 24.3 40/40 · 24.5 46/46 · 24.6 46/46 · 24.7a PASS · 24.7b
  29/29 · 24.7c 30/30 · 24.7g 25/25 · 24.7h 27/27 · 24.8 34/34.
- `compileall` PASS · `tsc --noEmit` PASS · ESLint PASS · `git diff --check`
  clean · alembic head `c4d5e6f7a8b9` unchanged (no migration).
- No browser/E2E run performed (operator responsibility). Production
  untouched; `.env` unchanged (local dev target).

## Phase 24.10 - Subject-Specific Elective Events (COMPLETE, 2026-08-30)

**DISCOVERED GAP:** the divergent elective-event capability was already
canonical - Phase 23.6/23.7/23.8 implemented it inside
`EventSessionSynchronizer` (`_desired_schedule` computes
`desired_outcomes[subject_id]` for subject-scoped events whose slot has a
timetable session; `_reconcile_outcomes` materializes `occurrence_outcomes`
keyed (anchor session, subject), state-based and idempotent; cancellation
wins over modification). The actual gaps were admin-surface exposure:
subject-slot context, server-computed mutation capability, slot-wide
targeting in the Create dialog, and a divergence verifier.

**Implemented (no second engine, no schema change):**
- `AdminEventResponse.subject_slot` + `can_mutate` (server-computed).
- `/admin/events` Create dialog: slot-wide (HEAD-only) vs concrete-subject
  targeting with an unambiguous distinction; "DE-I/DE-II member" badge;
  Edit gated by backend `can_mutate`.
- `scripts/verify_phase_24_10.py` PASS **35/35**: ELECTIVE_ADMIN (BCS-058)
  SURPRISE_QUIZ + BCS-056 CLASS_CANCELLED on the SAME slot/date; BCS-055
  normal lecture (no outcome); anchor session intact; no per-student
  duplication; EXTRA fallback only for the targeted subject; duplicate
  guard; idempotency; isolated per-subject reversal on PATCH-move/DELETE;
  QUIZ_DAY guard intact; isolation + spoofing + baseline restored.
- Verification defect fixed (narrow): `verify_phase_24_9.py` E4 outcome
  residue - outcome-composing fixture events now deactivated through the
  canonical DELETE path; 24.9 verifier 40/40 restored.

**Next slice (recommended)**

Phase 24.11 - Admin & Scope Management (admin accounts, scope
assign/revoke/activate, provisioning workflow). NOT STARTED.
## Next slice (recommended)

Phase 24.10 — Subject-Specific Elective Events (per-elective-subject outcome
divergence, e.g. BCS-058 Surprise Quiz vs BCS-055 normal vs BCS-056
cancelled on the same DE-II date). NOT STARTED.
## Next slice (recommended)

Phase 24.9 � Event Manager (holidays/closures/overrides + scoped event UX consolidation; reuses the existing `/events` surface). NOT STARTED.

---

## Student Portal Usability & Session Recovery Fixes (2026-08-31)

Frontend-only fixes after the 2026-08-30 production recovery, addressing
real-world usage issues (PWA + web): repeated auto-logout, perceived
slowness, calendar UI, mobile navigation. Root cause of the logout loop was
AuthContext clearing the JWT on ANY transient profile-fetch failure (Render
cold starts / flaky mobile networks); the session is now destroyed only on
genuine 401/403, with focus-based self-healing retry. Also: mobile bottom
nav "Profile" -> "More" (Profile entry removed from the sheet), notification
bell breathing space, notifications as a mobile bottom sheet, and a cleaner
calendar grid. No backend/schema/DB/.env changes; `tsc` PASS; ESLint only
pre-existing errors; `git diff --check` clean; uncommitted for operator
review. Operator browser verification pending.

---

## Student Portal Audit � Phase 1 Root-Cause Investigation (2026-08-31)

**Status: AUDIT COMPLETE � no code changes in this phase.**

### Findings summary
- **Auth redirect/logout loop � ROOT CAUSE FOUND and ALREADY FIXED (commit 859b1f7).** AuthContext previously cleared the JWT on ANY profile-fetch error, including transient network/cold-start failures. Trace: dashboard renders ? parallel /student/me (or any) request fails transiently ? token removed + setUser(null) ? redirect effect pushes /login ? re-login loop. Fixed: token cleared only on genuine 401/403; redirect gated on token absence; focus/visibility self-healing retry added.
- **Remaining perf findings:** duplicate `/api/v1/student/me` (AuthContext direct apiFetch + SWR useProfile); NotificationBell fetches `/notifications` on every shell mount AND the backend regenerates notifications on every read (expensive); STANDARD_CACHE revalidateOnFocus triggers parallel refetches on every mobile focus; service-worker navigation is cache-first (stale-shell risk); Render free cold start is the primary "slow" driver.
- **UI items 6-10 (mobile nav Profile?More, bell spacing, notification panel, More-sheet Profile removal) � ALREADY FIXED in 859b1f7.** Calendar grid mobile layout improved in 859b1f7.
- No Admin Portal, DB, migration, or deployment work in this phase.

---

## Phase A � Deduplicate /student/me Requests (2026-08-31)

**Status: IMPLEMENTED (committed as 2c90240).**

Duplicate request root cause: AuthContext used `apiFetch("/api/v1/student/me")` directly (not via SWR), while TopNav/UserMenu/MobileBottomNav/GreetingHeader consumed `useProfile()` (SWR with same key). SWR deduped its own consumers but AuthContext was outside that cache � net 2 requests per authenticated load.

Architecture chosen: shared SWR profile resource. AuthContext consumes the same `PROFILE_KEY` (`/api/v1/student/me`) via `useSWR`, gated on token presence. SWR coalesces AuthContext and useProfile() into one logical request. The shared key is defined in `lib/api.ts` (neutral leaf both modules import). Auth invariants preserved: token gating prevents stale profile authentication; derived user (no setUser state) ensures immediate null on token removal; cache cleared on logout/401/403; global mutate used for refreshUser cross-key; self-heal retry via `mutate()` on focus/visibility; SWR dedup replaces manual in-flight guard.

Validation: `npx tsc --noEmit` PASS. ESLint: AuthContext has 2 `set-state-in-effect` errors (1 pre-existing pattern, 1 new � same class, CI informational). No eslint changes in useApi.ts/api.ts. git diff --check clean. No backend/DB/schema/.env changes. No commit/push.

---

## Phase B � Notification Fetch & Regeneration Optimization (2026-08-31)

**Status: IMPLEMENTED (committed as 2c90240).**

### Previous flow
Every GET /api/v1/notifications called NotificationService.get_notifications,
which ALWAYS regenerated all projection kinds (class reminders, quiz
approaching, attendance items, academic events) and upserted each into the DB
� even for a routine shell-mount unread-badge read. NotificationBell calls
useNotifications(!!token) at shell mount with STANDARD_CACHE
(revalidateOnFocus: true) so every mount + focus + panel open triggered full
regeneration; worst on Render cold starts / PWA foreground transitions.

### New architecture (backend, minimal)
Short-lived per-user in-process TTL cache in NotificationService:
- Key = authenticated user UUID (strictly per-user, no cross-user leak).
- TTL = 60s monotonic; after expiry the next read regenerates + upserts once.
- get_notifications serves cached response within TTL (no regeneration, no writes).
- update_state (read/dismiss PATCH) invalidates the user entry so badge stays correct.
- No Redis/new infra; in-process limitation documented (single-worker deployment
  fully benefits; N workers would run N independent per-user caches � no leak).

Frontend untouched: NotificationCenter already gates fetch on `open`; bell
mutate() on open forces a fresh GET; SWR dedupingInterval 60s dedupes rapid
fetches. Backend TTL makes all these cheap.

### Validation
Backend compile + import OK. In-memory cache mechanics test PASS (hit,
per-user isolation, invalidate, TTL expiry/eviction). Frontend tsc PASS.
git diff --check clean. No DB/migration/engine/JWT/Admin changes. No commit/push.

---

## Phase C � SWR Cache & Refetch-Storm Optimization (2026-08-31)

**Status: IMPLEMENTED (committed as 2c90240).**

### Previous behavior
Universal STANDARD_CACHE = { revalidateOnFocus: true, dedupingInterval: 60000 } was used by profile, dashboard summary, analytics overview, notifications, calendar, events, history, lab, preferences � all on every authenticated page. On PWA foreground transition, every mounted hook refetched simultaneously (a "refetch storm"), worst on cold Render instances.

### New cache policies (resource-aware)
- INTERACTIVE_CACHE: revalidateOnFocus true, revalidateIfStale true, dedupingInterval 60s. Used for profile, daily sessions, subject summary, quiz eligibility, current quiz cycle, calendar day.
- DASHBOARD_CACHE: revalidateOnFocus true, revalidateIfStale true, dedupingInterval 120s (moderate dedupe, controlled focus). Used for dashboard summary.
- SEMI_STATIC_CACHE: revalidateOnFocus false, revalidateIfStale true, dedupingInterval 5 min. Used for analytics overview, calendar month, events, attendance history, lab records/summary/activity, preferences.
- STANDARD_CACHE unchanged: notifications (Phase B backend TTL) + all admin hooks (out of scope).
- LONG_CACHE unchanged: subjects, timetable, lab experiments.

### Cross-user cache isolation
AuthContext.logout and refreshUser now clear the entire SWR cache via `globalMutate(() => true, () => undefined, { revalidate: false })` � a new login can never flash stale data from the previous user.

### Attendance freshness
After attendance mutations (lab/Track page), mutate() + mutateDashboard() revalidate daily sessions and dashboard summary. Analytics overview revalidates on navigation (revalidateIfStale); dashboard summary refetches on focus (DASHBOARD_CACHE). Targeted invalidation is preserved.

### Files changed
frontend/src/hooks/useApi.ts (cache policies + hook assignments),
frontend/src/contexts/AuthContext.tsx (cross-user cache clear on logout/refreshUser).

### Validation
npx tsc --noEmit PASS. ESLint: AuthContext has 2 pre-existing set-state-in-effect errors (same class as committed baseline). useApi.ts clean. git diff --check clean. No backend/DB/migration/Admin changes. No commit/push.

---

## Phase D � Service Worker Reliability & Cache Strategy (2026-08-31)

**Status: IMPLEMENTED (committed as 2c90240). Student Portal PWA only.**

### Old service-worker behavior
- Navigation requests served **cache-first** (`caches.match` before network) � stale HTML application shell could persist indefinitely after deployment.
- `/api/*` handled network-first with a **clone-but-not-cache** no-op and a 503 JSON offline fallback.
- `STATIC_ASSETS` hardcoded invalid paths `/_app`, `/_error`, `/globals.css` � these are NOT produced as literal files by the App Router build; `cache.addAll` could reject and fail installation.
- `self.skipWaiting()` on install + `self.clients.claim()` on activate � forced immediate worker takeover (HTML/JS mismatch risk).
- No cache-version constant (hardcoded `attendancedash-pro-v1`).
- Navigation branch matched by pathname (`startsWith("/")`) � effectively every same-origin GET; JS/CSS fell into cache-first handling.

### New caching strategy
- **Navigation: network-first with cache fallback** (`request.mode === "navigate"`): always fetch the latest HTML, store a copy in the versioned cache via `cache.put`, and fall back to the cached shell only when the network is unavailable. A returning PWA user gets the current shell after deployment instead of an obsolete one.
- **API: network-only, never cached** � preserved; authenticated/personalized data (`/student/me`, dashboard summary, attendance, notifications, calendar, etc.) stays strictly network-driven; no shared cache that could cross-user leak. Offline JSON 503 fallback retained.
- **Static precache**: `STATIC_ASSETS` reduced to verified paths (`/`, `/favicon.ico` [served from `src/app/favicon.ico`], `/manifest.json`, `/icons/icons-192.svg`, `/icons/icons-512.svg`); invalid `/_app`, `/_error`, `/globals.css` removed. `cache.addAll` errors swallowed so a single missing path cannot fail installation. Hashed `/_next/static/*` artifacts are NOT enumerated (browser HTTP cache handles content-addressed assets).
- **Non-navigation, non-API requests** (JS/CSS/images/fonts) no longer intercepted � content-addressed build artifacts are served by the browser cache.

### Cache versioning & update lifecycle
- `CACHE_VERSION = "v2"` constant ? `attendancedash-pro-v2`; activate deletes all non-current caches. Bumping the constant invalidates everything on next SW update.
- `skipWaiting` **removed**: the new worker waits for reload instead of force-takeover, avoiding fresh-HTML-with-stale-JS/CSS pairing. `clients.claim()` retained (safe under network-first navigation).
- Registration hook (`useServiceWorker.ts`) adds: update-notice logging on `onupdatefound`, hourly `registration.update()` check, and an update check on window focus � active clients eventually receive the deployed worker without an unsafe immediate takeover.
- Note: the hook is currently **not mounted** anywhere in the app (pre-existing wiring gap; SW never registered at runtime). Not changed in this phase � documented for a follow-up.

### Files changed
- `frontend/public/service-worker.js` (rewritten)
- `frontend/src/components/pwa/useServiceWorker.ts` (update lifecycle + cleanup)

### Validation
- `node --check frontend/public/service-worker.js` � syntax PASS.
- `npx tsc --noEmit` (frontend) � PASS, 0 errors.
- ESLint on `useServiceWorker.ts` � clean.
- Static asset paths verified against repo (`public/` + `src/app/favicon.ico`).
- No backend/DB/migration/API/auth/JWT/Admin changes. No commit/push.

---

## Phase E � Targeted Mobile Calendar & Notification Polish (2026-08-31)

**Status: IMPLEMENTED (committed as 2c90240). Student Portal only. No redesign of Calendar or notification architecture; no backend/API/DB/Admin changes; no business-logic changes.**

### Calendar remaining issues
1. Non-working reason text truncated inside small day cells � replaced on mobile (<sm) with a compact dot indicator; the full reason remains in the cell's aria-label (already present) and is rendered completely in DayDetail. On sm+ the truncated reason text with `title` tooltip is preserved.
2. DayDetail long stacked card on mobile � reduced vertical rhythm on mobile (`mt-4` sections to `mt-3 sm:mt-4`, events header `mb-3` to `mb-2 sm:mb-3`); non-working reason line now wraps (`items-start` + `leading-relaxed`) instead of clipping.
3. Event rows excessive mobile spacing � row padding `px-3 py-2` to `px-2.5 py-1.5 sm:px-3 sm:py-2`; subject-code + name row now wraps (`flex-wrap`) so long names cannot overflow.

### Notification remaining issues
1. Bottom sheet drag handle � ShellDialog (mobileSheet mode) renders a centered visual handle bar above the header, mobile-only (`sm:hidden`), purely visual; no gesture/JS added.
2. Safe-area bottom padding � mobileSheet content adds `pb-[env(safe-area-inset-bottom)] sm:pb-0` (pure CSS env(), no JS viewport detection), so the sheet content clears the home-indicator area; desktop unchanged.
3. Long notification message spacing � reviewed; existing `text-sm leading-snug` with `mt-1.5` and wrapping paragraphs is sufficient; no change made.

### Preserved (no regression)
Full-width mobile sheet, desktop centered dialog, vertical scrolling (max-h caps + overflow-y-auto), Read/Dismiss actions, unread indicator, calendar backend read model and event semantics (all values still rendered directly from API data; no business rules in React).

### Files changed
- frontend/src/components/shell/ShellDialog.tsx (drag handle + safe-area padding for mobileSheet)
- frontend/src/components/calendar/CalendarGrid.tsx (mobile compact non-working indicator)
- frontend/src/components/calendar/DayDetail.tsx (mobile spacing + wrapping)

### Validation
- npx tsc --noEmit (frontend) � PASS, 0 errors.
- npm run lint � 10 errors / 2 warnings, all pre-existing in files not touched by this phase (admin dialogs, login/signup, history, AuthContext, GlassCard, api.ts). Changed files lint-clean.
- npm run build � PASS (25/25 static pages). Note: the build requires NEXT_PUBLIC_API_URL to be a production HTTPS URL (intentional guard from commit 99f6619); verified with a placeholder value.
- No commit/push, no deploy, no browser automation.

---

## Final Integration & Performance Regression Audit (2026-08-31)

**Status: COMPLETE (code-level audit). No code changes made. Phases A�E committed as 2c90240.**

### 1. Authentication � INTACT
- Hydration distinguishes loading (`tokenStatus "unknown"` or in-flight first profile fetch) from unauthenticated (`"absent"`); loading never redirects to /login.
- Transient failures (no status / 5xx) keep the token; only genuine 401/403 removes the token and clears the cached profile (AuthContext.tsx:80-89).
- Focus/visibility self-healing retry intact (AuthContext.tsx:95-107); SWR dedupes.
- Redirect logic: /login only when `tokenStatus === "absent"`; /dashboard when authenticated on a public route. No loop possible (loading gates all redirects).
- No accidental hard logout; logout is explicit-only (plus full-cache clear).

### 2. /student/me � DEDUPLICATED
- Single shared SWR key PROFILE_KEY ("/api/v1/student/me") consumed by both AuthContext and useProfile() � one logical request; no provider/hook circular dependency; key gated on token presence so a stale cached profile can never surface while logged out.

### 3. Notifications � CONSISTENT WITH PHASE B
- Bell and center share one SWR key (gated on token presence / center `open`); open triggers one revalidation; no polling. Backend: per-user UUID-keyed 60s TTL in-process cache; PATCH read/dismiss invalidates; never cross-user. STANDARD_CACHE retained for notifications deliberately (backend TTL makes focus revalidation cheap).

### 4. SWR � NO REFETCH STORM
- INTERACTIVE (profile, dashboard-adjacent reads, daily sessions, quiz, calendar day), DASHBOARD (summary, 2-min dedupe), SEMI_STATIC (analytics, calendar month incl. `keepPreviousData`, events, history, lab, preferences), LONG (subjects, timetable, lab experiments), STANDARD (admin + notifications). Attendance mutations revalidate daily sessions + dashboard summary via mutateAttendance callers. Calendar month keys include year+month. No cache-key collisions (distinct paths per resource); profile coherent across context and hooks.

### 5. Service worker � CONSISTENT
- Network-first navigation + versioned `cache.put` fallback; CACHE_VERSION "v2" constant; activate deletes non-current caches; `/api/*` network-only (never caches authenticated data); invalid `/_app`/`/_error`/`/globals.css` precache entries removed; no skipWaiting (no shell/asset mismatch); syntax check PASS.
- Known pre-existing gap (documented, unchanged): the `useServiceWorker()` hook is not mounted, so no SW registers at runtime until wired. Not changed in this audit (mounting is a feature/wiring decision, out of scope).

### 6. Calendar � FROZEN CONTRACT INTACT
Diff since 859b1f7 touches only presentation classNames/indicators in CalendarGrid/DayDetail/ShellDialog; zero changes to calendar engine semantics, API contract, event semantics, EventSessionSynchronizer, or persistence. `useCalendarMonth` key includes year+month; SEMI_STATIC + keepPreviousData preserves grid behavior.

### 7. Mobile navigation/header � INTACT
- Bottom nav: Home, Attendance, History + More (4th, grid-cols-4). More sheet lists Track/Laboratory/Quiz Eligibility/Calendar/Events (+ Feedback for ADMIN role) � Profile NOT duplicated.
- TopNav: NotificationBell then UserMenu avatar in `ml-auto flex gap-2 sm:gap-3` � top-right avatar and bell spacing unchanged.

### 8. Scope-creep audit � CLEAN
Diff 859b1f7..HEAD: 13 files (4 governance docs + 9 code). Backend: only notification_service.py. NO admin changes, NO DB/migration changes, NO auth rewrite (AuthContext change is the planned Phase A dedupe), NO new dependencies (package.json/requirements unchanged), NO duplicate caching systems, NO timeout hacks, NO overflow:hidden hacks, NO fake loading states, NO security weakening, NO dead code introduced. `py_compile` on notification_service.py PASS.

### Validation
- `npx tsc --noEmit` � PASS (0 errors).
- `npm run lint` � 10 errors / 2 warnings; the exact pre-existing baseline (admin student dialogs `any`, login/signup, history set-state-in-effect, AuthContext intentional hydration setState, GlassCard unused import, api.ts location warning). No new findings from Phases A�E.
- `npm run build` � PASS 25/25 (with production NEXT_PUBLIC_API_URL per the 99f6619 guard).
- `node --check frontend/public/service-worker.js` � PASS.
- `python -m py_compile backend/app/services/notification_service.py` � PASS.
- No browser automation, no deploy, no commit/push of this audit.

---

## Branding & Logo System (2026-08-31)

**Status: COMPLETE � new AttendanceDash Pro brand system implemented (uncommitted).**

New brand: a bold geometric "A" monogram whose crossbar is an attendance checkmark � primary-blue legs on the slate tile with a light check. Reads as a distinct glyph at 16px and stays clean on masked PWA icons.

- Authoritative source: `frontend/scripts/generate_brand_icons.py` (one geometry spec ? SVG masters + all rasters).
- Vector masters: `frontend/public/brand/logo-mark.svg` (transparent), `logo-mark-tile.svg` (on tile).
- Rasters: `icon-512/192.png` (any), `icon-maskable-512/192.png` (maskable, full-bleed), `apple-touch-icon.png` (180), `logo-mark.png` (256 transparent), `logo-mark-tile.png` (256 tile), plus regenerated `src/app/favicon.ico` (16/32/48).
- In-app usage: TopNav + AdminShell headers now render the mark (`/brand/logo-mark.png`); AdminShell "Student app" button icon switched to LayoutDashboard (was broken Gauge reference after import removal).
- Metadata: `manifest.json` icons updated to brand PNGs (any + maskable purposes); `layout.tsx` metadata.icons adds icon + apple touch; `service-worker.js` precache updated to brand icons (CACHE_VERSION v2?v3).
- Stale assets removed: `public/icons/icons-192.svg`, `public/icons/icons-512.svg`.
- Preserved: brand name "AttendanceDash Pro", existing dark design tokens (no color-system changes), login/signup text branding (no logo image was present there � no change), frozen phases untouched.
- Known limitation: PWA/SW registration hook remains unmounted (pre-existing) � icons are correctly referenced but the service worker does not register at runtime until wired.

---

## Investigation: Dashboard date/time consistency bug (2026-08-31)

**Status: INVESTIGATION COMPLETE � no code change made (fix pending separate authorization).**

Observed: header "Monday � 31 Aug 2026" (browser IST) vs Today's Attendance "Sunday � 30 Aug 2026" and This Week "2026-08-24 ? 2026-08-30" (backend).

Root cause: the dashboard/analytics/calendar/history/quiz/lab/event services use Python's `date.today()` (server OS-local clock). The server runs in UTC, so at 31 Aug 02:27 IST (= 30 Aug 20:57 UTC) `date.today()` returns 2026-08-30. The GreetingHeader renders `new Date()` in the browser's IST timezone ? 2026-08-31. Two independent "today" values disagree.

- 31 Aug: `frontend/src/components/dashboard/home/GreetingHeader.tsx:22` ? `formatLongDate(new Date())` (browser-local).
- 30 Aug: `backend/app/services/dashboard_service.py:63` `today = date.today()` ? `_build_today` (Today's Attendance `date`), `_build_weekly` (week_start 24 Aug, week_end 30 Aug), `generated_at`, quiz-snapshot future filter (line 306), upcoming events (line 361).
- The repo already has the canonical IST helper `institution_today()` (`backend/app/services/attendance_service.py:32-34`, driven by `INSTITUTION_TIMEZONE = "Asia/Kolkata"` in `app/core/config.py:18`) � used by notifications, the attendance mutation guard, and admin analytics, but NOT by the dashboard/analytics/calendar/history/quiz/lab/event paths.
- SWR/cache NOT involved: the observed week range is the live UTC week (a stale cache would show an earlier week); `DASHBOARD_CACHE` (revalidateOnFocus, 120 s dedupe) and `SEMI_STATIC` analytics only determine freshness, not which date is computed.
- No hydration mismatch: both values are live-computed (browser vs server), not stale renders.
- Systemic: same `date.today()` pattern exists in `analytics_service.py:44`, `api/v1/endpoints/calendar.py:63`, `eligibility_service.py:233`, `attendance_service.py:263` (history range_end), `laboratory_service.py:120`, `calendar_repo.py:38`, plus Admin `admin_dashboard_service.py:45,186,225` and `admin_dashboard_repo.py:274,289` (out of scope). Notifications and the attendance future-date mutation guard already use `institution_today()`.
- Recommended fix (not yet applied): replace `date.today()` with `institution_today()` in the student-facing read paths listed above. No DB/migration/auth/attendance-math change. Risks: none to auth/performance/cache; read/mutation "today" become the same IST clock. Regression tests: assert dashboard `today`/week range equals IST date during the 00:00�05:30 IST UTC-overlap window; assert weekly.week_start is the Monday of the IST week; verify analytics series last week matches dashboard week_start.

---

## Investigation: Student Portal Auto-Logout After Several Hours (2026-09-02)

**Status: INVESTIGATION COMPLETE � NO CODE CHANGES MADE.** Static/code inspection
only; no browser/E2E runs; no backend, frontend, schema, migration, deployment,
or auth-behavior modification. This is a follow-up to the 2026-08-31 audit: the
transient-failure logout loop was already fixed (commits `859b1f7`, `2c90240`),
but the user still reports being logged out after being logged in for several
hours (web + PWA).

### Root cause (exact)

**The reported logout is EXPECTED JWT access-token expiration.**

- Exact configured lifetime: **480 minutes = 8 hours** � `backend/app/core/config.py:23`
  (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480`, env-overridable), and pinned to
  `"480"` in `render.yaml:33` (production). No other lifetime exists in the repo.
- `create_access_token` (`backend/app/core/security.py:48-60`) sets
  `exp = now(UTC) + 480min`, with claims `sub` (user UUID), `roll_number`, `type="access"`.
- `get_current_user` (`backend/app/api/dependencies/deps.py:21-54`) verifies the
  JWT via `jwt.decode(..., algorithms=["HS256"])`; `jwt.ExpiredSignatureError` ?
  **HTTP 401 `{"detail": "Token has expired"}`**. Invalid signature/bad claims also
  ? 401; `HTTPBearer()` returns 403 for a missing Authorization header.
- **No refresh token, no `/auth/refresh`, no `/auth/logout`, no token revocation,
  no blacklist, no session store exists anywhere in the repository.** The JWT is
  stateless; once issued it is valid until `exp`. Confirmed by repo-wide search.

### Exact logout path (end-to-end)

1. Login/signup stores the token: `localStorage.setItem("access_token", ...)`
   (`frontend/src/app/(auth)/login/page.tsx:41`, `signup/page.tsx:110`).
2. `apiFetch` attaches `Authorization: Bearer <token>` on every authenticated
   request (`frontend/src/lib/api.ts:43-49`).
3. After 8h the token is expired. The next authenticated request � typically the
   shared SWR profile (`/api/v1/student/me`) or any revalidating resource after a
   focus/visibility return � hits the backend.
4. `get_current_user` raises 401 `Token has expired` (`deps.py:36-37`).
5. `apiFetch` receives the 401: `localStorage.removeItem("access_token")` +
   `window.location.href = "/login"` hard redirect (`api.ts:72-78`).
6. `AuthContext`'s 401/403 effect (`AuthContext.tsx:80-89`) also removes the
   token, sets `tokenStatus="absent"`, clears the cached profile; the route-guard
   effect (`AuthContext.tsx:109-121`) redirects to `/login`. **The token is
   removed in exactly two places: `api.ts:73` (on 401) and `AuthContext.tsx:84/143`
   (on 401/403 and explicit logout).**

### Expected or defect?

- **Expected behavior (B):** the 8h expiry is deliberate, documented Phase 16
  hardening ("JWT expiry bounded 8h env-configurable"), and matches the user's
  "several hours" report. No defect in the expiry path itself.
- **No premature-logout path exists in the current code:** transient network
  failures (no status) and 5xx preserve the token (hardened, unchanged);
  Render cold starts produce network errors/5xx/503, never token deletion; the
  service worker is network-only for `/api/*` (returns `503 {offline:true}` on
  failure � status present but not 401/403 ? token preserved) and is **not even
  registered at runtime** (the `useServiceWorker` hook is never mounted, a
  documented pre-existing gap) so it cannot contribute to token loss; there are
  NO timers, NO client-side `exp` checks, NO JWT decoding in the frontend; no
  `setTimeout`/`setInterval` tied to auth.
- **Multi-tab/PWA:** `localStorage` is shared across tabs. A genuine 401 in one
  tab removes the shared token, so other tabs lose the session on their next
  request � this is consistent with genuine expiry, not a premature logout.

### Classification

| Class | Finding |
|---|---|
| A. Genuine bug | **NONE FOUND.** No premature logout path exists in the committed code. |
| B. Expected behavior | The 8h JWT expiry logout itself � configured, deliberate, documented. |
| C. UX limitation | Abrupt hard redirect to `/login` at expiry with no warning/countdown/renewal. |
| D. Architectural limitation | **No refresh-token/session-renewal mechanism exists** � mandatory re-login every ~8h by design. **Refresh-token/session renewal is REQUIRED to fix the user-facing complaint.** |
| E. Unknown (needs production evidence) | Whether any user sees logout before 8h: possible contributors would be server clock skew (Render) or a changed `JWT_SECRET_KEY` (invalidates ALL tokens immediately � would log everyone out at once, not "after several hours"). Both unconfirmed; would require production logs/evidence. |

### Proposed refresh-token architecture (DESIGN ONLY � NOT IMPLEMENTED)

Safest minimal design (D-class resolution), additive and non-breaking:

- **Access token:** keep the existing `type="access"` JWT; recommended lifetime
  **30�60 minutes** (shorter exposure window) with silent renewal, or keep 8h as
  an interim fallback. Configure via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (already
  env-overridable). Verification/401 semantics in `get_current_user` unchanged.
- **Refresh token:** **opaque, DB-backed, high-entropy** (NOT a JWT) so it can be
  revoked. Lifetime **30 days absolute** (env-configurable). Issued at
  login/register alongside the access token; returned in the login response and/or
  as an `HttpOnly` + `Secure` + `SameSite=Lax/None` cookie (cross-site
  Vercel?Render means `SameSite=None; Secure` + CORS `allow_credentials=true`,
  already configured in `main.py`).
- **Storage strategy:** access token stays in `localStorage` (current behavior,
  no change to the hardened path); refresh token in an `HttpOnly` cookie to
  reduce XSS theft, with `SameSite`/`Secure` set correctly for the cross-site
  deployment.
- **Rotation/revocation:** rotating refresh tokens � every `/auth/refresh`
  validates the presented token, issues a new access + new refresh, marks the old
  one used/rotated. **Reuse detection:** if a previously-rotated/revoked refresh
  token is presented again ? revoke the user's entire token family (theft
  indicator). New table `refresh_tokens` (user_id FK, token_hash SHA-256,
  family_id, created_at, expires_at, used/revoked flags, replaced_by). Logout
  revokes all of the user's active refresh tokens.
- **Logout behavior:** `logout()` now also calls `POST /api/v1/auth/logout`
  (best-effort) to revoke refresh tokens server-side and clear the cookie, then
  preserves the existing localStorage/`tokenStatus`/cache-clear behavior.
- **Token theft considerations:** short access lifetime limits exposure;
  HttpOnly cookie reduces XSS surface; refresh rotation + family revocation
  limits replay; refresh endpoint rate-limited like login; `sub`/user
  still validated per request.
- **Multi-tab/PWA behavior:** single-flight refresh (one in-flight refresh shared
  across concurrent requests/tabs) + `storage`/`broadcast` event so one tab's
  refresh updates the others; a focus/visibility refresh before profile
  revalidation.
- **Backward compatibility:** access tokens issued before deploy remain valid
  until their 8h `exp`; `/auth/login` + `/auth/register` keep returning
  `access_token` (additive `refresh_token`/cookie); old frontend continues to
  work against the new backend (new fields ignored); new frontend gracefully
  falls back to a direct login when refresh is unavailable.
- **Production migration requirements (future):** additive Alembic migration for
  `refresh_tokens`; new `/auth/refresh` + `/auth/logout` endpoints; Render env:
  no new secret strictly required (refresh tokens are DB-random), CORS already
  credentials-enabled; Vercel/Render cookie policy verified over HTTPS.
- **Regression risks (must be respected when implemented):** 401 handling,
  JWT verification, authorization, token expiry, and transient-error handling
  must NOT be weakened; refresh must be attempted ONLY on genuine 401 (never on
  403/5xx/network), must never mask real auth failures, and must never clear the
  token on transient failures; no change to attendance calculations or schema
  beyond the additive `refresh_tokens` table; Admin Portal untouched.
- **Independence:** refresh-token/session-renewal implementation is **fully
  independent of the performance work** (SWR/cache/notification/service-worker
  phases). It touches only the auth client/endpoints + one additive table. It
  requires a separate, explicitly-authorized execution phase � NOT started.

**HARD STOP: Investigation only. No code, schema, migration, deployment, or
auth-behavior change was made.**

Targeted hotfix for the investigation above. Reused the authoritative institutional clock (`institution_today()`, Asia/Kolkata) across the student-facing read paths that were still using server-local `date.today()`:

- Extracted the helper to the lowest-level shared utility `backend/app/core/timezone.py` (`INSTITUTION_TZ` + `institution_today()`); `attendance_service.py` re-exports it (backward compatible for `notification_service`, `admin_attendance_service`, verify scripts).
- Replaced with `institution_today()`: `dashboard_service.py` (summary today, weekly range, quiz filter, upcoming events), `analytics_service.py` (as-of), `endpoints/calendar.py` (`/calendar/today`), `eligibility_service.py` (timeline commencement fallback + next-cycle filter), `attendance_service.py` (history default range_end), `laboratory_service.py` (as-of), `calendar_repo.py` (upcoming event filter).
- Circular-import handling: repositories no longer import a service module � `calendar_repo.py` imports from `app.core.timezone`; all modules import cleanly (verified).
- Boundary verified: at 31 Aug 02:27 IST, `institution_today()` = 2026-08-31, weekly week_start = 2026-08-31, week_end = 2026-09-06 (Monday-start semantics unchanged).
- Out of scope / unchanged: Admin Portal (`admin_dashboard_service.py`, `admin_dashboard_repo.py`), frozen Phase 7 eligibility engine placeholders (`eligibility_engine.py:140-141`, invalid-window only), attendance/eligibility/calendar/event math, schemas, DB, migrations, auth/JWT, SWR/cache, all frontend date handling, GreetingHeader.
- Verification: `compileall` PASS on backend app; all 8 changed modules import without circular-import errors; py_compile PASS. No DB-touching verifier run (quota-efficient static verification only). No commit/push/deploy.

---

## Investigation: Student Portal Content-Load Performance (2026-09-02)

**Status: INVESTIGATION COMPLETE � NO CODE CHANGES MADE.** Static code + query
analysis only; no browser/E2E automation, no backend/frontend/schema/migration/
deployment modification. Follow-up to the Phases A�E performance work
(committed `2c90240`). The observed symptom persists: **the app shell loads
quickly, but dashboard content appears much later** (worst on the deployed PWA
on mobile).

### 1. What fires on dashboard load (exact request set)

After hydration, the dashboard route mounts exactly **four** authenticated API
requests, all client-side (SWR), all issued in parallel:

| Request | SWR policy | Blocks visible content? |
|---|---|---|
| `GET /api/v1/student/me` | INTERACTIVE (shared PROFILE_KEY, deduped with AuthContext) | No � skeleton only (greeting, avatar, nav role) |
| `GET /api/v1/dashboard/summary` | DASHBOARD (focus-revalidate, 120 s dedupe) | **YES � ALL 6 cards** (page renders skeletons until `summary` arrives) |
| `GET /api/v1/analytics/overview` | SEMI_STATIC (no focus revalidate, 5 min dedupe) | No � cards degrade gracefully (forecast/weekly series enrich only) |
| `GET /api/v1/notifications` | STANDARD (focus-revalidate; backend 60 s TTL cache) | No � bell badge only |

**Critical path = `/api/v1/dashboard/summary` alone.** Every other request is
non-blocking decoration. The dashboard page (`frontend/src/app/(authenticated)/dashboard/page.tsx`)
renders the entire card grid behind `isLoading || !summary`.

### 2. Request waterfall (measured by code trace, not instrumentation)

```text
Shell (static HTML + client JS from Vercel edge, fast)
  ? hydration (App Router, client component)
  ? token read (AuthContext: localStorage, one-time)
  ? four parallel fetches against the SINGLE uvicorn worker:
  /student/me          ~9 light queries      (profile/context resolution)
  /notifications       ~12 queries + N upserts/commits  (badge; backend 60s TTL)
  /analytics/overview  ~9 queries incl. 2 heavy range scans (duplicated work)
  /dashboard/summary   ~15 queries + 2N window scans + 3 full event scans  ? BLOCKS CONTENT
  ? cards render only after /dashboard/summary returns
```

### 3. Backend query trace per endpoint

**`/student/me`** (~9 queries, all light, none heavy):
JWT decode ? `get_current_user` (User + section, 1 query) ?
`StudentContextService.get_context`: placement (?4 point lookups: Section,
Semester, AcademicSession, Subsection), enrollments (1), elective choices
(1 + 1 catalog query), first quiz date (1). Not a bottleneck.

**`/dashboard/summary`** (~15 fixed + 2N queries; N = quiz-applicable subjects;
?31 queries for a typical N=8):
- `get_current_user` (1), `get_enrolled_subjects` (1), placement (?4)
- `get_sessions_with_status(user, semester_start?today)` � **1 heavy 6-table
  join range scan** (class_sessions � timetable_entries � elective choices �
  occurrence_outcomes � subjects � enrollments � attendance_records); no
  index on `class_sessions.date` ? sequential scan
- `get_subject_summaries` ? `get_subject_counts_for_user` � **1 more heavy
  full-semester scan**, same joins (2nd scan)
- `get_mid_sem_sessions` (1)
- `_build_today` ? `get_day_schedule` ? `get_all_events` � **full table scan
  of academic_events (no filter!)**
- `_build_quiz_snapshot` ? `chosen_elective_map` (1) +
  `get_effective_quiz_dates_for_subjects` (1) + `get_quiz_cycle_with_policy` (1)
  ? `get_quiz_eligibility_for_subjects`:
  - re-fetches `get_quiz_cycle_with_policy` (**duplicate**)
  - re-fetches `get_all_events` (**duplicate full scan**)
  - re-fetches `chosen_elective_map` (**duplicate**)
  - re-fetches `get_effective_quiz_dates_for_subjects` (**duplicate**)
  - per subject: `_evaluate_subject` ? **2� `get_subject_counts_between`
    (window + cumulative) � 2N additional heavy 6-table scans**
- `_build_upcoming_events` ? `load_choices` (**duplicate**) +
  `anchor_subjects` ? `get_all_subjects` (full scan) +
  `get_all_events` (**3rd full scan of academic_events**)

**`/analytics/overview`** (~9 queries):
placement (?4), `get_sessions_with_status` (**duplicate of dashboard's heavy
scan**), `get_enrolled_subjects` (duplicate), `get_subject_summaries` ?
`get_subject_counts_for_user` (**duplicate of dashboard's heavy scan**) +
`get_mid_sem_sessions` (duplicate). **Entirely overlapping work with
`/dashboard/summary`.**

**`/notifications`** on cache miss (~12 + N queries, **N sequential
upserts each with its own COMMIT**):
`get_current_user` (1), `get_enrolled_subjects` (1), preferences (1),
class reminders (1 heavy scan IF enabled � default off), quiz approaching ?
`get_current_quiz_cycle` (re-fetches enrolled subjects, elective map, quiz
dates, cycle policy), `_attendance_items` ? `get_subject_summaries` ?
`get_subject_counts_for_user` (**3rd heavy scan of the semester**) +
mid-sem (1), `_academic_events` ? `load_choices` (1) + `anchor_subjects`
(full subjects scan) + `get_all_events` (full scan), then **N upserts, each
committing separately** (N round trips), then inbox (1) + unread count (1).

### 4. Root-cause summary

**A. Frontend waterfall � MINOR.** Requests are already parallel and correctly
policied; profile/notifications/analytics do not block content. The only
blocking dependency is `summary` for the card grid, which is inherent to the
page design. Hydration is client-side (all pages are `"use client"`), so
content always waits for a full network round trip � no SSR/streaming.

**B. Backend computation � MAJOR.** The same expensive work is repeated
across the four parallel requests AND inside `/dashboard/summary` itself:
- 5+ heavy 6-table range scans per dashboard load (dashboard �2, analytics �2,
  notifications �1) where 1 would suffice
- 2N quiz-window scans inside dashboard summary (eligibility re-scans the
  semester per subject, per window)
- `get_all_events` full-table scan executed **4�** per cold load (dashboard �3,
  notifications �1) � never filtered at the source
- quiz cycle policy / elective map / quiz dates fetched **2�** within one request
- notifications: N sequential upsert+commit round trips

**C. Database/query latency � MODERATE.** No index on
`class_sessions.date` / `(subject_id, date)` ? every range query is a
sequential scan; many small queries (?55�70 per cold dashboard load) each pay
a Supabase-pooler round trip (~5�30 ms each); single uvicorn worker
(`UVICORN_WORKERS=1`) serializes the Python CPU portions of all four
concurrent requests on 0.1 CPU.

**D. Render infrastructure/cold start � MAJOR for FIRST load only.** Render
Free spins down after ~15 min idle; first request after idle pays 30�60 s of
container boot + Python import before ANY query runs. This is the dominant
"first open of the day" cost, but it does NOT explain warm reloads.

**E. PWA/service-worker � MINOR.** The service worker is NOT registered at
runtime (`useServiceWorker` never mounted � pre-existing, documented in
Phase D); it neither helps nor hurts warm load. Phase C policies already
prevent focus refetch storms. Mobile simply amplifies every backend round
trip (cellular RTT).

**F. Combination � the actual observed behavior.** "Shell fast, content slow"
= static shell (fast) + one heavy blocking endpoint (`/dashboard/summary`)
executing ~31 queries on a 0.1-CPU single worker over a poolered connection,
optionally preceded by a Render cold start. Warm latency of summary is
estimated ~1�2 s (30 queries � 5�30 ms + Python grouping/serialization);
cold latency is 30�60 s+. Analytics adds ~1 s of parallel non-blocking work;
notifications ~1�2 s on cache miss.

### 5. Optimization plan (ordered by impact � risk; NOT executed)

1. **Deduplicate queries inside `/dashboard/summary` (HIGH impact, LOW risk,
   behavior-neutral).** Fetch `get_all_events` once and reuse for day
   schedule + eligibility windows + upcoming events; fetch cycle policy /
   elective map / quiz dates once. Cuts ~8 queries and 2�3 full scans with
   zero semantic change. Files: `dashboard_service.py`.
2. **Share the semester scan across summary + analytics (HIGH impact,
   MEDIUM risk).** Compute analytics overview fields from the same
   enrollment-scoped scan already used by the dashboard (or a small TTL cache
   keyed by user, mirroring the Phase B notification pattern). Removes 2 heavy
   scans per load. Files: `dashboard_service.py`, `analytics_service.py`.
3. **Eliminate 2N quiz-window scans (HIGH impact, MEDIUM risk).** Bucket the
   existing per-subject counts in memory per quiz window (window start/end are
   already computed by the calendar engine) instead of re-running
   `get_subject_counts_between` per subject per window; preserve
   `exclude_quiz_day` + cancellation semantics exactly. Files:
   `eligibility_service.py`, `attendance_service.py`, `dashboard_service.py`.
4. **Batch notification upserts into ONE transaction (MEDIUM impact, LOW
   risk).** N sequential commits ? 1 commit. Files:
   `notification_service.py`, `notification_repo.py`.
5. **Filter `get_all_events` at the source (LOW-MEDIUM impact, LOW risk).**
   Pass `active=True, date_from, date_to` from dashboard/notifications instead
   of loading the full table 4� per load. Files: `calendar_repo.py`,
   `dashboard_service.py`, `notification_service.py`.
6. **Defer non-blocking requests off the critical path (LOW-MEDIUM impact,
   LOW risk).** Notifications bell fetch and analytics overview already render
   non-blocking; optionally lazy-mount analytics after summary renders.
   Files: `dashboard/page.tsx`, `NotificationBell.tsx`.
7. **DB indexes on `class_sessions(date)` / `(subject_id, date)` and
   `academic_events(start_date)` (MEDIUM impact, LOW risk).** Requires a new
   Alembic migration � **EXCLUDED by this phase's constraints** (no DB schema /
   migration changes); listed as the natural follow-up execution phase.
8. **Optional infra follow-up (EXCLUDED here):** `pool_pre_ping=True`,
   pool-size tuning, direct-Supabase vs pooler trade-offs � production
   infrastructure configuration, out of scope.

### 6. What can run in parallel

All of 1, 4, 5, 6 are independent and parallelizable immediately. Items 2 and
3 build on 1 (they deduplicate the same scan family) and are parallelizable
with 4/5/6. Item 7 requires its own authorized execution (migration).
Item 2 and 3 must each preserve exact engine semantics (verified by the
existing verifiers).

### 7. Regression risks (when implemented)

- Item 3 must reproduce `BETWEEN` window bounds, `exclude_quiz_day`, cancelled-
  exclusion, and practical-block collapse byte-for-byte (eligibility verifiers
  are the guard).
- Item 2 must keep analytics/dashboard byte-identical to the canonical
  attendance engine (Phase 8.0 contract).
- Item 4 must preserve upsert idempotency and the returned row id.
- Any backend TTL cache must stay per-user (never cross-user) and invalidate
  on attendance mutations.
- None of the above touch auth/JWT, attendance mathematics, elective
  resolution, Admin Portal, schema, or migrations.

**HARD STOP: Investigation only. No code, schema, migration, deployment, or
infrastructure change was made.**


---

# Phase 25 -- Session Renewal (Refresh Tokens)

Resolves the confirmed architectural limitation from the 2026-09-02 auto-logout investigation (mandatory re-login every ~8h; no refresh mechanism existed). Additive only; PostgreSQL + JWT remains authoritative; Firebase stays retired.

- **25.1 Backend refresh-token infrastructure COMPLETE (2026-09-02)** -- additive migration `a9b8c7d6e5f4` (single Alembic head chaining `c4d5e6f7a8b9`): `refresh_tokens` table (`user_id` FK, UNIQUE SHA-256 `token_hash` -- raw secret never persisted, `family_id`, `expires_at`, `is_used`/`is_revoked`, `replaced_by` link, family/user revocation indexes). Opaque CSPRNG refresh secrets (never JWTs); SHA-256 hash lookup; ~30-day config-driven expiry; `POST /api/v1/auth/refresh` (rotation + reuse detection -> family revocation on reuse; generic-401, rate-limited) and `POST /api/v1/auth/logout` (idempotent family revocation + cookie clear); login/register mint a family and set an HttpOnly + Secure + SameSite=None cookie scoped to `Path=/api/v1/auth` with the JSON login/register contract unchanged. Rotation is concurrency-safe (`SELECT ... FOR UPDATE` + single atomic commit; simultaneous refreshes serialize, the loser takes the reuse path). Access-JWT contract, localStorage access-token support, 401/403 semantics, transient-error handling, attendance/eligibility/calendar, Admin Portal: untouched. Verified: `compileall` PASS; single head `a9b8c7d6e5f4` + offline `--sql` upgrade/downgrade validated; app import + 4 auth routes registered; `verify_phase_25_1.py` **50/50 PASS**. Migration NOT applied anywhere yet (dev Docker down this session; operator boundary for production). No commit. **Frontend refresh interceptor NOT implemented (25.2, next).**
- **25.2 Frontend refresh integration COMPLETE (2026-09-02)** -- `apiFetch` now intercepts genuine 401s ONLY (never 403/5xx/network/timeout) and performs ONE single-flight `POST /api/v1/auth/refresh` with `credentials: 'include'` (module-level shared promise; all concurrent 401s await it, then retry their original request exactly once -- no refresh storm, no loop). Success stores the new access token via the existing localStorage architecture; permanent refresh failure (401 on refresh) falls through to the existing 401 handler (clear token + redirect); transient refresh network failure throws a status-less error so AuthContext keeps the session and SWR retries on focus (transient-failure preservation intact). Multi-tab: localStorage is the shared token bus + a `storage` event listener re-syncs `tokenStatus` across tabs/PWA contexts (no state rewrite). Logout best-effort fires `POST /api/v1/auth/logout` (`credentials: 'include'`) then immediately clears local state -- usable with backend down, missing cookie, or revoked session. Login/signup: `credentials: 'include'` added to the auth POSTs so the cross-origin browser stores the HttpOnly refresh cookie; JSON contract, localStorage handling, refreshUser flow unchanged. Hydration/route guards/self-healing/401-403 semantics preserved; no /student/me transient-failure logout regression. Verified: `tsc --noEmit` PASS, `npm run build` (CI placeholder URL) PASS (25/25 pages), ESLint ZERO new errors (5 pre-existing in frozen files). No migration/schema/CORS change, no commit.
- **25.3 Production rollout** -- operator-gated: apply migration to dev/prod; optionally shorten `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` after 25.2 is live.


- **25.2 Frontend refresh integration COMPLETE (2026-09-02)** -- `apiFetch` now intercepts genuine 401s (never 403/5xx/network/timeout/arbitrary errors) and performs ONE single-flight `POST /api/v1/auth/refresh` with `credentials: 'include'` (shared module-level promise; all concurrent 401s await the same refresh, then retry their original request exactly once with the new access token -- no refresh storm, no infinite loop). Refresh success stores the new access token via the EXISTING localStorage architecture and retries the original request once; a second 401 after a fresh token falls through to the genuine-auth-failure path (clear token + redirect). Refresh 401 (permanent) clears auth and redirects via the existing 401 handler; refresh NETWORK failure (transient) throws a status-less error so AuthContext does NOT clear the session -- SWR retries on focus/visibility (transient-failure preservation intact). Multi-tab: localStorage is the shared token bus (apiFetch reads it fresh per request); AuthContext adds a `storage` event listener so other tabs/PWA contexts re-sync tokenStatus on refresh/logout without a state-management rewrite. Logout now best-effort fires `POST /api/v1/auth/logout` with `credentials: 'include'` (revokes the refresh family server-side, clears the HttpOnly cookie) while IMMEDIATELY clearing local state -- works when backend is down, cookie is missing, or session is already revoked. Login/signup: added `credentials: 'include'` to the auth POSTs so the cross-origin browser stores the HttpOnly refresh cookie (Set-Cookie on login/register responses); JSON contract, localStorage token handling, and refreshUser flow unchanged. AuthContext hydration/unknown-present-absent semantics, route guards, self-healing focus retry, and explicit logout behavior preserved; the /student/me transient-failure logout bug is not reintroduced. Verified: `npx tsc --noEmit` PASS, `npm run build` (with CI placeholder `NEXT_PUBLIC_API_URL`) PASS -- compiled successfully, 25/25 pages, ESLint unchanged (5 pre-existing errors in frozen files; ZERO new). No migration, no schema, no CORS/deployment change, no commit.


- **25.2 Frontend refresh integration COMPLETE (2026-09-02)** -- `apiFetch` now intercepts genuine 401s (never 403/5xx/network/timeout/arbitrary errors) and performs ONE single-flight `POST /api/v1/auth/refresh` with `credentials: 'include'` (shared module-level promise; all concurrent 401s await the same refresh, then retry their original request exactly once with the new access token -- no refresh storm, no infinite loop). Refresh success stores the new access token via the EXISTING localStorage architecture and retries the original request once; a second 401 after a fresh token falls through to the genuine-auth-failure path (clear token + redirect). Refresh 401 (permanent) clears auth and redirects via the existing 401 handler; refresh NETWORK failure (transient) throws a status-less error so AuthContext does NOT clear the session -- SWR retries on focus/visibility (transient-failure preservation intact). Multi-tab: localStorage is the shared token bus (apiFetch reads it fresh per request); AuthContext adds a `storage` event listener so other tabs/PWA contexts re-sync tokenStatus on refresh/logout without a state-management rewrite. Logout now best-effort fires `POST /api/v1/auth/logout` with `credentials: 'include'` (revokes the refresh family server-side, clears the HttpOnly cookie) while IMMEDIATELY clearing local state -- works when backend is down, cookie is missing, or session is already revoked. Login/signup: added `credentials: 'include'` to the auth POSTs so the cross-origin browser stores the HttpOnly refresh cookie (Set-Cookie on login/register responses); JSON contract, localStorage token handling, and refreshUser flow unchanged. AuthContext hydration/unknown-present-absent semantics, route guards, self-healing focus retry, and explicit logout behavior preserved; the /student/me transient-failure logout bug is not reintroduced. Verified: `npx tsc --noEmit` PASS, `npm run build` (with CI placeholder `NEXT_PUBLIC_API_URL`) PASS -- compiled successfully, 25/25 pages, ESLint unchanged (5 pre-existing errors in frozen files; ZERO new). No migration, no schema, no CORS/deployment change, no commit.


- **26.1 Dashboard summary query deduplication COMPLETE (2026-09-02)** -- optimization #1 from the performance investigation: `/dashboard/summary` now fetches each request-scoped dataset ONCE and reuses it in memory across all builders, instead of letting each builder (and the eligibility/calendar services beneath them) re-fetch the same rows. Datasets consolidated: `get_all_events` (was 3 fetches -> 1), `get_quiz_cycle_with_policy` (2 -> 1), elective choices/`load_choices` (2-3 -> 1), `get_effective_quiz_dates_for_subjects` (2 -> 1). Total ~6 queries saved per summary request; the 2N quiz-window scans (optimization #3) remain intentionally untouched. Implemented by: pre-fetching in `DashboardService.get_summary` and threading results into `_build_today`, `_build_quiz_snapshot`, `_build_upcoming_events`; additive optional parameters on `CalendarService.get_day_schedule` and `EligibilityService.get_quiz_eligibility_for_subjects` that default to `None` (fetch) for non-dashboard callers. Behavioral preservation: same queries, same ordering, same filters, same engine path — the fetched data is byte-identical. Verified: `compileall` PASS, full app import PASS, `verify_phase_25_4.py` **25/25 PASS** (call-site counts vs HEAD, guard-pattern analysis, data-threading assertions, scope guard). No schema, migration, engine, frontend, auth, or API contract change. No commit.


- **26.3 Quiz-window 2N scan elimination COMPLETE (2026-09-02)** -- optimization #3 from the performance investigation: `/dashboard/summary`'s quiz-snapshot section previously issued **2N per-subject database scans** for N quiz-applicable subjects (cycle window + cumulative window, each via `get_subject_counts_between`). Replaced by computing per-subject windows via the canonical calendar engine once (in-memory, same function calls), loading ALL matching sessions for milestone-resolved subjects in **ONE date-bounded scan** (`get_subject_counts_between_for_subjects`), then bucketing per (subject, window) + practical-collapsing in memory via `collapse_count_rows` -- every row for a (subject, window) is byte-identical to the per-subject query's rows. The single-subject `get_quiz_eligibility` endpoint path is untouched (defaults to the existing per-subject scans). Files: `attendance_repo.py` (new bulk method), `eligibility_service.py` (shared `_build_domain_subject`, `_quiz_window_counts_by_subject`, `_bucket_window_counts`, `_evaluate_subject` optional counts). Verified: compileall PASS, full app import PASS, `verify_phase_26_3.py` 27/27 PASS. No schema, migration, engine, frontend, auth, or API contract change. No commit.


- **26.5 Event source filtering COMPLETE (2026-09-02)** -- optimization #5 from the performance investigation: the dashboard summary's event fetch no longer performs an unfiltered full-table scan. `/dashboard/summary` now calls `get_all_events(active=True, date_from=floor)` where `floor = min(semester_start, today)` -- the earliest date any dashboard consumer can reference (day schedule needs events covering `today`; eligibility windows start at commencement; upcoming events require `end_date >= today`). The repository's existing range-overlap semantics (`end_date >= date_from`) keep events that SPAN the semester boundary, and inactive events are excluded at the source (no consumer uses them -- calendar/eligibility engines and the upcoming builder all filter `active` in memory). Behavior preserved: event inclusion/exclusion, date boundaries, event types, ordering (start_date), user relevance (subject/elective filtering stays in-memory), calendar/dashboard responses unchanged. Only `dashboard_service.py` changed; repo already supported the filters. Callers outside the dashboard (calendar endpoint, eligibility single-subject endpoint, notification service) fetch their own events unchanged. Verified: compileall PASS, app import PASS, `verify_phase_26_5.py` 17/17 PASS. No schema, migration, index, engine, frontend, auth, or API contract change. No commit.
- **26.7 Local launcher env hardening COMPLETE (2026-09-02)** -- PERMANENT fix for the recurring `InvalidRequestError: The asyncio extension requires an async driver to be used. The loaded 'psycopg2' is not async.` at `backend/app/db/session.py:4`. Root cause (final, proven): a stale **process-level** `DATABASE_URI` environment variable (bare Supabase `postgresql://postgres.zwkdiervvtjalaazscdv:...@aws-0-ap-south-1.pooler.supabase.com:5432/postgres`) was baked into the environment block of the long-lived terminal/IDE process tree. The earlier registry cleanup (HKCU/HKLM) was correct but INSUFFICIENT: removing a persistent env var does NOT mutate the in-memory environment block of already-running processes -- every child they spawn (including `Start-Process` from `start-dev.ps1`, and even fresh `-NoProfile` shells) inherits the stale value. pydantic-settings precedence (env vars > `.env` file > defaults) then let the bare `postgresql://` URL win over `backend/.env`'s correct `postgresql+asyncpg://` URL, routing SQLAlchemy to the sync `psycopg2` dialect. Fix (smallest, launcher-scoped, no app-level URL normalization): `start-dev.ps1` now strips any inherited `DATABASE_URI` from the backend child process's environment immediately before `Start-Process` and restores it afterward, so the backend always resolves the intended local asyncpg config from `backend/.env`. Also restored the UTF-8 BOM on `start-dev.ps1` (a BOM-less edit had made PS 5.1 mis-parse the file's box-drawing characters). Verified LIVE: with the stale env var present in the launching shell, `.\start-dev.ps1` launched the backend, port 8080 listening, `GET /` ? HTTP 200 `{"message":"AttendanceDash Pro API is running."}`, `backend_err.log` clean (no psycopg2 error); direct check with env stripped resolves `postgresql+asyncpg` / localhost:55432 / attendancedash. No schema, migration, engine, frontend, auth, or API contract change. No commit.
- **26.8 Login "Unable to reach the server" fix COMPLETE (2026-09-02)** -- login at `POST /api/v1/auth/login` failed with 500 `relation "refresh_tokens" does not exist`. Root cause (proven from runtime evidence): the local dev database (`attendancedashpro_db`, port 55432) was at Alembic revision `c4d5e6f7a8b9`, NOT at head `a9b8c7d6e5f4` -- the Phase 25.1 migration `a9b8c7d6e5f4` (add_refresh_tokens) had never been applied to the local DB (the earlier "successfully applied" claim likely referred to a different database, possibly the Supabase production DB via the stale `DATABASE_URI` documented in 26.7). The login endpoint (`auth.py:124`) calls `RefreshTokenService.issue()` on every successful login, which INSERTs into `refresh_tokens`; without the table every login returned 500. CORS was confirmed correct (OPTIONS 200 with `access-control-allow-origin: http://localhost:3100`, credentials true; POST returned 500 with full CORS headers). Fix: ran `alembic upgrade head` against the local dev DB (stale `DATABASE_URI` env var removed first so the migration could not be redirected to production). Verified: `alembic current` = `a9b8c7d6e5f4 (head)`; `refresh_tokens` table exists; `POST /api/v1/auth/login` with bad credentials now returns 401 `{"detail":"Incorrect roll number or password"}` (not 500); backend health 200. No application code changed. No commit.
