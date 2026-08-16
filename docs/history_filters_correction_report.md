# History Page Filters — Focused Correction Report

**Date:** 2026-08-16
**Status:** COMPLETE — focused read/filter correction after Phase 9.2.1 (no Phase 9.3 started)
**No commit made.**

---

## 1. Summary

The History page (`/history`) crashed with
`TypeError: Cannot read properties of undefined (reading 'total_count')` at
`src/app/(authenticated)/history/page.tsx:322` whenever a filter (subject,
state, date, search) was applied. The backend History API was **healthy** — all
filters were verified correct in-process. The defect was frontend state logic
in the "Load more" button.

The fix is frontend-only (one file) plus a new focused verifier
(`backend/scripts/verify_history_filters.py`, 20/20). **No backend app code,
schema, migration, attendance/event data, or frozen verifier assertion was
changed.**

## 2. Root cause

### 2a. The `total_count` crash (every filter)

`useAttendanceHistory` keys SWR on the full request URL. When any filter
changes, the URL changes, so SWR returns `history === undefined` with
`isLoading === true` for the new key while it fetches. The page's Load-more
button was rendered under the condition:

```tsx
(isLoading || (history && rows.length < history.total_count)) && ( ... )
```

`rows` still held the **previous** filter's items (`rows.length > 0`), so the
button rendered during the fetch and its label dereferenced
`history!.total_count` on `undefined` — the exact reported crash. The same
defect also exists on plain pagination ("Load more"), because changing
`offset` is also a new SWR key.

### 2b. Stale-rows flash

While a filtered request was in flight, the previous filter's rows remained on
screen (the accumulate effect ignores `history === undefined`), so the page
showed old rows under the new filter until the response arrived.

### 2c. Backend filters

All backend filters were audited and are correct: `subject_code`, `status`
(regex `Attended|Missed|Pending|Cancelled`), inclusive `date_from`/`date_to`
clamped to the student's semester and today, case-insensitive `search` over
subject code / subject name / class type / date, occurrence-level status
matching, filtered `total_count`, and a `summary` computed over the **full**
filtered set (not the loaded page). An inverted range (`from > to`) yields the
deterministic empty intersection — no incorrect data. No backend change was
required.

## 3. Files changed

| File | Change |
| --- | --- |
| `frontend/src/app/(authenticated)/history/page.tsx` | Load-more gating + stale-rows reset (the only product fix) |
| `backend/scripts/verify_history_filters.py` | **New** focused verifier (20 checks) |

No other file was modified. `git status` contains only these two changes
(uncommitted).

## 4. Implementation approach

1. **Load-more button gated on `history` existing.** The button now renders
   only when `history && rows.length < history.total_count`; while a
   filtered/page request is in flight (`isLoading` with `history ===
   undefined`) a centered spinner row renders instead of a button that would
   dereference `history.total_count`. `history!.total_count` → `history.total_count`.
2. **Stale rows dropped on filter change.** The existing filter-signature
   reset effect now also `setRows([])`, so the skeleton renders during the
   filtered fetch and the previous filter's rows are never shown or mixed into
   the new result. Pagination resets (offset 0) and the accumulate effect
   (replace on offset 0, dedupe-by-id on later pages) are unchanged.

