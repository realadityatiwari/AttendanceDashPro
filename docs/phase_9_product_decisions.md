# Phase 9 — Product Decision Review

> **Scope**: DECISION REVIEW + SPECIFICATION only. No application code, schema,
> migration, data mutation, API, UI, seed, or commit. Phase 9.1 remains
> **BLOCKED / NOT STARTED** until the decisions below are explicitly confirmed.
> **Date**: 2026-08-15. Companion: `docs/phase_9_0_laboratory_domain_audit.md`
> (§16 enumerates the seven blocking decisions this document resolves by
> recommendation).

Every recommendation below distinguishes three classes of statement:

- **FACT (repository)** — directly evidenced by code, docs, or DB (PROVEN in
  the Phase 9.0 audit).
- **PRODUCT RECOMMENDATION** — this review's proposed decision, pending owner
  confirmation (§14).
- **UNKNOWN / REQUIRES REAL-WORLD INPUT** — cannot be decided from the
  repository; needs the institution/owner.

---

## 1. Decision summary

| # | Decision | Recommended choice | Blocks Phase 9.1? |
|---|---|---|---|
| 1 | Curriculum source | **E. Hybrid** — admin-curated ingestion of an authoritative institutional import; no seeds until a catalog exists | Yes (experiment sections) |
| 2 | Faculty role | **Defer** — keep STUDENT + ADMIN for 9.1; add FACULTY only with a defined signature/grading workflow (9.2+) | No |
| 3 | Audit identity | **Minimal additive** — timestamps + `signed_by` + `designated_by/at` + catalog provenance; no created_by on attendance | No (cheap, do in 9.1) |
| 4 | Experiment↔session linkage | **Nullable FK** `laboratory_records.class_session_id` + validation; single primary link per record | Yes (schema) |
| 5 | Mid-sem progress rule | **C. Advisory only** — "Eligible for mid-sem designation" derived from the real catalog; designation stays manual ADMIN action | No (read-only advisory) |
| 6 | Student mutation boundary | **Two-tier** — students self-track (pending); only ADMIN/FACULTY signs (official) | Yes (authority surface) |
| 7 | Grading / viva | **Exclude from Phase 9** — defer to a separate academic-assessment phase; keep dormant `marks`/`remarks` columns | No |

---

## 2. Current evidence (FACT from repository)

- Practical attendance is canonical: `ClassSession(PRACTICAL)` +
  `AttendanceRecord`; labs excluded from quiz eligibility (`quiz_applicable =
  false`, eligibility endpoint 404); cancelled sessions excluded; pending stays
  pending; current recorded-only. Verified 18/18 by `verify_phase_8_2.py`.
- `laboratory_experiments` (subject_id, experiment_number, title?) and
  `laboratory_records` (user_id, experiment_id, date_conducted, signature_status
  pending/signed, signed_on, marks, remarks) exist with **0 rows**.
- Mid-sem is an ADMIN-only, session-bound fact: `class_sessions.designation =
  MID_SEM_PRACTICAL` (Phase 8.2); never inferred from experiment counts; never
  a computed date; attendance against it uses the normal mutation.
- Every lab day materializes **two** PRACTICAL sessions (P1+P2 slots kept
  separate) — a bare `date_conducted` cannot disambiguate which session hosted
  an experiment.
- `UserRole` = STUDENT | ADMIN only (Phase 6.5). No faculty role, no signer
  identity, no audit columns anywhere (attendance/events/designation).
- Students may create/update/deactivate flexible subject-scoped events
  (`EXTRA_LECTURE/TUTORIAL/PRACTICAL`, `CLASS_CANCELLED`, `SURPRISE_QUIZ`) for
  their own enrolled subjects (Phase 8.2 policy); global/closure/quiz-schedule
  events and mid-sem designation are ADMIN-only.
- Legacy "10 experiments" and `LAB_RULES.grading.enabled = false` live only in
  the retired vanilla-JS engine/docs — **not authoritative** for the modern
  architecture.
- Subjects are semester-bound (`Subject.semester_id`), so a subject-scoped
  experiment catalog is implicitly semester-scoped — reusable per semester.

---

## 3. Decision 1 — Authoritative Curriculum

### Options evaluated

