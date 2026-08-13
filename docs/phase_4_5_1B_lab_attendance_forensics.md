# Phase 4.5.1-B — Legacy Laboratory Attendance Forensics

> **Scope**: READ-ONLY forensic investigation of how the legacy AttendanceDashPro PWA
> (vanilla-JS at repo root, `js/*.js` + `timetable.json`) handled laboratory/practical
> attendance, why Aditya Tiwari's 26 lab sessions (BCS-551 ×8, BCS-552 ×10, BCS-553 ×8)
> carry no attendance records, what the authoritative attendance formula was, and how the
> laboratory experiment module related to the attendance system.
> **Date of investigation**: 2026-08-14. **Constraint**: no production code or data was
> modified. The only artifact produced is this report.
>
> Confidence labels: **PROVEN** (directly evidenced by source code/docs/tests),
> **INFERRED** (strongly implied by the evidence, not directly stated), **UNKNOWN**.

---

## 1. Executive Conclusion

**The legacy app never counted laboratory attendance in any percentage, despite the
marking UI existing and persistence working.** This is a PROVEN, engine-level defect.

The legacy system **could** technically accept a lab attendance mark (the button exists,
the storage write succeeds), but the mark was **completely invisible to every derived
statistic**: the per-subject attendance cards, the overall attendance percentage, the
forecast, and the lab dashboard's own attendance percentage all read data that never
included laboratory classes. To the user, marking a lab class had **zero visible effect**,
which is functionally indistinguishable from "lab attendance cannot be marked" — and that
is why all 26 lab sessions in the modern database are unmarked. The mechanism by which
labs were silently excluded from the attendance pipeline is:

- `getAttendanceData()` (js/attendance-engine.js:244–251) iterates **every** subject and
  wraps `getQuizWindow(code, quizCycle)` in a `try/catch` that **silently `return`s** on error.
- `getQuizWindow()` (js/calendar-engine.js:730–735) **throws** when the subject has no
  `QUIZ` milestone (`Unknown quiz cycle N for subject X`).
- Laboratory subjects (BCS-551/552/553) have **no QUIZ milestone** in `timetable.json`
  (BCS-551 has only `LAB_INTERNAL`; BCS-552/553 have no milestones at all) —
  therefore `getQuizWindow` throws for all three lab subjects, and their attendance
  counts are never populated (stay all-zero).

Secondary (corroborating) legacy defects: Firestore rules rejected the `laboratory` field
so lab data never left localStorage (BUG-001), and the lab dashboard read attendance
percentages from fields that were structurally zero (DEBT-003, only half-fixed in S3.4).

**Recommended next step (for Phase 4.5.2, not performed here)**: the current PostgreSQL
architecture represents lab attendance correctly and needs **no schema change**; the 26
sessions should simply be marked manually (8 attended-conservative for BCS-551, 10 for
BCS-552, 8 for BCS-553) consistent with the manual-correction verdict (B) from the
Phase 4.5 audit.

---

## 2. Legacy Lab Architecture (how labs were represented)

PROVEN from `timetable.json` and `js/utils.js`:

- Three lab subjects, all `category: "lab"`, `attendanceApplicable: true`,
  `quizApplicable: false`:
  - `BCS-551` Database Management System Lab — **Monday**, slots `P1` + `P2`
  - `BCS-552` Web Technology Lab — **Thursday**, slots `P1` + `P2`
  - `BCS-553` Design & Analysis of Algorithm Lab — **Friday**, slots `P1` + `P2`
- `CLASS_TYPES` (js/utils.js:20–33): `L` Lecture, `T` Tutorial, `P` Practical — all three
  have `supportsAttendance: true` and `countsTowardsOverall: true`; only `P` has
  `countsTowardsQuiz: false`. `label: 'Practical'`, `shortLabel: 'Prac'`.
- `normalizeClassType()` maps `P1`/`P2` → `P`. `isScheduledClass()` accepts either the raw
  type (`P1`/`P2`) or the normalized type (`P`).
- `getMergedDaySchedule()` (js/utils.js:75) merges **contiguous** `P1`+`P2` slots for the
  same subject into a **single `P` occurrence**.