No change to `useAttendanceHistory` (no `keepPreviousData` — that would show
the old filter's data during the new fetch, violating "never mix rows from the
previous filter with rows from the new filter").

## 5. API contract

**Unchanged.** `GET /api/v1/attendance/history` still returns
`{ semester_start, semester_end, range_start, range_end, items, total_count,
summary }` with `summary = { total, attended, missed, pending, cancelled,
pct }` — identical shape whether filtered or not. Filtered `total_count` and
`summary` reflect the filtered set. Query params unchanged: `subject_code`,
`status`, `date_from`, `date_to`, `search`, `limit` (1–200), `offset`.

## 6. Practical occurrence grouping preserved

The two-hour lab block (two contiguous one-hour timetable periods → one
logical occurrence) is untouched. The verifier pins it: `subject_code=BCS-551`
history returns **4 items, one per lab block** (not 8 rows), and the 2026-07-20
lab appears as exactly one item (`01:00 PM – 03:00 PM`, PRACTICAL). Subject,
state, date, and search filters all operate on the **collapsed occurrence
level** (status matching is occurrence-aware; a cancelled block is one
Cancelled occurrence). No filtering change bypasses or undoes the collapse.

## 7. Verification — new focused verifier

`backend/scripts/verify_history_filters.py` — **20/20 PASS** (temp student
enrolled in BCS-501 theory + BCS-551 lab; exact baseline restored, check 19):

1. Unfiltered shape + `total_count` == occurrence count (22) + pristine summary
2. Subject filter — theory (BCS-501, 18)
3. Subject filter — practical (BCS-551, 4 blocks); 2-hour lab is ONE occurrence
4. `date_from` inclusive (10)
5. `date_to` inclusive (7)
6. `date_from` + `date_to` inclusive range (1)
7. Search by subject code, case-insensitive (4)
8. Search by subject name, case-insensitive (4)
9. Search by class type — practical/lecture/tutorial (4/14/4)
10. Present: marking the lab block creates EXACTLY ONE canonical record;
    `status=Attended` returns it
11. Absent: `status=Missed` returns exactly the marked lecture
12. Pending: all unrecorded non-cancelled occurrences (20)
13. Cancelled: LAB_CANCELLED event → one Cancelled occurrence; marking it → 409
14. Combined subject+state+dates+search (1)
15. Zero-result filters — 200, empty items, `total_count` 0, same shape
16. Pagination: fixed page size, disjoint pages, constant `total_count`,
    offset beyond end empty
16b. Load More accumulation: every occurrence exactly once, no duplicates
17. Clearing filters: unfiltered `total_count` 22 with end-state summary
    (attended 1, missed 1, pending 19, cancelled 1, pct 50.0)
18. Response-shape consistency across every filtered request
19. Database restored to the exact baseline

## 8. Static + regression results

- `python -m compileall app scripts` — PASS
- `npx tsc --noEmit` — PASS
- `npm run build` (Next.js) — PASS
- ESLint on the changed file — **2 pre-existing errors** (`react-hooks/
  set-state-in-effect` on the original effect patterns at HEAD — verified by
  linting the HEAD version of the file; the change adds none). Left untouched
  to avoid refactoring pagination logic.
- Frozen regressions (run unmodified):
  - 6.5 **27/27** · 6.6 **36/36** · 7.2 **26/26** · 8.2 **18/18** ·
    attendance-spec **15/15** · 9.1 **28/28** · 9.2 **29/29** ·
    track-lab-fix **16/16**
  - 7.1 **24/26** — checks 6 + 23: documented pre-existing fixture drift
    (events 19/18; records 101 vs fixture 92)
  - 6.7 **28/31** — checks 4/6/7: documented pre-existing fixture drift
    (22 active events + 4 inactive owner-entered events vs seeded 18)
  - 8.1 **21/22** — check 7: **pre-existing live-data drift, not a
    regression** — the admin now has a BCS-551 practical record (2026-07-20,
    Missed, owner-entered manual test data that existed at this turn's start
    baseline of 101 records). The check's fixture (all-pending lab → current
    null, forecast 100) no longer matches the live admin data. Per the
    frozen-verifier policy it was **not** modified.

## 9. Database baseline

Turn-start baseline (read-only capture): events 26 · sessions 695 · records
101 · cancelled 0.
End-of-turn: events **26** · sessions **693** · records **101** · cancelled 0 ·
extra 2 · enrollments 18 · subjects 9 · quizzes 18 · users 30 (1 admin) ·
lab tables 0/0 · designations 0.

- **Attendance records: 101 before and after — zero records added or removed
  by this work.**
- Sessions 695 → 693: the frozen 6.6 verifier's **documented startup cleanup**
  (removes stale *unattended* extra sessions, snapshots its baseline after)
  removed 2 owner-created unattended extra sessions. The 2 remaining extra
  sessions (07-31, 08-14 BNC-501 lectures) are attended owner data and were
  preserved — the "never delete attended sessions" rule held.
- No schema, migration, event, or seed change.

## 10. Remaining known failures / pre-existing drift

All three non-green frozen suites (7.1 checks 6+23, 6.7 checks 4/6/7, 8.1
check 7) are **pre-existing live-data fixture drift** caused by owner-entered
manual test data (events and attendance records) accumulated after the seeded
fixtures were frozen — same category documented in the Phase 9.2.1 report.
None is caused by this correction; none was weakened.

## 11. Manual browser checks (owner)

1. `/history` unfiltered loads; use **Load more** until all rows shown — no
   crash, spinner while the next page loads.
2. Apply each filter alone (subject, state, from, to, search) — page shows the
   skeleton while loading, then filtered rows; **no "Cannot read properties
   of undefined" error**.
3. Load a few pages, then change a filter — rows reset immediately; no old
   rows mixed with the new filter's rows.
4. Filter to a state/subject with no matches — empty state, no crash.
5. Pick a two-hour lab subject (e.g. BCS-551) — History shows each lab block
   ONCE (e.g. "01:00 PM" row, not two 1-hour rows) and `total_count` matches
   the block count.
6. Filter `Status = Cancelled` after creating a Lab Cancelled event — the lab
   appears once as Cancelled.
