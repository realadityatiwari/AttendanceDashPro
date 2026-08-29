# Phase 24.0 — Admin Portal Discovery & Architecture (DISCOVERY REPORT)

Status: **DISCOVERY COMPLETE** (2026-08-29). No implementation performed. No code,
schema, migration, or data changes. No commit / push / merge / PR.

Decision-status legend used throughout this report:

- **CONFIRMED** — verified against repository code (file paths cited); frozen fact.
- **PROPOSED** — recommended design, not yet implemented; requires a later phase.
- **DEFERRED** — intentionally pushed to a later phase / decision gate.
- **UNKNOWN** — genuinely unresolved; must not be guessed.

---

## 1. Executive Summary

Phase 24.0 is a discovery-only phase. Its objective was to design the architecture and
implementation boundaries for a dedicated **Admin Portal** — the master control surface of
AttendanceDashPro — without building anything, without touching the frozen Phase 23
Academic Core, and without inventing architecture.

Key conclusions:

1. **The authorization foundation is ready.** Phase 23.11 (`f9a0b1c2d3e4`) already provides
   everything the Admin Portal must rely on: `AdminRole` (HEAD_ADMIN / CLASS_ADMIN /
   SUBSECTION_ADMIN / ELECTIVE_ADMIN), the `admin_scopes` table with a DB CHECK constraint
   enforcing role–scope consistency, and `AuthorizationService` resolving authority from
   PostgreSQL on every request. The portal must consume this layer; it must never add a
   parallel one.
2. **The event pipeline is the canonical occurrence-control mechanism.** The
   `timetable_entries → class_sessions → occurrence_outcomes` chain is driven declaratively
   by `EventSessionSynchronizer`: subject-scoped academic events become per-subject outcomes
   on the shared anchor session. The DE-II shared-slot case in the phase brief
   (BCS-058 SURPRISE_QUIZ / BCS-055 NORMAL_LECTURE / BCS-056 CANCELLED) is **already
   representable with the existing engine** through subject-scoped events — no new outcome
   mutation API should be created.
3. **The Admin Portal is mostly a new API surface.** Of 41 existing endpoints, the vast
   majority are student-self-scoped reads. Only 7 endpoints are admin-gated today
   (`require_head_admin`), and there is **no** admin endpoint for students, academic
   structure, subjects, timetable, enrollment, quiz schedules, admin scopes, or attendance
   correction. Phase 24 is therefore primarily additive backend + new frontend surface.
4. **Subsection administration stays disabled.** The schema models subsections
   (null-preserving), but no authoritative subsection data exists and no subsection-scoped
   scheduling is modeled. SUBSECTION_ADMIN remains conservatively inert; the portal may
   display subsection structure but must not pretend subsection administration works.
5. **Two schema gaps are genuine but must not be silently filled:** the timetable model has
   no room / faculty / subsection-scope / effective-date fields, and `users` has no
   activation flag. Both are recorded as decision gates — no fields invented in discovery.
6. **Recommended sequence:** 14 sub-phases (24.1–24.14) starting with the admin identity +
   portal shell, then read models before mutations, structure before timetable, timetable
   before session operations, with admin management and monitoring last.

Everything below is grounded in the exact files listed in Appendix A.

---

## 2. Current Architecture Baseline

**CONFIRMED**

- Stack: FastAPI + SQLAlchemy (async) + PostgreSQL (local dev container; Supabase in
  production), Alembic migrations; Next.js App Router + TypeScript + Tailwind + shadcn/ui
  frontend; SWR data layer; PWA (manifest + service worker).
- Backend entry: `backend/app/main.py` — CORS, security headers (X-Frame-Options DENY,
  nosniff, referrer policy, optional HSTS), global 500 handler (never leaks internals),
  health endpoints `GET /` and `GET /health`. API mounted at `settings.API_V1_STR`
  (`/api/v1`) from `backend/app/api/api.py`.
- `backend/app/api/v1/router.py` is a **legacy placeholder router not wired into the app**
  (`api/api.py` is the live one). Admin Portal work must not touch it.
- Academic hierarchy (models in `backend/app/models/academic.py`, `user.py`):
  `AcademicSession → Semester → Section (program) → Subsection` ;
  `Subject` (semester-scoped, `UNIQUE(code, semester_id)`, typed `elective_slot` catalog
  marker, `category` THEORY/LAB, `quiz_applicable`, `attendance_applicable`) ;
  `StudentEnrollment` (`UNIQUE(user_id, subject_id)`, `enrollment_type`
  COMPULSORY/ELECTIVE) ; `StudentElectiveChoice` (`UNIQUE(user_id, elective_slot)`).
- Frozen migration state (Phase 23.12): **25 revisions, single linear chain, one head
  `f9a0b1c2d3e4`** (`add_admin_scopes`, revises `f8a9b0c1d2e3`). Verified in this phase by
  reading every `revision`/`down_revision` pair in `backend/alembic/versions/`:
  `7117a007a0da → 8a2b3c4d5e6f → c3d4e5f6a7b8 → d4e5f6a7b8c9 → e5f6a7b8c9d0 →
  a1b2c3d4e5f6 → f1a2b3c4d5e6f → f6a5b4c3d2e1f → a7b8c9d0e1f2 → b1c2d3e4f5a6 →
  b1c2d3e4f5a7 → c1d2e3f4a5b6 → d1e2f3a4b5c6 → e1f2a3b4c5d6 → f2e3d4c5b6a7 →
  a3b4c5d6e7f8 → b7c8d9e0f1a2 → c8d9e0f1a2b3 → d0e1f2a3b4c5 → e3f4a5b6c7d8 →
  f5a6b7c8d9e0 → f6a7b8c9d0e1 → f7a8b9c0d1e2 → f8a9b0c1d2e3 → f9a0b1c2d3e4`.
- Every table row carries `id` (UUID), `created_at`, `updated_at` (IST) from
  `backend/app/db/base_class.py` — the current "database history" baseline (see §21).
- Seeded elective catalog (from `verify_phase_22_4.py` assertions + `ElectiveResolver`):
  ELECTIVE_I = BCS-052, BCS-053, **BCS-054 (anchor)**;
  ELECTIVE_II = BCS-055, BCS-056, **BCS-058 (anchor)** — six concrete elective subjects,
  matching the six conceptual ELECTIVE_ADMIN assignments.

---

## 3. Existing Frontend Architecture

**CONFIRMED** — all paths under `frontend/src/`.

- **Framework:** Next.js App Router with route groups. `(auth)/login`, `(auth)/signup`;
  `(authenticated)/` layout wrapping `dashboard`, `calendar`, `history`, `laboratory`,
  `profile`, `subjects`, `tools/{events,feedback,laboratory,quiz-schedule}`.
- **Layout/navigation:** `components/layout/AppShell.tsx` (top nav + scrollable main +
  mobile bottom nav below `md`), `TopNav.tsx`, `MobileBottomNav.tsx`, `UserMenu.tsx`.
  Nav is role-gated only by the legacy `profile?.role === "ADMIN"` check (adds the Feedback
  admin nav item) — UI-layer gating only; the backend remains the boundary.
- **Auth/session:** `contexts/AuthContext.tsx` — JWT `access_token` in `localStorage`,
  profile via `GET /api/v1/student/me`, redirect guards (public vs authenticated routes),
  `logout()` clears token. **No refresh-token flow; no role beyond `UserRole`.**
- **API client:** `lib/api.ts` `apiFetch()` — JSON, bearer attach, network-error
  translation, `401 → clear token + redirect /login`, error `detail` extraction,
  production URL guard (`NEXT_PUBLIC_API_URL`, refuses localhost in prod builds).
- **Data layer:** `hooks/useApi.ts` — SWR hooks with `STANDARD_CACHE` (focus revalidate,
  60 s dedupe) and `LONG_CACHE` (1 h) strategies; mutation helpers return the updated
  object and callers revalidate specific SWR keys.
- **Reusable UI:** `components/ui/` shadcn primitives — `button, card, badge, dialog,
  dropdown-menu, input, avatar, progress, separator, sheet, skeleton`. Shared patterns:
  `components/shared/` (`EmptyState`, `ErrorState`, `GlassCard`, `PageHeader`);
  `components/shell/ShellDialog.tsx` modal foundation (backdrop, focus, Escape, scroll
  lock) reused by Appearance/Feedback/InstallApp/Profile/Settings modals.