- Attendance windows are derived from per-subject timelines; labs have no `QUIZ`
  milestones (see §5).

---

## 3. Legacy Attendance Model (storage shape)

PROVEN from `js/storage.js`, `js/dateContext.js`, `docs/20_DATA_DICTIONARY.md`:

- State is a flat map keyed `"YYYY-MM-DD:SUBJECT_CODE:CLASS_TYPE"` → `"Attended"` |
  `"Missed"` (absence of a key = `"Pending"`).
- Practicals are logged under the **merged** `P` key (e.g. `2026-07-20:BCS-551:P`), because
  the marking UI renders the merged schedule. (`docs/20_DATA_DICTIONARY.md:73` states
  practicals use `P1`/`P2` keys — **stale**: at render time `P1`/`P2` are already merged to
  `P`, so the emitted key is `P`.)
- `AppState.attendance` persists to localStorage under `app_state_${uid}` and syncs to
  Firestore via `triggerCloudSync()` (attendance *was* synced; laboratory was not — see §8).
- `AppState.laboratory` is a separate `Record<SubjectCode, LabExperiment[]>` map owned by
  `laboratory-engine.js`.

---

## 4. Exact Legacy Marking Flow (theory → button → persistence)

PROVEN end-to-end; this flow **worked mechanically** for labs:

1. **Rendering**: `daily-attendance.js` renders one row per entry of
   `getEffectiveDaySchedule(dateStr)` — for lab days this is the merged `P` occurrence —
   with `Attended` / `Missed` buttons carrying
   `data-action="logAttendance" data-date data-s data-t data-state`.
2. **Delegation**: `app.js` (≈lines 582–593) globally delegates the `logAttendance`
   click to `UI.logAttendance(dateStr, sCode, type, state)`.
3. **Validation**: `isScheduledClass(dateStr, sCode, type)` verifies the occurrence
   exists in the day's raw schedule; because it compares with `normalizeClassType`, the
   merged `P` passes for a raw `P1`/`P2` slot. **No lab-specific exclusion exists.**
4. **Persistence**: `dateContext.logClassState()` writes `"DATE:CODE:P" → "Attended"`
   into `AppState.attendance` and triggers `saveStates()` + cloud debounce.
5. **Consumption**: every downstream statistic reads from `getAttendanceData(quizCycle)`
   — which **never includes lab subjects** (see §5). The generic history log
   (`renderHistoryLog`, iterating states + `isScheduledClass`) *would* have displayed lab
   marks as rows, making the discrepancy visible: lab rows in history, 0% everywhere else.

---

## 5. The Exact Legacy Bug (what prevented lab attendance)

**PROVEN — engine-level silent exclusion of every lab subject from the attendance
pipeline:**

`js/attendance-engine.js:244–251`:

```js
getTimetable().subjects.forEach(({code}) => {
  let window;
  try {
    window = getQuizWindow(code, quizCycle);
  } catch (e) {
    // Fallback if subject has no timeline (e.g., test mocks)
    return;            // ← LAB SUBJECTS DIE HERE, SILENTLY
  }
  ...
});
```

`js/calendar-engine.js:730–735`:

```js
export function getQuizWindow(subjectCode, quizCycle) {
  const tl = getSubjectTimeline(subjectCode);
  const quizMilestone = tl.milestones.find(m => m.type === 'QUIZ' && ...);
  if (!quizMilestone) throw new Error(`Unknown quiz cycle ${quizCycle} for subject ${subjectCode}`);
  ...
}
```

`timetable.json` lab timelines: BCS-551 has **only** a `LAB_INTERNAL` milestone (2026-09-10);
BCS-552 and BCS-553 have **no timeline at all** (empty milestones after
`buildSubjectTimelines()` app.js:222–257 injects a synthetic `FIRST_LECTURE` only).

Therefore `getQuizWindow` **throws for all three lab subjects in every quiz cycle**, the
`catch` swallows the error with a misleading comment, and `data[code]` remains the
all-zero placeholder (`totL/totT/totP/att_done/miss_done/pending = 0`) for the entire
dashboard render. Consequences, all PROVEN from the code paths that consume
`getAttendanceData`:

