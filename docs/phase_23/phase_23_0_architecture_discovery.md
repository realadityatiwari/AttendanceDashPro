# Phase 23.0 — Architecture Discovery & Implementation Blueprint

**Date:** 2026-08-27 (initial discovery); 2026-08-27 (reconciliation)
**Status:** READ-ONLY DISCOVERY COMPLETE + BLUEPRINT RECONCILIATION — no code, no schema, no migration, no seed, no UI, no auth, no production data touched. No commit, no push, no PR.
**Scope:** Deep repository-grounded investigation producing the exact blueprint used to implement Phase 23.1 onward. This document is the authoritative discovery report.

---

## 0. Correction Reconciliation (2026-08-27)

The core findings were accepted; ten corrections were applied to the blueprint.
This section records each correction and how the report was updated. The
corrections constrain Phase 23.1 and the full Phase 23.x sequence.

| # | Correction | Applied where | Effect on blueprint |
|---|---|---|---|
| 1 | Separate academic model from admin authorization | §21, §22, §31, §33, §34, §36, §37 | `admin_scopes`/role schema moved OUT of 23.1 and fully into 23.9. 23.1 is academic hierarchy/data foundation only. 23.1 may document the future authorization dependency but must not implement it. |
| 2 | Fix the production migration model | §31, §32, §34, §36 | Each schema-changing phase carries its own discovery/design → offline validation → local/dev migration → verification → explicit operator boundary → production migration only when separately authorized → read-only post-production verification. 23.10 is the final Phase-23 migration reconciliation/rollout/closure, NOT the first production migration point. |
| 3 | Explicitly separate OCCURRENCE from OUTCOME | §19, §25, §26, §28, §34 | Canonical terminology fixed as: EXPECTED TIMETABLE → CLASS SESSION / OCCURRENCE → COHORT/SUBJECT-SPECIFIC OUTCOME OR OVERRIDE → resolved student-facing reality. The critical example (BCS-058 → Surprise Quiz; BCS-055 → Normal Lecture; BCS-056 → Cancelled on the same date/time/slot) remains representable WITHOUT per-student timetable/session duplication. `occurrence_outcomes` stays the minimal candidate, NOT finalized until the phase designs it. |
| 4 | Remove ambiguous `CLASS` event scope | §22, §26, §31, §36 | The undefined `CLASS` scope is removed from the blueprint. Event scope enumeration is NOT implemented until scope semantics are defined by the 23.1 hierarchy. Proposed explicit terms (GLOBAL / SECTION / SUBSECTION / SUBJECT / ELECTIVE_SLOT) are documented as pending, not authoritative. Admin role naming uses explicit SECTION_ADMIN (not ambiguous "CLASS_ADMIN"). |
| 5 | Mark hypothetical examples as hypothetical | §14, §15, §21, §25, §36 | Subsection examples (`CS-5A` → `51`/`52`) are explicitly labelled conceptual examples only. The current CTT is authoritative for B.Tech III Year (V Semester), CSE-51 only. No subsection name is treated as an established academic fact without an authoritative source or existing production data. |
| 6 | Resolve `AcademicSession` vs `Academic Year` | §3, §21, §36 | Repository evidence strongly establishes `AcademicSession` (name unique e.g. "2026-27", start/end, is_active) as the existing academic-year/session entity, with `Semester.session_id` referencing it. No second year/session entity is proposed. 23.1 must confirm this interpretation before schema implementation; absent contradictory evidence, `AcademicSession` remains canonical. |
| 7 | Do not assume Branch parentage | §3, §21, §33, §36 | The current model has NO Branch entity — `Section.program` (e.g. "CSE") is an attribute, and the chain is AcademicSession → Semester → Section(program) → User/Subject. Whether Branch becomes a separate entity (and whether Semester is shared across branches) is an OPEN decision to be settled by evidence in 23.1, NOT assumed from the roadmap. |
| 8 | Resolve `student_enrollments` uniqueness semantics | §21, §28, §36 | No unique constraint is added blindly. The correct key (student+semester / student+subject / student+semester+subject) must preserve multi-semester historical correctness. If unresolved, the decision is an explicit gate instead of a guessed constraint. |
| 9 | Preserve legacy unknown state | §21, §32, §36 | Existing students without authoritative subsection/elective/branch assignment remain explicitly UNASSIGNED/UNKNOWN. Nothing is fabricated. Backfill/remediation is a documented future controlled operation, not an automatic step. |
| 10 | Hard boundary for Phase 23.1 | §34, §37 | 23.1 is schema/data-model foundation ONLY. It does NOT wire timetable resolution, synchronizer, attendance, Track, History, Dashboard, quiz eligibility, events, registration, frontend academic selection, or admin authorization. Those belong to later Phase 23 slices. |

The remainder of this report reflects these corrections. Where a section still
describes a candidate (not finalized) design, it is explicitly labelled.

---

## 1. Executive Summary

AttendanceDashPro is a live production application (Vercel Hobby + Render Free + Supabase Free PostgreSQL, FastAPI + PostgreSQL + JWT + Next.js). It currently models **one academic session → one semester → one section (CSE-51) → one class**, and Phase 22.3/22.4 introduced the **first version of departmental-elective resolution** (two logical slots `ELECTIVE_I` / `ELECTIVE_II`, a per-student `student_elective_choices` table, an authoritative `ElectiveResolver`, and `elective_slot` marker columns on `timetable_entries`, `class_sessions`, `quiz_schedules`, and `academic_events`).

The operator requirements describe a **TARGET academic hierarchy** (conceptual,
not yet established in the model): Branch → Semester → Section (max 60 students)
→ Subsection (≈30 students), plus the full B.Tech CSE elective catalog
(Elective-I: BCS-052/053/054; Elective-II: BCS-055/056/058), and the eventual
**Admin Portal as the authoritative control plane**. **Branch parentage is a
23.1 DECISION GATE — the current model has NO Branch entity (`Section.program`
is a string attribute); whether Branch becomes a separate entity, whether
Semester is shared across branches, and where curriculum belongs must be
decided by evidence in 23.1.** See §3 (current), §21 (candidate model), §36
(gate).

The central architectural finding of this phase: **the current architecture conflates the CLASS SESSION / OCCURRENCE layer with the COHORT/SUBJECT-SPECIFIC OUTCOME OR OVERRIDE layer** — the three-layer model (EXPECTED TIMETABLE → CLASS SESSION/OCCURRENCE → COHORT/SUBJECT-SPECIFIC OUTCOME → resolved student-facing reality, see §25) is not fully representable. Phase 22.4 solved slot→subject resolution *at read time* by marking slots, but the **class_sessions pipeline has no concept of a per-cohort "actual outcome/override"** that differs by subsection or by elective cohort, and **events are one shared row per date/type** with no ability to express different outcomes for different cohorts on the same date/time (e.g. BCS-058 → Surprise Quiz, BCS-055 → Normal Lecture, BCS-056 → Cancelled on the same date/time/slot).

Additionally, the architecture has **no Subsection concept at all**, **no Section-level admin scoping**, **no multi-section registration**, **no per-semester section sets**, and **many single-semester/single-section assumptions** (mostly in seed/verifier/engine constants rather than in the core ORM, which is already session-scoped).

This phase produces the full blueprint: a migration-safe, additive path that preserves all production data, UUIDs, timestamps, and FK integrity, ordered into logical implementation phases (23.1…23.10) with a recommended phase order that differs from the sketch in the task brief because repository evidence shows the correct sequencing. The blueprint was reconciled on 2026-08-27 per ten corrections (§0) — most importantly: 23.1 is schema/data-model foundation ONLY (no admin-authorization schema, no consumer wiring), each schema-changing phase ships its own operator-bound migration lifecycle (23.10 is final reconciliation, not the first production migration point), and the occurrence-vs-outcome terminology is fixed (§25).

---

## 2. Current Architecture

```
Vercel (Next.js 16 SSR, PWA)
        ↓  HTTPS /api/*
Render (FastAPI, Docker, uvicorn)
        ↓  asyncpg
Supabase Free PostgreSQL (18 tables)
```

Layering (governance Rule 1): `API endpoints → Services → Engines → Repositories → Database`. `Engines` are pure, frozen, formula-owning modules (`attendance_engine`, `eligibility_engine`, `calendar_engine`, `practical_occurrence`). Services consume engines and compose read models. Repositories are the only DB access layer. The frontend is presentation-only (reads backend read models; no React-side business math — a frozen architectural rule).

