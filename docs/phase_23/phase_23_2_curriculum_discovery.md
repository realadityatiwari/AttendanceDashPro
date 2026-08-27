# Phase 23.2 — Curriculum Model Discovery Report

**Date:** 2026-08-27
**Status:** READ-ONLY DISCOVERY COMPLETE — no code, no schema, no migration, no seed, no frontend, no auth, no database, no production changes. No commit, no push, no PR.
**Purpose:** Establish the authoritative curriculum/subject model required for the later Phase 23 architecture, before any implementation is authorized.

---

## A. Current Subject Model

### ORM Definition (`app/models/academic.py`)

```python
class Subject(Base):
    __tablename__ = "subjects"
    code: Mapped[str] = mapped_column(String, index=True)      # NOT unique
    name: Mapped[str] = mapped_column(String)
    tag: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[SubjectCategory] = mapped_column(Enum(SubjectCategory))  # THEORY / LAB
    quiz_applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    attendance_applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    semester_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("semesters.id"))
```

### Key Observations

| Column | Data Type | Unique? | Nullable? | Domain Semantics |
|--------|-----------|---------|-----------|------------------|
| `id` | UUID PK | Yes | No | Surrogate key |
| `code` | String | **No** (indexed only) | No | E.g. "BCS-501", "BCS-052", "BNC-501" |
| `name` | String | No | No | E.g. "Database Management System" |
| `tag` | String | No | **Yes** | Used for elective marking: "Elective-I", "Elective-II", "Lab" |
| `category` | Enum(THEORY/LAB) | No | No | Only two values: "theory" or "lab" |
| `quiz_applicable` | Boolean | No | No | True for theory subjects, False for labs |
| `attendance_applicable` | Boolean | No | No | True for all subjects currently |
| `semester_id` | UUID FK | No | No | Scopes the subject to a single semester |

### Critical Finding: `Subject.code` is NOT unique