| Option | Strengths | Weaknesses |
|---|---|---|
| A. Hardcoded application data | Fastest; no tooling | No auditability, no corrections without deploys, not per-semester reusable, curriculum entangled with code |
| B. DB seed data | Deterministic; versioned like `seed_academic_baseline.py` | Seeds imply the product *owns* the data; with no source they become the de-facto fabricator; corrections need seed re-runs |
| C. Admin-managed curriculum | Correctable at runtime; per-semester; matches existing ADMIN authority | Admin could invent data unless ingestion is provenance-bound |
| D. Institutional/imported dataset | The true origin (syllabus/LMS) | No such dataset exists in the repository today; building a pipeline for a nonexistent source is speculative |
| E. Hybrid | Import as authoritative origin + admin-curated corrections, both recorded | Slightly more machinery |

### Recommendation — **E (hybrid), implemented via C's mechanism with D as the intended origin**

FACT: the schema already fits a catalog (`LaboratoryExperiment(subject_id,
experiment_number, title)`); subjects are semester-bound; the tables are
empty; no authoritative source exists in the repo.

PRODUCT RECOMMENDATION:
1. **No experiment rows are created until a documented catalog is supplied**
   (department syllabus / institution export). Until then the UI shows an
   honest "curriculum not yet available" empty state — never a guessed 1–N
   list, never a default of 10.
2. The ingestion boundary accepts an explicit payload per subject:
   `{ experiment_number, title, optional description }`, validated as
   non-negative, unique per subject, **no assumed fixed count** — subject-
   specific counts come from the catalog itself (count of rows), never a
   constant.
3. Every catalog row records **provenance**: source reference, imported-vs-
   corrected flag, `corrected_by`, timestamps (§3 audit identity). Corrections
   are new provenance entries, not silent overwrites.
4. Future-semester reuse: catalog rows are implicitly bound to the subject's
   semester (via `Subject.semester_id`); a new semester's catalog is a fresh
   authoritative import, never a copy-with-drift.
5. Optional `UniqueConstraint(subject_id, experiment_number)` is added only
   when the catalog becomes authoritative (a future migration, not now).

UNKNOWN: the actual source of the catalog; whether titles are standardized
institution-wide; whether experiment lists change mid-semester (would need a
correction/revision workflow — out of 9.1 scope).

---

## 4. Decision 2 — Faculty Role

### Recommendation — **DEFER. Keep STUDENT + ADMIN for Phase 9.1.**

FACT: no faculty concept, workflow, or signer identity exists anywhere in the
repository; every elevated action today is ADMIN; the application is a
personal tracker (30 migrated users, one ADMIN).

PRODUCT RECOMMENDATION:
- Do **not** add a `FACULTY` role in Phase 9.1. The audit explicitly forbids
  introducing "a role that has no defined academic workflow" — and no
  signature/grading workflow exists yet (§7/§6 decisions).
- Phase 9.1 authority surface is fully buildable with the existing
  `STUDENT | ADMIN` pair: students read their own progress and self-track
  (§6); ADMIN ingests curriculum, designates mid-sem, and signs.
- Introduce `FACULTY` **only when the signature/completion workflow (Decision
  6 official tier) and/or grading (Decision 7) are implemented** — i.e. a
  later phase. Design the permission model as a **capability matrix** (not
  role-string checks) so FACULTY can be added additively: FACULTY would hold a
  *narrower* elevation than ADMIN — sign/complete experiments, designate
  mid-sem, correct curriculum — but NOT global calendar/closure/quiz-schedule
  administration.

UNKNOWN: whether the institution distinguishes faculty accounts from admin
accounts; whether multiple faculty per subject must be supported (affects the
`FACULTY` role design, not 9.1).

---

## 5. Decision 3 — Audit Identity

### Recommendation — **Minimal additive audit fields; three distinct tiers.**

FACT: no `created_by`/`updated_by`/`signed_by`/`designated_by` or timestamps
exist on any mutation model (`AttendanceRecord`, `LaboratoryRecord`,
`AcademicEvent`, `ClassSession.designation`).

PRODUCT RECOMMENDATION — record identity per tier, matching who the system
already allows to act:

| Tier | Action | Audit to record |
|---|---|---|
| Student-entered progress | student creates/edits own progress row (date, remarks, status pending) | `created_by` (student), `updated_by`, `created_at`/`updated_at` on `laboratory_records` |
| Faculty-approved completion | elevated user sets `signature_status = signed` | `signed_by` (user FK) + `signed_on` on the record — the single *official* identity |
| Admin scheduling/designation | mid-sem designation / curriculum ingestion | `class_sessions.designated_by` + `designated_at`; catalog provenance (`source_ref`, `corrected_by`, timestamps) |