### Current API surface (14 routers)
- `/api/v1/auth` (login, register)
- `/api/v1/student` (me, sync, preferences)
- `/api/v1/subjects`
- `/api/v1/timetable`
- `/api/v1/attendance` (daily, history, summary, mutation)
- `/api/v1/quiz-eligibility` (per subject/cycle, current-cycle)
- `/api/v1/calendar` (month, today, date)
- `/api/v1/events` (list + admin mutation)
- `/api/v1/laboratory` (summary, experiments, records, activity, mid-sem)
- `/api/v1/dashboard` (summary)
- `/api/v1/analytics` (overview)
- `/api/v1/feedback` (student POST + admin GET)
- `/api/v1/notifications` (inbox + PATCH)

### Authorization model today
Single binary `UserRole` enum (`STUDENT` / `ADMIN`). `require_admin` dependency → 403 for non-ADMIN. Role resolved from the DB per request (never JWT). `provision_admin.py` grants ADMIN. No scoping of ADMIN by section/subsection/subject. Registration is single-section auto-assign.

---

## 3. Current Academic Data Model

The ORM already models the expected hierarchy at the session→semester→section→subject level, but **Subsection does not exist** and **Branch is not a separate entity — Section.program is an attribute**:

```
AcademicSession (unique name, start/end, is_active)
  └── Semester (session_id FK, start/end)
        ├── Subject (code [indexed, NOT unique], tag, category, quiz_applicable,
        │            attendance_applicable, semester_id FK)
        ├── Section (name unique, program[string] e.g. "CSE", semester_id FK)
        │     └── User (roll_number unique, role, section_id FK nullable)
        │     └── TimetableEntry (subject_id FK, day_of_week 0=Mon..6, start/end,
        │                         class_type, section_id FK NOT NULL [22.1],
        │                         elective_slot nullable [22.3])
        ├── StudentEnrollment (user_id FK, subject_id FK) — no unique constraint
        ├── StudentElectiveChoice (user_id FK, elective_slot, subject_id FK,
        │                          UNIQUE(user_id, elective_slot) [22.3])
        ├── QuizCycle (cycle_number unique) + EligibilityPolicy (lecture_threshold)
        ├── QuizSchedule (subject_id FK, quiz_cycle_id FK, elective_slot nullable
        │                 [22.4], date, schedule_status)
        ├── LaboratoryExperiment / LaboratoryRecord
        └── AcademicEvent (event_type, start/end, subject_id nullable,
                           elective_slot nullable [22.4], class_type, note, active)
```

Key observations (all evidence-backed):
- **Repository evidence strongly establishes `AcademicSession` as the existing academic-year/session entity.** Evidence: `name` is unique (e.g. "2026-27"), `start_date`, `end_date`, `is_active`. `Semester` (e.g. "V Semester") has `session_id` FK → AcademicSession. **No second year/session entity is proposed.** 23.1 must confirm this interpretation before schema implementation; absent contradictory evidence, `AcademicSession` remains canonical. (Correction 6 applied.)
- **Branch is NOT a separate entity (CURRENT MODEL).** The current model has `Section.program` as a string attribute (e.g. "CSE"). The current chain is `AcademicSession → Semester → Section(program) → User/Subject`. **Whether Branch becomes a separate entity above Section, whether Semester is shared across branches, and where curriculum belongs is a 23.1 DECISION GATE to be settled by evidence — NOT assumed from the roadmap.** (Correction 7 applied.)
- `Section.name` is globally unique (`sections.name` unique index) — this must be relaxed for multi-semester/multi-branch operation (Correction 5: section names like "CS-5A" are conceptual examples; the current production section is "CSE-51").
- `Subject.code` is indexed but NOT unique; subjects are scoped to `semester_id`. Good for cross-semester code reuse.
- `TimetableEntry.section_id` is NOT NULL (Phase 22.1). There is **no subsection column** and no way to express a per-subsection timetable.
- `users.section_id` is nullable (legacy users), and the academic context chain is: `User.section_id → Section → Semester → AcademicSession`.
- `StudentEnrollment` has **no DB unique constraint** `(user_id, subject_id)` — dedup is enforced at service level only. The correct uniqueness key is unresolved (Correction 8): the choice between `(user_id, subject_id)`, `(user_id, subject_id, semester_id)`, or `(user_id, semester_id)` must preserve multi-semester historical correctness. This is an explicit decision gate, not a blind constraint addition.

---

## 4. Current Timetable Model

- `TimetableEntry`: one row per (section, subject, day_of_week, start_time, end_time, class_type), with optional `elective_slot`.
- Timetable is **weekly-recurring** and **section-scoped** (`TimetableRepository.get_weekly_entries_for_section(section_id)`).
- `class_sessions` is the **materialized** occurrence table: `expand_baseline.py` expands the weekly timetable into dated `ClassSession` rows over the semester span (2026-07-15 → 2026-12-31), and the `EventSessionSynchronizer` reconciles it against events.
- Elective slots: the timetable carries the **anchor subject** (BCS-054 for Elective-I, BCS-058 for Elective-II) and an `elective_slot` marker; per-student resolution happens at read time via `COALESCE(TimetableEntry.elective_slot, ClassSession.elective_slot)` joined to `StudentElectiveChoice`.
- **No subsection-specific timetable exists.** All sections share one schedule set per section.

---

## 5. Current Elective Model

Authoritative resolver: `backend/app/services/elective_resolver.py` — `ELECTIVE_I_CODES = ["BCS-052","BCS-053","BCS-054"]`, `ELECTIVE_II_CODES = ["BCS-055","BCS-056","BCS-058"]`, anchors BCS-054/BCS-058. `validate_selection()`, `slot_for_code()`, `ElectiveResolver` class with `load_choices`, `chosen_elective_map`, `anchor_subjects`, `resolve_subject`, `resolve_events`.