- **Tables/forms/modals/drawers:** no generic table component exists; lists are composed
  from card primitives (`EventRow`, lab records, feedback list). Forms are hand-built
  (`EventFormDialog` is the richest reference: validation, loading, error, edit/create
  modes, admin-only option sets). `sheet.tsx` exists (drawer) — used by notification
  center; available for admin panels.
- **Loading/empty/error:** per-card skeletons; `EmptyState` and `ErrorState` shared
  components; full-page error states on dashboard/history.
- **Notifications:** `NotificationBell` + `NotificationCenter` (SWR-gated inbox, PATCH
  idempotent transitions).
- **Styling:** Tailwind + dark-locked design tokens (Phase 1); `globals.css`.
- **Existing admin-related screens:** only three — `/tools/feedback` (admin feedback
  review, UI-guarded, backend `require_head_admin`), admin event type options inside
  `EventFormDialog` (admins see all event types; students only flexible types), and lab
  experiment catalog management UI (`isAdmin` prop in laboratory page). **There is no
  admin dashboard, no admin route group, and no admin data layer today.**
- **Dashboard patterns to reuse:** `components/dashboard/home/*` cards
  (GreetingHeader, OverallAttendanceCard, WeeklyAttendanceCard, QuizSnapshotCard,
  AttentionRequiredCard, UpcomingEventsCard) — established card/bento composition,
  status banding (SAFE ≥80 / WATCH ≥60 / CRITICAL <60 computed backend-side).

---

## 4. Existing Admin/Auth Architecture (Phase 23.11 trace)

**CONFIRMED** — the authoritative layer the portal must reuse.

- `backend/app/models/enums.py` — `AdminRole` (HEAD_ADMIN, CLASS_ADMIN,
  SUBSECTION_ADMIN, ELECTIVE_ADMIN); `UserRole` (STUDENT, ADMIN — legacy).
- `backend/app/models/admin_scope.py` — `admin_scopes` table: `user_id` (FK users),
  `role` (adminrole), nullable `section_id` / `subsection_id` / `subject_id` FKs, `active`
  boolean (default true). CHECK `ck_admin_scopes_role_scope` enforces:
  HEAD_ADMIN → all three NULL; CLASS_ADMIN → section only; SUBSECTION_ADMIN → subsection
  only; ELECTIVE_ADMIN → subject only. `active=false` scopes are treated as nonexistent.
  A user may hold multiple scope rows.
- `backend/app/services/authorization_service.py` — `AuthorizationService`:
  - `get_active_scopes(user_id)` — active `admin_scopes` rows (one query).
  - `_legacy_role(user)` — `users.role == ADMIN` ⇒ HEAD_ADMIN (global).
  - `effective_admin_roles(user)` — union of legacy + scope roles.
  - `is_head_admin(user)`.
  - `can_access_section(user, section_id)` — HEAD any; CLASS exact-section scope; others
    denied.
  - `can_access_subsection(user, subsection_id)` — HEAD any; SUBSECTION_ADMIN exact
    subsection; **conservative deny otherwise** (no authoritative subsection data exists).
  - `can_access_subject(user, subject_id)` — HEAD any; ELECTIVE_ADMIN exact concrete
    subject; CLASS_ADMIN when `subjects.semester_id == sections.semester_id` for an
    assigned section (semester-wide, by design). SUBSECTION_ADMIN not granted.
  - `can_mutate_event(user, subject_id, elective_slot_is_set, student_creatable)` —
    slot-scoped (`elective_slot` set) or global (`subject_id` None) events: HEAD_ADMIN
    only; subject-scoped events: scope check via `can_access_subject`; non-admins fall
    through to the enrollment rule ("student").
- `backend/app/api/dependencies/deps.py`:
  - `get_current_user` — JWT decode (`type=access`), user loaded from DB every request.
  - `require_head_admin` — `AuthorizationService.is_head_admin` (legacy ADMIN or active
    HEAD_ADMIN scope). DB-resolved per request; never from JWT claims/body/query/frontend.
  - `require_class_scope(section_id)`, `require_subsection_scope(subsection_id)`,
    `require_elective_subject_scope(subject_id)` — dependency factories (exact-target
    checks).
  - `require_admin` — **legacy STUDENT/ADMIN gate; currently unused by any endpoint**
    (kept for compatibility; portal must use the Phase 23.11 gates instead).
- **EventService authorization** (`backend/app/services/event_service.py`):
  - `STUDENT_CREATABLE_EVENT_TYPES` = EXTRA_LECTURE/TUTORIAL/PRACTICAL, CLASS_CANCELLED,
    SURPRISE_QUIZ, MID_SEM_PRACTICAL, LAB_CANCELLED, CLASS_MODIFIED (frozen product
    behavior).
  - `assert_mutation_allowed` — admins → `can_mutate_event`; students → flexible types on
    enrolled subjects only.
  - `_resolve_elective_scope` — elective-slot events resolve to the shared anchor subject
    (BCS-054 / BCS-058) and require HEAD_ADMIN; `subject_id` + `elective_slot` mutually
    exclusive.
  - Duplicate-active-event guard (409), registry validation (422), single-transaction
    commit with `EventSessionSynchronizer.sync_event` reconciliation (rollback on error).
- **Laboratory authorization:** experiment catalog create/update/deactivate and mid-sem
  designate/clear are `require_head_admin`-gated endpoints; record CRUD is
  self-service/admin with sign protection (`laboratory_service._guard_write`).
- **Feedback authorization:** `GET /feedback/admin`, `GET /feedback/admin/{id}` gated by
  `require_head_admin`.
- **Database constraints:** `uq_subjects_code_semester`, `uq_student_enrollments_user_subject`,
  `uq_user_elective_slot`, `uq_sections_semester_name`, `uq_subsections_section_name`,
  `uq_occurrence_outcome_session_subject`, `uq_admin_scopes_role_scope` CHECK, plus
  `adminrole` enum. These are the hard backstops behind any portal mutation.
- **Provisioning today:** `backend/scripts/provision_admin.py` (operator-only; sets
  `users.role=ADMIN`); `backend/scripts/set_initial_password.py` (operator password set).
  **No API path grants roles or scopes** — self-assignment is structurally impossible.

**What the portal can safely rely on today:** all of the above. What it must NOT do:
create another role/scope/resolver system; trust any client-provided role/scope; gate on
JWT claims.

---

## 5. Existing Backend/Admin API Inventory

All 41 endpoints (live router `backend/app/api/api.py`; verified per file). Legend:
**Auth** = gate; **Portal-safe** = reusable as-is for the Admin Portal.

### auth (`endpoints/auth.py`)
| Route | Method | Purpose | Auth | Portal-safe |
|---|---|---|---|---|
| `/api/v1/auth/login` | POST | JWT login (roll_number+password, rate-limited 10/900 s, timing-equalized) | public | Reusable (admins log in the same way) |
| `/api/v1/auth/register` | POST | Student self-registration; auto-resolves the active session's single semester + single section; enrolls compulsory subjects + validates elective choices against DB catalog; single transaction | public, rate-limited 5/3600 s | Reusable as registration path; **not** an admin create-student API |

### student (`endpoints/student.py`, `preferences.py`)
| Route | Method | Purpose | Auth | Portal-safe |
|---|---|---|---|---|
| `/api/v1/student/sync` | POST | Legacy profile sync (fills only unset name/roll) | JWT | Not admin-relevant |
| `/api/v1/student/me` | GET | Own profile + full academic context (StudentContextService: placement, subsection, program, enrollments, elective choices, first quiz date) | JWT | **Reusable** — the pattern for admin student-detail reads |
| `/api/v1/student/preferences` | GET/PUT | Own preferences | JWT | Not admin-relevant |

### subjects / timetable (`endpoints/subjects.py`, `timetable.py`)
| Route | Method | Purpose | Auth | Portal-safe |
|---|---|---|---|---|
| `/api/v1/subjects` | GET | Subjects of the active session's semester (student-facing) | JWT | Partially reusable; needs admin-scoped variant (semester parameter, catalog fields) |
| `/api/v1/timetable` | GET | Weekly entries for the caller's **own section**, elective slots resolved per-student | JWT | Not directly reusable (self-section only; no admin section parameter) |

### attendance (`endpoints/attendance.py`)
| Route | Method | Purpose | Auth | Portal-safe |
|---|---|---|---|---|
| `/api/v1/attendance/history` | GET | Own history (filters, outcome-aware) | JWT | Pattern only |
| `/api/v1/attendance/daily/{date}` | GET | Own daily sessions | JWT | Pattern only |
| `/api/v1/attendance/summary/{subject_code}` | GET | Own subject summary | JWT | Pattern only |
| `/api/v1/attendance` | POST | **Self** mutation (`user_id = current_user.id`); CANCELLED-outcome rejection (Phase 23.9) | JWT | **No admin correction path exists** — new admin endpoints required |