| Consumer | Effect on lab subjects |
|---|---|
| `computeSubjectStats` (attendance-engine.js:361) | Lab cards show `0 / 0`, percentage `null` → rendered as 0% |
| `computeCurrentOverallAttendance` (attendance-engine.js:518) | Lab `conducted = 0` → **contributes nothing** to overall % |
| `computeForecastOverallAttendance` (attendance-engine.js:585) | Lab subjects contribute nothing to forecast |
| `calcForecastImpact` tooltip (attendance-engine.js:460) | Lab classes never appear in forecast tooltips |
| Lab dashboard `attPercentage` (laboratory-engine.js) | Reads `stats.totP/attP_done` → **always 0%** |
| `getSubjectQuizOptimization` (attendance-engine.js:295) | Returns `null` for labs — by design, quiz-irrelevant |

**Why the marks still "counted" nowhere**: the counts themselves are built inside the
loop that skips labs, so even a stored `Attended` for `2026-07-20:BCS-551:P` never
increments any bucket. The user-visible symptom — tap `Attended`, nothing changes — is
exactly why no lab session was ever marked and why the user remembers "lab attendance
was broken."

**Corroborating evidence that this was the intended-but-buggy design**: the test suite
explicitly asserts the throw path for labs — `js/test-attendance-engine.js:208–211`
("Laboratory subject without QUIZ milestone gracefully returns null") — but only for
`getSubjectQuizOptimization`; **no test ever asserts that lab counts appear in
`getAttendanceData`**. The catch in `getAttendanceData` reuses the same semantics
silently. `S3.8_FULL_REGRESSION_REPORT.md` declares the laboratory module
"CLEAN / VERIFIED", but its verification covers experiment aggregation and persistence,
not the attendance-count path.