Mechanics (evidence-backed):
- **Timetable**: `GET /api/v1/timetable` resolves each elective slot to the authenticated student's chosen subject (anchor when no choice).
- **Attendance read paths**: repo predicates `_elective_choice_on` (ON join by COALESCE slot) and `_resolved_subject_match` (WHERE: session subject matches, OR slot session + student's choice == subject). Applied to `get_subject_counts_up_to_date`, `get_subject_counts_for_user`, `get_subject_counts_between`, `get_sessions_with_status`, `get_daily_sessions`, `_fetch_history_occurrences`.
- **Attendance mutation**: `record_attendance` resolves the effective subject from `session.elective_slot` (or the timetable entry's slot) → student's choice → enrollment check.
- **Quiz**: `QuizRepository.get_effective_quiz_dates_for_subjects(subject_ids, elective_scope)` resolves slot quiz dates from active `QUIZ_DAY` events scoped by `elective_slot`.
- **Events**: `AcademicEvent.elective_slot` + `subject_id`(anchor). Admin creates "Departmental Elective-I/II" events; reads resolve per student via `ElectiveResolver.resolve_events`.
- **Event-created sessions**: the synchronizer sets `ClassSession.elective_slot` on extras and quiz-day sessions created from slot events.

**Gap**: The catalog is **hardcoded in code** (`ELECTIVE_I_CODES` etc.), not a DB-driven configuration. This is acceptable now but conflicts with the Admin-Portal-as-control-plane goal (curriculum/electives should become config).

---

## 6. Current Quiz Model

- `QuizCycle` (cycle_number 1..3, label) + `EligibilityPolicy` (lecture_threshold, combined_threshold).
- `QuizSchedule` (subject_id, quiz_cycle_id, elective_slot nullable, date, schedule_status).
- **Authoritative runtime quiz dates** = active `QUIZ_DAY` AcademicEvents (not `QuizSchedule`; the latter is a seed-time derived projection). Ranked chronologically into cycles 1..N.
- Eligibility engine (`eligibility_engine.py`): Criterion I (cycle window) OR Criterion II (cumulative from commencement), both `(Lecture% + Tutorial%)/2`, thresholds 70/75/75 fallback but persisted policy wins. Must-Attend/Safe-Skip via `optimize_attendance`. Labs excluded via `quiz_applicable`.
- Phase 22.4: elective subjects resolve the shared slot's quiz dates.
- **Gap**: only BCS-054/BCS-058 have quiz schedules/quiz-day events. The other four elective subjects (BCS-052/053/055/056) have **no quiz dates** (documented in Phase 22.3/22.4: quiz dates not present in CTT data). A shared elective slot currently has ONE authoritative quiz date set shared by all cohorts of that slot.

---

## 7. Current Event Model

`AcademicEvent`: one shared row (not per-student/per-subsection). Fields: event_type (17 values), start_date, end_date, subject_id (nullable), elective_slot (nullable), class_type (nullable), is_working_day, substitution_schedule_override, note, active. Admin mutations + student-creatable flexible types.

**Critical limitation (Section 7 of the brief):** the shared-event architecture **cannot** express, on the same date/time, different outcomes for different elective cohorts (e.g. Student A's subject has a Surprise Quiz while Student B's subject has a normal lecture). An event row is (event_type, subject_id|elective_slot, class_type, date-range). A SURPRISE_QUIZ on an elective slot applies to the whole slot. There is **no subject-specific occurrence/outcome dimension** on events.

---

## 8. Current ClassSession Model

`ClassSession`: subject_id, date, class_type, is_extra, is_cancelled, timetable_entry_id (nullable), elective_slot (nullable), designation (nullable MID_SEM_PRACTICAL).

**Critical finding — the materialized-schedule model:**
- `class_sessions` is the **single source of truth** for attendance. Every consumer (Track, History, Dashboard, Analytics, Calendar, Eligibility, Notifications) reads this table.
- Sessions are **materialized by section/subject**, not per student, and not per subsection.
- **There is no per-subsection notion** — a session row belongs to (subject, date) via the timetable entry, and the timetable entry belongs to a section. When subsections exist, one timetable entry cannot represent "subsection A has this class, subsection B has another at the same time."
- Event-created sessions (extras, quiz-day) are shape-count matched (no event linkage FK). They carry `elective_slot` but no `subsection_id` and no `event_id`.
- Cancellation is a flag (`is_cancelled`); cancelled ≠ absent (409 mutation guard); the synchronizer is state-based and idempotent, attendance-safe (attended sessions never deleted/cancelled except CLASS_CANCELLED class-reality propagation).

---

## 9. Current Attendance Model

`AttendanceRecord`: user_id, class_session_id, status (Attended/Missed/Pending), UNIQUE(user_id, class_session_id). One canonical mutation endpoint `POST /api/v1/attendance`; future-date rejection (400); cancelled rejection (409); enrollment-scoped.

Practical occurrences: two contiguous one-hour practical timetable periods collapse to ONE logical occurrence (`practical_occurrence.py`), one AttendanceRecord on the representative session. This is a read-model grouping, not a schema change.

---

## 10. Current Student Context

There is **no dedicated student-context read model/endpoint**. Academic context is reconstructed per-service:
- `UserRepository.get_academic_context(user)` returns `program`, `semester_name`, `academic_session`, `semester_start`, `semester_end`, `first_quiz_date` — used by `/student/me`, Track/History bounds, Calendar.
- But section/subsection/elective choices are **not** in that payload. The student app must call `/student/me` + `/timetable` + `/subjects` + `/quiz-eligibility` and implicitly rely on the backend's per-request resolution.
- **No subsection field anywhere** in student context.
- Elective choices are resolved server-side per request via `ElectiveResolver` but are **not exposed** as a canonical student-context payload.

---

## 11. Current Admin/Authorization Model

- Single `UserRole` (STUDENT/ADMIN). `require_admin` dependency. No hierarchy.
- Admin surfaces today: event CRUD (admin + student-creatable types), feedback admin read, laboratory experiment CRUD, mid-sem designation.
- **No HEAD_ADMIN / SECTION_ADMIN / SUBSECTION_ADMIN / ELECTIVE_ADMIN roles exist.** No scoping by section/subsection/subject. No capability matrix. (Note: the target role names use explicit `SECTION_ADMIN` — the ambiguous "CLASS_ADMIN" term is dropped, Correction 4.)

---

## 12. Current Frontend Architecture

- Next.js 16 (App Router), SWR hooks, `types/api.ts` mirrors backend schemas, `lib/api.ts` guarded `apiFetch`.
- Pages: `/dashboard`, `/subjects`, `/history`, `/calendar`, `/tools/events`, `/tools/quiz-schedule`, `/tools/laboratory` (Track), `/laboratory`, `/tools/feedback` (admin), `/profile`.
- Identity: `AuthContext.loadUser()` → `GET /student/me` → `StudentProfile` (name, roll, role, section_name, semester_name, academic_session, semester_start/end, first_quiz_date).
- Academic context consumed via `useProfile()` (student/me), `useSubjects()`, `useTimetable()`, `useDashboardSummary()`, `useAnalyticsOverview()`, etc. **The frontend never recomputes business math** (frozen rule).
- **Frontend assumptions that depend on single section/semester:** signup auto-assigns the single section (no section/subsection selector); dashboard/track/history bounds come from `/student/me` semester_start/end; timetable is section-scoped from the user's section. No subsection anywhere in the UI.

---

## 13. Current PWA Architecture

- Phase 13: manifest at `/manifest.json`, service worker at `/service-worker.js` (network-first for API, cache-first for navigation), SVG icons, install prompt, online/offline state. No offline data claims. No academic-context assumptions beyond the API-consumer pattern.

---

## 14. Every Single-Semester Assumption Found

| # | Location | Assumption | Evidence |
|---|---|---|---|
| S1 | `auth.py` register | exactly ONE active session; exactly ONE semester; exactly ONE section (else 409/503) | `auth.py:132-152` |
| S2 | `UserRepository.get_academic_context` | context via `user.section.semester` | `user_repo.py:33-41` |
| S3 | `seed_academic_baseline.py` | hardcoded "2026-27", "V Semester", section "CSE-51"; single section resolution; single section for timetable | `seed_academic_baseline.py:41-57,151-167` |
| S4 | `timetable.json` | single semester's start/end, single day_schedule | repo file |
| S5 | `verify_*` scripts | fixed date spans 2026-07-15 → 2026-12-31, fixed counts | multiple verifiers |
| S6 | Calendar/eligibility windows | `commencement_date = semester_start` (from academic context, OK) but engines treat a single timeline | `eligibility_service.py:158` |
| S7 | Notifications | `_occurrence_key` uses subject_code / quiz cycle / event id / session id — no semester dimension | `notification_service.py:107-121` |
| S8 | Dashboard/analytics weekly | bounded by `user.section` semester only | `dashboard_service.py:44-50` |
| S9 | Registration | "active session → its semester" — no semester selection UI | `auth.py` |
| S10 | Quiz snapshot / current-cycle | picks min future quiz date across enrolled subjects (single semester) | `dashboard_service.py`, `eligibility_service.py:211-257` |
| S11 | `settings.INSTITUTION_TIMEZONE` | single institution timezone | config |
| S12 | Practical-occurrence | collapses by (subject_id, date) — no section/subsection dimension (collision risk when two sections share a subject+date) | `practical_occurrence.py` |

Also: `Phase 17.4` documented hardcoded current-semester assumptions (2026-07-15/2026-12-31, weekday 0=Monday, registration auto-assign single section, quiz cycle thresholds). The ORM is already session-scoped (academic_sessions.is_active) — multi-semester is largely an **operational** change (new session row + is_active switch), not a schema rewrite.

---

## 15. Every Single-Section/Subsection Assumption Found

| # | Location | Assumption | Evidence |
|---|---|---|---|
| X1 | `sections.name` | **globally unique** — prevents repeating a section name across branches/semesters (e.g. the conceptual "CS-5A"; current production section is "CSE-51") | `user.py` Section |
| X2 | `auth.py` | exactly one section per semester → auto-assign | `auth.py:143-152` |
| X3 | `TimetableEntry.section_id` NOT NULL | entries belong to a single section; **no subsection dimension** | `timetable.py` |
| X4 | `class_sessions` | one occurrence per (subject,date,class_type) — **no subsection**; a subsection cannot have a different schedule | `timetable.py` |
| X5 | `timetable.json` | single `day_schedule` for the whole section | repo file |
| X6 | `users.section_id` | user belongs to a section, not a subsection | `user.py` |
| X7 | Enrollment scoping | `StudentEnrollment` join scoped by resolved subject only — no section/subsection filter | `attendance_repo.py` |
| X8 | Event/session sync | `entries_by_dow` built from ALL entries (no section/subsection filter — a second section's events would collide if schedules overlap) | `event_session_service.py:160-163` |
| X9 | Calendar engine | events are global (no section/subsection scoping) | `calendar_engine.py` |
| X10 | Practical occurrence | groups by (subject_id, date) across the whole table — two sections with the same subject on the same date could be merged | `practical_occurrence.py` |
| X11 | Section max strength 60 / subsection ≈30 | **not modeled anywhere** (strength/headcount targets are operator-requirements; examples like "CS-5A → 51/52" are conceptual only, not established facts) | — |

> **Note (Correction 5):** subsection examples throughout this report (e.g.
> "Subsection 51/52", "CS-5A") are **conceptual examples only**. The supplied CTT
> is authoritative only for B.Tech III Year (V Semester), CSE-51 and its listed
> subjects/elective catalogs. No subsection name is treated as an established
> academic fact unless an authoritative source or existing production data proves
> it.

---

## 16. Every Elective Assumption Found

| # | Location | Assumption | Evidence |
|---|---|---|---|
| E1 | `elective_resolver.py` | catalog hardcoded in code (3 EI + 3 EII codes, anchors) | `elective_resolver.py:40-53` |
| E2 | `subjects.tag` | elective slots backfilled from the subject's tag ("Elective-I"/"Elective-II") | migration 22.3/22.4, `seed_academic_baseline.py:199-203` |
| E3 | quiz dates | only anchors BCS-054/BCS-058 have quiz dates; other four elective subjects have none | Phase 22.3/22.4 docs |
| E4 | Events | elective-slot events ADMIN-only, one shared row, mutually exclusive subject_id | `event_service.py:109-140` |
| E5 | Enrollment | registration enrolls non-elective subjects + chosen electives only | `auth.py:168-204` |
| E6 | Admin | ADMIN keeps anchor subjects (no elective choice) | resolver fallback |
| E7 | Slot-vs-subject | a slot is marked via `elective_slot` on 4 tables; but there is **no single "elective configuration" row** describing (slot, allowed codes, anchor) in the DB | all evidence |

---

## 17. Every Scheduling Assumption Found

| # | Location | Assumption | Evidence |
|---|---|---|---|
| T1 | `timetable.json` | weekday 0 = Monday convention | seed + docs |
| T2 | `expand_baseline.py` | expands only teaching days; one session per timetable entry per date | Phase 6.6 docs |
| T3 | `class_sessions` | materialized span bounded by existing session min/max (`get_session_date_span`) | `session_repo.py`, `event_session_service.py:154-157` |
| T4 | session creation | `is_extra` sessions have no timetable link; quiz-day shape = LECTURE, is_extra=false, timetable_entry_id=null | `event_session_service.py:562-567` |
| T5 | extras matched | extras matched by (subject_id, class_type) count — **no event linkage FK** (cannot distinguish which event produced which extra) | `event_session_service.py:495-533`, Phase 6.6 known limitation |
| T6 | practical block | contiguous 2×1h practical = one occurrence | `practical_occurrence.py` |
| T7 | substitution | `substitution_schedule_override` day swap; working Saturday | `calendar_engine.py:105-106` |
| T8 | cancelled | cancelled ≠ absent, never deleted; CLASS_CANCELLED propagates over stale marks | `event_session_service.py` |

---

## 18. Every Quiz/Event Assumption Found

| # | Location | Assumption | Evidence |
|---|---|---|---|
| Q1 | quiz dates | active QUIZ_DAY events are authoritative; `quiz_schedules` is a derived projection | `quiz_repo.py:48-121` |
| Q2 | cycles | cycles ranked chronologically 1..N from event start dates | `quiz_repo.py:104-112` |
| Q3 | elective quiz | a slot has ONE quiz date set shared by all cohorts | Phase 22.4 |
| Q4 | Surprise Quiz | SURPRISE_QUIZ = one extra occurrence per (subject, class_type) per date; **cannot differ per cohort on the same date** | `event_session_service.py:333-340` |
| Q5 | events | one shared row per (type, subject|slot, class_type, date range); no per-subsection/cohort outcome dimension | `event.py` |
| Q6 | events global | events are not scoped to a section/subsection at all | `calendar_repo.get_all_events` |
| Q7 | eligibility | attendance windows from quiz dates; labs excluded | `eligibility_engine.py` |
| Q8 | notifications | QUIZ_APPROACHING uses `get_current_quiz_cycle`; event notifications use dashboard's shared selection | `notification_service.py` |

---

## 19. Engine-by-Engine Impact Matrix

For every surface: current source of truth, student/subject/section identity, elective awareness, per-cohort outcome/override awareness (Correction 3 terminology), and what must change vs. must NOT change.

| # | Surface | Source of truth | Identifies student? | Identifies subject? | Section/subsection? | Understands elective slots? | Understands per-cohort actual occurrence? | Must change | Must NOT change |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Timetable | `timetable_entries` (section) | via section | via subject/choice | section only; **no subsection** | YES (COALESCE read resolution) | No (slot is a schedule concept) | Add subsection scoping + subsection-specific schedules | Weekly recurring model; read-time elective resolution |
| 2 | Track (daily) | `class_sessions`+`attendance_records` | via enrollment scope | via resolved subject | section only (via timetable entry); no subsection | YES | No (a session row has one subject) | Add subsection to sessions/timetable; materialize per-subsection occurrences | Mutation guard (cancelled 409, future 400); record-wins |
| 3 | Class sessions | `class_sessions` materialized | — | via subject_id | section only via timetable; no subsection | YES (elective_slot marker) | No (one row = one subject occurrence) | Add subsection dimension + optional event linkage; represent "actual outcome" | Cancellation/extra/quiz-day semantics; attendance safety |
| 4 | Attendance | `class_sessions`+`attendance_records` | user_id | resolved subject | section via session; no subsection | YES | No | Subsection-aware scoping for reads; keep unique (user,session) | Unique constraint; ERP formulas; cancelled≠absent |
| 5 | Attendance history | `class_sessions`+records (same pipeline) | user_id | resolved subject | no subsection | YES | No | Subsection display; keep filters/summary | Occurrence collapse; filter semantics |
| 6 | Dashboard | `class_sessions`+records+services | user_id | resolved subject | section via semester bound; no subsection | YES | No | Subsection-aware bounds; keep ERP overall | Banding; delta; attention |
| 7 | Analytics | same | user_id | resolved subject | no subsection | YES | No | Subsection-aware; keep read-model semantics | Weekly series; forecast |
| 8 | Calendar | `calendar_engine` + events + sessions | user_id | resolved subject | events are global; no subsection | YES (event resolution) | No | Scope events to section/subsection; represent cohort-specific outcomes | Engine weekend/closure semantics |
| 9 | Notifications | engine/service outputs | user_id | resolved subject | no subsection | YES | No | Subsection-aware occurrence keys (add section/subsection to occurrence_key to avoid cross-semester collisions) | Consume-engine-only rule |
| 10 | Quiz schedules | active QUIZ_DAY events | user_id | resolved subject | no subsection | YES | Partially (slot quiz shared) | Per-subsection/cohort quiz occurrence when schedules differ; keep authoritative dates | Authoritative-date rule; no invented dates |
| 11 | Quiz eligibility | attendance + quiz dates | user_id | resolved subject | no subsection | YES | No | Subsection scope; keep formulas | Criterion I/II; thresholds; must-attend/safe-skip |
| 12 | Events | `academic_events` | user_id | resolved subject | global | YES | **NO — biggest gap** | New model: actual occurrence/outcome per (event, subject-specific cohort); scope to section/subsection | Shared-row admin creation; idempotent sync; attendance safety |
| 13 | Extra classes | synchronizer | — | subject | section via entry; no subsection | YES | No | Per-subsection extras | Shape-count idempotency |
| 14 | Cancelled classes | synchronizer | — | subject | section; no subsection | YES | No | Per-subsection cancellation | Cancelled≠absent; 409 |
| 15 | Surprise quizzes | synchronizer | — | subject | section; no subsection | YES | No | **Per-cohort outcome** (A surprise quiz vs B normal lecture on same date/time) | Occurrence count semantics |
| 16 | Practical attendance | `class_sessions` P + records | user_id | subject | no subsection | N/A (labs not elective) | No | Subsection scope | Block collapse; record-wins |
| 17 | Subject summaries | counts | user_id | resolved subject | no subsection | YES | No | Subsection scope; keep formulas | Health banding; optimizer |
| 18 | Forecast | counts | user_id | resolved subject | no subsection | YES | No | Subsection scope | Pending-as-attended |
| 19 | Safe-skip / must-attend | optimizer | user_id | resolved subject | no subsection | YES | No | Subsection scope | Optimizer tie-breaks |
| 20 | Eligibility calculations | engine | user_id | resolved subject | no subsection | YES | No | Subsection scope | Formula/window semantics |
| 21 | Session synchronization | synchronizer | — | subject | **ALL entries, no section filter (X8)** | YES | No | **Must filter by section/subsection** to avoid cross-section session collisions | State-based idempotency; span bounds |

**Summary of what must change:** (a) add a Subsection concept threaded through timetable/sessions/events/context; (b) introduce an **explicit outcome/override model** so a shared elective slot's occurrence can have per-cohort outcomes (Surprise Quiz / Normal Lecture / Cancelled per cohort, not per slot); (c) scope events and sync by section/subsection; (d) add a canonical **student academic-context read model**; (e) evolve the binary admin role into the small hierarchy (23.9).

**What must NOT change:** all engine formulas (attendance ERP, eligibility Criterion I/II, must-attend/safe-skip, forecast, banding), the unique (user, session) attendance constraint, cancelled≠absent + 409, future-date 400, practical occurrence collapse, the "consumers consume engine outputs" rule, React presentation-only rule, and all existing production data/UUIDs/FKs.

---

## 20. Required Target Architecture

```
ADMIN PORTAL (future)
     ↓  authoritative configuration
AUTHORITATIVE ACADEMIC CONFIGURATION (DB: branches, semesters, sections,
     subsections, students, admins, subjects, curriculum, electives,
     timetables, quiz schedules, events, occurrences, attendance admin,
     monitoring)
     ↓
BACKEND / DATABASE
     ↓
STUDENT CONTEXT RESOLUTION (canonical read model: branch → semester →
     section → subsection → elective-I → elective-II)
     ↓
STUDENT WEB APP + PWA (primarily consumes authoritative configuration)
```

The student application should consume a canonical backend context rather than reconstructing it from scattered calls.

---

## 21. Recommended Database Model (additive, migration-safe)

All changes **additive** (new tables/columns), preserving every existing row, UUID, timestamp, FK.

**Phase ownership (Correction 1 applied):** only the academic-hierarchy/data
items below (1–3) belong to **23.1**. The admin role/scope schema (item 11) is
**23.9** — 23.1 documents the future authorization dependency but does not
implement it. Items 4–5 (timetable/session subsection columns) are **23.3**
scheduling columns, NOT 23.1 — the 23.1 foundation does not need them (see
Correction 6 governance below).

1. **`subsections`** table (NEW, 23.1):
   - `id` UUID PK, `name` (example only: "51", "52", "A", "1" — actual names are a 23.1 gate, Correction 5), `section_id` FK → sections (NOT NULL), `max_strength` int (default 30), `created_at`, `updated_at`
   - `UNIQUE(section_id, name)` — subsection names are unique within a section only (NOT globally)
   - Backfill (Correction 9): **no fabrication, no automatic subsection creation or assignment to satisfy the migration.** Existing students retain their current academic data; the new `subsection_id` FK stays NULL. **NULL means UNKNOWN/UNASSIGNED** where student placement is not authoritative. No default subsection is fabricated. Controlled backfill happens later through an explicitly authorized operation.
2. **`sections`** (23.1): relax global-unique `name` → `UNIQUE(semester_id, name)` (drop global unique index, add composite unique). This is a **constraint change** — verify no duplicate names exist across semesters before applying (currently one section → safe). **Do NOT add a `branch` column here** until the Branch relationship is decided (Correction 7, §36 gate).
3. **`users.subsection_id`** (nullable FK → subsections, 23.1). `NULL` = explicitly unassigned/unknown (Correction 9). Keep `section_id`. **No automatic backfill of existing users.**
4. **`timetable_entries.subsection_id`** (nullable FK → subsections, **23.3** — scheduling column, NOT 23.1): NULL = applies to the whole section; non-NULL = subsection-specific schedule. 23.3 owns the schema + resolution wiring. **23.1 does NOT change timetable resolution, synchronizer behavior, or session generation.**
5. **`class_sessions.subsection_id`** (nullable FK → subsections, **23.3** — scheduling column, NOT 23.1): NULL = whole section. Additive. 23.3 owns the schema + all consumer wiring; **23.1 does NOT change session generation.**
6. **`academic_events.section_id` / `.subsection_id`** (nullable FKs, later phase — event scoping is 23.7): NULL = global (legacy behavior). **Event-scope enum is NOT implemented until scope semantics are defined by the 23.1 hierarchy (Correction 4).**
7. **Actual-occurrence/outcome model** — see §25. `occurrence_outcomes` is the **current minimal candidate** (not finalized until 23.4 designs it). Not part of 23.1.
8. **Branch modeling** (23.1 gate, Correction 7): the current model has no Branch entity — `Section.program` is a string. Whether a `branches` table is introduced, and where it sits relative to `semesters`, is decided in 23.1 from evidence. **No `semesters.branch_id` is assumed.**
9. **`elective_catalog` configuration** (NEW, 23.5 scope): DB-driven catalog. Not part of 23.1; the code-hardcoded `ElectiveResolver` constants remain authoritative until 23.5.
10. **`class_sessions.event_id`** (nullable FK → academic_events, 23.4 scope): trace extras to their source event. Not part of 23.1.
11. **Admin scoping (23.9, NOT 23.1 — Correction 1):** new `admin_scopes` table (`user_id`, `role`, `section_id`/`subsection_id`/`subject_id` nullable, `active`, `created_at`) OR a richer `users.role` enum + scope columns. **Recommended:** extend `UserRole` with the admin roles + an `admin_scopes` table mapping role → scope. This entire item is deferred to 23.9.

> **Academic Session / Academic Year terminology (Correction 6):** Repository
> evidence strongly establishes `AcademicSession` (name unique, start/end,
> is_active) as the existing academic-year/session entity, with
> `Semester.session_id` referencing it. **No second year/session entity is
> proposed.** 23.1 must confirm this interpretation before schema
> implementation; absent contradictory evidence, `AcademicSession` remains
> canonical.

---

## 22. Recommended Authorization Model (23.9 scope — NOT 23.1)

> **Ownership (Correction 1):** This section describes the eventual target
> authorization model. It is **23.9 scope**. 23.1 documents the dependency but
> does NOT implement it. The role/scope schema is not part of 23.1.

- Extend `UserRole`: `STUDENT`, `HEAD_ADMIN`, `SECTION_ADMIN`, `SUBSECTION_ADMIN`, `ELECTIVE_ADMIN` (keep `ADMIN` as alias for `HEAD_ADMIN` for back-compat or migrate it).
- New `admin_scopes` table: `user_id`, `role`, `section_id` (nullable), `subsection_id` (nullable), `subject_id` (nullable, for elective admins), `active`, `created_at`.
- New dependency functions: `require_head_admin`, `require_admin_in_scope(section_id|subsection_id|subject_id)`.
- Rules:
  - HEAD_ADMIN: everything (superset of current ADMIN).
  - SECTION_ADMIN: scoped to assigned section(s). (Explicit naming: "SECTION_ADMIN" replaces the ambiguous "CLASS_ADMIN" — Correction 4.)
  - SUBSECTION_ADMIN: scoped to assigned subsection(s).
  - ELECTIVE_ADMIN: scoped to one concrete elective subject (six admins, one per BCS-052/053/054/055/056/058) — **do not collapse**.
- Backend-authoritative (role+scope resolved from DB per request; never from JWT).
- Default migration behavior: existing ADMIN → HEAD_ADMIN.
- **Event-scope enum is NOT implemented until 23.7 defines scope semantics from the 23.1 hierarchy (Correction 4).** Proposed terms (GLOBAL / SECTION / SUBSECTION / SUBJECT / ELECTIVE_SLOT) are a candidate, not authoritative.

---

## 23. Recommended Student Context Model (23.2 scope)

A canonical backend read model — **combination of a resolver + an endpoint**, not a new table:
- Extend `UserRepository.get_academic_context` (or new `StudentContextResolver`) to return: `branch` (as resolved by 23.1 — Correction 7; currently only `Section.program` exists), `semester_name`, `academic_session`, `section_name`, `section_id`, `subsection_name`/`subsection_id` (nullable — Correction 9: NULL = unknown, never fabricated), `semester_start/end`, `elective_i` (code+name+id), `elective_ii`, `role`.
- Expose via `GET /api/v1/student/me` (extend `StudentProfile`) and/or a dedicated `GET /api/v1/student/academic-context`.
- The student app consumes this single endpoint for identity + academic context; timetable/quiz/attendance endpoints already resolve per-student server-side.
- Recommendation: a single `StudentContextResolver` service (single source of truth), consumed by `/student/me`; no separate DB table needed (context is derived from the authoritative ORM chain). This is safer than reconstructing in the frontend.
- **23.2 is a read-model slice only** — no registration/frontend academic-selection wiring in 23.1 (Correction 10).

---

## 24. Recommended Timetable Model (23.1 schema / 23.3 resolution)

- Keep weekly-recurring `timetable_entries` per section.
- Add `subsection_id` (nullable, 23.1 SCHEMA ONLY): NULL = common/core to the whole section; non-NULL = subsection-specific slot.
- Resolution (23.3): a student's timetable = entries for their section where `subsection_id IS NULL OR subsection_id = <their subsection>`, with elective slots resolved to their choice.
- `GET /api/v1/timetable` filters accordingly (23.3 — no wiring in 23.1, Correction 10).
- This supports "Section → Subsection A/B, possibly different schedules" without per-student schedules and without duplicating core slots.

---

## 25. Recommended Actual Occurrence vs Outcome Model (23.4 scope — the critical distinction)

> **Terminology (Correction 3):** the architecture now uses the canonical
> three-layer model and never conflates these layers:
>
> ```
> EXPECTED TIMETABLE  (timetable_entries: day/time, subject|slot, class_type)
>     ↓  materialized
> CLASS SESSION / OCCURRENCE  (class_sessions: dated occurrence of the expected
>     ↓                       schedule; the attendance substrate)
> COHORT/SUBJECT-SPECIFIC OUTCOME OR OVERRIDE  (what actually happens for a
>     ↓                       given subject/cohort on that occurrence)
> resolved student-facing academic reality
> ```
>
> The critical example must remain representable — same date/time/logical
> elective slot, three cohorts, three outcomes:
> - BCS-058 cohort → **Surprise Quiz**
> - BCS-055 cohort → **Normal Lecture**
> - BCS-056 cohort → **Cancelled**
>
> This must be solved WITHOUT duplicating complete student-specific
> timetables/sessions (a shared occurrence is preserved; only the
> outcome/override is per cohort).

The four concepts that must not be conflated:
- **(A) TIMETABLE SLOT** (EXPECTED): `timetable_entries` row (Monday 10:00, Departmental Elective-II, Lecture).
- **(B) SCHEDULED CLASS OCCURRENCE**: `class_sessions` row (Monday 2026-09-01 10:00, Elective-II slot, subsection — example only) — linked via `timetable_entry_id` (+ new `subsection_id`).
- **(C) STUDENT'S RESOLVED SUBJECT**: `StudentElectiveChoice` → `ElectiveResolver` (Student A → BCS-058, Student B → BCS-055). Read-time, not materialized per student.
- **(D) COHORT/SUBJECT-SPECIFIC OUTCOME OR OVERRIDE**: what actually happens for a given subject/cohort on that occurrence — Surprise Quiz for the BCS-058 cohort, Normal Lecture for the BCS-055 cohort, Cancelled for the BCS-056 cohort, Extra, etc.

**Does the current architecture separate them?**
- (A), (B), (C) are separated: (A)=timetable_entries, (B)=class_sessions, (C)=choices+resolver.
- (D) is **NOT separated**: events (D-source) mutate (B) directly via the synchronizer. A SURPRISE_QUIZ event on the elective-II slot materializes an extra session for the whole slot (subject_id = anchor), and `class_sessions` cannot express "BCS-058 cohort had a quiz, BCS-055 cohort had a normal lecture, BCS-056 cohort had it cancelled" on the same date/time because **one session row has one subject and one is_extra/is_cancelled state**.

**Minimum clean architectural correction (candidate, NOT finalized):**
Add an **outcome/override** dimension — the smallest correct evolution:
- Option 1 (recommended, smallest): add a new table `occurrence_outcomes` (or `class_occurrences`):
  - `id`, `event_id` (FK → academic_events, nullable), `class_session_id` (FK → class_sessions, nullable), `date`, `subject_id` (FK, nullable = slot-level), `elective_slot` (nullable), `section_id`/`subsection_id` (nullable), `class_type`, `outcome` (enum: NORMAL_LECTURE / EXTRA_LECTURE / EXTRA_TUTORIAL / EXTRA_PRACTICAL / SURPRISE_QUIZ / CLASS_CANCELLED / LAB_CANCELLED / MID_SEM_PRACTICAL / QUIZ_DAY), `active`.
  - The synchronizer writes actual outcomes; student-facing reads resolve (subject, outcome) per student/cohort: for a slot occurrence, a student's subject's outcome = the outcome row whose subject_id == their choice (or the slot-level outcome when none is subject-specific).
  - A subject-specific Surprise Quiz row (`subject_id = BCS-058`, slot II, date) yields "Surprise Quiz" for the BCS-058 cohort, "Normal Lecture" for the BCS-055 cohort, and (with a subject-specific cancelled row for BCS-056) "Cancelled" for the BCS-056 cohort — on the SAME date/time/slot, with ONE shared `class_sessions` occurrence.
- Option 2 (heavier): redesign `class_sessions` into per-(occurrence × subject) rows — **rejected** (creates per-subject session duplication, violates the shared-occurrence goal, touches the frozen attendance pipeline).

Recommendation: **Option 1** — additive table, preserves the shared occurrence, keeps `class_sessions` as the attendance substrate, and makes the synchronizer the only writer. This is the architectural centerpiece of Phase 23.4/23.7. **The candidate schema (`occurrence_outcomes`) is NOT finalized — Phase 23.4 designs it with the evidence in hand; the constraint is that the three-cohort example above must be representable without per-student duplication.**

---

## 26. Recommended Event Model (23.7 scope)

- Keep `academic_events` as the admin-facing configuration surface (one shared row per (type, subject|slot, class_type, date-range)) — unchanged admin UX.
- Add `section_id`/`subsection_id` (nullable, NULL=global) for scoping (23.7).
- The **actual per-cohort outcome** lives in `occurrence_outcomes` (Option 1, §25), written by the synchronizer when materializing events, so the shared event remains one row while student reads see cohort-specific outcomes.
- Elective events continue to be ADMIN-only, slot-scoped; a subject-specific occurrence row is created only when the admin/authority specifies a concrete subject outcome (e.g. "Surprise Quiz on Elective-II for BCS-058").
- **Event-scope terminology (Correction 4):** the ambiguous `CLASS` scope is removed. Event scope is NOT enumerated until the 23.1 hierarchy defines it; proposed candidate terms are GLOBAL / SECTION / SUBSECTION / SUBJECT / ELECTIVE_SLOT (pending, not authoritative).

---

## 27. Recommended Quiz Model

- Keep authoritative quiz dates from active QUIZ_DAY events (no new dates invented).
- For a shared elective slot quiz: one authoritative slot-level quiz date remains valid when all cohorts share the date. When quiz schedules differ by subsection, the event gets `subsection_id` scoping and the occurrence model carries it.
- Quiz eligibility continues to resolve each student's chosen subject to the slot's quiz dates via `get_effective_quiz_dates_for_subjects` (extended with section/subsection filters).
- **No redesign of quiz cycles** — the 3-cycle threshold model stays.

---

## 28. Recommended Attendance Integration

- `class_sessions` gains `subsection_id` (nullable); all attendance read queries add subsection scoping (a student's sessions = their section's entries where `subsection_id IS NULL OR subsection_id = theirs`).
- `occurrence_outcomes` does NOT change attendance counting: outcomes map to the existing is_extra/is_cancelled semantics (Surprise Quiz = extra occurrence, Cancelled = cancelled occurrence) so ERP/eligibility formulas remain byte-identical.
- `StudentEnrollment` uniqueness is **unresolved (Correction 8)** — see §36 open question. No constraint is added blindly. The correct key must preserve multi-semester historical correctness (student+semester / student+subject / student+semester+subject options are evaluated in 23.1).
- Keep unique `(user_id, class_session_id)` attendance constraint.

---

## 29. Recommended Admin Portal Boundary

- Admin Portal = separate future surface consuming the authoritative configuration.
- Backend endpoints to evolve for admin scoping: event CRUD (already admin), laboratory experiment CRUD, mid-sem designation, feedback admin, plus NEW configuration endpoints (branches, semesters, sections, subsections, subjects, curriculum, electives, timetable, quiz schedules, occurrences, attendance administration, monitoring).
- Authorization via the new role/scope model (§22).
- NOT in Phase 23 scope: building the Admin Portal UI itself (that is post-23.10); 23.9 lays the authorization foundation and the configuration APIs that the portal will consume.

---

## 30. Recommended Student App Boundary

- Consume the canonical student-context endpoint (§23) for identity + academic context.
- Never display "Departmental Elective-I/II" as a subject name in normal surfaces — resolve to the concrete subject (already enforced in Phase 22.4 read paths; extend to new surfaces).
- Timetable/quiz/attendance surfaces read section+subsection-scoped endpoints.
- No React-side business math (frozen rule).

---

## 31. Migration Strategy

> **Migration governance (Correction 2):** each schema-changing phase owns its
> own migration lifecycle — discovery/design → offline validation (`alembic
> upgrade/downgrade --sql`) → local/dev migration → verification (phase
> verifier) → **explicit operator boundary** → production migration ONLY when
> separately authorized → read-only post-production verification. Production
> migrations are NOT deferred to 23.10; 23.10 is the final Phase-23 migration
> **reconciliation/rollout/closure**, not the first production migration point.

For every proposed schema change (all additive unless noted):

| Change | Phase | Additive/Destructive | Migration strategy | Backfill (Correction 9: no fabrication) | Rollback | Production risk |
|---|---|---|---|---|---|---|
| `subsections` table + `users.subsection_id` | 23.1 | Additive | New table + nullable FK column | **NO automatic subsection creation or assignment.** Existing users retain current data; `subsection_id` stays `NULL` (UNKNOWN/UNASSIGNED). No default subsection is fabricated. Controlled backfill later (authorized operation). | `downgrade`: drop column + table | Low (new NULL-safe column; data preserved) |
| `sections.name` global unique → `UNIQUE(semester_id, name)` | 23.1 | Constraint change | Drop global unique index, add composite unique | Verify no duplicate names before applying (1 section today) | Re-add global unique | Low–Medium (must verify uniqueness before applying) |
| Branch entity (decided in 23.1 gate; possibly `branches` + `semesters.branch_id`) | 23.1 gate | Additive | New table + nullable FK | Pending 23.1 evidence (Correction 7) — NOT assumed | Drop | Low |
| `student_enrollments` uniqueness key | 23.1 gate | Additive constraint (key TBD) | New unique index (key chosen from §36 gate, Correction 8) | Verify no duplicates; preserve multi-semester history | Drop index | Low |
| `timetable_entries.subsection_id` | 23.3 (scheduling) | Additive | Nullable FK | NULL for all existing (whole-section) | Drop column | Low |
| `class_sessions.subsection_id` | 23.3 (scheduling) | Additive | Nullable FK | NULL for all existing | Drop column | Low |
| `academic_events.section_id`/`subsection_id` | 23.7 | Additive | Nullable FKs | NULL = global | Drop columns | Low |
| `occurrence_outcomes` table | 23.4 (design) | Additive | New table | Empty (populated by synchronizer going forward) | Drop table | Low |
| `class_sessions.event_id` | 23.4 | Additive | Nullable FK | NULL (backfill optional, via matching events) | Drop column | Low |
| `elective_catalog` config table | 23.5 | Additive | New table | Empty (resolver falls back to code constants) | Drop table | Low |
| `admin_scopes` + `UserRole` extension | 23.9 | Additive | New table + ALTER TYPE (add enum values) | Backfill ADMIN → HEAD_ADMIN | Drop table / enum values | Low–Medium (PG enum ADD VALUE is non-transactional in older PG; Supabase PG 15 supports it) |

All migrations: single linear Alembic chain (currently head `b7c8d9e0f1a2`); each new revision chains to the previous head. Downgrade paths explicit. No destructive migration is required.

**Production risk**: every migration is additive except the `sections.name` uniqueness change and the (key-pending) `student_enrollments` unique index — both verified safe given current data (1 section, no duplicate enrollments). Each schema-changing phase follows the per-phase operator-boundary governance above; production migration happens only when separately authorized, never implicitly.

---

## 32. Production Safety Strategy

- Preserve: existing users, attendance, history, events, quiz schedules, timetable data, UUIDs, timestamps, FK integrity — **all preserved** by the additive plan (no deletes, no column renames, no data transforms beyond NULL-backfills).
- Backfill strategy (Correction 9): every new FK column is nullable; existing rows get NULL (for `users.subsection_id` NULL = **UNKNOWN/UNASSIGNED**, never a fabricated default; for timetable/session/event scope columns NULL = "whole section"/"global"). **Legacy unknown state is preserved** — students without authoritative subsection/elective/branch/academic placement remain explicitly UNASSIGNED/UNKNOWN. Never fabricate a subsection, DE-I, DE-II, branch, or academic placement. Backfill/remediation is a documented FUTURE CONTROLLED OPERATION (a dedicated script with operator authorization), never an automatic migration step; no automatic subsection creation/assignment is used to satisfy the migration.
- Rollback: `alembic downgrade <prev>` for each revision.
- Production risk: low. The only caution is the enum `ALTER TYPE ... ADD VALUE` for new admin roles (use the non-transactional ADD VALUE then a transaction that doesn't depend on it, or add all enum values in one migration, matching the Phase 9.1 pattern).
- Do NOT recommend destructive migration unless unavoidable — none is required.

---

## 33. Phase Dependency Graph

```
23.1 Academic hierarchy/data foundation (subsections, users.subsection_id,
     sections uniqueness, Branch decision gate, enrollment-uniqueness gate,
     AcademicSession/Academic-Year confirmation gate)
     — SCHEMA/DATA MODEL ONLY (no timetable resolution, no synchronizer,
       no session generation, no engine/registration/UI wiring)
   ↓
23.2 Student academic context (canonical read model)
   ↓
23.3 Timetable + subsection scheduling (timetable_entries.subsection_id +
     class_sessions.subsection_id schema AND resolution wiring +
     synchronizer scoping)
   ↓
23.4 Actual class occurrence / outcome model (occurrence_outcomes design,
     event_id; per-cohort outcome representation)
   ↓
23.5 Elective subject resolution (config-driven catalog + resolution surfaces)
   ↓
23.6 Quiz architecture (subsection-scoped dates; keep cycles)
   ↓
23.7 Event architecture (section/subsection scoping + per-cohort outcomes)
   ↓
23.8 Attendance/engine integration (subsection scoping; formulas untouched)
   ↓
23.9 Admin authorization foundation (roles + scopes + config APIs)
   ↓
23.10 Phase-23 migration reconciliation / rollout / closure
     (NOT the first production migration point — each phase ships its own)
```

Dependencies: 23.1 → 23.2 (context needs subsection). 23.3 needs 23.1. 23.4 needs 23.3 (outcomes reference occurrences). 23.5 can run in parallel with 23.6 (both need 23.2). 23.7 needs 23.4. 23.8 needs 23.3 + 23.4. 23.9 is independent of 23.4-23.7 (can start after 23.1). 23.10 last, as closure. **Admin authorization (23.9) is NOT part of 23.1** (Correction 1); 23.1 only documents the dependency.

---

## 34. Proposed Phase 23.x Breakdown (evidence-based ordering, reconciled)

The task brief's sketch was close. Repository evidence + the ten corrections refine the ordering:

- **23.0 — Architecture discovery + blueprint reconciliation (COMPLETE).** Read-only. Delivers this report.
- **23.1 — Academic hierarchy / data foundation (SCHEMA ONLY — Correction 10).** Subsection entity, `sections` composite-unique name, `users.subsection_id`, the Branch decision gate (Correction 7), the enrollment-uniqueness gate (Correction 8), the Academic-Session/Academic-Year confirmation gate (Correction 6). **Does NOT wire** timetable resolution, synchronizer, attendance, Track, History, Dashboard, quiz eligibility, events, registration, frontend academic selection, or admin authorization (Corrections 1, 10). **Does NOT create `admin_scopes`** (deferred to 23.9). **Does NOT introduce `timetable_entries.subsection_id` / `class_sessions.subsection_id`** — those are 23.3 scheduling columns (Correction 6 governance; they are not needed for the 23.1 foundation).
- **23.2 — Student academic context.** `StudentContextResolver` + extended `/student/me` (branch as resolved, section, subsection [NULL=unknown], elective I/II). Read-model only; no registration wiring.
- **23.3 — Timetable + subsection scheduling.** Introduce `timetable_entries.subsection_id` + `class_sessions.subsection_id` schema AND wire them into resolution + synchronizer scoping (fixes X8 cross-section collision). Directly enables "Section → Subsection A/B with differing schedules." 23.3 owns ALL timetable/session behavioral wiring; 23.1 does not.
- **23.4 — Actual class occurrence / outcome model.** Design + implement the outcome/override model (`occurrence_outcomes` candidate) + `class_sessions.event_id`; synchronizer writes outcomes; per-cohort read resolution. THE critical architectural step. The candidate schema is finalized here (not in 23.0).
- **23.5 — Elective subject resolution (config-driven).** `elective_catalog` table; resolver reads DB (fallback to code); full read-path verification across timetable/quiz/events/attendance; registration continues to use the catalog.
- **23.6 — Quiz architecture.** Subsection-scoped quiz events/dates; keep authoritative dates + cycles; verify eligibility resolves per cohort.
- **23.7 — Event architecture.** Section/subsection event scoping (scope terms finalized from the 23.1 hierarchy — Correction 4); per-cohort actual outcomes (the three-cohort example: Surprise Quiz / Normal Lecture / Cancelled); admin event creation for slots/subjects/subsections.
- **23.8 — Attendance/engine integration.** Thread subsection through all attendance read paths; verify all engine formulas byte-identical; full regression.
- **23.9 — Admin authorization foundation.** Role enum extension + `require_*` dependencies + `admin_scopes` + admin-scoped config APIs (branches/semesters/sections/subsections/subjects/electives/timetable/quiz/occurrences/attendance admin/monitoring). No Admin Portal UI.
- **23.10 — Phase-23 migration reconciliation / rollout / closure.** Reconcile the linear Alembic chain, confirm every operator-run production migration + read-only post-production verification, backfill/remediation operations (with operator authorization), downgrade paths, governance closure. **This is NOT the first production migration point** (Correction 2) — each schema-changing phase shipped its own.

Rationale for the refined order: subsections must exist before context, timetable, occurrences, or events can reference them; the outcome model (23.4) must precede event per-cohort outcomes (23.7); authorization (23.9) is the foundation for the Admin Portal but is independent of the occurrence work so it can be parallelized after 23.1. 23.1 is deliberately schema-only to keep the foundation verifiable and frozen before any consumer wiring.

---

## 35. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| `sections.name` global-unique change | Medium | Verify zero duplicates pre-migration (currently 1 section); run in 23.1 with dry-run |
| PG enum ADD VALUE for admin roles | Low–Medium | Non-transactional in older PG; add all values in one migration (Phase 9.1 pattern); Supabase PG15 supports |
| Occurrence model (Option 1) touches the attendance pipeline | High if wrong | Keep `class_sessions` untouched as attendance substrate; synchronizer-only writes; full regression in 23.8 |
| Cross-section session collision in the synchronizer (X8) | High | Fix sync to filter by section/subsection before multi-section exists (23.3) |
| Practical-occurrence collapse colliding across sections (X10) | Medium | Add section/subsection to the collapse key |
| New quiz dates for the four uncovered electives | Medium | Do NOT invent dates; keep anchor-only dates; document as data gap until CTT provides them |
| Elective catalog config-drift | Medium | Resolver reads DB with code fallback; admin writes gated by scope |
| 60-student/30-subsection capacity | Low | Modeled as config; enforce at admin/registration boundary, not in engine |
| Admin hierarchy scope confusion | Medium | Explicit scope table; role+scope resolved from DB per request; capability matrix documented |

---

## 36. Open Questions (require operator/product decision — several are 23.1 GATES)

**23.1 GATES (must be resolved before/within the 23.1 schema slice):**
1. **Academic Session vs Academic Year (Correction 6, gate)** — Repository evidence strongly establishes `AcademicSession` as the existing academic-year/session entity (`name`, start/end, is_active), with `Semester.session_id` referencing it. 23.1 must confirm this interpretation before schema implementation; **absent contradictory evidence, `AcademicSession` remains canonical.** No second year/session entity is created unless the gate proves otherwise.
2. **Branch parentage (Correction 7, gate)** — current model: no Branch entity, `Section.program` string only. Decide whether Branch becomes a separate entity, whether `semesters` is shared across branches, and where curriculum belongs. Document the evidence and chosen relationship BEFORE FKs are written.
3. **`student_enrollments` uniqueness key (Correction 8, gate)** — evaluate `student + semester`, `student + subject`, `student + semester + subject`, historical enrollment across semesters, duplicate current enrollment, legitimate future/historical enrollment. The final key must preserve multi-semester historical correctness. If unresolved, document the gate instead of a guessed constraint.
4. **Event-scope semantics (Correction 4, gate)** — remove the undefined `CLASS` scope; define explicit scope terms (candidate: GLOBAL / SECTION / SUBSECTION / SUBJECT / ELECTIVE_SLOT) once 23.1 finalizes the hierarchy. No event-scope enum is implemented before this.

**NON-GATE OPEN QUESTIONS:**
5. **Subsection naming convention** — "51/52" (roll-number-derived), "A/B", or "1/2"? These are conceptual examples (Correction 5), not established facts; needed for 23.1 subsection creation + 23.2 UI.
6. **Quiz dates for BCS-052/053/055/056** — authoritative CTT quiz dates are absent. Do NOT invent; confirm whether they share the slot's existing quiz dates (09-07/09-28/10-23 for EI; 09-11/10-05/10-26 for EII) or have their own (data gap).
7. **Per-cohort Surprise Quiz authority** — when different elective cohorts get different outcomes on the same date/time, who authorizes the subject-specific outcome (HEAD_ADMIN / SECTION_ADMIN / ELECTIVE_ADMIN)? This determines the 23.7 event UI.
8. **Admin Portal UI** — is 23.9 limited to backend authorization + config APIs, with the portal UI deferred to a separate phase (recommended)? Or does 23.9 include a minimal admin UI?
9. **Legacy user assignment / backfill** — existing users without authoritative subsection/elective/branch placement remain UNKNOWN (Correction 9). Confirm the backfill/remediation is a FUTURE CONTROLLED OPERATION (documented, operator-authorized), not automatic.
10. **Multi-semester rollover** — confirm a new `academic_sessions` row + `is_active` switch is the intended rollover mechanism (Phase 17.4 documented) and that no engine changes are expected for it.
11. **Registration flow (PAGE 1 branch/semester/section/subsection + PAGE 2 electives)** — confirm the client submits section/subsection IDs now (Phase 4.5.3 froze "client submits no academic IDs"). The new requirement contradicts that frozen rule → requires an explicit decision to allow client-driven section/subsection selection with server-side validation. (Registration wiring is NOT in 23.1; this is 23.2+ scope.)
12. **Subsection strength (max 30) and section strength (max 60)** — modeled as configuration (subsections.max_strength); confirm the authoritative source for these numbers.

---

## 37. Explicit Non-Goals (Phase 23.0 — and deferred out of 23.1+ until authorized)

- NO semester rollover implementation.
- NO new quiz dates invented.
- NO quiz-cycle redesign.
- NO Admin Portal UI (backend authorization + config APIs only, if authorized).
- NO self-service elective change (admin correction only, per brief).
- NO student-facing display of "Departmental Elective-I/II" names.
- NO per-student schedule/occurrence duplication.
- NO engine formula changes.
- NO destructive migration.
- NO access or mutation of production data (this phase).
- **23.1 is schema/data-model foundation ONLY (Correction 10):** it does NOT wire timetable resolution, synchronizer behavior, attendance, Track, History, Dashboard, quiz eligibility, events, registration, frontend academic selection, or admin authorization. Those belong to later Phase 23 slices.
- **23.1 does NOT introduce `timetable_entries.subsection_id` / `class_sessions.subsection_id`** — those are 23.3 scheduling columns; 23.1 does not change timetable resolution, synchronizer behavior, or session generation.
- **23.1 does NOT implement admin authorization schema/dependencies (Correction 1):** `admin_scopes`/role extension is 23.9. 23.1 may only document the dependency.
- **No event-scope enum is implemented until scope semantics are defined (Correction 4).**
- **Existing students are NOT backfilled or fabricated in 23.1 (Correction 9):** no automatic subsection creation/assignment, no deterministic default subsection; `subsection_id` stays NULL (UNKNOWN/UNASSIGNED).

---

## 38. Final Recommendation

Proceed to **Phase 23.1** with the additive, migration-safe plan above, in the evidence-ordered sequence 23.1 → 23.2 → 23.3 → 23.4 → 23.5 → 23.6 → 23.7 → 23.8 → 23.9 → 23.10, **reconciled per the ten corrections** (§0). The single most important architectural decision is the **introduction of an explicit outcome/override model that separates CLASS SESSION / OCCURRENCE from COHORT/SUBJECT-SPECIFIC OUTCOME (Correction 3, §25)** so the three-cohort example (BCS-058 → Surprise Quiz, BCS-055 → Normal Lecture, BCS-056 → Cancelled on the same date/time/slot) is representable without per-student duplication, plus the **Subsection concept** threaded through timetable/sessions/events/context, and a **canonical student-context read model**.

Phase 23.1 is deliberately **schema/data-model foundation only** (Corrections 1, 10): it resolves the four gates (Academic-Session/Academic-Year confirmation, Branch parentage, enrollment-uniqueness, event-scope semantics), creates the subsection/hierarchy data model, and does NOT wire any consumer, engine, registration, UI, or admin authorization. Each schema-changing phase ships its own migration lifecycle with an explicit operator boundary (Correction 2); 23.10 is the final reconciliation/closure, not the first production migration point. All engine formulas, the shared-occurrence invariant, the attendance constraint, and every existing production row are preserved; legacy unknown state stays unknown (Correction 9).

---

## Verification of the discovery phase

- **Repository inspection:** complete (models, migrations, services, engines, repositories, endpoints, frontend, PWA, seed scripts, governance docs).
- **Read-only status:** no files under `backend/app`, `backend/alembic`, `frontend/src`, migrations, seeds, or tests modified.
- **New files:** `docs/phase_23/phase_23_0_architecture_discovery.md` (this report, including the §0 correction-reconciliation block).
- **Governance changes:** MASTER_ROADMAP.md, implementation_plan.md, task.md, walkthrough.md — Phase 23.0 recorded as a discovery phase (status: COMPLETE-DISCOVERY, implementation not started) and reconciled per the ten corrections.
- **Database:** not touched (no connection opened, no SELECT/INSERT/UPDATE/DELETE, no migration).
- **Git:** clean working tree before and after; no commit, no push, no PR.