### quiz (`endpoints/quiz.py`)
| Route | Method | Purpose | Auth | Portal-safe |
|---|---|---|---|---|
| `/api/v1/quiz-eligibility/current-cycle` | GET | Canonical current cycle for the caller | JWT | Pattern only |
| `/api/v1/quiz-eligibility/{subject_code}/{cycle}` | GET | Own eligibility (enrollment-scoped; EligibilityService engine) | JWT | Engine reusable for admin views |

### calendar (`endpoints/calendar.py`)
| Route | Method | Purpose | Auth | Portal-safe |
|---|---|---|---|---|
| `/api/v1/calendar` | GET | Month view (engine-derived) | JWT | Engine reusable |
| `/api/v1/calendar/today`, `/api/v1/calendar/{date}` | GET | Academic day schedule | JWT | **Reusable** as a shared day-read |

### events (`endpoints/events.py`)
| Route | Method | Purpose | Auth | Portal-safe |
|---|---|---|---|---|
| `/api/v1/events` | GET | Active/inactive + date-range + upcoming filters; ElectiveResolver resolution | JWT | **Reusable** (admin sees anchor representation when no choices) |
| `/api/v1/events` | POST | Create event; EventService authorization (students flexible/enrolled; slot+global = HEAD; subject-scoped = scope check) | JWT + service gate | **Reusable as-is** — this is the canonical occurrence-control write path |
| `/api/v1/events/{id}` | PATCH | Partial update; re-authorizes initial and final state; slot events HEAD-only | JWT + service gate | **Reusable as-is** |
| `/api/v1/events/{id}` | DELETE | Safe deactivation (`active=false`) + reconciliation; re-enable via PATCH | JWT + service gate | **Reusable as-is** |

### laboratory (`endpoints/laboratory.py`) — 13 endpoints
Reads (summary/experiments/records/activity/mid-sem) are enrollment/subject-guarded;
record CRUD is self/admin; **experiment create/update/deactivate and mid-sem
designate/clear are `require_head_admin`** — **directly reusable admin surfaces.**

### dashboard / analytics (`endpoints/dashboard.py`, `analytics.py`)
| Route | Method | Purpose | Auth | Portal-safe |
|---|---|---|---|---|
| `/api/v1/dashboard/summary` | GET | Self dashboard (reuses Attendance/Eligibility/Calendar services) | JWT | Pattern only |
| `/api/v1/analytics/overview` | GET | Self analytics read model (forecast, weekly, per-subject) | JWT | **Engine reusable; needs admin-scoped variant** |

### feedback (`endpoints/feedback.py`)
| Route | Method | Purpose | Auth | Portal-safe |
|---|---|---|---|---|
| `/api/v1/feedback` | POST | Submit feedback | JWT | Reusable (admins can report too) |
| `/api/v1/feedback/admin` | GET | Paginated list, filters | **require_head_admin** | **Reusable as-is** |
| `/api/v1/feedback/admin/{id}` | GET | Single item | **require_head_admin** | **Reusable as-is** |

### notifications (`endpoints/notifications.py`)
| Route | Method | Purpose | Auth | Portal-safe |
|---|---|---|---|---|
| `/api/v1/notifications` | GET | Own inbox | JWT | Pattern only |
| `/api/v1/notifications/{id}` | PATCH | Own read state (idempotent) | JWT | Not admin-relevant |

**Admin-gated endpoints today: 7** (2 feedback + 5 laboratory). Everything else is
student-self-scoped. `require_head_admin`-ready services the portal can call without new
authorization work: EventService (role-aware), FeedbackService.list_admin, LaboratoryService
catalog/mid-sem.

---

## 6. Admin Role Model

**CONFIRMED** (frozen Phase 23.11 semantics; restated for the portal design):

- **HEAD_ADMIN** — global authority. Realized as legacy `users.role == ADMIN` **and/or**
  an active `admin_scopes` row with role HEAD_ADMIN (scope columns NULL). The only role
  allowed to: create elective-slot events, create global/closure events (subject_id NULL),
  manage lab experiment catalog, designate mid-sem practicals, read admin feedback —
  today; and the only role that will manage academic structure, subjects, admins, scopes,
  quiz schedules, and system configuration.
