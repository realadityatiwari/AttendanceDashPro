# SYSTEM FUNCTIONAL BACKEND AUDIT REPORT — AttendanceDashPro

**Audit type:** READ-ONLY FORENSIC DISCOVERY (no code, DB, migration, seed, config, or environment changes were made; no migrations run; no seeds executed; no verifier scripts that mutate were run)
**Audit date:** 2026-09-29 (Asia/Kolkata)
**Code state audited:** working tree at commit `da4f4a1` ("feat(sessions): add deactivated-extra lifecycle with provenance tracking") plus uncommitted audit tooling only
**DB state audited:** local PostgreSQL `attendancedash` (docker `attendancedashpro_db`), alembic revision **`e2f3a4b5c6d7` (head)**
**Evidence method:** full source read (backend `app/`, `alembic/versions/`, `scripts/`, `tests/`; frontend `lib/`, `contexts/`, key components; deploy configs) + strictly SELECT-only database probes (`backend/scripts/audit_ro_db.py`, `backend/scripts/audit_ro_notifications.py` — new files created as audit artifacts, SELECT-only)

---

## A. EXECUTIVE SUMMARY

The system is in materially good architectural health. The three pillars the roadmap demands — **one canonical elective resolver**, **one canonical attendance/eligibility math core**, and **expected-timetable vs actual-occurrence separation** — are real, not aspirational:

- Elective resolution flows through `ElectiveResolver` + per-user `StudentElectiveChoice` joins in every read path; database forensics found **zero** slot mismatches, zero anchor-leak enrollments, and zero phantom enrollments (27 enrollments, all invariant-conformant: 21 COMPULSORY + 6 ELECTIVE across 3 enrolled users).
- Attendance math is pooled L+T in one implementation (`attendance_engine.pooled_pct`); eligibility, forecast, optimizer, and dashboard all consume it. ERP overall (Σattended/Σrecorded) is a separate, documented, deliberate formula.
- `class_sessions` is the actual-occurrence table; `timetable_entries` is the expected schedule; `occurrence_outcomes` provides per-subject overrides with a DB-enforced UNIQUE key. The 702 sessions, 18 quiz-day sessions, and 1 canonical MODIFIED outcome row are internally consistent.
- AuthZ is DB-authoritative per request (never from JWT claims), refresh tokens are hashed + rotating with family revocation, and registration is transactional with the Chunk-16 centralized enrollment invariant.

No CRITICAL (data-corrupting or authorization-bypassing) defect was confirmed. However, the audit confirms **5 HIGH and 13 MEDIUM** issues, the most consequential being:

1. A **policy-interpretation conflict with the supplied academic notice**: Cycle I's 70% threshold is applied to *both* Criterion I and Criterion II, while the notice ties 70% to the first criterion of Cycle I (75% thereafter) — and the relaxation framework (activity participation) is not implemented at all.
2. **Deactivation does not end sessions**: `get_current_user` never checks `users.is_active`, so a deactivated account keeps full API access for up to 8 hours (access-token lifetime).
3. **Elective correction silently re-attributes attendance history**: changing a student's elective choice leaves their AttendanceRecords on the shared slot sessions, which immediately count toward the *new* subject's statistics — historical meaning is not immutable across choice changes.
4. **Notification inbox pollution (DB-proven)**: 452 of 465 notification rows are ACADEMIC_EVENT projections whose `event_id` no longer exists — verifier fixtures emitted notifications to real users, then cleanup hard-deleted the events but not the notifications. The owner's inbox holds 182 unread ghosts.
5. **Effective quiz-cycle numbering is re-derived chronologically** from QUIZ_DAY event dates, ignoring the QuizSchedule cycle label — an out-of-order date edit silently renames cycles for every eligibility read.

The report separates, per finding: what the system currently does, what the architecture/academic sources require, what is actually broken, and what is only a risk.

---

## B. CURRENT ARCHITECTURE MAP

Layering is consistent throughout: `endpoint → service → repository → SQLAlchemy → PostgreSQL`, with pure engines (`engines/`) consumed by services and never touching the DB.

| Domain | API entry (prefix /api/v1) | Service(s) | Repository/Engine | Tables |
|---|---|---|---|---|
| Authentication | `/auth` (login/register/refresh/logout) | `RefreshTokenService` | `core/security`, `core/rate_limit` | users, refresh_tokens |
| Student context | `/student/me`, `/student/sync` | `StudentContextService` (authoritative, read-only) | — | users, sections, subsections, semesters, academic_sessions, student_enrollments, student_elective_choices |
| Academic structure | `/admin/structure/*` | `AdminStructureService` | `AdminStructureRepository` | academic_sessions, semesters, sections, subsections |
| Subjects / catalog | `/subjects`, `/admin/subjects` | `AdminSubjectService` | `SubjectRepository`, `AdminSubjectRepository` | subjects |
| Electives | (embedded) | `ElectiveResolver` (single canonical resolver; `resolve_subject`, `load_choices`, `catalog_codes`, `anchor_subjects`) | — | student_elective_choices, subjects.elective_slot |
| Timetable (expected) | `/timetable`, `/admin/timetable` | `AdminTimetableService` | `TimetableRepository` | timetable_entries |
| Sessions / occurrences | (read layer of attendance) | `EventSessionSynchronizer` (event→session reconciliation) | `SessionRepository`, `practical_occurrence` engine | class_sessions, occurrence_outcomes |
| Events | `/events`, `/admin/events` | `EventService` + `event_registry` + `AdminEventService` | `EventRepository`, `CalendarRepository` | academic_events |
| Attendance | `/attendance` (daily/history/summary/POST) | `AttendanceService` | `AttendanceRepository`, `attendance_engine`, `practical_occurrence` | attendance_records, class_sessions |
| Quiz / eligibility | `/quiz-eligibility`, `/admin/quizzes` | `EligibilityService`, `eligibility_engine`, `calendar_engine` (windows), `AdminQuizService` | `QuizRepository` | quiz_cycles, eligibility_policies, quiz_schedules, academic_events (QUIZ_DAY) |
| Safe skip / optimizer | (fields on attendance summary + eligibility) | `attendance_engine.optimize_attendance` (single implementation) | — | — |
| Dashboard | `/dashboard/summary` | `DashboardService` (pure consumer) | Attendance/Eligibility/Calendar services | (aggregates) |
| Analytics | `/analytics/overview` | `AnalyticsService` (pure consumer) | AttendanceService | (aggregates) |
| History / Track | `/attendance/history`, `/attendance/daily/{date}` | `AttendanceService` | `AttendanceRepository` | class_sessions, attendance_records |
| Calendar | `/calendar`, `/calendar/today`, `/calendar/{date}` | `CalendarService` | `CalendarRepository`, `calendar_engine` | academic_events |
| Notifications | `/notifications` (read-only inbox + PATCH state) | `NotificationService` (emit boundary, mutation triggers, callable sweep) | `NotificationRepository`, `PushDispatchService` | notifications, push_subscriptions |
| Laboratory | `/laboratory/*` | `LaboratoryService` | `LaboratoryRepository`, AttendanceService | laboratory_experiments, laboratory_records |
| Feedback | `/feedback`, `/feedback/admin` | `FeedbackService` | `FeedbackRepository` | feedback |
| Preferences | `/student/preferences` | `PreferenceService` | `PreferenceRepository` | userpreferences |
| Admin identity / RBAC | `/admin/me`, `/admin/admins/*` | `AuthorizationService` (single authority) | `AdminAdminRepository` | admin_scopes, users |
| Admin attendance analytics | `/admin/attendance/*` | `AdminAttendanceService` | `AdminAttendanceRepository` | (aggregates) |
| Admin dashboard | `/admin/dashboard` | `AdminDashboardService` | `AdminDashboardRepository` | (aggregates) |

**Frontend consumption:** Next.js app router; `lib/api.ts` is the single fetch boundary (production URL guard, single-flight refresh, 401/403 handling); SWR keys `PROFILE_KEY`/`NOTIFICATIONS_KEY` shared across consumers; `AuthContext` clears the entire SWR cache on logout (cross-user isolation). Presentation components (`SubjectAttendanceCard`, `QuizEligibilityCard`) render backend fields; no attendance/eligibility math is recomputed in React (one presentation-only threshold coloring in `QuizEligibilityCard`, see L-7). `components/events/eventRules.ts` is an explicit, documented frontend mirror of `event_registry.py` used only for form shaping — the backend registry remains authoritative.

**Background processes:** none. No scheduler exists; notifications are generated by mutation triggers and an unscheduled callable sweep. Push delivery is synchronous best-effort inside the mutating request.

**Caches:** one — a 60s per-user in-process notification TTL cache. No server-side query/context caching.

---

## C. SOURCE-OF-TRUTH MAP