Scope control:
- **No** `created_by` on `AttendanceRecord` — it is a personal ledger and the
  mutation endpoint already authenticates the actor; adding it later is
  trivial and adds nothing today.
- `signed_by` is recorded at the moment of signing (never edited afterwards).
- The existing `signed_on` is reused; `designated_at` is new only if the
  decision to audit designations is confirmed.

FACT/recommendation boundary: audit columns are additive and nullable — a
future migration, zero impact on the frozen pipeline.

UNKNOWN: whether the owner wants designation audit history (who changed mid-sem
and when) or only the current fact.

---

## 6. Decision 4 — Experiment ↔ Class Session Linkage

### Recommendation — **Nullable FK `laboratory_records.class_session_id`, validated; single primary link per record.**

FACT: `date_conducted` is a bare date, and every lab day has **two** PRACTICAL
sessions (P1+P2) — a date cannot say which session hosted an experiment. No FK
exists today; the tables are empty (no backfill burden).

PRODUCT RECOMMENDATION — model shape preserving the three-entity distinction
(ClassSession = scheduled occurrence · Experiment = curriculum entity ·
LaboratoryRecord = occurrence/progress of an experiment):

- **Nullable FK** — required for traceability when known; NULL for historical/
  unlinked rows (no backfill problem: 0 rows today).
- **Validation on write**: the referenced session must (a) belong to the
  experiment's subject, (b) be `class_type = PRACTICAL` (mid-sem designated
  sessions are PRACTICAL and allowed), (c) **not** be `is_cancelled` (a
  cancelled session hosted nothing), (d) not be a substituted lecture.
- **Multiple experiments per session**: allowed — no unique constraint on
  `(class_session_id)`; the existing `UniqueConstraint(user_id, experiment_id)`
  (one record per student/experiment) is unchanged.
- **Sessions without experiments**: allowed (no record). "Conducted but no
  experiment" intent remains invisible — accepted limitation (§12 unknowns),
  not modeled in 9.1.
- **Experiments spanning multiple sessions**: a single record links its
  **primary hosting session**; a multi-session junction is deferred until
  evidence requires it (UNKNOWN whether institutions track it).
- **Mid-sem practical sessions**: allowed as the linked host (the mid-sem is a
  real practical session).
- **Date-only association**: retained as the fallback (when no session is
  known), but the UI should prefer session selection.

FACT/recommendation boundary: the FK itself is a future additive migration
(gated on this decision); everything else is validation/presentation logic.

UNKNOWN: whether the institution maps experiments to sessions at all, or
tracks progress purely by order/date.

---

## 7. Decision 5 — Mid-Sem Progress Rule

### Recommendation — **C. Progress-aware recommendation + authoritative designation (advisory only).**

Options:
- **A. Free designation** — current behavior (Phase 8.2); faculty/admin picks
  any practical session. Kept as the *mechanics*.
- **B. Automatic designation from experiment count** — **REJECTED, frozen**
  (Phase 8.2 hard stop): fabricates an academic date from a threshold.
- **C. Advisory + manual designation** — the system *reports* readiness;
  designation remains a human act. **RECOMMENDED.**