- **CLASS_ADMIN** — section-scoped. Authority = active scope rows per section. Subject
  access is **semester-wide by design**: any subject whose semester contains an assigned
  section is in scope (`can_access_subject` section-semester join). This is a frozen
  Phase 23.11 semantic — the portal must present it honestly (a CLASS_ADMIN may operate
  on subjects of their section's semester, including elective subjects), and must not
  fabricate narrower or broader rules.
- **SUBSECTION_ADMIN** — subsection-scoped; **inert**. `can_access_subsection` exists but
  no authoritative subsection data exists (subsections table empty; `users.subsection_id`
  NULL for all users) and no resource can be proven inside a subsection scope. The portal
  must keep every subsection capability disabled/deferred.
- **ELECTIVE_ADMIN** — concrete-subject-scoped, one subject per scope row. Exact subject
  match only; BCS-058 authority can never touch BCS-055 (no slot-level or DE-level
  collapse exists anywhere in the authorization path).
- **STUDENT** — no portal authority. Every admin endpoint must deny students
  (403 via the Phase 23.11 gates).
- Effective authority is always the union of legacy + active scopes, resolved from the DB
  per request. The portal may *display* the resolved identity (new read endpoint,
  PROPOSED) but must never *decide* from it.

---

## 7. Admin Capability Matrix

Legend: **H** = HEAD_ADMIN, **C** = CLASS_ADMIN, **S** = SUBSECTION_ADMIN, **E** =
ELECTIVE_ADMIN. Values: FULL / OWN (resource-owned subset) / ROSTER (only students
enrolled in own subject) / NO. Status: **[C]** = confirmed available through existing
services+authorization; **[P]** = proposed (needs additive endpoints following existing
architecture); **[D]** = deferred; **[U]** = unknown/decision gate.

| Capability | H | C | S | E | Notes / Status |
|---|---|---|---|---|---|
| View students | FULL | OWN (assigned sections) | DEFERRED (inert) | ROSTER (own subject) | New read endpoints [P]; context via StudentContextService [C] |
| Search students | FULL | OWN | DEFERRED | ROSTER | [P] |
| Create student | FULL | NO | NO | NO | Admin-create flow [P]; registration self-service stays separate [C] |
| Edit student (name/password reset) | FULL | NO | NO | NO | [P]; password set flow exists as operator script today [C] |
| Deactivate student | FULL | NO | NO | NO | **[U] decision gate** — `users` has no activation flag; additive column required or defer |
| Assign section (move) | FULL | NO | NO | NO | [P] with reassignment-safety rules (§12) |
| Assign subsection | FULL (warned) | NO | NO | NO | Representable (`users.subsection_id`) but scheduling-inert; display warning [P][D] |
| View enrollment | FULL | OWN-semester subjects | DEFERRED | OWN subject | [P]; model [C] |
| Manage compulsory enrollment | FULL | NO | NO | NO | [P]; UNIQUE(user,subject) backstop [C] |
| View elective choices | FULL | OWN-semester | DEFERRED | OWN subject choosers | [P] |
| Manage elective choices | FULL | NO | NO | NO | [P]; choice-change semantics = decision gate (§25) |
| View subjects | FULL | OWN-semester | NO | OWN subject | Admin variant of GET /subjects [P] |
| Create/edit subjects | FULL | NO | NO | NO | [P]; UNIQUE(code,semester) [C] |
| Manage elective catalog (`elective_slot`, anchors) | FULL | NO | NO | NO | [P]; anchor codes frozen constants — changing them is a decision gate |
| Timetable view | FULL | OWN sections | DEFERRED (no subsection timetable) | OWN-subject slot entries only | [P]; shared per-section model [C] |
| Timetable creation / editing / deletion | FULL | OWN sections [P] | NO | **NO** | Timetable is the institutional shared schedule; an ELECTIVE_ADMIN must never own the shared slot entry. Event path is their write surface [C] |
| Schedule L / T / P (recurring) | FULL | OWN sections | NO | NO | Timetable CRUD [P] |
| Cancel L/T (or P) | FULL (all) | OWN-section subjects | NO | OWN subject only | Via CLASS_CANCELLED events — **[C] works today** for scoped admins |
| Add extra L/T | FULL | OWN-section subjects | NO | OWN subject only | Via EXTRA_* events — **[C] works today** |
| Create subject-specific occurrence outcome | FULL | OWN-section subjects | NO | OWN subject only | **[C] confirmed**: subject-scoped events → OccurrenceOutcome on the anchor session (EventSessionSynchronizer lines 400–428). No direct outcome API to be created |
| Schedule Surprise Quiz (event) | FULL | OWN-section subjects | NO | OWN subject only | SURPRISE_QUIZ event **[C]**; students may also record (frozen product behavior) |
| Manage quiz schedules (QuizSchedule rows/cycles) | FULL | NO | NO | NO | [P]; engine/policy models untouched |
| Manage quiz-day events | FULL | OWN-section subjects (subject-scoped QUIZ_DAY) | NO | OWN subject | Slot-scoped QUIZ_DAY = HEAD only **[C]** (can_mutate_event) |
| Manage holidays / closures / breaks | FULL | NO | NO | NO | Global (subject_id NULL ⇒ HEAD only) **[C]** |
| Manage working-day overrides | FULL | NO | NO | NO | Global **[C]** |
| Manage academic events (general) | FULL | subject-scoped per scope | NO | OWN subject | **[C]** via can_mutate_event |
| View attendance | FULL (any student) | OWN sections | DEFERRED | OWN-subject roster | New admin read endpoints [P]; engines reused [C] |
| Administrative attendance correction | FULL | OWN sections | NO | OWN subject | **[P]** new capability; no endpoint exists (POST /attendance is self-only **[C]**); high-impact confirmation required; policy = decision gate |
| View analytics | FULL (global) | OWN sections | NO | OWN subject | New admin reads over existing engines [P] |
| Manage class/session state (direct is_cancelled/is_extra writes) | NO — event-driven only | NO | NO | NO | Sessions are materialized state; events are the canonical driver. Read-only session views [P]; direct writes rejected by design |
| Manage sections | FULL | NO | NO | NO | [P]; UNIQUE(semester,name) [C] |
| Manage subsections | FULL (warned) | NO | NO | NO | [P][D] — creation representable; use stays inert |
| Manage academic sessions | FULL | NO | NO | NO | [P]; single-active-session invariants relied on by registration [C] |
| Manage semesters | FULL | NO | NO | NO | [P]; registration requires exactly-one-semester ambiguity guard [C] |
| Manage admins (accounts) | FULL | NO | NO | NO | [P]; provisioning workflow = decision gate (§25) |
| Assign scopes | FULL | NO | NO | NO | [P]; admin_scopes writes; CHECK constraint is the backstop [C] |
| Revoke scopes | FULL (deactivate) | NO | NO | NO | `active=false` is the canonical path — **[C]** semantics |
| Activate/deactivate admin scopes | FULL | NO | NO | NO | Same toggle **[C]** |
| System monitoring | FULL | NO | NO | NO | /health exists **[C]**; richer monitoring [P]; feedback admin review reusable **[C]** |

Explicit matrix principles (from resource ownership + Phase 23.11 — no blind grants):

1. ELECTIVE_ADMIN isolation is guaranteed by exact-subject scope matching **[C]**;
   BCS-058 can never administer BCS-055 (different subject rows; no slot-wide authority).
2. CLASS_ADMIN subject breadth is semester-wide **[C]** — frozen; portal labels it
   "section's semester", not "my subjects only".
3. SUBSECTION_ADMIN is granted nothing operationally until subsection-aware scheduling
   exists **[C]** (conservative deny).
4. Session-level direct mutation is never exposed; all class-reality changes flow through
   events so the reconciler stays canonical **[C]** (design principle, proposed).

---

## 8. HEAD_ADMIN Information Architecture

**PROPOSED** portal information architecture (conceptual; no screens built).

Primary navigation (desktop-first sidebar):

1. **Dashboard** — landing overview.
2. **Students** — search/list/detail/mutations.
3. **Academic Structure** — sessions → semesters → sections → subsections.
4. **Curriculum** — subjects, elective catalog, lab experiment catalog (reuses existing
   head-admin endpoints), mid-sem designation status.
5. **Timetable** — per-section weekly editor.
6. **Sessions & Occurrences** — class_sessions calendar/day views, occurrence outcomes.
7. **Quizzes** — cycles, policies (read), schedules, quiz-day derivation status.
8. **Events** — holidays/closures/overrides/subject events; calendar integration.
9. **Attendance** — student/subject attendance views; administrative correction.
10. **Admins** — admin accounts, scope assignment (the six ELECTIVE_ADMIN subjects as
    six distinct assignable scopes).
11. **Monitoring** — system health, feedback review (reuses `GET /feedback/admin`).
12. **Settings** — only if justified by a real configuration need (UNKNOWN — see §25).

Area details:

- **Dashboard:** purpose = operational snapshot. Major screens: today's sessions, active
  quiz cycle, upcoming events/holidays, data-quality warnings (unplaced students,
  unassigned electives, inconsistencies from StudentContextService), row counts.
  Backend: new aggregate read endpoint [P]. Visibility: HEAD only.
- **Students:** purpose = authoritative student lifecycle management. Screens: searchable
  table (roll/name/section/semester/status), detail (context, enrollments, elective
  choices, attendance snapshot), create/edit/move dialogs with confirmation. Backend: new
  admin student endpoints [P]. Visibility: HEAD full; CLASS scoped; ELECTIVE roster.
- **Academic Structure:** sessions/semesters/sections/subsections CRUD with guards
  (cannot delete/retro-edit structure with dependent data; creation warns about
  registration ambiguity rules). Visibility: HEAD only.
- **Curriculum:** subjects CRUD, `elective_slot` assignment (catalog), quiz/lab
  applicability flags, experiment catalog (reuse), anchors displayed as frozen facts.
  Visibility: HEAD only (ELECTIVE_ADMIN gets read-only view of own subject).
- **Timetable:** per-section weekly grid editor (§14). Visibility: HEAD all sections;
  CLASS own sections; ELECTIVE read-only own-subject entries.
- **Sessions & Occurrences:** day/week browser of `class_sessions` with effective
  outcome composition (anchor + outcomes), and links to the events that produced them.
  All mutations redirect to the Events surface (event-driven only).
- **Quizzes:** QuizCycle/EligibilityPolicy read models; QuizSchedule management (set
  dates, CANCELLED status); QUIZ_DAY derivation overview (materialization parity).
  Visibility: HEAD manages; scoped admins see subject-scoped slices.
- **Events:** the central write surface. Filters by type family (closure / override /
  extra / cancel / quiz / modified / mid-sem). Reuses POST/PATCH/DELETE /events
  untouched. Visibility per matrix.
- **Attendance:** cross-student attendance views (scoped), correction workflow with
  confirmation (§19). Visibility: HEAD full; CLASS sections; ELECTIVE roster.
- **Admins:** admin account list, create/provision flow, scope assignment matrix
  (user × role × target), activate/deactivate toggles. CHECK-constraint-aware UI.
  Visibility: HEAD only.
- **Monitoring:** health checks, feedback review, audit-ish activity views (from
  updated_at baselines; richer audit deferred). Visibility: HEAD only.

---

## 9. CLASS_ADMIN Information Architecture

**PROPOSED** — section-scoped by default; unrelated sections structurally invisible.

Post-login experience: the portal resolves the admin's active scopes (new DB-resolved
identity endpoint [P]) and pins the working context to the assigned section(s). If exactly
one section is assigned, all screens are pre-filtered; with multiple scopes, a scope
switcher limited to assigned sections is shown.

- **Dashboard:** own-section snapshot — today's sessions for the section, active quiz
  cycle for the section's semester, upcoming section-relevant events, attendance risk
  list (WATCH/CRITICAL students of the section).
- **Students:** roster of the assigned section(s) only (detail view read-only for CLASS).
- **Timetable:** read/edit (PROPOSED) of the assigned sections' weekly grid only.
- **Sessions:** day/week session views for the section's subjects (semester-wide subject
  set — frozen semantic, honestly labeled).
- **Quizzes:** subject-scoped quiz day/events for in-scope subjects; read-only schedule
  views.
- **Events:** create/edit subject-scoped events (extra/cancel/quiz/modified) for
  in-scope subjects; no global/holiday/slot events (backend denies **[C]**).