| Value | Authoritative source | Derived/consumers | Divergences found |
|---|---|---|---|
| Quiz dates | **Active `QUIZ_DAY` AcademicEvents** (Phase 2) | eligibility windows, current-cycle pick, dashboard snapshot, admin projection `quiz_schedules` | H-5 (cycle numbering re-derived chronologically), M-6 (first_quiz_date ignores slot resolution) |
| `quiz_schedules` | Derived seed-time projection/plan of the above | admin CRUD surface, verifier compat | — |
| Elective selection | `StudentElectiveChoice` (+ DB catalog `subjects.elective_slot`) | every read via `ElectiveResolver` / per-user choice joins | M-9 (registration re-implements catalog validation inline), H-3 (choice change re-attributes history) |
| Enrollment | `student_enrollments` (`enrollment_type` explicit on new writes) | subject list, dashboard, eligibility, notifications, admin scope | M-2 (no defensive read boundary), M-3 (type-vs-slot not DB-enforced) |
| Actual occurrence | `class_sessions` (+ `occurrence_outcomes` per-subject overrides, `is_deactivated` lifecycle) | every attendance/history/track/calendar/dashboard/analytics read | — |
| Expected schedule | `timetable_entries` (`is_active`, subsection scope) | student timetable endpoint, synchronizer, expansion | — |
| Day semantics (working/closure/substitution) | `calendar_engine.get_academic_day` (single implementation) | calendar, synchronizer, dashboard, eligibility windows | — |
| Attendance % (subject) | `attendance_engine.pooled_pct` — pooled L+T, count-level | subject summaries, forecast, optimizer, eligibility | — |
| ERP overall % | Σ attended / Σ recorded (occurrence level) | dashboard overall, analytics, admin analytics, history summary | Distinct from pooled formula **by design** (documented); not a defect |
| Eligibility thresholds | `eligibility_policies.lecture_threshold` (engine 70/75/75 only as fallback) | both criteria | H-1 (policy interpretation; `combined_threshold` column unused) |
| Attendance status | `attendance_records` (UNIQUE user+session) | all reads; cancelled/deactivated handled at occurrence layer | L-1 (explicit PENDING accepted) |
| Notification state | `notifications` rows (DB idempotency key) | inbox, push side-channel | H-4 (orphaned projections) |
| Academic context | `StudentContextService` (single resolver) | profile, history bounds, calendar clamp, dashboard, analytics, quiz | — |

---

## D. DATABASE / SCHEMA AUDIT

Live DB observed: 4 users (1 ADMIN `2401220100027`, 3 STUDENT incl. new `7777777777777` with canonical 052/055 enrollments and choices), 1 session/semester/section, 13 subjects (slot markers exactly match tags), 28 timetable entries (no duplicates, no slot/subject contradictions), 702 class_sessions (all `is_cancelled=false`, `is_deactivated=false`; 18 unlinked quiz-day sessions; 0 with event provenance), 43 attendance records (none on cancelled/deactivated/future sessions), 27 enrollments, 8 choices (0 slot mismatches), 18 events (all active QUIZ_DAY), 3 cycles/policies (70/75/75), 18 quiz schedules (1:1 active-event coverage), 1 occurrence outcome (canonical MODIFIED BCS-058 2026-09-23), 465 notifications, 6 refresh tokens.

**DATABASE-ENFORCED INVARIANTS (verified present):**
- `attendance_records` UNIQUE(user_id, class_session_id)
- `student_enrollments` UNIQUE(user_id, subject_id); `student_elective_choices` UNIQUE(user_id, elective_slot)
- `subjects` UNIQUE(code, semester_id); `sections` UNIQUE(semester_id, name); `subsections` UNIQUE(section_id, name) + UNIQUE(section_id, id)
- `occurrence_outcomes` UNIQUE(class_session_id, subject_id)
- `notifications` UNIQUE(user_id, kind, occurrence_key); `push_subscriptions` UNIQUE(endpoint)
- `timetable_entries` CHECK(end_time > start_time), CHECK(day_of_week 0..6), composite FK (section_id, subsection_id) → subsections(section_id, id)
- `admin_scopes` CHECK role-scope shape (`ck_admin_scopes_role_scope`)
- `laboratory_experiments` UNIQUE(subject_id, experiment_number); `laboratory_records` UNIQUE(user_id, experiment_id)