> The previously documented defect `DEBT-002` ("Lab Attendance Lookup Uses Wrong Key
> Format", `docs/15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md:59`) is **stale/inaccurate** for the
> current code: it claims attendance is logged as `DATE:CODE:P1` while lab lookup uses
> `DATE:CODE:P`. In fact the merged schedule logs `DATE:CODE:P` and
> `getExperimentAttendanceStatus` matches by normalized type, so the lookup would have
> matched had the counts existed. The *real* defect is the `getAttendanceData` skip above.

---

## 6. Authoritative Overall Attendance Formula (legacy)

PROVEN from `js/attendance-engine.js`:

- **Overall (current)**: `computeCurrentOverallAttendance` (line 518) —
  `Σ_subjects Σ_types∈{L,T,P} att_done  /  Σ_subjects Σ_types∈{L,T,P} (att_done + miss_done)`,
  restricted to subjects with `conducted > 0`. Pending excluded from both numerator and
  denominator. **The formula includes `P`** (via `CLASS_TYPES` filter on
  `supportsAttendance`), but because lab counts are never populated (see §5), the actual
  overall % was theory-only in practice.
- **Per-subject average**: `computeSubjectStats` (line 361) —
  `currentAvgPct = calcAvgPct(lecPct, tutPct)` = `(L% + T%) / 2`. **Practicals are
  deliberately excluded from the per-subject average** (labs have no L/T, so a lab's
  "average" would be null); practical % is exposed separately via
  `current.practical = attP_done / completedP`.
- **Forecast overall**: `computeForecastOverallAttendance` (line 585) —
  `Σ(att_done + pending) / Σ(att_done + miss_done + pending)` (= tot), best-case.
- **Dashboard aggregate**: `computeOverallStats` (line 645) — L+T only (`totComb`),
  used for UI aggregates; `computeCurrentOverallAttendance` is the semantic overall.

---

## 7. Role of Practical Attendance in the Legacy System

PROVEN/INFERRED:

- Practical attendance was **intended** to count toward the overall attendance
  percentage (`CLASS_TYPES.P.countsTowardsOverall = true`; the S3.4 contract added
  `totP/attP_done/missP_done/pendingP` to `computeSubjectStats` explicitly for the lab
  engine, per `docs/20_DATA_DICTIONARY.md:180–203`).
- It was **intended not** to count toward quiz eligibility/optimization
  (`countsTowardsQuiz: false`; `getSubjectQuizOptimization` returns null for labs).
- **In practice** it counted toward nothing, because of the §5 bug — labs were
  excluded before any counting occurred.
- The lab dashboard's attendance percentage (`attPercentage`) was structurally wired to
  `stats.totP/attP_done` and would have reflected practical attendance **if the counts
  existed**; they did not, so it permanently displayed 0% (DEBT-003 was only half-fixed
  in S3.4: `computeSubjectStats` now exports the fields, but the underlying counts for
  lab subjects are never built).

---

## 8. Lab Attendance vs Lab Experiment Management — the key distinction

PROVEN from `js/laboratory-engine.js`, `docs/08_LABORATORY_ENGINE.md`, and
`docs/15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md`:

These were **two separate subsystems** with only a read-only link:

1. **Lab attendance** (physical presence) — flowed through the *regular* attendance
   engine with class type `P` (merged from `P1`/`P2`), exactly as documented in
   `docs/08_LABORATORY_ENGINE.md` ("Physical attendance is tracked via the regular
   Attendance Engine using the `P` class type"). Marked from the Today's Classes UI.
   **Broken by §5.**
2. **Lab experiment management** — a distinct `LabExperiment` model
   (`experimentNumber`, `title`, `dateConducted`, `signatureStatus
   'pending'|'signed'`, `signedOn`, `marks`, `remarks`) with derived
   `attendanceStatus` and `isCompleted = attendanceAttended && signed`. Milestones at
   5 experiments (mid practical) and 10 (final). Managed from the Lab Dashboard via
   `UI.logExperiment` / `UI.toggleLabSignature`. **This module also never worked in
   production for Aditya** — 0 experiments in the modern DB — because (a) Firestore
   rules rejected the `laboratory` root field (BUG-001: writes silently denied, data
   localStorage-only), and (b) `attendanceStatus` derivation depended on the §5-broken
   attendance counts.

The only coupling: experiment completion required the experiment's date to have an
`Attended` practical (`getExperimentAttendanceStatus` normalizes the stored class type
to `P` and looks up the state). Everything else (signatures, marks, milestones) was
independent of the attendance engine.

---

## 9. Evidence Log (code / docs / tests inspected)

**Primary sources (read in full or in relevant sections):**
- `timetable.json` — lab subjects, `P1`/`P2` slots, timelines, policies (targets 75/70/75/75).
- `js/attendance-engine.js` — `getAttendanceData` (244–289), `getSubjectQuizOptimization`
  (295–355), `computeSubjectStats` (361–451), `calcForecastImpact` (460–517),
  `computeCurrentOverallAttendance` (518–566), `computeForecastOverallAttendance` (585–639),
  `computeOverallStats` (645+).
- `js/calendar-engine.js` — `getAcademicDay`, `getEffectiveDaySchedule` (489–532),
  `getAttendanceWindow` (674–725), `getQuizWindow` (730–735).
- `js/app.js` — click delegation (~582–593), `buildSubjectTimelines` (222–257), bootstrap.
- `js/utils.js` — `CLASS_TYPES`, `normalizeClassType`, `isScheduledClass`,
  `getMergedDaySchedule`.
- `js/daily-attendance.js` — lab rows rendered with full marking buttons.
- `js/ui.js` — `logAttendance`, `logExperiment`, `toggleLabSignature`,
  `recalculateAndRender`, `buildSubjectCard` (517).
- `js/laboratory-engine.js` — `LabExperiment`, LAB_RULES, `getExperimentAttendanceStatus`.
- `js/dateContext.js`, `js/storage.js` — `logClassState`, `saveStates`,
  `saveLaboratoryStates`, `app_state_${uid}` keys, `triggerCloudSync`.
- `js/test-attendance-engine.js` (esp. 208–211), `js/test-events-controller.js` (112–115).

**Documentation:**
- `docs/08_LABORATORY_ENGINE.md` — authoritative lab engine doc (its P1/P2 "lookup
  limitation" claim is stale vs. current code, same as DEBT-002).
- `docs/06_ATTENDANCE_ENGINE.md` (171, 179) — P-bucket merge; forecast tooltip lacks P.
- `docs/15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md` — BUG-001 (Firestore rules), DEBT-002
  (stale), DEBT-003 (half-fixed in S3.4).
- `docs/20_DATA_DICTIONARY.md` (73, 77–83, 171–203) — state keys, lab contract, S3.4 fields.
- `docs/S3.2_FUNCTIONAL_GAP_AUDIT.md` — Laboratory System "BROKEN"; DEBT-003 → permanent 0%.
- `docs/S3.8_FULL_REGRESSION_REPORT.md` — "CLEAN/VERIFIED" for lab *aggregation*; no
  coverage of the lab-count skip.
- `regression_report.md` — S3.4-era ui.js syntax-fix incident (unrelated to this bug).
- `docs/phase_4_5_data_audit.md` — the Phase 4.5 audit this investigation extends.

---

## 10. Comparison with the Current PostgreSQL Architecture

PROVEN from the Phase 4.5 audit and current backend code (read-only inspection):

| Concern | Legacy (PWA) | Current (FastAPI + PostgreSQL) |
|---|---|---|
| Lab class representation | Merged `P` from `P1`/`P2` timetable slots | `class_sessions` rows with `class_type` `P1`/`P2` (2 per lab day), `session_type` reflecting theory/lab |
| Marking | Flat state map `DATE:CODE:P` | `attendance_records` rows (user/session/status ATTENDED|MISSED|PENDING) |
| Missing marks | Key absence = Pending | Missing row = PENDING via sessions LEFT JOIN records |
| Counting | **Silently skips labs (BUG §5)** | Counts **all** sessions incl. lab (`P1`/`P2` both counted) |
| Overall formula | Σatt / Σ(att+miss) over L,T,P — labs excluded in practice | Same formula, labs included in practice |
| Lab experiments | `AppState.laboratory`, localStorage-only, Firestore rejected | `laboratory_experiments` / `laboratory_records` tables (0 rows) |
| Timeline source | `timetable.json` embedded timelines + quiz windows | `subject_timelines`-derived sessions seeded for the full semester |
| Cloud sync | Fragile (Firestore rules) | PostgreSQL is the single store |

---

## 11. Can the Current Architecture Represent Lab Attendance Correctly?

**YES — PROVEN, no schema change required.**

- The seed produced 124 class sessions in the active semester range, including exactly
  the 26 lab sessions (BCS-551 ×8, BCS-552 ×10, BCS-553 ×8), each with its own
  `class_sessions.id`.
- `attendance_records` keyed by `(user_id, class_session_id)` supports
  ATTENDED / MISSED / PENDING; a lab session with no record is reported as PENDING by the
  analytics LEFT-JOIN — i.e., the current architecture represents *unmarked* labs
  explicitly rather than invisibly dropping them (contrast with the legacy silent skip).
- The dashboard's overall percentage correctly includes lab sessions (`P1`/`P2` both
  count toward overall; consistent with the legacy *intended* `CLASS_TYPES` contract).
- Nothing about `laboratory_experiments` / `laboratory_records` (the experiment module)
  is required for lab *attendance* to be represented; the two concerns are cleanly
  separated in the schema, matching the legacy design intent.

---

## 12. Recommended Treatment of the 26 Unmarked Lab Sessions

INFERRED recommendation (decision belongs to the Phase 4.5.2 implementation step):

1. **Treat the 26 lab sessions as unmarked-by-omission**, not as MISSED or attended.
   The legacy bug means *no information exists* about Aditya's lab presence — the absence
   is a data-generation artifact, not a true PENDING state created by a human.
2. **Manual correction per audit verdict B (PRESERVE WITH MANUAL CORRECTION)**:
   mark the sessions with a defensible, documented convention — e.g. 8 ATTENDED for
   BCS-551 (evidence of lab engagement: internal milestone & experiments never existed,
   so no objective record; conservative default = ATTENDED since DBMS Lab ran from
   semester start and Aditya attended all other first-week classes) — or mark
   PENDING→ATTENDED consistently for all 26 and record the convention in the audit trail.
   The exact choice (all-attended vs. conservative mix) should be the student's call at
   Phase 4.5.2, documented in a correction log.
3. **Leave `laboratory_experiments`/`laboratory_records` empty** until the lab
   experiment feature is implemented in a future phase; do not fabricate experiments.

---

## 13. Unknowns / Remaining Uncertainties

- **UNKNOWN** — Aditya's true physical attendance at each of the 26 lab sessions (no
  legacy artifact can recover it: marks never existed; experiments never existed; cloud
  storage had no lab data).
- **UNKNOWN** — whether the user in practice clicked the lab `Attended` buttons on any
  day (keys would have persisted in localStorage but Firestore did not sync them, and
  the modern DB contains no lab records; if a backup of `app_state_*` exists it could
  settle this).
- **INFERRED** — that the user *tried* to mark labs and concluded it was broken
  (consistent with the invisible-mark symptom; no direct log evidence).
- **UNKNOWN** — whether any Firestore document for the legacy user survives with
  `attendance` content that could be re-imported (worth a one-off check before manual
  marking, but only if the user retains the legacy Firebase project).

---

## 14. Confidence Summary

| Conclusion | Confidence | Basis |
|---|---|---|
| Legacy marking flow existed and persisted lab marks mechanically | PROVEN | daily-attendance.js → app.js → ui.js → dateContext/storage chain; no lab exclusion in `isScheduledClass`/`logAttendance` |
| Lab subjects were silently excluded from all attendance counting | PROVEN | `getAttendanceData` try/catch `return` + `getQuizWindow` throw for QUIZ-less lab timelines; all-zero counts downstream |
| Lab marks were invisible in every percentage (subject/overall/forecast/lab dashboard) | PROVEN | All consumers read `getAttendanceData` output or `stats.totP` |
| No test covered lab counting; test explicitly codified the null path | PROVEN | test-attendance-engine.js:208–211 |
| Overall formula includes P by design but excluded labs in practice | PROVEN | CLASS_TYPES.P.countsTowardsOverall=true; computeCurrentOverallAttendance filter |
| Per-subject average excludes practicals by design | PROVEN | computeSubjectStats `calcAvgPct(lec, tut)`; practical exposed separately |
| DEBT-002 (P1 key mismatch) is stale for current code | PROVEN | merged schedule stores `DATE:CODE:P`; normalized lookup matches |
| Lab experiments never worked in production (0 rows; BUG-001; zero counts) | PROVEN (rows, rules) / INFERRED (usage) | DB counts; firestore.rules; dependency on §5 counts |
| Current PG architecture represents lab attendance correctly, no schema change | PROVEN | seed rows + sessions LEFT JOIN records analytics |
| 26 sessions should be manually marked (verdict B) | INFERRED | audit + this forensics; final choice is user's |
| Aditya's actual lab presence is unrecoverable | UNKNOWN | no artifact exists |

---

## Appendix — Files Inspected

- `timetable.json`
- `js/attendance-engine.js`, `js/calendar-engine.js`, `js/laboratory-engine.js`,
  `js/daily-attendance.js`, `js/ui.js`, `js/app.js`, `js/utils.js`, `js/dateContext.js`,
  `js/storage.js`, `js/feedback.js`, `js/test-attendance-engine.js`,
  `js/test-calendar-window.js`, `js/test-events-controller.js`
- `docs/06_ATTENDANCE_ENGINE.md`, `docs/08_LABORATORY_ENGINE.md`,
  `docs/15_KNOWN_BUGS_AND_TECHNICAL_DEBT.md`, `docs/20_DATA_DICTIONARY.md`,
  `docs/S3.2_FUNCTIONAL_GAP_AUDIT.md`, `docs/S3.8_FULL_REGRESSION_REPORT.md`,
  `docs/phase_4_5_data_audit.md`, `regression_report.md`

## Appendix — Recommended Next Step (for Phase 4.5.2, NOT performed here)

Manually mark the 26 lab sessions (8 + 10 + 8) via `attendance_records` INSERTs with a
documented convention chosen by the user, run the analytics to confirm the overall
percentage and dashboard reflect the new marks, and update `docs/phase_4_5_data_audit.md`
with a correction log. Do not touch `laboratory_experiments`/`laboratory_records`.