- **Attendance/monitoring:** section attendance views; no correction unless granted in a
  later phase (policy gate).
- **Analytics:** section analytics built on existing engines.

**Unrelated-section prevention:** every screen renders from scope-filtered endpoints;
the backend filters by `can_access_section`/`can_access_subject` per request. UI
filtering is convenience only — the authorization service is the boundary **[C]**.

---

## 10. SUBSECTION_ADMIN Boundaries

**CONFIRMED constraints** (no fabrication):

- Schema supports: `subsections` rows (name, section_id, nullable max_strength),
  `users.subsection_id` (nullable), `admin_scopes` SUBSECTION_ADMIN rows, and the
  `can_access_subsection` check.
- What the portal could safely display: the subsection tree of a section; membership
  counts; unassigned-student counts. Display-only.
- What must remain disabled: any subsection-scoped **operation** — the portal shows
  SUBSECTION_ADMIN scopes as assignable-but-inert, and any SUBSECTION_ADMIN login sees
  dashboards/empty states with an explicit "subsection administration is not yet
  operational" state, not fake data.
- **DEFERRED until subsection-aware scheduling exists:** subsection-scoped timetable
  entries (the model has no subsection scope column), subsection-resolved class
  sessions/occurrences, subsection attendance views, and all SUBSECTION_ADMIN mutations.
- Decision gate: the subsection scheduling schema (additive `subsection_id` on
  `timetable_entries` or a separate mapping) must be designed in a dedicated later
  phase; discovery deliberately does NOT propose the column (§25).

---

## 11. ELECTIVE_ADMIN Information Architecture

**PROPOSED** — six concrete-subject-scoped admin experiences. The UI must make the
concrete subject scope unmistakable: header badge like
`ELECTIVE_ADMIN → BCS-058 — Data Warehousing & Data Mining`, and a scope switcher when a
user holds several subject scopes (each a separate `admin_scopes` row **[C]**).

What this admin can do (all through existing, confirmed service paths):

- **View:** own subject detail (code/name/semester/category/flags), the shared slot
  entries that include the subject (read-only), own subject's sessions/occurrences
  (including outcomes affecting the subject), roster (students whose
  StudentElectiveChoice resolves to the subject), attendance of that roster, subject
  analytics, subject-scoped event history.
- **Schedule:** extra L/T/P for the own subject via EXTRA_* events **[C]** — when the
  slot has no timetable session that date, the synchronizer creates a standalone extra
  session; when it has one, an outcome is written.
- **Cancel:** CLASS_CANCELLED for the own subject **[C]** — outcome CANCELLED on the
  shared anchor session when the slot has a session; no-op otherwise.
- **Modify:** CLASS_MODIFIED for the own subject **[C]** — MODIFIED outcome.
- **Surprise Quiz:** SURPRISE_QUIZ for the own subject **[C]** (quiz-day/eligibility
  pipeline untouched).
- **Manage class sessions:** no direct session edits — outcomes only, via events (the
  reconciler stays canonical; no per-student sessions are ever created **[C]**).
- **View attendance:** roster attendance read [P].
- **View analytics:** subject-scoped analytics [P].
- **Quiz-related events:** subject-scoped QUIZ_DAY creation for the own subject is
  authorized by `can_mutate_event` **[C]**; slot-wide quiz-day scheduling stays
  HEAD-only.

**Isolation test (conceptual, verified against code paths):**

- BCS-058 admin creates SURPRISE_QUIZ: `can_access_subject(user, BCS-058)` exact match ⇒
  authorized; outcome row `(session, BCS-058, SURPRISE_QUIZ)` ⇒ BCS-058 students see a
  quiz; BCS-055 has no outcome ⇒ normal lecture; BCS-056 admin separately creates
  CLASS_CANCELLED ⇒ `(session, BCS-056, CANCELLED)` ⇒ BCS-056 students see cancelled.
  The DE-II brief case is fully representable **[C]**.
- The BCS-058 admin attempting `POST /events` with `subject_id=BCS-055` fails
  `can_access_subject` ⇒ 403 **[C]**. Attempting `elective_slot=ELECTIVE_II` (slot-wide)
  fails HEAD_ADMIN requirement ⇒ 403 **[C]**. No code path collapses subjects by slot.

---

## 12. Student Management Architecture

**PROPOSED** (no reassignment implemented in discovery).

Registration (existing, unchanged **[C]**): `POST /auth/register` collects name, roll
number (13-digit), password; branch/program, semester, section are currently
auto-resolved from the active session (single-semester/single-section guards; the UI
collects electives I/II — the full 9-step selection flow from the brief requires the
academic-structure management phases first, since multi-section/branch selection is not
supported by registration guards today). The Admin Portal is the authoritative
administrative surface **after** registration.

Admin workflow (Phase 24 targets):

- **Create:** HEAD-only flow creating the user with roll/name/password + section +
  compulsory enrollments + elective choices in one transaction (mirrors registration
  logic; service-level reuse of ElectiveResolver.validate_selection **[C]**).
- **Edit:** name corrections; password reset (flows exist as scripts today **[C]**).
- **Move section:** HEAD-only, confirmation-gated; must decide enrollment semantics
  (enrollments are subject-semester rows; a cross-semester move is structurally different
  from an intra-semester move). **[U] decision gate** on cross-semester moves.
- **Assign subsection:** HEAD-only; allowed but labeled inert (see §10).
- **Assign/change electives:** HEAD-only management of `StudentElectiveChoice` +
  ELECTIVE-type enrollments; changing a choice with historical attendance raises the
  elective-switch decision gate (§25). Safety: UNIQUE(user, elective_slot) and
  UNIQUE(user, subject_id) backstops **[C]**; the service must never delete attendance
  history.
- **Deactivate/reactivate:** **[U]** — requires an additive `users.is_active` (or
  equivalent) decision; login/registration guards must be updated consistently.
  DEFERRED until the gate is resolved; not guessed.
- **View academic context:** reuse `StudentContextService.get_context` **[C]** as the
  single context authority (placement, enrollments with COMPULSORY/ELECTIVE types,
  choices, inconsistencies list).
- **Legacy/unknown states:** represent honestly — unplaced students (section NULL),
  unassigned subsections, elective inconsistencies (the context service already exposes
  `inconsistencies` **[C]**); portal surfaces them as data-quality warnings, never
  auto-repairs.
- **Auditability:** every student mutation records who/when via `created_at/updated_at`
  baseline; richer audit trail deferred (§21).
- **Safety against accidental reassignment:** move/choice changes require explicit
  confirmation with before/after diff; scope admins (CLASS/ELECTIVE) can never mutate
  student identity/placement (matrix: NO).

---

## 13. Academic Structure Management

**PROPOSED** — HEAD-only CRUD over `AcademicSession / Semester / Section / Subsection`.

- Sessions: create (name, start, end), single `is_active` invariant — registration and
  ElectiveResolver catalog reads depend on exactly one active session **[C]**; deactivating
  a session requires confirmation and a successor.
- Semesters: create under a session; date ranges; the registration ambiguity guard
  (exactly one semester per session) must be surfaced as a warning when multiple semesters
  exist **[C]**.
- Sections: name unique per semester **[C]** (`uq_sections_semester_name`), `program`
  free-text (no Branch entity — Phase 23.1 gate open). Creating a second section in the
  active semester changes registration behavior (auto-assign becomes impossible) — the
  UI must warn.
- Subsections: create under a section (unique per section **[C]**); nullable
  max_strength (no fabricated default **[C]**); inert-use warning displayed.
- No destructive deletes of structure with dependents (sections with students/timetable;
  semesters with subjects) — soft-deactivation or refusal; policy gate §25.

---

## 14. Timetable Management Architecture

**CONFIRMED model facts** (what exists — nothing invented):

`timetable_entries`: `subject_id`, `day_of_week` (0–6), `start_time`, `end_time`,
`class_type` (L/T/P), `section_id`, `elective_slot` (nullable; slot entries keep the
anchor subject). The weekly grid is **recurring-only** — there are no effective-date
ranges, no room, no faculty, no subsection scope, and no per-entry exception fields.

**Sufficiency assessment:** the current model is sufficient for Phase 24's core editor:
per-section weekly L/T/P grid, elective slot entries carrying anchors, subject-scoped
reality (cancellations/extras/modification/quizzes) handled by the existing event
pipeline rather than entry exceptions. It is **not** sufficient for: rooms, faculty
assignment, subsection-differentiated schedules, or dated timetable versions — all
**DEFERRED**; each requires a later schema phase with its own decision gate. Do not
silently invent columns.