- **D. Hard eligibility gate** — designation blocked below N experiments.
  **REJECTED**: requires a universal count (violates "no universal experiment
  count"), and gating an academic event on app logic is a faculty-council
  matter, not a software rule.

PRODUCT RECOMMENDATION:
- Display, when an authoritative catalog exists: **"Eligible for mid-sem
  designation — X of Y experiments completed"**, where X = records with
  `signature_status = signed` (and attended via the canonical pipeline) and
  Y = the catalog's own row count for the subject. **Never a constant.**
- The advisory is read-only and hidden entirely when no authoritative catalog
  exists (nothing to count — no fabricated progress).
- Designation itself stays exactly as today: ADMIN-only `PUT/DELETE` on a real
  PRACTICAL session; no auto-designation, no gate, no computed date.
- If a per-subject threshold is ever wanted, store it **per subject** in the
  catalog metadata (not globally); default = none (pure advisory of raw count).

FACT: current behavior is A; Phase 8.2 forbids B.
UNKNOWN: the institution's actual threshold (5 is a legacy assumption only);
whether the mid-sem session hosts a distinct "mid-sem experiment" or is
standalone (affects whether the advisory counts it — see §12).

---

## 8. Decision 6 — Student Mutation Boundary

### Recommendation — **Two-tier model: STUDENT SELF-TRACKING vs OFFICIAL ACADEMIC RECORD, with `signature_status` as the boundary.**

FACT: students already self-track attendance and flexible events for enrolled
subjects (Phase 8.2 policy); mid-sem designation is ADMIN-only; no experiment
mutation exists.

PRODUCT RECOMMENDATION — authority matrix:

| Action | Tier | Who |
|---|---|---|
| View experiment progress (own) | read | Student (enrollment-scoped) |
| Record personal progress (date, remarks; status stays pending) | SELF-TRACK | Student (own record) |
| Mark experiment complete / officially confirm (`signed`) | OFFICIAL | ADMIN only (FACULTY later — §4) |
| Change experiment identity / curriculum | OFFICIAL | ADMIN only |
| Designate / change mid-sem | OFFICIAL | ADMIN only (frozen) |
| Cancel a practical / substitute / add extra | SELF-TRACK | Student (own enrolled) + ADMIN — existing Phase 8.2 policy |
| Edit historical laboratory data | OFFICIAL | ADMIN only, audit-trailed |

Mechanics:
- `signature_status` is the official boundary: **PENDING = self-tracked /
  unconfirmed** (student-writable); **SIGNED = official** (elevated-writable
  only, records `signed_by`/`signed_on`). Students can never set SIGNED.
- Student self-tracked edits are limited to their own records and to
  non-signature fields.
- Attendance and event authority are **unchanged** — the Phase 8.2 policy is
  frozen.

UNKNOWN: whether the institution wants students to self-track at all vs
faculty-only entry (if faculty-only, the self-track tier is simply disabled —
the model still supports it).

---

## 9. Decision 7 — Grading / Viva

### Recommendation — **EXCLUDE marks, viva, practical-file, and experiment-wise grading from Phase 9 entirely.**

FACT: `marks` (nullable Float) and `remarks` exist on `laboratory_records`;
legacy `LAB_RULES.grading.enabled = false`; viva was never implemented in any
architecture; no assessment workflow, rubric, or UI exists.

PRODUCT RECOMMENDATION:
- Phase 9 (including 9.1) delivers **progress states only**: pending → signed
  + session linkage. No marks input, no viva, no file/signature artifact
  storage, no grading UI/API.
- The dormant `marks`/`remarks` columns are **retained** (additive, harmless)
  but untouched.
- Grading/viva belong to a **separate academic-assessment phase** (Phase 10
  candidate), gated on (a) the FACULTY-role decision (§4) and (b) an assessment
  spec (per-experiment max marks, viva flag, rubric, who grades) — none of
  which exists today.
- Rationale: grading is institutional policy with no authoritative basis here;
  adding it expands laboratory scope beyond the audit's "no fabrication" and
  minimal-increment constraints.

UNKNOWN: whether the institution wants per-experiment grading at all; viva
requirements; who grades.

---

## 10. Recommended final architecture

```
Canonical pipeline (frozen, unchanged)
   class_sessions + attendance_records ─► attendance engine ─► summaries/analytics
   academic_events ─► synchronizer ─► class_sessions (cancelled/extra/substitution)
   quiz_applicable=false ─► labs excluded from eligibility (404)

Phase 9 additions (ALL additive; no engine/rule changes)
   LaboratoryExperiment   — catalog rows, populated ONLY by provenance-bound
                            admin ingestion (Decision 1); semester-scoped via
                            subject; optional (subject_id, experiment_number)
                            unique; per-subject count = row count.
   LaboratoryRecord       — nullable class_session_id FK (Decision 4);
                            created_by/updated_by/timestamps + signed_by/
                            signed_on (Decision 3); signature_status = official
                            boundary (Decision 6); marks/remarks dormant.
   ClassSession.designation — unchanged; designated_by/at audit (Decision 3).
   Lab read model (service → API → React)
       GET /laboratory/{code}/summary      — practical attendance + mid-sem
                                             (attendance pipeline + designation)
       GET /laboratory/{code}/activities   — session-scoped history
                                             (class_sessions + events + records)
       GET /laboratory/{code}/experiments  — catalog (empty until ingested)
       GET /laboratory/{code}/records      — own progress
       mid-sem readiness advisory          — "Eligible for mid-sem designation
                                             (X of Y)" — read-only, hidden
                                             without authoritative catalog
   Authority: STUDENT read + self-track; ADMIN everything elevated; FACULTY
              deferred (capability-matrix ready).
```

Constraints preserved: no React attendance math; no second attendance engine;
no experiment/session conflation; no fabricated data; no auto mid-sem; labs
stay 404 on quiz surfaces; frozen Phase 6/7/8 contracts untouched.

---

## 11. Phase 9.1 prerequisites (exact)

Phase 9.1 may start **only after** the owner confirms (§14) — recommended
defaults in parentheses:

1. **D1 curriculum** — confirmed that no catalog is seeded until an
   authoritative source is supplied, and 9.1 includes the ingestion boundary
   (or the owner explicitly defers experiment sections to 9.2, in which case
   9.1 = read model + audit only).
2. **D2 role** — confirmed STUDENT + ADMIN only for 9.1 (no FACULTY yet).
3. **D3 audit** — confirmed the minimal audit set (timestamps, `signed_by`,
   `designated_by/at`, catalog provenance).
4. **D4 linkage** — confirmed the nullable `class_session_id` FK + validation
   rules (this is the one schema migration 9.1 needs).
5. **D5 mid-sem** — confirmed advisory-only readiness (no auto-designation,
   no gate, no universal count).
6. **D6 boundary** — confirmed two-tier progress (student self-track pending;
   elevated sign).
7. **D7 grading** — confirmed grading/viva excluded from Phase 9.

With these, Phase 9.1 = additive lab read model + ingestion boundary +
nullable FK migration + audit columns + advisory + dedicated Laboratory page
IA (§12 of the audit), all verified read-only with exact-baseline restore.

---

## 12. Explicitly rejected approaches

- **Hardcoded experiment curriculum** (Decision 1-A) — no auditability,
  corrections, or semester reuse.
- **Seeding experiments without an authoritative source** (Decision 1-B as a
  fabricator) — the seed becomes the de-facto curriculum.
- **"10 experiments" as a default/cap** anywhere — legacy-only, non-authoritative.
- **Automatic mid-sem from experiment count** (Decision 5-B) — frozen hard stop
  (Phase 8.2); fabricates an academic date.
- **Hard eligibility gate on mid-sem** (Decision 5-D) — requires a universal
  count and over-constrains faculty.
- **Required (non-nullable) experiment↔session FK** (Decision 4) — impossible
  for unlinked/historical rows and sessions without experiments.
- **A FACULTY role without a defined workflow** (Decision 2) — violates the
  audit's explicit constraint.
- **Marks/viva/grading inside Phase 9** (Decision 7) — scope expansion with no
  authoritative basis.
- **Any second lab attendance engine or React-side attendance math** — frozen.

---

## 13. Remaining unknowns (require real-world input, not repository)

1. Origin and format of the authoritative experiment catalog (syllabus? LMS?).
2. Per-subject experiment counts and whether they differ (expected: yes).
3. The institution's actual mid-sem readiness threshold (if any).
4. Whether the mid-sem practical hosts its own experiment or is standalone
   (affects advisory counting and session linkage).
5. Whether students should self-track at all, or faculty-only entry.
6. Whether experiments are ever mapped to sessions institutionally, or tracked
   by order/date only.
7. Grading/viva policy (if ever), who grades, and per-experiment max marks.
8. Multi-user lab administration (multiple faculty per subject, co-signing).
9. Whether designation history (who/when changed mid-sem) is required beyond
   the current fact.
10. Mid-sem correction mid-semester (curriculum revisions) — needed only if
    catalogs change after the semester starts.

---

## 14. Product-owner decisions still requiring Aditya's confirmation

| # | Decision | Recommended | Needs confirmation |
|---|---|---|---|
| 1 | Curriculum source | E hybrid — provenance-bound admin ingestion; nothing until a real catalog | Yes — and the catalog source itself |
| 2 | Faculty role | Defer; STUDENT+ADMIN for 9.1; FACULTY with the 9.2+ workflow | Yes |
| 3 | Audit identity | Minimal additive (timestamps, signed_by, designated_by/at, provenance) | Yes |
| 4 | Session linkage | Nullable `class_session_id` FK + validation | Yes — one migration |
| 5 | Mid-sem rule | Advisory-only readiness; manual designation; no universal count | Yes |
| 6 | Student boundary | Two-tier: self-track pending / elevated signed | Yes |
| 7 | Grading/viva | Excluded from Phase 9; separate assessment phase | Yes |

**Phase 9.1 remains BLOCKED / NOT STARTED until these are confirmed.**