**APPLICATION-ENFORCED ONLY (no DB backstop) — a direct write, race, or future writer can violate each:**
1. `enrollment_type` consistency: nothing prevents a COMPULSORY enrollment on an elective-catalog subject, or an ELECTIVE enrollment without a matching choice (chunk-15's phantom mechanism is only *conventionally* closed).
2. `student_elective_choices.subject_id` must be a slot-matching elective subject (validated only at registration / `correct_elective`).
3. `quiz_schedules` UNIQUE(subject_id, quiz_cycle_id) — guarded app-side only (`schedule_exists_for_subject_cycle`); a race creates duplicate cycle schedules.
4. At most one active `academic_sessions` (409 in service only).
5. Timetable overlap/conflict detection (same section/day/overlapping time) — pure application logic; concurrent creates can both commit.
6. AcademicEvent duplicate guard (`exists_active_duplicate`) — application-level; race-window duplicates possible; identity ignores `elective_slot` (see L-8).
7. QUIZ_DAY event ↔ schedule synchronization (no constraint ties them).
8. `subsections.max_strength` capacity (`assign_subsection` count-then-set race, L-4).
9. Registration's single-semester/single-section auto-assignment assumptions (structure service warns; DB allows multiples).

**Missing indexes (DB-confirmed): 27 FK columns have no leading-column index**, including hot paths: `class_sessions.subject_id`, `class_sessions.timetable_entry_id`, **`class_sessions.date` (no index at all — the most-filtered column in the system)**, `attendance_records.class_session_id`, `student_enrollments.subject_id`, `student_elective_choices.subject_id`, `academic_events.subject_id`, `quiz_schedules.subject_id/quiz_cycle_id`, `timetable_entries.section_id/subject_id/subsection_id`, `users.section_id/subsection_id`, `admin_scopes.*`, `laboratory_records.*`, `feedback.user_id`, `occurrence_outcomes.subject_id`, `semesters.session_id`, `subjects.semester_id`, `eligibility_policies.quiz_cycle_id`. Harmless at current volumes (702 sessions), a real cost at multi-semester scale (M-7).

**Soft-delete / immutability posture (good):** events deactivate (`active`), timetable entries deactivate (`is_active`), deactivated attended extras preserve rows (`is_deactivated`), quiz-day unattended sessions are the only event-reversible deletions, sessions with attendance are never deleted except the documented explicit CLASS_CANCELLED propagation. No dangerous cascades exist (all FKs are RESTRICT-by-default; no ON DELETE CASCADE found in migrations).

**Cross-semester/section/subsection/elective leakage:** every student read joins `StudentEnrollment` on the resolved subject; timetable is section-scoped with subsection exclusion in `TimetableRepository.get_weekly_entries_for_student`; elective attribution is per-user. No leakage path found with current data. The boundary is *enrollment-row trust* (M-2), not a schema rule.

---

## E. MIGRATION AUDIT

- **Chain (single linear, no branches):** `7117a007a0da` → `8a2b3c4d5e6f` → `c3d4e5f6a7b8` → `d4e5f6a7b8c9` → `e5f6a7b8c9d0` → `a1b2c3d4e5f6` → `f1a2b3c4d5e6f` → `f6a5b4c3d2e1f` → `a7b8c9d0e1f2` → `b1c2d3e4f5a6` → `b1c2d3e4f5a7` → `c1d2e3f4a5b6` → `d1e2f3a4b5c6` → `e1f2a3b4c5d6` → `f2e3d4c5b6a7` → `a3b4c5d6e7f8` → `b7c8d9e0f1a2` → `c8d9e0f1a2b3` → `d0e1f2a3b4c5` → `e3f4a5b6c7d8` → `f5a6b7c8d9e0` → `f6a7b8c9d0e1` → `f7a8b9c0d1e2` → `f8a9b0c1d2e3` → `f9a0b1c2d3e4` → `eb880e108f19` → `c4d5e6f7a8b9` → `a9b8c7d6e5f4` → `f0e1d2c3b4a5` → **`e2f3a4b5c6d7` (head, applied)**.
- **Destructive steps:** only legacy-Firebase removal (`e1f2a3b4c5d6` drop `firebase_uid` column) — pre-meditated replacement of the auth system, documented. All other migrations are additive with deterministic, guarded backfills (duplicate-count pre-checks that *refuse* to run rather than corrupt — `c8d9e0f1a2b3`).
- **Nullable → non-null transitions:** `student_enrollments.enrollment_type` (e3f4…) uses server_default + backfill before NOT NULL — correct. `users.hashed_password` remained nullable by design (script-provisioned accounts).
- **Backfill correctness notes:** `e3f4a5b6c7d8` backfills ELECTIVE via a join on `subjects.tag IN ('Elective-I','Elective-II')` — deterministic today, but tag-coupled (tag is now "informational only" per 23.5; a future tag edit would have made the historical backfill miss rows; frozen-history caveat only). `f5a6b7c8d9e0` backfills `subjects.elective_slot` from tag — same 1:1 mapping, verified live.
- **Rollback feasibility:** every migration has a symmetric `downgrade()`; none are practically irreversible except data created after the fact.
- **Model ↔ migration drift:** none found. All model columns/constraints (incl. `class_sessions.is_deactivated`/`source_event_id`, `timetable_entries.room/sort_order/is_active/subsection_id`, `subjects.elective_slot`, `admin_scopes`) are present in the applied chain, and the DB's constraint inventory matches.
- **Cosmetic defect (L-3):** `e2f3a4b5c6d7`'s docstring header claims `Revision ID: a7b8c9d0e1f2 / Revises: f0e1d2c3b4a5` — stale copy-paste (the actual identifiers in the file are correct; `a7b8c9d0e1f2` is the holiday migration). Confusing for forensics, zero runtime effect.
- **Config note:** `alembic.ini` hardcodes the dev URI `postgresql+asyncpg://postgres:postgres@localhost:55432/attendancedash` (dev-only credentials; redacted here deliberately). `alembic/env.py` was not exercised (no migrations run).
- **Production compatibility:** c4d5e6f7a8b9 explicitly marks itself LOCAL-ONLY ("must never be applied to production by an automated process") — an operator decision gate that is documented in the file but not enforced by tooling.

---

## F. BACKEND / API AUDIT

All 16 routers are mounted under `/api/v1` with consistent dependency chains. Contract observations:

- **Authentication requirement:** every domain router depends on `get_current_user` (HTTPBearer JWT); admin routers layer `require_any_admin` / `require_head_admin`; feedback admin + lab experiment CRUD + quiz writes are HEAD-only. `/`, `/health`, `/auth/*` are the only unauthenticated surfaces.
- **Validation:** Pydantic schemas with bounded queries (`limit ≤ 200`, `page_size ≤ 100`, `q ≤ 100`, search max-length), enum-typed params, date range checks (events 422 on inverted range).
- **Ownership:** `user_id` is never client-supplied anywhere (notifications, preferences, push, feedback, attendance, history) — verified in every affected endpoint.
- **Contract mismatches found:**
  - `/attendance/summary/{subject_code}` resolves the default `as_of` with `date.today()` (server-local, UTC on Render) instead of `institution_today()` (M-1). Docstring claims "resolved per request" — true per request, wrong clock.
  - `/quiz-eligibility/{code}/{cycle}` falls back to `date.today()` for `semester_start` (M-1 family).
  - `/admin/dashboard` computes `sessions_today`, `upcoming_sessions`, `next_quiz_date` from `date.today()` (M-1 family) while student surfaces use `institution_today()` — the two clocks disagree daily 18:30–24:00 IST on a UTC host.
  - `POST /attendance` accepts `status=PENDING` (L-1) — semantically a no-op row that suppresses CLASS_REMINDER generation for that session (`status is not None` filter).
  - Registration's 503 detail ("selected elective subjects are not configured…") is swallowed by the broad `except Exception` and re-raised as generic 503 (L-2).
  - `POST /student/sync` can set `roll_number` from the client when the account lacks one (L-3 family; unreachable via normal registration).
- **Over-exposure (POTENTIAL, L-6):** `GET /events` returns all active events including subject-scoped events for subjects the student is not enrolled in (institution-shared calendar semantics; single-section deployment makes this moot today).

---

## G. ATTENDANCE ENGINE AUDIT

`attendance_engine` is the single math core. Traced end-to-end:

**Raw records → classification → counting.** `AttendanceRepository` count queries LEFT JOIN records (missing = Pending), join the per-user elective choice (`_elective_choice_on`, coalescing timetable-entry slot with session slot), join the per-subject `occurrence_outcomes` (`_outcome_join_on` keyed on the *resolved* subject), filter with `_resolved_subject_match`, order by `(date, start_time nulls last, id)`, apply `_apply_outcome_to_row` (CANCELLED → is_cancelled; EXTRA_*/SURPRISE_QUIZ → is_extra; MODIFIED → flags unchanged, type exposed), then collapse via `practical_occurrence.collapse_count_rows`: deactivated rows dropped, contiguous same-subject/date PRACTICAL blocks = one occurrence, cancelled theory always dropped (stale mark loses), cancelled labs counted only by record (frozen lab contract). All consumers (summary, batch summaries, eligibility windows, dashboard, analytics, history, calendar counts, notifications, admin analytics) route through these same helpers — **no second counting implementation exists**.

**Formulas (all verified against the pooled contract):**
- CURRENT subject: `(L_att + T_att) / (L_done + T_done) × 100` (pending excluded); zero done → None. Practical % separate; never in the L+T denominator.
- FORECAST: pending-as-attended, pooled; zero total → None.
- ERP overall: attended/recorded (dashboard `_build_overall`, `AnalyticsService._overall`, admin analytics `_pcts`) — occurrence-level, cancelled excluded, pending never absent. This is intentionally *not* the pooled subject formula (documented in Phase 8.0 contract; both formulas coexist by design, not by accident).
- Weekly analytics/weekly delta: ERP recorded-only per Monday-start week.

**Boundary behavior checked:** 0 classes → None everywhere; 1-class subject → 0% or 100% (integer counts, float division); exactly 75.0 → passes (>=); 74.999… → fails; no rounding before comparisons in engine/optimizer (rounding only at presentation: history pct `round(...,1)`, frontend `Math.round`/1-decimal formatting); integer division absent (all `/` float); missing type contributes zero both sides (no fabricated 0/0).

**Edge cases confirmed safe:** duplicate attendance impossible (DB UNIQUE; race surfaces as 400, L-5); marking on cancelled session → 409; on deactivated session → 409; on future date → 400 (`session.date > institution_today()`, institution-local — correct); outcome-CANCELLED for the resolved subject → 409 keyed per-subject (elective-isolated); enrollment checked against the *resolved* subject, so a slot session is markable only via the student's own choice or anchor fallback.

**Findings in this domain:** M-1 (endpoint `as_of` clock), L-1 (PENDING accepted), L-5 (first-mark race), and the batch/per-subject path equivalence is proven by shared `_aggregate_counts`/`_build_subject_summary` (byte-identical construction).

---

## H. QUIZ + ELIGIBILITY ENGINE AUDIT

**Pipeline traced:** QUIZ_DAY events → `QuizRepository.get_effective_quiz_dates_for_subject(s)` (chronological rank, per-date dedup, elective scope: chosen subject resolves slot events; anchor events carry `elective_slot`) → `EligibilityService._build_domain_subject` (milestones q1..qn, commencement = semester_start) → `calendar_engine` windows (Criterion I: prev quiz date … day before quiz; Criterion II: commencement … day before quiz; inverted windows → empty, not error) → window counts via the canonical repo scan / Phase-26.3 single-scan bucketing with `exclude_quiz_day=True` (quiz-day-shaped sessions never inflate eligibility L/T) → `evaluate_quiz_eligibility`.

**Formula:** both criteria use the identical pooled L+T count-level percentage over their own window (Chunk 4/5 contract). `(Criterion I qualifies) OR (Criterion II qualifies)`; state derivation ELIGIBLE / RECOVERABLE (best-case pending-as-attended pooled ≥ required on either window) / NOT_ELIGIBLE / UNRESOLVED (no confirmed date). Must-Attend = min-deficit among *reachable* criteria (ties prefer C-I); Safe-Skip = max skips among reachable criteria; unreachable routes can never win or surface guidance (QC-II remediation verified in code).

**Thresholds:** persisted `eligibility_policies.lecture_threshold` authoritative (70/75/75 seeded from timetable.json and matching `determine_quiz_threshold`'s engine fallback); `combined_threshold` column is seeded but never consumed.

**Findings:**

- **H-1 (HIGH, CONFIRMED conflict with academic source — REPORTED, NOT FIXED):** the supplied attendance notice ties **70% to the first criterion of Cycle I** with **75% for subsequent cycles**. The implementation applies the cycle's single threshold to **both** criteria — so in Cycle I, the *cumulative* Criterion II also passes at 70% rather than 75%. This makes Cycle-I eligibility *more lenient* than the notice's plain reading. The engine's own docstring ("Both criteria share the SAME required percentage") documents the implementation choice; the audit records the conflict rather than resolving it. If the official reading is C-I=70 / C-II=75 in Cycle I, remediation belongs in `eligibility_policies` (add a per-criterion threshold) + `evaluate_quiz_eligibility`.
- **H-5 (HIGH, CONFIRMED mechanism):** effective cycle numbers are *positional* over chronologically sorted event dates. QuizSchedule.cycle is ignored at read time. An admin who edits Q3's date earlier than Q2's (allowed; only semester bounds are checked) silently renames cycles in every eligibility read, notification (`QUIZ_APPROACHING` occurrence_key = cycle number), and the dashboard snapshot — schedule labels and reality diverge.
- **Off-by-one day audit:** window end = quiz_date − 1 (correct "day prior"); window start = previous quiz *date* inclusive (documented ADR-010 semantics; the quiz-day session on that date is excluded from the window via `exclude_quiz_day`, while ordinary timetable classes on the previous quiz date count toward the next cycle — deliberate, no double counting). Dates are `date` objects throughout; the only clock risk is M-1's `date.today()` fallbacks.
- **Subject-specific vs semester-wide:** counts are strictly per-subject window scans (elective attribution per user) — semester-wide attendance cannot leak into eligibility.
- **Unreachable/reachable:** best-case RECOVERABLE uses pooled pending-as-attended over window totals — identical to the optimizer's reachability test; zero-pending windows reduce to the current pooled check; NOT_ELIGIBLE suppresses Safe-Skip entirely (UI withholds guidance).
- **M-5 (MEDIUM):** dashboard quiz snapshot counts UNRESOLVED subjects (no confirmed date) as `not_eligible` (`is_eligible=False`, optimizer None → else-branch) — they should be "unknown," inflating the not-eligible figure.
- **Relaxation framework (activity participation) and any physical-attendance requirement are not modeled anywhere** — a documented-capability gap versus the supplied academic rules (recorded here; no code pretends otherwise).

---

## I. SAFE-SKIP / FORECAST AUDIT

Single optimizer (`attendance_engine.optimize_attendance`) exhaustively enumerates attend/skip combinations over pending L/T under the pooled constraint with final-total denominators; tie-breaks minimize total attendance then minimize lectures attended (maximizing lecture skips). Reachability with zero pending = current pooled ≥ target.

- Consumers: subject summaries (75% target via `SUBJECT_OPTIMIZATION_TARGET_PCT`), eligibility criteria (per-window, required threshold), notifications (MUST_ATTEND / SAFE_SKIP texts), analytics per-subject fields. **No consumer reimplements the math.**
- Correctness: pending treated as resolved in the denominator (candidate-invariant); "recommend skipping when attendance would become ineligible" cannot happen — any combo that keeps pooled ≥ target qualifies, and the emitted skip counts are the complement of the minimum-attendance combo; unreachable states return `is_reachable=False` with deficit = full pending and no skip recommendation; rounding is not applied before comparison.
- Forecast fields: `forecast_avg_pct` pooled pending-as-attended; per-type forecasts individual. Consistent with the optimizer's model.
- Residual: the optimizer assumes all pending classes in the window are still future (counts include pending from *past* unmarked sessions, which after the quiz date simply remain pending — the eligibility window ends before the quiz so this is bounded there; subject-level optimization includes past-unmarked sessions as "attendable," which overstates skip capacity for past sessions the student can no longer attend). This is a **KNOWN model simplification** (POTENTIAL, P-3-class): the system cannot distinguish "pending because not yet marked" from "pending because class in the future."

---

## J. ELECTIVE RESOLUTION AUDIT

**One canonical resolver** (`ElectiveResolver`): DB-backed catalog (`subjects.elective_slot`, active-session scoped), `ANCHOR_CODES` (BCS-054/BCS-058) for schedule anchors, `load_choices`, `resolve_subject` (choice → anchor fallback, never fabricated), `resolve_events` (non-mutating response projection).

**Consumer verification (all resolve consistently):**
- Timetable endpoint: per-user choice; **slot entries with no choice are OMITTED** (anchor never exposed as a pseudo-elective).
- Attendance/counts/history/track/dashboard/analytics/calendar: per-user choice JOIN keyed on `coalesce(TT.elective_slot, CS.elective_slot)`; enrollment + Subject joins on the resolved subject.
- Quiz: `chosen_elective_map` → slot events resolve the chosen subject's quiz dates.
- Events/Calendar responses: `resolve_events` per user (non-mutating — one student's resolution cannot leak to another's objects).
- Notifications: choice-aware recipient resolution for slot events (choice holders + anchor-enrolled fallback).
- Registration/EnrollmentService: `resolve_subject` via the centralized plan; explicit ELECTIVE typing.
- Mutation gate: `record_attendance` resolves the effective subject from TT slot → session slot → choice; enrollment and outcome checks against the resolved subject.

**Conceptual Student A (054/058) vs Student B (052/055) test (static + DB):**
- Attribution rows: A's choice join matches only ELECTIVE_I/II slots → A sees 054/058-attributed occurrences; B sees 052/055. Neither's reads include the other's chosen subject; anchor-fallback exposure only for users *without* choices (admins) and only via the anchor subject itself.
- Enrollment scoping upstream: B is never enrolled in 054/058, so per-subject endpoints 404 for B on anchor subjects (no existence leak).
- Divergent occurrence outcomes: `occurrence_outcomes` keyed (session, resolved subject) — a CANCELLED outcome on 058 does not affect a 055 student (Phase-23.6 design verified in both read and mutation gate).
- DB state at audit time: 0 slot mismatches; 0 elective enrollments without matching choice; 0 elective-subject enrollments typed COMPULSORY; 0 timetable/session slot-vs-subject contradictions.

**Findings:** M-9 (registration re-implements catalog validation inline; `ElectiveResolver.validate_selection` is production-dead — two validation paths exist even though only one runs), H-3 (choice change re-attributes history — below), P-1 (an enrollment in an anchor subject *plus* a different slot subject — possible only through legacy/direct data — would double-attribute slot sessions to the anchor in counts; no such rows exist today).

**H-3 (HIGH, CONFIRMED mechanism):** `AdminStudentService.correct_elective` swaps the choice and the ELECTIVE enrollment but does **not** touch AttendanceRecords. Because occurrence attribution is choice-based at read time, the student's past marks on shared slot sessions instantly count toward the *new* subject (and vanish from the old one). The roadmap requires "immutable historical meaning"; this operation retro-actively rewrites it. No such correction has been exercised in the live DB (only one choice-set per user), so impact is latent-but-real.

---

## K. SESSION / OCCURRENCE AUDIT

Architecture rule verified: timetable (expected) → `EventSessionSynchronizer` materializes/reconciles `class_sessions` (actual) → every read consumes sessions + per-subject outcomes; **no consumer treats timetable rows as attendance reality** (the only timetable-based reads are the expected-schedule endpoint and the synchronizer itself).

- **Idempotency:** state-based reconciliation per date across ALL active events; deterministic ordering (priority desc, event id); re-running converges (verified by design and by the 702-row clean state: no duplicate (entry, date) rows).
- **Attendance safety:** sessions with records are never deleted and never cancelled by day-wide mutations; the single exception is explicit CLASS_CANCELLED propagation (stale Absent loses to class-reality); LAB_CANCELLED never cancels attended labs; attended extras withdrawn → `is_deactivated=True` (preserved, excluded from all logical reads at the single occurrence layer); reactivation restores the same provenance-linked row.
- **Quiz-day occurrences:** exactly one per (subject, date), LECTURE-shaped, unlinked, independent of ordinary timetable classes (Option A); created only when absent; deleted only when no event implies them and unattended; 18 live rows match 18 active events 1:1; `is_quiz_day` detection in Track uses the same shape predicate.
- **Weekend artifacts:** scheduled sessions on default weekends are sync projections (working Saturday/substitution); unattended ones are removed when no longer implied; attended ones preserved.
- **Span guard:** the synchronizer never creates sessions outside the baseline `[min,max]` scheduled-session window (2026-07-15 → 2026-12-31); events outside affect calendar reads only (0 live violations).
- **Gaps:** no DB uniqueness on (timetable_entry_id, date) — reconciliation is the only guard (M-3 family); `designation` (mid-sem) is managed only by MID_SEM_PRACTICAL events and the frozen admin endpoint, and never alters counting (verified).

---

## L. EVENT ENGINE AUDIT

Per-type semantics verified against `event_registry` (single validation authority) and `calendar_engine` priorities:

| Type | Scope | Session effect | Attendance | Quiz | Calendar | Notifications |
|---|---|---|---|---|---|---|
| EXTRA_LECTURE/TUTORIAL/PRACTICAL | subject or slot (slot = HEAD only, anchor stored + slot marker) | +1 extra with provenance | counts as conducted | — | shown | ACADEMIC_EVENT |
| CLASS_CANCELLED | subject (L/T) | removes one match; attended-session exception propagates | excluded (never absent) | — | shown | ACADEMIC_EVENT |
| LAB_CANCELLED | subject P only | cancels matching practical (attended labs protected) | excluded (record-less) | — | shown | ACADEMIC_EVENT |
| MID_SEM_PRACTICAL | subject P | designates/reuses/materializes one occurrence | normal counting | — | shown | ACADEMIC_EVENT |
| SURPRISE_QUIZ | subject L/T (or slot via outcome) | extra or per-subject SURPRISE_QUIZ outcome | counts | no quiz-date effect | shown | ACADEMIC_EVENT |
| QUIZ_DAY | subject/slot | materializes quiz-day session | attendance-bearing | authoritative date source | shown | ACADEMIC_EVENT (+ QUIZ_APPROACHING via quiz triggers) |
| HOLIDAY family / breaks / closures | global (HEAD only) | day non-working; desired schedule empty | cancelled/excluded | window shrinks | non-working reason | ACADEMIC_EVENT |
| WORKING_SATURDAY / DAY_OVERRIDE | global | flips Saturdays / day state | sessions materialize | — | shown | ACADEMIC_EVENT |
| CLASS_MODIFIED | subject only (slot rejected) | MODIFIED outcome on anchor session | counts (conducted) | counts | shown | ACADEMIC_EVENT |

**Propagation completeness:** event + session effect + outcomes commit atomically (single transaction; caller commits); deactivation always re-syncs (self-healing); outcomes reconciled even when `desired_outcomes` is empty (stale cleanup); update re-syncs the union of old and new spans; duplicate guard 409s identical actives.

**Elective divergence requirement (BCS-058 Surprise Quiz vs BCS-055 normal vs BCS-056 cancelled on one shared session):** implemented exactly via subject-specific outcomes on the shared anchor session; students without outcomes see the anchor state; outcomes never duplicate sessions/events per student. **The system does not collapse these into one shared student-facing state.** Verified in `_desired_schedule` (outcome precedence: CANCELLED > others), `_reconcile_outcomes` (stale removal), and the read/mutation application points.

**Findings:** L-8 (`exists_active_duplicate` identity omits `elective_slot` — a slot event and a same-subject non-slot event of the same type/dates collide in dedup; benign today), P-3 (concurrent event edits are last-write-wins on fields; reconciliation remains idempotent), and the notification fan-out issue H-4 (below).

---

## M. NOTIFICATION ENGINE AUDIT

**What exists:** persisted inbox (`notifications`, DB idempotency key user+kind+occurrence), read-only GET (60s TTL cache), PATCH read/dismiss (owner-scoped, preserved across regeneration), canonical `emit()` boundary (ON CONFLICT DO NOTHING → push only on genuine insert), mutation triggers (attendance, event, quiz schedule), one callable (NOT scheduled) sweep, Web-Push best-effort side-channel (VAPID currently unconfigured → `CONFIGURATION_ERROR` warnings only; 0 subscriptions live).

**Architectural gaps (creation vs delivery):**
- **Nothing generates CLASS_REMINDERs in production.** The projection builder exists but is reachable only through the unscheduled sweep; no daily/trigger path calls it. Daily class reminders are effectively unimplemented at runtime (H-4-adjacent capability gap, CONFIRMED by design docs "NOT scheduled in P4" + 0 CLASS_REMINDER rows live).
- **No retention/pagination:** the inbox query is unbounded; 465 rows / 452 orphans demonstrate unbounded growth (H-4).
- **After server restart:** rows persist (good); no regeneration occurs (a restart loses nothing but also never re-derives missed facts); missed notifications during downtime are never back-filled except by manual sweep.
- **Duplicates:** impossible per kind+key (DB-enforced); the trigger for an *edited* event refreshes in place without re-pushing.
- **Missed notifications:** event triggers skip past/inactive events (`end_date < today`); an event created for today is caught; one created and deactivated between sweeps for an offline user is lost forever (no retry).
- **Timezone:** `institution_today()` used consistently; `created_at` staggered microseconds for stable ordering.

**H-4 (HIGH, DB-CONFIRMED):** every `after_event_mutation` emits to *all enrolled users of the subject* (and all users for global events). Verifier scripts create fixture events, the trigger emits ACADEMIC_EVENT rows to **real** users (owner + students), then cleanup hard-deletes the events and only the *temp users'* notifications. Result: **452/452 ACADEMIC_EVENT rows reference nonexistent event ids** (182 unread for the owner, 182 for `9999999999999`, 88 for `8888888888888`); deep links 404 conceptually; the bell shows permanent unread noise. Root cause: verifier cleanup ignores notification side effects on non-fixture users; system lacks both a retention policy and referential hygiene for projections.

---

## N. AUTH / RBAC AUDIT

- **Registration:** backend-authoritative catalog validation (422), 13-digit roll, password policy (8–128, letter+digit), transactional user+enrollments+choices, atomic rejection (503/rollback) when a slot is unresolvable, IntegrityError → 409 (no enumeration), rate-limited 5/h/IP. Timing-equalized login (dummy PBKDF2) with generic errors.
- **Sessions:** 8h HS256 access JWT (`sub`, `type=access`), opaque SHA-256-hashed rotating refresh tokens in HttpOnly SameSite=None Secure path-scoped cookie; rotation with `FOR UPDATE` serialization; reuse ⇒ family revocation; refresh blocked for deactivated users.
- **Authorization:** `AuthorizationService` resolves legacy ADMIN ⇒ HEAD_ADMIN plus active `admin_scopes` from the DB **on every request**; scope factories (`require_class_scope`, `require_subsection_scope`, `require_elective_subject_scope`) and capability gates (can_access_section/subsection/subject, can_mutate_event) are composed server-side; SUBSECTION_ADMIN is conservatively inert; ELECTIVE_ADMIN never collapses to a slot.
- **IDOR checks:** notifications/push/preferences/feedback/attendance/history owner-scoped; admin student detail/attendance 404-masked out-of-scope targets (no existence leak); admin timetable/quiz/event reads server-scoped with user filters only narrowing.
- **Conceptual matrix test (Head / Class CS-5A / Subsection CS-5A/51 / Elective BCS-058):** passes in code — class admin limited to assigned sections (semester-wide subject visibility is the documented frozen semantic), subsection admin denies everything (inert, honest), elective admin limited to exact subject rows; scope assignment validates role-shape mirroring the DB CHECK; HEAD_ADMIN scope rows cannot be minted.

**Findings:**
- **H-2 (HIGH, CONFIRMED):** `get_current_user` never checks `user.is_active`. `set_student_status(is_active=False)` blocks *new* logins and refreshes, but a live access token keeps full student API access until expiry (up to 8h). No token-version/invalidation channel exists. Deactivation is therefore eventual, not immediate.
- **M-2-adjacent:** authorization depends on enrollment rows for ownership scoping (see M-2).
- **L-3 family:** `require_admin` (legacy) dependency is production-dead (verifier-only); role changes are per-request (good) but there is no audit log of admin mutations anywhere (roadmap asks for one in the mutation chain: Input→…→Audit log — **audit log absent system-wide**, recorded as P2 gap).

---

## O. CACHE / STATE CONSISTENCY AUDIT

- **Backend caches:** only the notification TTL cache. **Multi-worker hazard (M-8):** with `UVICORN_WORKERS > 1` (prod compose allows it), each worker holds its own cache and its own rate-limit buckets; a PATCH read/dismiss invalidates only the serving worker — other workers serve a ≤60s-stale inbox (bounded, low harm); login/register rate limits become per-worker (effectively multiplied).
- **Student-context caching:** none — every request re-resolves via `StudentContextService` (no staleness possible; slight query cost accepted by design).
- **Frontend:** SWR with shared canonical keys; `refreshUser()` and `logout()` clear the **entire** cache (`globalMutate(() => true, () => undefined)`) — the "User A logs out → User B logs in → A's data visible" scenario is explicitly defended in `AuthContext`. Token-gated profile key prevents a cached profile from authenticating without a token. Multi-tab sync via storage events. **No stale-cross-user path found.**
- **Stale elective/semester data:** every read re-resolves choices/placement per request — a corrected elective or placement change reflects immediately in all reads (except the H-3 history re-attribution semantics).

---

## P. PERFORMANCE / QUERY AUDIT

Evidence-based items (current volumes are small; these scale):

1. **M-7: missing FK/date indexes** (see §D). `class_sessions.date` unindexed is the standout — every dashboard/history/analytics request range-scans it.
2. **Admin aggregates cross-join shape:** `AdminAttendanceRepository.get_sessions_with_status_for_users` joins `User.id IN (…)` against all sessions then narrows via enrollment — a sessions × users product pruned by enrollment; fine for one section, quadratic-ish at multi-section scale.
3. **N+1 patterns (bounded, admin-facing):** `AdminQuizService.list_quiz_schedules` (per-row event lookup), `AdminEventService.list_events` (per-event subject + authz + managed checks), `AdminSubjectService.list_subjects` (per-subject semester fetch), `AdminStructureService` lists (per-row counts). Student-facing paths are already batched (Phases 25/26: grouped counts, single window scan, pre-fetched events/choices).
4. **Synchronous push in request path:** `_notify_push` awaits delivery per subscription with a 10s timeout each, post-commit — a user with several stale subscriptions adds latency to their attendance/event mutations (P2).
5. **`after_event_mutation` fan-out:** per-recipient `emit()` = 2 statements + commit each; a global event over N users is N sequential commits (observed: 452-row accumulation). Batch upsert exists (`upsert_many`) but is production-dead.
6. **Unbounded inbox read** (no limit/offset on `get_inbox`).
7. **Repeated elective resolution** is already memoized per-resolver-instance where it matters (catalog); choices are loaded once per request in dashboard/eligibility paths.
8. **`collapse_count_rows` in Python** over per-user row sets — fine at semester scale; the single-scan bucketing (26.3) already removed the worst duplication.

No blind optimization recommended; items 1–3 are the only ones with real future cost.

---

## Q. ERROR / FAILURE AUDIT

- **Global handler:** logs full exception server-side, returns generic 500 — no traceback/SQL leakage. Security headers present.
- **Domain errors:** consistent mapping (404 masked existence, 403 scope, 409 conflicts incl. structured timetable conflicts, 422 registry validation).
- **Fail-safe mutation chains:** event→session sync and quiz→event sync are single-transaction with rollback; attendance notification/push triggers are post-commit and fully isolated (`except Exception` + log) — they cannot roll back the write.
- **Swallowed-exception inventory (all logged, none silent):** attendance/event/quiz triggers; push dispatch per-subscription isolation; registration's broad `except Exception` (L-2: converts the specific 503 detail into a generic one — the only place a *useful* error is actually lost).
- **Partial-mutation risks:** none found in the write paths audited (registration atomic; correct_elective single commit; event chains atomic). `assign_subsection` capacity check-then-set is the only TOCTOU (L-4).
- **Frontend recoverability:** apiFetch translates network failures into actionable messages, preserves status/body on errors, retries once after refresh, keeps session on transient refresh failure; SWR revalidates on focus.
- **Logging:** single stdout INFO stream, no request IDs/correlation, no structured fields — adequate locally, thin for production debugging (P2 note).

---

## R. PRODUCTION CONFIGURATION AUDIT

- **Secrets:** none committed beyond dev defaults; production guard rejects the dev JWT secret, dev DB hosts, localhost CORS, and insecure refresh cookies under `APP_ENV=production`; render.yaml marks all secrets `sync:false`. (Dev DB URI in `alembic.ini`/config defaults is dev-credential only.)
- **Local/prod separation:** dev frontend guard refuses production builds with missing/localhost `NEXT_PUBLIC_API_URL` (fail-loud); prod compose builds private DB network, pinned proxy subnet matching `FORWARDED_ALLOW_IPS`, no exposed DB/backend ports; Render blueprint HTTPS + HSTS.
- **H-6 (production-path risk, CONFIRMED configuration contradiction):** `docker-compose.prod.yml` Phase-18A serves **HTTP only via Caddy ("TLS later")**, while `REFRESH_COOKIE_SECURE=True` + `SameSite=None` are **required** by the production guard. Browsers reject `Secure` cookies over plain HTTP ⇒ the cross-site refresh flow cannot function on that deployment path until TLS lands. The Render path (HTTPS) is unaffected.
- **M-8 family:** in-process rate limiting/cache documented as single-process; prod compose defaults to 1 worker but exposes the worker-count override without warning.
- **VAPID unset by default:** push silently degrades to log warnings (`CONFIGURATION_ERROR`) — acceptable, documented, but operationally invisible.
- **Migration application:** manual `alembic upgrade head` documented for prod; `c4d5e6f7a8b9` self-declares LOCAL-ONLY with no tooling enforcement (operator discipline required).
- **CORS:** explicit origin list, credentials enabled — correct (no wildcard).
- **Observability:** no request IDs, no metrics, no error tracking hooks (P2).

---

## S. TEST COVERAGE AUDIT

Present: 10 DB-free suites (~129 tests) — pooled formula baselines, optimizer/practical-occurrence safety, ERP-overall safety, deactivated-extra lifecycle, UI formula text, Chunk-16 enrollment invariant (Case A 054/058 and Case B 052/055 divergence at the plan level, atomic no-op gate, builder typing), and a sandboxed real-`register()` end-to-end (savepoint rollback; 422/503/atomicity paths). `pytest.ini` scopes to `backend/tests`; integration dir empty.

**Missing coverage for high-risk logic (each maps to a §V finding):**
- Student A vs Student B **service-level** divergence (dashboard/history/track reads with two choosers) — covered only by DB-mutating verifier scripts, which cannot run in CI and are the source of H-4 pollution.
- Eligibility windows/boundaries: exact-threshold passes/fails at 70/75, day-prior cutoff, previous-quiz-date inclusive start, `exclude_quiz_day`, dedup/ranking of effective dates (H-5 class), Cycle-I dual-criterion threshold (H-1).
- Calendar engine: closure/working-Saturday/substitution priority ties, inverted windows.
- Authorization boundaries: scoped-admin matrices (verifier-only today), deactivated-user-with-live-token (H-2).
- Notifications: trigger idempotency, push-once semantics, orphan avoidance (H-4).
- History/summary occurrence semantics (cancelled-with-stale-mark, recorded-lab-blocks) — verifier-only.
- Concurrency: none (by policy; noted).
- No `conftest.py`; DB-touching tests live outside pytest by design — the CI safety net is therefore only as good as the pure suites.

---

## T. CROSS-ENGINE CONSISTENCY MATRIX

Traced the same academic reality across timetable → sessions → attendance → quiz → eligibility → history/track → calendar → notifications → analytics. Contradictions found (all others consistent):

| # | Systems | Contradiction | Finding |
|---|---|---|---|
| 1 | Profile/StudentContext `first_quiz_date` ↔ Eligibility quiz dates | `first_quiz_date` joins events on `enrollment.subject_id` only — a student whose choices are non-anchor subjects (052/055) gets `None` despite slot quiz dates existing (proven live: user `7777777777777`). Eligibility for the same user resolves dates correctly. | **M-6 CONFIRMED** |
| 2 | Dashboard weekly bars ↔ weekly % | `weekly_pct` includes Saturday; the Mon–Fri `days` array and its `recorded` sum exclude it — one response disagrees with itself on working Saturdays. | **M-4 CONFIRMED** (latent; no Saturday classes in current CTT) |
| 3 | Dashboard quiz snapshot ↔ eligibility states | UNRESOLVED-cycle subjects counted as `not_eligible`. | **M-5 CONFIRMED** |
| 4 | QuizSchedule labels ↔ effective eligibility cycles | Cycle numbers re-derived chronologically from event dates; admin date edits can rename cycles across all reads/notifications. | **H-5 CONFIRMED mechanism** |
| 5 | Notifications ↔ events | 452 inbox rows reference deleted events (calendar/history have no such ghosts). | **H-4 CONFIRMED** |
| 6 | Enrollment change ↔ attendance history | Elective correction re-attributes past marks to the new subject; history/track/dashboard all agree with the *new* attribution (internally consistent, externally history-rewriting). | **H-3 CONFIRMED mechanism** |
| 7 | Attendance-summary endpoint clock ↔ every other surface | `date.today()` vs `institution_today()` (also quiz fallback, admin dashboard). | **M-1 CONFIRMED** |
| 8 | Timetable ↔ counts | No contradiction: counts never read timetable as reality. | consistent |
| 9 | Subject pooled % ↔ ERP overall | Two formulas, both documented, both labeled — deliberate duality, not a defect. | consistent-by-design |
| 10 | Calendar day semantics ↔ synchronizer | Both consume `get_academic_day`; no second day-resolution exists. | consistent |
| 11 | Notification QUIZ_APPROACHING ↔ dashboard current-cycle pick | Same `get_current_quiz_cycle` semantics (mirrored intentionally). | consistent |
| 12 | Admin analytics ↔ student analytics | Same occurrence pipeline + outcome application (24.13 integration fix verified in repo). | consistent |

---

## U. STALE / DEAD ARCHITECTURE

Confirmed production-dead (reported, not removed):
- `eligibility_engine._combined_pct` (historical mean-of-percentages; documented, 0 callers).
- `require_admin` dependency (Phase 6.5; verifier-only).
- `ElectiveResolver.validate_selection` (superseded by registration's inline catalog build — the duplication is the problem, see M-9).
- `QuizRepository.get_quiz_schedules_for_subject(s)` (quiz_schedules is now a derived projection; verifier compat only).
- `NotificationRepository.upsert_many` (built for the old generation loop; the emit boundary commits per row).
- `attendance_engine.normalize_class_type` legacy aliases (`P1/P2`, `*_extra_` producers no longer exist).
- `EligibilityPolicy.combined_threshold` column (seeded, never read).
- `UserPreference.week_starts_on` / `auto_mark_present` (storage-only by documented design).
- `Subject.tag` (informational only since 23.5; still the seeder's input and the enrollment-type backfill's key — frozen-history coupling).
- Duplicate `get_db` implementations (`app/db/session.py` vs `api/dependencies/deps.py`).
- `backend/verify_phase_25_1.py` stray at `backend/` root (siblings all live in `scripts/`).
- `Firebase` remnants: none in code; only the two historical migrations referencing it (correctly dropped).
- Mojibake (UTF-8 artifacts `â€”`) in docstrings of `feedback.py`, `laboratory.py` endpoints, `admin_event_service.py` — cosmetic.
- `e2f3a4b5c6d7` docstring revision-header drift (see §E).
- Hardcoded current-semester assumptions: none found in `app/` (registration auto-assignment *requires* exactly one active semester/section and fails closed otherwise — the correct shape). Seeders hardcode "2026-27"/"V Semester"/"CSE-51" by design (bootstrap tooling).

---

## V. ISSUE INVENTORY

Severity: CRITICAL / HIGH / MEDIUM / LOW. Confidence: CONFIRMED / LIKELY / POTENTIAL. "Systemic" = affects a class of paths; "isolated" = single site.

| ID | Sev | Conf | Domain / Layer | Component (file · function) | Problem (what is broken vs what is only risk) | Root cause | Impact | Scope | Remediation direction | Regression risk |
|---|---|---|---|---|---|---|---|---|---|---|
| **H-1** | HIGH | CONFIRMED (conflict reported, not fixed) | Quiz eligibility / engine+policy | `eligibility_engine.evaluate_quiz_eligibility` · `EligibilityPolicy` | System applies the cycle threshold to **both** criteria (Cycle I ⇒ C-II at 70%). Academic notice ties 70% to the *first criterion* of Cycle I; 75% thereafter. Relaxation framework entirely unmodeled. | Single `lecture_threshold` per cycle; `combined_threshold` unused; policy interpretation frozen in Chunk 4/5 | Cycle-I eligibility more lenient than the official rule; potential academic non-compliance | Systemic (all Cycle-I evaluations) | Per-criterion thresholds (populate `combined_threshold` or add columns); document relaxation as unimplemented scope | Medium — changes Cycle-I verdicts |
| **H-2** | HIGH | CONFIRMED | Auth/RBAC / API dep | `deps.get_current_user` | `is_active` never checked on authenticated requests; deactivation only blocks new login/refresh. 8h access-token window remains fully authorized. | Access tokens carry no revocation channel; check omitted | Deactivated student keeps reading/mutating own data up to 8h | Systemic | Check `is_active` in `get_current_user` (cheap) or shorten token TTL | Low |
| **H-3** | HIGH | CONFIRMED mechanism / latent data | Electives / admin write | `admin_student_service.correct_elective` | Choice swap leaves AttendanceRecords on shared slot sessions; read-time attribution instantly re-attributes history to the new subject (violates "immutable historical meaning"). | Attribution is choice-derived at read time; no record migration/re-basing step | Retroactive reinterpretation of a student's attendance history | Isolated operation, systemic effect | On correction: snapshot/freeze old-subject attribution (e.g. write outcome/enrollment-scoped records) or require explicit re-basing with consent | High — touches history semantics |
| **H-4** | HIGH | CONFIRMED (DB evidence) | Notifications / verifier hygiene + retention | `NotificationService.after_event_mutation` · verifier `finally` cleanups · `NotificationRepository.get_inbox` | 452/452 ACADEMIC_EVENT rows reference deleted (verifier-fixture) events; emitted to real users; no retention, no pagination; CLASS_REMINDERs unreachable in production (no scheduler). | Triggers fan out to real enrollees; cleanup deletes events but not third-party notifications; no retention policy | Inbox pollution (182 unread ghosts for owner); unbounded growth; daily reminders unimplemented | Systemic | Purge orphans (P0 cleanup task), exclude/annotate missing-ref rows at read, add retention cap + pagination, implement scheduled sweep for CLASS_REMINDER | Low |
| **H-5** | HIGH | CONFIRMED mechanism / POTENTIAL trigger | Quiz / read model | `QuizRepository.get_effective_quiz_dates_for_subjects._rank` | Effective cycle number = chronological position of QUIZ_DAY dates; QuizSchedule.cycle ignored. Out-of-order admin date edits silently rename cycles across eligibility, notifications, dashboard. | Positional derivation chosen for event-authoritative model | Cycle labels/notifications/eligibility windows diverge from the admin plan | Systemic under date edits | Rank by schedule cycle with chronological tie-break, or validate date ordering on quiz mutations | Medium |
| **M-1** | MEDIUM | CONFIRMED | Timezone / API+admin | `endpoints/attendance.py get_attendance_summary`; `endpoints/quiz.py`; `admin_dashboard_service` | `date.today()` (UTC on Render) instead of `institution_today()` for as_of/semester fallback/sessions-today — disagrees with all other surfaces 18:30–24:00 IST. | Inconsistent clock helpers adoption | Counts/pct off-by-a-day in an evening window; cross-surface disagreement | Isolated sites | Replace with `institution_today()` | Very low |
| **M-2** | MEDIUM | CONFIRMED gap | Enrollments / read boundary | `user_repo.get_enrolled_subjects` (all consumers) | Chunk-15 prevention layer G (defensive read boundary: enrollment must match placement/session and elective invariants) was designed but never implemented; reads blindly trust enrollment rows. | Layer deferred after write-path centralization (chunk 16 covered writers only) | Any future phantom/garbage enrollment row propagates to every read (the exact chunk-15 incident class) | Systemic defense-in-depth | Add boundary filter (elective-slot ⟂ enrollment-type consistency + placement match) or DB CHECK (see M-3) | Low |
| **M-3** | MEDIUM | CONFIRMED | DB invariants | `student_enrollments`, `student_elective_choices`, `quiz_schedules`, `academic_sessions`, `timetable_entries`, `academic_events` | 9 correctness rules are application-enforced only (list §D); races/direct writes can violate (incl. duplicate quiz schedule per (subject,cycle), two active sessions, overlapping timetable entries). | DB used as backstop only for identity/shape, not academic semantics | Invalid states possible without app bugs | Systemic | Targeted CHECKs/unique indexes (enrollment-type-vs-slot, choice-slot-vs-subject, UNIQUE(subject,cycle) partial, partial-unique single-active-session, timetable overlap exclusion constraint) | Medium (needs guarded migration) |
| **M-4** | MEDIUM | CONFIRMED (latent) | Dashboard / read model | `dashboard_service._build_weekly` | `days` iterates Mon–Fri only; Saturday classes counted in `weekly_pct` but absent from bars and from the response's `recorded` sum. | Hardcoded 5-day loop (legacy CTT assumption) | Self-inconsistent weekly card on working Saturdays | Isolated | Iterate 6/7 days or bound weekly_pct to the same range | Very low |
| **M-5** | MEDIUM | CONFIRMED | Dashboard / quiz snapshot | `dashboard_service._build_quiz_snapshot` | UNRESOLVED subjects counted as `not_eligible` in eligible/attention/not-eligible tallies. | Else-branch lumps unknown with failing | Misleading snapshot totals | Isolated | Count UNRESOLVED separately (schema already has room via state) | Very low |
| **M-6** | MEDIUM | CONFIRMED | Cross-engine (profile↔quiz) | `user_repo.get_academic_context`; `student_context_service._load_first_quiz_date` | `first_quiz_date` ignores elective-slot resolution (join on enrollment.subject_id only) ⇒ None for non-anchor choosers (live-proven for `7777777777777`). | Query predates Phase-22.4 slot events | Profile shows no quiz date for elective-only quiz students | Isolated query, systemic rule | Reuse `QuizRepository.get_effective_quiz_dates_for_subjects` | Very low |
| **M-7** | MEDIUM | CONFIRMED | DB performance | 27 FK columns; `class_sessions.date` | No indexes on FKs/date (list §D). | Indexes never added beyond PK/unique | Range scans + join probes degrade with data growth | Systemic | Add indexes in a guarded migration (CONCURRENTLY in prod) | Low |
| **M-8** | MEDIUM | CONFIRMED design / POTENTIAL trigger | Infra / cache+limits | `notification_service` TTL cache; `core/rate_limit`; prod compose worker override | In-process cache + limiter break under multi-worker (stale inbox ≤60s; multiplied rate buckets); Render proxy-IP keying makes login limit effectively global per proxy. | Single-process assumptions documented but unenforced | Wrong limits/staleness at scale; global login lockout behind one proxy IP | Systemic in multi-instance prod | Redis limiter or sticky single-worker; document/force; trust proxy CIDR for real IP | Low |
| **M-9** | MEDIUM | CONFIRMED | Electives / duplication | `endpoints/auth.register` vs `ElectiveResolver.validate_selection` | Catalog validation implemented twice (inline in registration; resolver copy production-dead) — divergence risk for the "one canonical resolver" principle. | Registration predates resolver's DB-catalog API | Future catalog-rule edits can miss one site | Isolated | Route registration through `validate_selection` | Low |
| **M-10** | MEDIUM | CONFIRMED (seed-time) | Seeds | `seed_academic_baseline.py` subject loop | Subjects looked up by `code` only, ignoring semester — violates the 23.2 multi-semester model UNIQUE(code, semester_id) was built for; future second-semester seeding would attach rows to the wrong semester. | Seeder predates multi-semester schema | Corrupted cross-semester seed on reuse | Isolated tooling | Scope lookups by (code, semester_id) | Low |
| **M-11** | MEDIUM | CONFIRMED (documented divergence) | Eligibility windows | `eligibility_service._build_domain_subject` | Per-subject `commencementDate` from timetable.json ignored; commencement = semester start for all subjects ("commencement of first class" per academic docs). | Domain subject built from placement only | Q1 window start off by days for late-commencing subjects | Systemic, small | Thread per-subject commencement through effective-dates/subject build | Low |
| **L-1** | LOW | CONFIRMED | API validation | `POST /attendance` | Accepts `status=PENDING` — writes a no-op record that also suppresses CLASS_REMINDER for that session. | Enum passthrough without domain restriction | Record noise; reminder suppression | Isolated | Restrict to ATTENDED/MISSED | Very low |
| **L-2** | LOW | CONFIRMED | Error handling | `endpoints/auth.register` | Broad `except Exception` swallows the specific 503 elective-configuration detail, re-raising generic text. | Exception ordering | Operator/student loses the real reason | Isolated | Re-raise HTTPException before generic handler | Very low |
| **L-3** | LOW | CONFIRMED | Dead/stale | (see §U list) | Dead code + docstring drift + mojibake + duplicate helpers + unused preference/policy columns + stray root verifier. | Accumulated phases | Maintenance noise | Systemic debt | P3 cleanup batch | Very low |
| **L-4** | LOW | POTENTIAL | Concurrency | `admin_student_service.assign_subsection` | Count-then-set capacity check; two concurrent assigns can exceed `max_strength`. | No lock/constraint | Capacity overrun (cosmetic today; subsections empty) | Isolated | `SELECT … FOR UPDATE` or DB constraint | Very low |
| **L-5** | LOW | CONFIRMED mechanism | Concurrency / UX | `attendance_service.record_attendance` | Read-modify-write first mark: concurrent duplicate marks hit UNIQUE → 400 "Unable to update attendance" instead of idempotent 200. | Check-then-insert | Spurious client error under double-tap | Isolated | Upsert (ON CONFLICT DO UPDATE) | Very low |
| **L-6** | LOW | POTENTIAL | API scope | `GET /events` | Returns subject-scoped events for subjects the student is not enrolled in (institution-shared semantics; single-section today). | Events treated as fully shared | Information exposure beyond enrollment | Systemic read | Optional enrollment filter per consumer | Low |
| **L-7** | LOW | CONFIRMED | Frontend contract | `QuizEligibilityCard` progress variants | Client-side threshold coloring (`pct >= required`) — presentation-only duplication of backend banding. | Convenience | Drift risk if banding changes | Isolated | Backend-emitted variant field | Very low |
| **L-8** | LOW | POTENTIAL | Events | `event_repo.exists_active_duplicate` | Duplicate identity omits `elective_slot`; slot vs non-slot same-type/date events collide in dedup. | Identity tuple incomplete | Legitimate distinct events rejected 409 (or vice versa) | Isolated | Add slot to identity | Very low |
| **P-1** | LOW | POTENTIAL | Electives / counts | `_resolved_subject_match` family | A user enrolled in an anchor subject *and* a different slot subject would double-attribute slot sessions; impossible with current invariant-conformant data. | Match predicate includes session-subject clause | Only under dirty data | Data-conditional | Covered by M-2/M-3 boundaries | — |
| **P-2** | LOW | POTENTIAL | Structure | Registration session pick | `first()` without order if >1 active sessions ever exist (DB allows; service prevents). | Guard upstream only | Arbitrary context pick under dirty data | Data-conditional | M-3 partial-unique closes it | — |
| **P-3** | LOW | POTENTIAL | Optimizer model | `optimize_attendance` consumers | "Pending" conflates future classes with past-unmarked ones; safe-skip may overstate capacity for already-passed unmarked sessions. | Count semantics frozen | Over-optimistic skip guidance | Systemic, bounded | Distinguish pending-by-date in windows | Medium |
| **P-4** | LOW | POTENTIAL | Admin students | `student.py /sync` | Client can set `roll_number` on accounts missing one (unreachable via normal registration). | Defensive legacy sync | Identity spoof edge | Isolated | Drop the field assignment | Very low |

**Totals: 0 CRITICAL · 5 HIGH · 11 MEDIUM · 8 LOW (confirmed/likely), plus 4 POTENTIAL items.** (H-4's CLASS_REMINDER sub-gap counted within H-4; relaxation-framework absence counted within H-1.)

---

## W. REMEDIATION BACKLOG

### P0 — DATA / SECURITY / CORE CORRECTNESS
1. **H-4 notification orphans + retention** — *Why:* user-visible integrity pollution, unbounded growth. *Subsystem:* notifications + verifier hygiene. *Files:* `notification_service.py`, `notification_repo.py`, `verify_*.py` cleanups. *Deps:* none. *Approach:* one-time orphan purge; read-layer inner-join to live refs (or annotate); retention cap + inbox pagination; verifier cleanup must delete notifications emitted to non-fixture users (or trigger through a disabled-push, fixture-scoped path). *Verify:* count(orphan refs)=0 after purge; inbox bounded.
2. **H-2 deactivation enforcement** — *Why:* authorization correctness. *Files:* `deps.py`. *Approach:* `if not user.is_active: 401/403` in `get_current_user`. *Verify:* deactivated user with live token rejected on next request.
3. **H-1 policy reconciliation** — *Why:* academic compliance. *Files:* `eligibility_engine.py`, `eligibility_service.py`, policies seed. *Approach:* owner decision on the notice's reading; implement per-criterion thresholds; explicitly scope the relaxation framework as unimplemented backlog. *Verify:* Cycle-I boundary tests for both criteria.
4. **H-5 cycle-number stability** — *Why:* cross-engine label consistency. *Files:* `quiz_repo.py`, `admin_quiz_service.py`. *Approach:* order validation on quiz mutation + schedule-cycle-based ranking. *Verify:* out-of-order edit test.
5. **H-3 elective-correction history semantics** — *Why:* "immutable historical meaning". *Files:* `admin_student_service.py` (+ design note). *Approach:* owner decision — freeze via outcome/record re-basing or explicit consent flow; **no silent behavior change**. *Verify:* correction leaves old-subject history byte-identical.

### P1 — MAJOR ENGINE / ARCHITECTURE
6. **M-2/M-3 invariant hardening** — read boundary at `get_enrolled_subjects` + targeted DB CHECKs/uniques (enrollment-type-vs-slot, choice-slot-vs-subject, UNIQUE(subject,cycle) on quiz_schedules, partial-unique single-active-session, timetable overlap exclusion). *Verify:* guarded migration dry-run; invariant verifier suite.
7. **M-1 clock unification** — replace remaining `date.today()` in app surfaces with `institution_today()`. *Verify:* grep-zero + evening-window test.
8. **M-6 first_quiz_date slot resolution** — reuse canonical effective-dates helper. *Verify:* non-anchor chooser returns slot dates.
9. **M-11 per-subject commencement** — thread timetable.json commencement (or a subjects column) into eligibility windows. *Verify:* window-start assertions per subject.

### P2 — RELIABILITY / PERFORMANCE / MAINTAINABILITY
10. **M-7 indexes** (`class_sessions.date` first, then FK set) via guarded migration; **M-4 weekly range fix**; **M-5 snapshot UNRESOLVED bucket**; **M-8 multi-worker posture** (Redis limiter or enforced single worker + documented cache semantics; real-IP trust behind proxies); **M-9/M-10 de-duplication** (registration→`validate_selection`; seger semester scoping); admin N+1 batching (quiz/event/subject/structure lists); push dispatch off the request path (background task); batched `after_event_mutation` emission (reuse `upsert_many`); inbox pagination (with H-4); minimal audit logging of admin mutations; request-ID logging.
11. **TLS gate for the Caddy path** (R/H-6): enable TLS before any HTTP-only production use, since Secure cookies are mandatory.

### P3 — TECHNICAL DEBT / CLEANUP
12. **L-1/L-2/L-4/L-5/L-6/L-7/L-8/P-2/P-4** small fixes (mutation status restriction; exception ordering; capacity lock; attendance upsert; optional event enrollment filter; backend variant field; slot in duplicate identity; ordered session pick; drop `/sync` roll_number write).
13. **L-3 dead-code batch** — remove or explicitly quarantine: `_combined_pct`, `require_admin`, `validate_selection` (or adopt it, per M-9), `get_quiz_schedules_for_subject(s)`, `upsert_many` (or adopt, per P2), `normalize_class_type` legacy aliases, `combined_threshold` (or adopt, per H-1), fix `e2f3a4b5c6d7` docstring header, mojibake cleanup, move `backend/verify_phase_25_1.py` into `scripts/`, consolidate `get_db`.

---

## APPENDIX — AUDIT ARTIFACTS & METHOD NOTES

- Read-only DB evidence: `backend/scripts/audit_ro_db.py` (24 SELECT-only probes), `backend/scripts/audit_ro_notifications.py` (6 probes). Both scripts only SELECT; no transaction is committed; they are new files added solely for this audit.
- No verifier scripts were executed (all are mutation-bearing). No migrations, seeds, repairs, or config changes were performed.
- DB numbers quoted in this report are the live state at audit time and may drift with subsequent legitimate use (e.g., the new canonical student `7777777777777` registered after Chunk 16 with invariant-conformant 052/055 data).
- Credentials redacted throughout; dev-only defaults referenced by name only.

*End of report.*