**PROPOSED editor design:**

- Grid: sections × weekdays × time slots; entry dialog = subject (semester-filtered),
  day, start/end (overlap validation per section), class type, elective slot marker
  (subject switcher constrained to the slot's catalog subjects; anchor default).
- Elective slot entries: ONE entry per slot per timeslot (anchor subject stored);
  the UI shows "shared slot (DE-I/DE-II)" — never six per-student copies.
- Scope behavior: HEAD edits any section; CLASS_ADMIN edits assigned sections
  (PROPOSED grant); ELECTIVE_ADMIN read-only for entries of the own subject's slot
  (they schedule via events, not the shared grid).
- Exceptions/cancellations/extras: NOT stored on entries — created as events that the
  synchronizer reconciles into sessions **[C]**.
- Backend: new admin timetable CRUD endpoints [P] with section-scope dependency
  (`require_class_scope` factory exists **[C]**); writes must re-run collision checks
  within the section.

---

## 15. Class Session / Occurrence Management

**CONFIRMED:** `class_sessions` (subject, date, class_type, is_extra, is_cancelled,
nullable timetable_entry link, elective_slot marker, designation) are **materialized
state** derived by `EventSessionSynchronizer` from timetable + active events;
reconciliation is idempotent and self-healing (deactivation re-derives; attendance-bound
extras preserved).

**PROPOSED portal surface:**

- Day/week browser per section (sessions of the section's subjects; elective sessions
  shown once per slot with their outcome composition: anchor + per-subject outcomes).
- Session detail: source (timetable entry / extra / quiz-day), designation
  (MID_SEM_PRACTICAL), effective outcome per subject, attendance counts (read-only).
- No direct mutation of `is_cancelled`/`is_extra`/designation through the portal —
  class reality flows through events (§18); mid-sem designation already has
  head-admin endpoints **[C]** (PUT/DELETE `/laboratory/{code}/mid-sem`).
- Class/session state management = viewing + event-driven change; "manage class/session
  state" in the matrix means this event-driven control, not row writes.

---

## 16. Elective Outcome Management

**CONFIRMED mechanism** (`backend/app/services/event_session_service.py:400-428,
725-810`; `backend/app/models/occurrence.py`):

- A subject-scoped event (elective_slot NULL, subject = a catalog elective subject) on a
  date whose slot has a timetable session ⇒ `OccurrenceOutcome(class_session_id,
  subject_id, outcome_type)` on the shared anchor session: CANCELLED (cancellations),
  SURPRISE_QUIZ / EXTRA_* (extras), MODIFIED (CLASS_MODIFIED). Cancellation wins over
  modification when both exist (Phase 23.8 ordering).
- Subjects without an outcome row follow the anchor session's own flags.
- UNIQUE(class_session_id, subject_id) — one outcome per (occurrence, subject) **[C]**.
- When the slot has no session that date: extras create a standalone extra session
  (elective_slot marked); cancellations are no-ops.

**PROPOSED portal UX for the shared-slot case:**

- The portal does NOT add a new "outcome writer" API. It renders the shared occurrence
  and offers per-subject outcome actions that create/deactivate the corresponding
  subject-scoped **events** (the authoritative declarative path). Direct
  `occurrence_outcomes` writes would bypass reconciliation and are rejected by design.
- UI sketch: select date → shared DE-II occurrence card → per-subject row
  (BCS-058 / BCS-055 / BCS-056) with effective state and actions
  (Mark Surprise Quiz / Cancel / Mark Modified / Clear via event deactivation), each
  action pre-authorized per the acting admin's scope (ELECTIVE_ADMIN sees only the own
  subject's row; HEAD sees all).
- The underlying architecture remains `timetable → class_session → occurrence_outcome`;
  never per-student sessions **[C]**.

---

## 17. Quiz Management

**CONFIRMED domain:**

- `QuizCycle` (number unique, label) + `EligibilityPolicy` (lecture_threshold,
  optional combined_threshold) per cycle; `QuizSchedule` (subject, cycle, elective_slot,
  nullable date, status SCHEDULED/UNRESOLVED/CANCELLED) with anchors BCS-054/BCS-058
  carrying the slot marker.
- QUIZ_DAY `AcademicEvent`s are derived from schedules (seed script pattern
  `seed_academic_events.py`; `materialize_quiz_day_sessions.py` materializes quiz-day
  sessions). Eligibility is computed by `eligibility_engine`/`EligibilityService` from
  attendance vs policy.
- Authorization today: quiz-day **events** follow the event rules (subject-scoped QUIZ_DAY
  allowed for scoped admins; slot-scoped/global HEAD-only **[C]**). There is **no** API to
  manage `QuizSchedule`/cycles — seed scripts only.

**PROPOSED placement (no quiz-engine redesign):**

- **Quiz management area (portal):** manage cycles (create/close), policies (set
  thresholds at cycle creation), schedules (set/clear dates, CANCELLED status) — HEAD
  only [P]; plus schedule→QUIZ_DAY derivation parity with the seed semantics (a schedule
  with a date must yield the same QUIZ_DAY event the scripts produce).
- **Timetable/session management:** owns the sessions the quiz-day materializer creates
  (display), not quiz semantics.
- **Event management:** owns subject-scoped SURPRISE_QUIZ events (class-reality,
  eligible to scoped admins **[C]**) and slot-scoped QUIZ_DAY (HEAD).
- **Eligibility interaction:** unchanged — the engine reads schedules + attendance;
  portal reads display results; elective-specific differences already resolve per-student
  through choice resolution **[C]**.

---

## 18. Event Management

**CONFIRMED type inventory** (`EventType`, `event_registry.py` rules) and scoping:

| Category | Types | Scoping |
|---|---|---|
| Closures/holidays | HOLIDAY (consolidated), PUBLIC/INSTITUTE/FESTIVAL_HOLIDAY, EMERGENCY_CLOSURE, SEMESTER_BREAK, MID_SEMESTER_BREAK | Global (subject NULL) → HEAD only **[C]** |
| Working-day overrides | WORKING_DAY_OVERRIDE, WORKING_SATURDAY | Global → HEAD only **[C]** |
| Extra classes | EXTRA_LECTURE / EXTRA_TUTORIAL / EXTRA_PRACTICAL | Subject-scoped: scoped admins + students (enrolled); slot-scoped: HEAD **[C]** |
| Cancellation | CLASS_CANCELLED, LAB_CANCELLED (practical-only) | Same as extras **[C]** |
| Class modification | CLASS_MODIFIED | Subject-scoped ONLY (registry rejects slot) → scoped admins/students **[C]** |
| Quiz | SURPRISE_QUIZ (subject), QUIZ_DAY (subject or slot) | Subject-scoped: scoped admins/students; slot: HEAD **[C]** |
| Lab reality | MID_SEM_PRACTICAL | Subject-scoped; students may record **[C]** |

**PROPOSED portal organization:** a single Events area with type-family filters and a
creation wizard that enforces the same registry validation client-side (mirroring
`EventFormDialog` behavior) while the backend stays authoritative. Global = HEAD;
section = CLASS via subject scope; slot = HEAD; concrete-subject = ELECTIVE_ADMIN/CLASS.
All lifecycle through POST/PATCH/DELETE `/events` untouched **[C]**.

---

## 19. Attendance / Analytics Administration

**CONFIRMED:** all existing attendance/analytics reads are self-scoped; the only
mutation is the student's self-mark (`POST /attendance` pins `user_id =
current_user.id`); outcome-aware rejection (CANCELLED) exists (Phase 23.9). There is no
administrative attendance correction path today.

**PROPOSED:**

- **Views (additive):** admin attendance reads per student (scope-checked), per subject
  roster, per section aggregates — built on `AttendanceService`/repo patterns; HEAD
  global, CLASS sections, ELECTIVE own-subject roster.
- **Correction (new, high-impact):** an admin mutation endpoint that records/corrects a
  student's attendance for a specific class_session **with**:
  authorization before mutation (scope on the session's subject + student's placement),
  CANCELLED-outcome rejection parity, idempotent upsert semantics where applicable,
  explicit confirmation UI, and reason capture. Policy details (who may correct what,
  retroactive windows, immutable history vs correct-in-place) = **decision gate §25**;
  discovery records the shape, not the verdict.
- **Analytics:** new admin aggregate reads reusing `AnalyticsService` computation
  patterns; the portal never recomputes attendance math client-side (existing frontend
  principle **[C]**).
- **System-wide monitoring:** health endpoint + feedback admin surface now; deeper
  monitoring [P].

---

## 20. API Gap Analysis

**Reusable as-is (no change):** `POST/PATCH/DELETE /events`, `GET /events`,
`GET /calendar/{date}`, `GET /feedback/admin*`, laboratory experiment + mid-sem head-admin
endpoints, `POST /auth/login`, `POST /feedback`, `GET /health`.

**Endpoints requiring additive changes (extend, don't replace):**
- `GET /subjects` — admin variant parameters (semester scoping, catalog detail). 
- `GET /student/me` identity contract — the portal needs a **new** admin identity read
  (below) rather than changing the student contract.
- Notification/analytics patterns — add admin-scoped variants alongside existing
  self-scoped endpoints (same services, scope-filtered).

**Genuinely new endpoints required (PROPOSED, grouped):**
1. **Admin identity:** `GET /api/v1/admin/me` — DB-resolved effective roles + scope list
   (section/subsection/subject descriptors). Required by every portal screen.
2. **Students:** list/search, detail (context), create, edit, move-section, assign
   subsection, elective-choice management, (deactivate — gated §25).
3. **Enrollment:** compulsory enrollment add/remove; elective-choice set/clear.
4. **Academic structure:** sessions/semesters/sections/subsections CRUD (read + write).
5. **Curriculum:** subjects CRUD + catalog (`elective_slot`) management.
6. **Timetable:** per-section weekly entry CRUD (+ collision validation).
7. **Class sessions/occurrences:** read models (day/week/detail with outcome
   composition). No write endpoints (event-driven only).
8. **Quizzes:** cycles/policies/schedules management (+ derivation parity).
9. **Attendance administration:** scoped attendance reads + correction mutation.
10. **Analytics administration:** scoped aggregate reads.
11. **Admin management:** admin account list/create/provision; scope assign/revoke/
    activate (admin_scopes writes); audit-ish activity reads.
12. **Optional schema-dependent:** user deactivation (if the gate lands).

**Endpoints that should NOT be created** because an existing service already provides the
authoritative behavior:
- **No direct `occurrence_outcomes` mutation API** — the event pipeline is canonical
  (§16).
- **No direct `class_sessions` mutation API** — sessions are materialized state (§15).
- **No elective resolution endpoint** — `ElectiveResolver` is in-process; resolution is
  embedded in existing reads **[C]**.
- **No new authorization/role endpoints** beyond scope management —
  `AuthorizationService` is the single authority **[C]**.
- **No student self-service change** — registration/`/student/me` stay student-facing.

---

## 21. Data Safety & Auditability

**Design requirements for all administrative mutations (PROPOSED standards):**

1. Authorization before any side effect (validate → authorize → mutate, the
   EventService pattern **[C]**).
2. Scope enforcement server-side per request; never trust client role/scope **[C]**.
3. No cross-section / cross-subject access — the Phase 23.11 checks are the boundary.
4. No accidental student reassignment: move/choice flows require before/after diff +
   explicit confirmation; UNIQUE constraints as backstops **[C]**.
5. No fabricated subsection assignment; no invented fields.
6. Deterministic, idempotent behavior where applicable (mirror the reconciler's
   idempotent re-derivation discipline **[C]**).
7. Transactions: single commit per logical operation, rollback on failure (existing
   service pattern **[C]**).
8. Destructive/high-impact actions (structure changes, scope revocation, corrections,
   student moves) require typed confirmation and are refusal-first when dependents exist.
9. **Audit trail:** today the only history is row `created_at/updated_at` (+ lab record
   audit fields) **[C]**. Initial portal phases can rely on this baseline plus
   server-side logging; a dedicated append-only `audit_log` (actor, action, target,
   before/after) is a **new architecture** proposed as its own later sub-phase/decision
   gate — not silently retrofitted.

---

## 22. Main App vs Admin Portal Boundary

**PROPOSED — two clearly separated surfaces sharing one backend:**

- **MAIN APP (student, frozen shape):** registration/login, dashboard, Track,
  timetable, attendance, quizzes, calendar, analytics, notifications, PWA mobile
  experience — `(auth)` + `(authenticated)` route groups unchanged.
- **ADMIN PORTAL:** administrative control, configuration, scheduling, student
  management, admin management, event/quiz management, occurrence control, monitoring —
  a new `(admin)` route group + `/admin` URL namespace + admin API namespace
  (`/api/v1/admin/*`), sharing the same JWT auth, `apiFetch`, SWR patterns, and design
  tokens but with its own shell (sidebar, desktop-first) rather than the student
  AppShell. The two are never merged for convenience; shared code lives in
  `components/ui`, `lib`, `hooks` only.

---

## 23. Responsive / PWA Strategy

**PROPOSED — desktop-first responsive web, separate shell, shared component system; no
separate PWA for the portal initially.**

Rationale from the repository: the existing PWA (`manifest.json` start_url `/dashboard`,
portrait orientation, service worker, install prompts) is explicitly tuned to the student
experience; the admin portal's density (tables, grids, matrices) is desktop-first.
Reuse `components/ui` primitives, tokens, `apiFetch`, SWR hooks; make the admin shell
responsive (usable on tablet) but do not register a second manifest/service worker in
Phase 24. A future installable admin PWA remains possible without conflict (UNKNOWN →
not planned).

---

## 24. Phase 24 Implementation Sequence (PROPOSED)

Ordering principle: identity/shell first; reads before writes; structure before
timetable; timetable before session operations; admin management and hardening last.
Merge/split only with repository evidence.

| # | Phase | Objective | Dependencies | Schema | Backend | Portal | Verification | Production boundary |
|---|---|---|---|---|---|---|---|---|
| 24.1 | Admin identity & portal shell | `GET /admin/me` (DB-resolved roles/scopes); `(admin)` route group, AdminShell, role-gated nav, login reuse | none | none | additive identity endpoint | shell + auth guard | endpoint verifier + tsc | additive only |
| 24.2 | HEAD dashboard & read-only overview | aggregate counts, data-quality warnings; reuse feedback admin | 24.1 | none | 1–2 read endpoints | dashboard screens | verifier | additive |
| 24.3 | Student management (read) | scoped student list/search/detail via StudentContextService | 24.1 | none | student read endpoints | students area (scoped) | verifier | additive |
| 24.4 | Student management (write) | create/edit/move-section/subsection-assign/elective choices with confirmations | 24.3, decision gates §25 (deactivation, cross-semester move) | possibly `users.is_active` (gate) | student mutation endpoints | mutation flows | verifier | migration if gate lands |
| 24.5 | Academic structure management | sessions/semesters/sections/subsections CRUD | 24.1 | none (tables exist) | structure endpoints | structure area | verifier | additive |
| 24.6 | Curriculum & subjects | subjects CRUD, elective catalog, experiment catalog reuse | 24.5 | none | subject endpoints | curriculum area | verifier | additive |
| 24.7 | Timetable management | per-section weekly CRUD + collision checks | 24.5, 24.6 | none (deferred fields gate) | timetable admin endpoints | timetable editor | verifier | additive |
| 24.8 | Class sessions & occurrences | day/week/detail read models with outcome composition | 24.7 | none | session read endpoints | sessions area | verifier | additive |
| 24.9 | Elective outcome controls | per-subject outcome UX on shared occurrences (event-driven) | 24.8 | none | none new (reuse /events) | outcome control UI | verifier | no schema |
| 24.10 | Quiz management | cycles/policies/schedules management + QUIZ_DAY derivation parity | 24.6 | none | quiz admin endpoints | quiz area | verifier | additive |
| 24.11 | Event management consolidation | holidays/closures/overrides + scoped event UX | 24.8 (can parallel 24.9/24.10) | none | none new | events area | verifier | additive |
| 24.12 | Admin management & scopes | admin accounts, scope assign/revoke/activate, provisioning workflow | 24.1, gates §25 | none (table exists) | admin-mgmt endpoints | admins area | verifier | additive |
| 24.13 | Attendance admin & analytics | scoped attendance reads + correction (gate), admin analytics | 24.3, 24.8 | audit_log if gate lands | attendance/analytics endpoints | attendance/analytics areas | verifier | migration if gate lands |
| 24.14 | Integration & hardening | end-to-end consistency, migration gate, regression, docs | all | — | — | — | full verifier suite | operator-gated |

---

## 25. Blockers / Decision Gates (must be resolved before the dependent phase — no guessing)

1. **Subsection-aware scheduling** — blocks all SUBSECTION_ADMIN functionality and any
   subsection timetable/session feature. Schema direction unknown; dedicated design phase
   required.
2. **Section/subsection assignment semantics** — what moving a student implies for
   enrollments, elective choices, attendance history; intra- vs cross-semester moves.
3. **Branch/program hierarchy** — `Section.program` is free text; no Branch entity
   (Phase 23.1 gate open); affects structure UI and future multi-branch sections.
4. **Student elective switching** — changing `StudentElectiveChoice` after attendance
   exists has undefined historical semantics; needs an explicit policy before 24.4.
5. **Student deactivation** — requires an additive activation flag + login/registration
   guard updates, or explicit deferral.
6. **Audit logging** — append-only audit-log table (new architecture) vs
   `created_at/updated_at` baseline; needed before high-impact corrections ship (24.13).
7. **Destructive action policy** — which structure deletes are permitted at all;
   soft-deactivation standards.
8. **Admin provisioning workflow** — today script-only (`provision_admin.py`,
   `set_initial_password.py` **[C]**); the portal needs an account-creation + password
   bootstrap design (invite flow vs admin-set password).
9. **Production migration strategy** — operator procedure documented in Phase 23.12,
   **not executed**; any Phase 24 schema change must follow that procedure.
10. **Multi-section-per-semester session scoping** — `class_sessions` has no section_id;
    section attribution relies on timetable linkage; currently one section exists
    **[C]**. Before multiple sections share a semester, session read scoping must be
    designed (gate, not redesign).
11. **CLASS_ADMIN semester-wide subject breadth** — frozen semantic **[C]**; if product
    intent is narrower, that is a Phase 23.11 amendment decision — NOT a Phase 24
    invention.
12. **Settings area justification** — whether any real system configuration belongs in
    the portal (UNKNOWN; do not build a settings page without concrete settings).

---

## 26. Risks

- **Client-trusted role drift:** existing UI checks `profile.role === "ADMIN"` (legacy).
  The portal must rely on `/admin/me` + backend gates; leaving legacy checks in student
  surfaces is acceptable (backend remains authoritative) but new code must not copy the
  pattern.
- **Legacy `require_admin` misuse:** unused today **[C]**; new endpoints must use the
  Phase 23.11 factories, never `require_admin`.
- **Reconciliation bypass temptation:** direct session/outcome writes would corrupt the
  canonical pipeline; the design explicitly forbids them.
- **Fabricated subsection data:** any seeding of subsections without authoritative
  source violates Phase 23.0 Correction 9; keep inert.
- **Timetable model gaps:** room/faculty/subsection/versioning absences may tempt
  column invention; all DEFERRED to gated schema phases.
- **Registration ambiguity changes:** creating a second section/semester changes
  self-registration behavior (guards return 409 **[C]**); structure changes must warn.
- **Quiz-day derivation parity:** portal-managed schedules must reproduce seed-script
  semantics exactly or quiz-day sessions diverge.
- **Elective isolation regression:** any future "convenience" broadening of
  `can_access_subject` for ELECTIVE_ADMIN would break the six-scope model; frozen.
- **Migration risk:** additive-only migrations; Phase 23.12 gate procedures apply.

---

## 27. Non-Goals

- No implementation of any portal screen or endpoint in Phase 24.0.
- No new role/scope/permission/resolver system (Phase 23.11 is final).
- No subsection scheduling semantics fabrication.
- No timetable field invention (room/faculty/subsection-scope/versioning).
- No per-student session duplication for UI convenience.
- No quiz-engine, attendance-engine, calendar-engine redesign.
- No production deployment/migration; no destructive DB operations.
- No browser/E2E runs; no commits/PRs.
- No student-app redesign; the two surfaces stay separate.

---

## 28. Recommended Next Phase

**Phase 24.1 — Admin Portal Shell & Admin Identity** (PROPOSED): the additive
`GET /api/v1/admin/me` identity endpoint (DB-resolved effective roles and scopes) plus
the `(admin)` frontend route group with its own desktop-first shell and auth guard,
reusing login, `apiFetch`, SWR, and UI primitives. It unblocks every later slice,
requires no schema change, and carries no decision-gate dependency. Decision gates §25.2,
§25.4–§25.8 should be resolved (in operator review) before their dependent phases
(24.4, 24.12, 24.13), not before 24.1.

---

## Appendix A — Evidence: exact files inspected (read-only)

**Backend — live code:** `backend/app/main.py`; `backend/app/api/api.py`;
`backend/app/api/v1/router.py`; `backend/app/api/dependencies/deps.py`;
`backend/app/api/v1/endpoints/{auth,student,subjects,timetable,attendance,quiz,calendar,events,laboratory,dashboard,analytics,feedback,preferences,notifications}.py`;
`backend/app/models/{academic,admin_scope,user,enums,timetable,occurrence,quiz,event}.py`;
`backend/app/db/base_class.py`;
`backend/app/services/{authorization_service,event_service,event_session_service,event_registry,elective_resolver,student_context_service}.py`;
`backend/scripts/{provision_admin,seed_academic_baseline,verify_phase_22_4}.py`.

**Migrations:** all 25 files in `backend/alembic/versions/` (revision/down_revision
extraction; chain walk to single head `f9a0b1c2d3e4`); detailed read:
`f9a0b1c2d3e4_add_admin_scopes.py`.

**Frontend:** `frontend/src/app/*` (route groups, layouts);
`frontend/src/lib/api.ts`; `frontend/src/hooks/useApi.ts`;
`frontend/src/contexts/AuthContext.tsx`; `frontend/src/components/layout/{AppShell,TopNav,MobileBottomNav}.tsx`;
`frontend/src/components/ui/*` inventory; `frontend/src/components/shared/*`;
`frontend/src/components/shell/*`; `frontend/src/components/{events,dashboard,notifications,quiz}/*`;
`frontend/public/manifest.json`; grep-level admin-usage survey of all `.tsx`.

**Governance (current state):** `MASTER_ROADMAP.md`, `implementation_plan.md`,
`task.md`, `walkthrough.md` (Phase 23 completion records; Phase 24 pending markers).

**Verification performed in this phase:** repository inspection; full route inventory
(41 endpoints); model/service/dependency tracing; migration-head inspection (25-revision
linear chain, head `f9a0b1c2d3e4`); static consistency checks between matrix claims and
authorization code. No DB connection was required; no tests, no browser, no mutations.

## Appendix B — Exact route list (41)

auth: `POST /api/v1/auth/login`, `POST /api/v1/auth/register` —
student: `POST /api/v1/student/sync`, `GET /api/v1/student/me`,
`GET|PUT /api/v1/student/preferences` —
subjects: `GET /api/v1/subjects` — timetable: `GET /api/v1/timetable` —
attendance: `GET /api/v1/attendance/history`, `GET /api/v1/attendance/daily/{date}`,
`GET /api/v1/attendance/summary/{subject_code}`, `POST /api/v1/attendance` —
quiz: `GET /api/v1/quiz-eligibility/current-cycle`,
`GET /api/v1/quiz-eligibility/{subject_code}/{cycle}` —
calendar: `GET /api/v1/calendar`, `GET /api/v1/calendar/today`,
`GET /api/v1/calendar/{date}` —
events: `GET|POST /api/v1/events`, `PATCH|DELETE /api/v1/events/{event_id}` —
laboratory: `GET /api/v1/laboratory/{subject_code}/summary`, `/experiments`,
`/records`, `/activity`, `/mid-sem`; `POST /api/v1/laboratory/{subject_code}/records`;
`PATCH|DELETE /api/v1/laboratory/{subject_code}/records/{record_id}`;
`POST /api/v1/laboratory/{subject_code}/experiments`;
`PATCH|DELETE /api/v1/laboratory/{subject_code}/experiments/{experiment_id}`;
`PUT|DELETE /api/v1/laboratory/{subject_code}/mid-sem` —
dashboard: `GET /api/v1/dashboard/summary` — analytics: `GET /api/v1/analytics/overview` —
feedback: `POST /api/v1/feedback`, `GET /api/v1/feedback/admin`,
`GET /api/v1/feedback/admin/{feedback_id}` —
notifications: `GET /api/v1/notifications`, `PATCH /api/v1/notifications/{notification_id}`.

**END OF PHASE 24.0 DISCOVERY REPORT — HARD STOP. Phase 24 implementation NOT STARTED.**