`Subject.code` is indexed but NOT unique. The same code (e.g. "BCS-501") can appear in multiple semesters as different rows with different UUIDs. This is **intentional and correct** for multi-semester operation — the same subject code in different semesters is a different curriculum instance. However, there is no `UNIQUE(code, semester_id)` constraint either, so accidental duplicate insertion within the same semester is possible (currently prevented by the seed script's `NOT EXISTS` guard, not by the schema).

### SubjectCategory Enum

```python
class SubjectCategory(str, Enum):
    THEORY = "theory"
    LAB = "lab"
```

Only two values. There is no:
- NON_CREDIT category
- ELECTIVE-I category
- ELECTIVE-II category
- CORE category

Elective status is represented via `tag`, not `category`. Non-credit status is not represented at all (BNC-501 is marked `category: "theory"`, `quiz_applicable: true`, `attendance_applicable: true` — identical to every other theory subject).

---

## B. Current Curriculum Model

### Hierarchy (repository evidence)

```
AcademicSession (name "2026-27", is_active, start/end)
  └── Semester (name "V Semester", session_id FK)
        ├── Subject (semester_id FK) — the curriculum
        ├── Section (semester_id FK) — the class group
        │     └── User (section_id FK)
        └── StudentEnrollment (user_id, subject_id FK) — UNIQUE(user_id, subject_id) [Phase 23.1]
```

### How subjects attach to a semester

`Subject.semester_id` is a **NOT NULL** FK → `semesters.id`. A subject is permanently tied to exactly one semester. There is no:
- Cross-semester subject sharing (the same Subject row belongs to one semester only)
- Global subject master table
- Subject versioning or historical retention

### Current curriculum (from `timetable.json` — the authoritative seed source)

| Code | Name | Tag | Category | Quiz Applicable | Has Timeline? |
|------|------|-----|----------|----------------|--------------|
| BNC-501 | Constitution of India | null | THEORY | Yes | Yes (3 quizzes) |
| BCS-501 | Database Management System | null | THEORY | Yes | Yes (3 quizzes) |
| BCS-502 | Web Technology | null | THEORY | Yes | Yes (3 quizzes) |
| BCS-503 | Design & Analysis of Algorithm | null | THEORY | Yes | Yes (3 quizzes) |
| BCS-054 | OOS Design with C++ | Elective-I | THEORY | Yes | Yes (3 quizzes) |
| BCS-052 | Data Analytics | Elective-I | THEORY | Yes | No (added by Phase 22.3 migration) |
| BCS-053 | Computer Graphics | Elective-I | THEORY | Yes | No (added by Phase 22.3 migration) |
| BCS-058 | Data Warehousing & Data Mining | Elective-II | THEORY | Yes | Yes (3 quizzes) |
| BCS-055 | Machine Learning Techniques | Elective-II | THEORY | Yes | No (added by Phase 22.3 migration) |
| BCS-056 | Application of Soft Computing | Elective-II | THEORY | Yes | No (added by Phase 22.3 migration) |
| BCS-551 | Database Management System Lab | Lab | LAB | **No** | Yes (lab internal) |
| BCS-552 | Web Technology Lab | Lab | LAB | **No** | No |
| BCS-553 | Design & Analysis of Algorithm Lab | Lab | LAB | **No** | No |

Total: **13 subjects** in the current V Semester.

### Semester-specific vs global

All 13 subjects are scoped to the same semester (`V Semester`). There is no mechanism for a subject to span multiple semesters or be a "global" subject. Each subject row is created once per semester.

### Curriculum level: semester-level, not section-level

Subjects are attached to `semester_id`, not `section_id`. Two sections in the same semester share the same set of subjects. The `StudentEnrollment` table determines which subset of semester subjects a particular student is enrolled in (students enrolled in all non-elective subjects + their chosen electives). This is correct for the current single-section model.

---

## C. Elective Representation

### Split across three locations (duplicate source of truth)

**1. Hardcoded in `elective_resolver.py` (code — authoritative)**

```python
ELECTIVE_I_CODES: List[str] = ["BCS-052", "BCS-053", "BCS-054"]
ELECTIVE_II_CODES: List[str] = ["BCS-055", "BCS-056", "BCS-058"]
ANCHOR_CODES: Dict[ElectiveSlot, str] = {
    ElectiveSlot.ELECTIVE_I: "BCS-054",
    ElectiveSlot.ELECTIVE_II: "BCS-058",
}
```

The catalog is hardcoded Python constants. `validate_selection()` and `slot_for_code()` read from these constants. This is the **operational source of truth** for registration validation (auth.py validates elective_i/elective_ii against these constants).

**2. Database `subjects.tag` column (DB — derived)**

Subjects have `tag = "Elective-I"` or `tag = "Elective-II"`. The Phase 22.3/22.4 migrations backfill `elective_slot` markers from `subjects.tag`. The `tag` is populated by:
- `timetable.json` for BCS-054 and BCS-058 (the two anchors)
- The Phase 22.3 migration for BCS-052/053/055/056 (the four added subjects)

**3. Database `elective_slot` marker columns (DB — derived)**

`elective_slot` (nullable enum ELECTIVE_I/ELECTIVE_II) appears on:
- `timetable_entries` (Phase 22.3)
- `quiz_schedules`, `academic_events`, `class_sessions` (Phase 22.4)

These are backfilled from `subjects.tag` and used for per-student read-time resolution.

### Duplicate verification

The resolver constants and the DB `subjects` table could disagree if:
- The resolver code is updated without inserting/updating DB rows
- DB rows are inserted without updating the resolver code
- A subject with `tag = "Elective-I"` but a code not in `ELECTIVE_I_CODES` exists

Currently they are aligned because both were created by the same Phase 22.3 migration and seed pipeline. But there is **no DB-level constraint ensuring `subjects.tag` values match the resolver's hardcoded catalog**. A rogue INSERT could create a subject with `tag = "Elective-I"` and code "BCS-999" that the resolver would reject.

### Student elective selection

`StudentElectiveChoice` table: `(user_id, elective_slot, subject_id)` with `UNIQUE(user_id, elective_slot)`. One row per elective slot per student. Registration creates both `StudentEnrollment` and `StudentElectiveChoice` rows.

### Quiz dates for elective subjects

Only BCS-054 (Elective-I anchor) and BCS-058 (Elective-II anchor) have quiz dates/timelines. The other four elective subjects (BCS-052/053/055/056) have **no quiz schedules** and **no quiz-day events**. This is a documented data gap (Phase 22.3/22.4, Phase 23.0 report §36). The eligibility engine resolves the student's chosen elective subject to the shared slot's quiz dates via `get_effective_quiz_dates_for_subjects`.

---

## D. Enrollment Model

### `StudentEnrollment` table

| Column | Type | Constraint |
|--------|------|-----------|
| `id` | UUID PK | Auto-generated |
| `user_id` | UUID FK → users.id | NOT NULL |
| `subject_id` | UUID FK → subjects.id | NOT NULL |
| `created_at` | DateTime | Auto |
| `updated_at` | DateTime | Auto |
| | | `UNIQUE(user_id, subject_id)` (Phase 23.1) |

### Semantics

- **What enrollment means:** "This student takes this subject in this semester." The semester is implicit via `subject.semester_id`.
- **Elective vs common:** Both are enrolled the same way (one `StudentEnrollment` row per subject). The difference is that elective subjects are not enrolled for all students — only the ones who selected them.
- **Practical subjects:** Enrolled the same way as theory subjects. Labs have `quiz_applicable = false` and are excluded from quiz eligibility.
- **Duplicate enrollment:** The Phase 23.1 `UNIQUE(user_id, subject_id)` constraint prevents a student from being enrolled in the same subject row twice. The same subject CODE across semesters is a different subject row, so multi-semester historical enrollment coexists.
- **The constraint is correct:** `(user_id, subject_id)` is the correct key because:
  - Subject is semester-scoped (subjects.semester_id NOT NULL)
  - Different semesters → different subject rows → same (user_id, subject_id) is different entities
  - It does NOT lock a student to one section forever
  - It does NOT prevent a student from taking the same subject code in a later semester

---

## E. Dependency Map

```
Subject (app/models/academic.py)
  ├── StudentEnrollment           — user enrolled in this subject
  │     ├── Registration (auth.py) — creates enrollment rows
  │     ├── Quiz eligibility (quiz.py) — checks enrollment
  │     ├── Timetable (timetable.py) — resolves student timetable
  │     └── Attendance (attendance_repo.py) — scopes reads to enrolled subjects
  ├── TimetableEntry              — weekly recurring schedule slot
  ├── ClassSession                — dated occurrence of a subject's class
  │     ├── AttendanceRecord      — student's attendance mark
  │     └── LaboratoryRecord      — experiment record linked to session
  ├── QuizSchedule                — quiz date per subject per cycle
  │     ├── quiz_eligibility      — eligibility engine uses quiz dates
  │     └── seed_academic_events  — creates QUIZ_DAY events from schedules
  ├── AcademicEvent               — subject-scoped events (extra, quiz-day, etc.)
  │     ├── EventSessionSynchronizer — materializes event→session effects
  │     └── Calendar/events API   — reads resolved events
  ├── LaboratoryExperiment        — experiment catalog for lab subjects
  ├── SubjectRepository           — get_by_code, get_by_id, get_all
  ├── ElectiveResolver            — elective catalog + per-student resolution
  ├── UserRepository              — get_enrolled_subjects
  │     ├── GET /api/v1/subjects  — enrolled subjects list
  │     ├── Dashboard service     — per-subject summaries
  │     ├── Analytics service     — per-subject analytics
  │     ├── Notification service  — per-subject threshold notifications
  │     └── Calendar service      — event resolution
  ├── AttendanceService           — get_summary, get_subject_summaries
  │     ├── Attendance engine     — compute_subject_stats
  │     ├── Eligibility engine    — evaluate_quiz_eligibility
  │     └── Practical occurrence  — collapse contiguous blocks
  ├── Seed scripts:
  │     ├── seed_academic_baseline.py — creates subjects from timetable.json
  │     ├── expand_baseline.py        — creates ClassSessions from timetable
  │     ├── seed_academic_events.py   — creates QUIZ_DAY events from QuizSchedules
  │     └── materialize_quiz_day_sessions.py — creates quiz-day ClassSessions
  └── API schemas:
        ├── SubjectResponse (schemas/subject.py) — id, code, name, tag, category, quiz_applicable, attendance_applicable
        ├── SubjectAttendanceSummary (schemas/attendance.py) — per-subject counts + percentages
        └── AnalyticsSubjectItem (schemas/analytics.py) — extends SubjectAttendanceSummary
```

### Frontend

```typescript
// frontend/src/types/api.ts
interface SubjectResponse {
  id: string;
  code: string;
  name: string;
  tag: string | null;
  category: SubjectCategory;  // "theory" | "lab"
  quiz_applicable: boolean;
  attendance_applicable: boolean;
}
```

Frontend never creates or modifies subjects — it reads them from the backend API. The `useSubjects()` SWR hook calls `GET /api/v1/subjects` which returns the authenticated student's enrolled subjects.

---

## F. Historical Data Analysis

### Current schema provides partial historical safety

| Aspect | Status | Evidence |
|--------|--------|----------|
| Old sessions retain their subjects | ✅ | `ClassSession.subject_id` FK → subjects row; the subject row is permanent (no cascade delete) |
| Attendance records stay valid | ✅ | `AttendanceRecord.class_session_id` FK → ClassSession → Subject; chains are immutable |
| Quiz schedules remain valid | ✅ | `QuizSchedule.subject_id` FK → subjects row; permanent |
| Event records remain valid | ✅ | `AcademicEvent.subject_id` FK → subjects row; permanent |
| Old curriculum coexists with new | ✅ | Each semester gets its own Subject rows; old semester's subjects are untouched |
| Subject code can repeat across semesters | ✅ | `Subject.code` is NOT unique; different UUIDs |
| Curriculum versioning | ❌ **No mechanism** | No `curriculum_version`, no `active_from`/`active_to`, no `superseded_by` |
| Cross-semester subject identity | ❌ **No mechanism** | BCS-501 in V Semester and BCS-501 in VI Semester are completely unrelated rows — no shared "subject identity" linking them |

### Key gap: No cross-semester subject identity

A subject like "BCS-501 — Database Management Systems" exists as a separate row in each semester it's taught. There is **no way to ask "what is the history of BCS-501 across all semesters?"** because each semester creates a new, unrelated Subject row. This is acceptable for the current architecture (attendance is per-semester) but would need to be addressed if the system ever needs cross-semester subject analytics or curriculum management.

---

## G. CTT Cross-Check

The CTT (Curriculum Time Table, supplied as domain context) lists the following for B.Tech CSE V Semester:

**CTT vs Repository comparison:**

| CTT Subject | Repository Status | Match? |
|-------------|------------------|--------|
| BNC-501 Constitution of India | Present, tag=null, category=THEORY | ✅ |
| BCS-501 Database Management Systems | Present, tag=null, category=THEORY (name: "Database Management System" — missing final "s") | ✅ Minor name discrepancy |
| BCS-503 Design & Analysis of Algorithm | Present, tag=null, category=THEORY (name: "Design & Analysis of Algorithm" — CTT says "Design & Analysis of AlgorithmS") | ⚠️ Minor name discrepancy |
| BCS-502 Web Technology | Present, tag=null, category=THEORY | ✅ |
| BCS-052 Data Analytics | Present (Phase 22.3), tag=Elective-I, category=THEORY | ✅ |
| BCS-053 Computer Graphics | Present (Phase 22.3), tag=Elective-I, category=THEORY | ✅ |
| BCS-054 OOS Design with C++ | Present, tag=Elective-I, category=THEORY | ✅ |
| BCS-055 Machine Learning Techniques | Present (Phase 22.3), tag=Elective-II, category=THEORY | ✅ |
| BCS-056 Application of Soft Computing | Present (Phase 22.3), tag=Elective-II, category=THEORY | ✅ |
| BCS-058 Data Warehousing & Data Mining | Present, tag=Elective-II, category=THEORY | ✅ |
| BCS-551 DBMS Lab | Present, tag=Lab, category=LAB | ✅ |
| BCS-552 Web Technology Lab | Present, tag=Lab, category=LAB | ✅ |
| BCS-553 Design & Analysis of Algorithm Lab | Present, tag=Lab, category=LAB | ✅ |

**Discrepancies found:**
1. **BCS-501 name:** Repository has "Database Management System" (no trailing "s"). CTT specifies "Database Management Systems". **Architecturally irrelevant** (cosmetic).
2. **BCS-503 name:** Repository has "Design & Analysis of Algorithm" (singular). CTT specifies "Design & Analysis of Algorithms" (plural). **Architecturally irrelevant** (cosmetic).
3. **BNC-501 (non-credit):** The CTT lists "Constitution of India" (BNC-501) as a non-credit compulsory subject. The repository represents it identically to every other theory subject — same `category: THEORY`, same `quiz_applicable: true`, same `attendance_applicable: true`. **No non-credit distinction exists.** This is architecturally relevant if non-credit subjects need different attendance/eligibility treatment in the future.

**No CTT data correction is warranted during discovery.** The discrepancies are cosmetic or semantic future concerns.

---

## H. Required Phase 23.2 Changes

### REQUIRED

1. **Make `Subject.code` unique within a semester.** Add `UNIQUE(code, semester_id)` to the `Subject` model. This prevents accidental duplicate insertion of the same subject code within the same semester (currently only prevented by the seed script's `NOT EXISTS` guard). Migration: additive constraint; verify no duplicates exist in the current semester (13 subjects, all unique). **Low risk, schema-only.**

2. **Document the elective catalog reconciliation path.** The current dual-source-of-truth (code constants + DB `tag` column) is acceptable for now but should be documented as a future single-source-of-truth candidate (Phase 23.5 — `elective_catalog` table). No code change in Phase 23.2.

### POSSIBLY REQUIRED (requires operator decision)

3. **Non-credit subject flag.** Add a `is_credit` or `credit` boolean column to `Subject` (nullable, default `true`) to distinguish non-credit subjects like BNC-501. This would allow future eligibility/attendance rules to treat non-credit subjects differently. **Requires an explicit product decision** — the current treatment (identical to credit subjects) may be intentional.

### NOT REQUIRED (deferred to later phases)

4. **`elective_catalog` configuration table** — Phase 23.5 (config-driven catalog).
5. **Cross-semester subject identity** — Not required by the current architecture; subjects are per-semester, attendance is per-semester, enrollment is per-semester. The Phase 23 scope does not include cross-semester analytics.
6. **Curriculum versioning** — Not required until the system needs to support multiple concurrent curriculum versions or historical curriculum changes.
7. **Subject active/inactive status** — Not required; subjects are created per-semester and are implicitly "active" for their semester. Deactivation is not needed.
8. **Faculty/room metadata** — Not required by the Phase 23 roadmap.

---

## I. Migration Risk

| Risk | Impact | Mitigation |
|------|--------|-----------|
| `UNIQUE(code, semester_id)` would fail if duplicate codes exist in the same semester | Low | Guard: verify no duplicates before adding the constraint (Phase 22.1 pattern). Current data: 13 subjects, all unique codes. |
| Phase 23.2 schema change breaks existing `Subject.code` lookup | Low | `SubjectRepository.get_by_code(code)` returns the first match. If multiple semesters share the same code, the query returns the first row (which may be wrong). This is a PRE-EXISTING risk (not introduced by 23.2). `get_by_code` should be scoped to a semester. |
| `Subject.code` NOT unique allows cross-semester confusion | Low | `get_by_code` is called by the quiz eligibility endpoint and elective resolver. If the same code exists in multiple semesters, these queries may return the wrong semester's subject. This is a PRE-EXISTING latent defect, not introduced by Phase 23.2. Safe with current single-semester data. |

---

## J. Unresolved Decisions

| Decision | Status | Evidence |
|----------|--------|----------|
| Subject identity: is code the canonical identifier? | **EVIDENCE SUPPORTS** | Repository uses `code` as the primary lookup key (`get_by_code`, timetable.json, seed scripts, quiz endpoint, registration). However, `code` is NOT unique — it's semester-scoped. The canonical identity is `(code, semester_id)`. |
| Should `Subject.code` be unique within semester? | **CONFIRMED (should be)** | `UNIQUE(code, semester_id)` is the correct constraint. Currently 13 unique codes in one semester. No code should be duplicated within a semester. |
| Is the elective catalog code constants acceptable? | **CONFIRMED (acceptable for now)** | The dual source of truth is a known Phase 23.5 concern. Phase 23.2 does not need to resolve this. |
| Does BNC-501 need non-credit treatment? | **REQUIRES OPERATOR DECISION** | No non-credit distinction exists in the repository. The next phase may need to decide whether non-credit subjects should be treated differently for attendance/eligibility. |
| Cross-semester subject identity needed? | **UNRESOLVED (not required now)** | The current architecture is per-semester. Cross-semester subject identity is not required for Phase 23. |
| Subject name discrepancies (BCS-501 "System" vs "Systems", BCS-503 "Algorithm" vs "Algorithms") | **REQUIRES OPERATOR DECISION** | Cosmetic discrepancies. If corrected, requires a data update (not a migration). |

---

## Answers to the 18 Hard Questions

1. **What is the authoritative identity of a subject?** The `(code, semester_id)` pair. `code` alone is not unique; `id` (UUID) is the primary key but is not semantically meaningful.

2. **Is subject code globally unique or scoped?** Scoped to a semester. The same code can appear in multiple semesters as different rows.

3. **Is subject identity independent from a particular academic session?** No. Subject is tied to a semester via `semester_id` FK. A subject cannot exist without a semester.

4. **Is curriculum currently semester-scoped?** Yes. All subjects belong to exactly one semester.

5. **Can the same subject exist in multiple academic sessions?** Yes — as different rows with the same `code` but different `semester_id` and different UUIDs.

6. **How are practical subjects distinguished?** Via `category: SubjectCategory.LAB` ("lab") and `tag: "Lab"`. Labs also have `quiz_applicable = false`.

7. **How is BNC/non-credit represented?** It is NOT distinguished. BNC-501 is identical to every other theory subject in the model.

8. **How are core/common subjects distinguished?** They are NOT distinguished. Core subjects have `tag = null` (no tag), while elective subjects have `tag = "Elective-I"` or `"Elective-II"`. There is no `is_core` flag.

9. **How are Departmental Elective-I and II represented?** Via `subjects.tag` ("Elective-I"/"Elective-II"), the `elective_slot` marker columns, and the hardcoded `ELECTIVE_I_CODES`/`ELECTIVE_II_CODES` constants in `elective_resolver.py`.

10. **Where is the six-subject elective catalog defined?** In `elective_resolver.py` as Python constants. The DB `subjects` table contains the rows but the resolver does not read the catalog from the DB — it validates against the hardcoded constants.

11. **Is the elective catalog duplicated across code/database/frontend?** Yes — in code (`elective_resolver.py` constants), in DB (`subjects` rows with `tag`), and in frontend (`ElectiveSlot` enum). All three agree today but could diverge.

12. **Where does student elective selection live?** `StudentElectiveChoice` table (user_id, elective_slot, subject_id). Created during registration along with `StudentEnrollment`.

13. **Can curriculum be changed without changing historical attendance?** Yes — old Subject rows are permanent; FK relationships prevent cascade deletion. Changing future semesters creates new Subject rows.

14. **Can historical curriculum versions coexist?** Yes — each semester has its own Subject rows. Old semesters' data is preserved.

15. **Does StudentEnrollment correctly represent this lifecycle?** **CONFIRMED.** `(user_id, subject_id)` is the correct key. Subject is semester-scoped, so enrollment is implicitly semester-scoped. Multi-semester enrollment is supported (different subject rows per semester).

16. **What existing code assumes the current Subject model?** See §E Dependency Map. Every consumer listed there assumes a single-semester subject model with `code` as the primary lookup key.

17. **What schema changes are genuinely required for Phase 23.2?** `UNIQUE(code, semester_id)` on Subject is the only genuinely required schema change. The elective catalog reconciliation is documentation-only.

18. **What should explicitly NOT change in Phase 23.2?** The `SubjectCategory` enum (no new categories), the `tag` usage (elective marking via tag is a known Phase 23.5 concern), the `elective_resolver.py` constants (Phase 23.5), the `StudentEnrollment` constraint (Phase 23.1), the `quiz_applicable`/`attendance_applicable` flags, the `semester_id` FK, and all consumer behavior.

---

## Verification

- **Read-only repository inspection:** models, migrations, seed scripts, schemas, API endpoints, services, engines, repositories, frontend types, governance docs.
- **No code, schema, migration, seed, frontend, auth, or database changes.**
- **No database mutations.**
- **Git working tree: clean before and after** (no files modified by this discovery).
- **No commit, no push, no PR.**

---

## Next Steps

Phase 23.2 implementation (if authorized) should:
1. Add `UNIQUE(code, semester_id)` to `Subject` (additive, guarded).
2. Document the elective catalog reconciliation path (no code change).
3. Address the operator decision on non-credit flag for BNC-501.
4. Update governance documents to reflect the current implementation state.