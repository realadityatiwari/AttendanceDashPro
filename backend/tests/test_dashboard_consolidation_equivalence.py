"""Perf batch 2 — dashboard query consolidation OLD-vs-NEW equivalence harness.

GET /dashboard/summary previously ran THREE overlapping ClassSession scans:

  A. get_sessions_with_status(user, scan_start, today)   -> read-model rows for
     Today / Overall / Weekly (date in [scan_start, today], resolved subject
     INNER-joined to enrollments, ordered (date, start_time nulls-last, id),
     practical blocks collapsed via group_practical_occurrences);
  B. get_subject_counts_for_user(user, today)            -> count tuples for
     per-subject summaries (date <= today, same enrollment join and ordering,
     collapse_count_rows(include_subject=True));
  C. get_subject_counts_between_for_subjects(user, ids, gs, ge) -> quiz-window
     rows for the quiz snapshot (NO enrollment join — attribution via
     session_subject_id / slot / choice_subject_id OR-filter, date in
     [global_start, global_end] which may extend into the future).

Batch 2 replaces the three scans with ONE unified retrieval whose rows are a
strict superset projection, then derives each consumer's input in Python:

  A' = group_practical_occurrences(
           [r for r in unified if r.date <= today
                               and resolved(r) in enrolled_ids])
  B' = collapse_count_rows(same scoped rows, include_subject=True)
  C' = _quiz_window_counts_from_rows(..., session_rows=unified)
       (per subject/window via the unchanged _bucket_window_counts)

Byte-identity argument per layer:
  - Row set: the unified query has A's joins minus the enrollment INNER join.
    resolved(r) in enrolled_ids re-expresses that join (the resolved subject is
    coalesce(choice.subject_id, session.subject_id); both columns FK-reference
    subjects, so the Subject join can never drop a row the enrollment join
    kept). Scan C deliberately keeps its own attribution: it can include a
    slot session the enrollment join would drop (a slot choice pointing at an
    un-enrolled subject while the anchor itself is enrolled) — the unified
    path preserves that behavior exactly (covered by the anomaly scenario).
  - Ordering: identical (date, start_time nulls-last, id); the practical
    collapse is order-sensitive.
  - Bounds: A'/B' re-apply <= today (the old queries guaranteed it) while the
    builders already re-apply their own lower bounds; C' windows bound their
    own dates; the unified upper bound is max(today, latest quiz date - 1).
  - Columns: strict superset with identical key names; consumers read named
    keys and ignore extras. The outcome join is applied once at the unified
    layer (each old scan applied it to its own copy — same rows, same rule).

This harness encodes the three OLD SQL semantics as faithful Python filters
over a synthetic session universe, runs the REAL old pipeline (real
grouping/collapse/bucketing and the real dashboard builders) and the REAL new
pipeline (real derivation functions + same builders), and asserts byte-identical
section outputs, per-subject summaries, and per-subject eligibility count
inputs. The eligibility engine is untouched and already proven pure — identical
count inputs imply identical eligibility results.

Scenarios (per the batch-2 requirement): Student A (DE-I BCS-054, DE-II
BCS-058 as anchors) and Student B (DE-I BCS-052, DE-II BCS-055 via choices);
mixed attendance states; quiz cycles past + future; practical blocks (attended
/ pending / cancelled-without-record); cancelled lecture with a stale mark;
a deactivated extra; elective isolation between the two students; the
elective-attribution anomaly; empty (no-session) subjects and a fully empty
universe; current-day sessions; sessions before the semester start; future
sessions inside the quiz window and beyond its horizon.
"""

from datetime import date, time, timedelta
from uuid import uuid4

from app.engines.practical_occurrence import (
    collapse_count_rows,
    group_practical_occurrences,
)
from app.models.enums import (
    AttendanceStatus,
    ClassType,
    ElectiveSlot,
    OccurrenceOutcomeType,
    SessionDesignation,
)
from app.repositories.attendance_repo import AttendanceRepository
from app.services.attendance_service import AttendanceService
from app.services.dashboard_service import DashboardService

# ---------------------------------------------------------------------------
# Fixed clock / calendar (never "today" dependent — deterministic dates)
# ---------------------------------------------------------------------------
TODAY = date(2026, 10, 7)            # Wednesday
SEMESTER_START = date(2026, 9, 1)
QUIZ1_DATE = date(2026, 9, 15)       # past cycle
QUIZ2_DATE = date(2026, 10, 20)      # future cycle -> horizon 10-19 > today
QUIZ_HORIZON = QUIZ2_DATE - timedelta(days=1)
UNIFIED_END = max(TODAY, QUIZ_HORIZON)

PREV_WEEK_START = TODAY - timedelta(days=TODAY.weekday() + 7)
SCAN_START = min(SEMESTER_START, PREV_WEEK_START)

# Subjects
S501 = {"id": uuid4(), "code": "BCS-501"}   # theory, quiz-applicable (common)
S502 = {"id": uuid4(), "code": "BCS-502"}   # theory, NOT quiz-applicable (A only)
S503 = {"id": uuid4(), "code": "BCS-503"}   # theory, enrolled by B, ZERO sessions
S054 = {"id": uuid4(), "code": "BCS-054"}   # DE-I anchor
S052 = {"id": uuid4(), "code": "BCS-052"}   # DE-I elective (B's choice)
S058 = {"id": uuid4(), "code": "BCS-058"}   # DE-II anchor
S055 = {"id": uuid4(), "code": "BCS-055"}   # DE-II elective (B's choice)
S551 = {"id": uuid4(), "code": "BCS-551"}   # lab (practicals, not quiz-applicable)
S056 = {"id": uuid4(), "code": "BCS-056"}   # DE-I elective that exists in the catalog but is NOT enrolled (anomaly fixture)

SUBJECTS = {s["id"]: s for s in (S501, S502, S503, S054, S052, S058, S055, S551, S056)}
for s in SUBJECTS.values():
    s.setdefault("name", f"Name {s['code']}")

QUIZ_IDS = {S501["id"], S054["id"], S052["id"], S058["id"], S055["id"]}

STUDENT_A = uuid4()
STUDENT_B = uuid4()
ENROLLED_A = {S501["id"], S502["id"], S551["id"], S054["id"], S058["id"]}
ENROLLED_B = {S501["id"], S503["id"], S052["id"], S055["id"]}
CHOICES_A = {}  # anchors themselves
CHOICES_B = {ElectiveSlot.ELECTIVE_I: S052["id"], ElectiveSlot.ELECTIVE_II: S055["id"]}
ELECTIVE_SCOPE_B = {S052["id"]: ElectiveSlot.ELECTIVE_I, S055["id"]: ElectiveSlot.ELECTIVE_II}

# Per-student effective quiz dates (subject-scoped for 501; slot-shared for the
# DE subjects — the shared slot schedule means both students see the same dates)
EFFECTIVE_BY_SUBJECT = {
    s_id: [(1, QUIZ1_DATE), (2, QUIZ2_DATE)] for s_id in QUIZ_IDS
}


def order_key(row):
    """(date, start_time nulls-last, id) — the SQL ORDER BY of all scans."""
    st = row["start_time"]
    return (row["date"], 1 if st is None else 0, st or time(0), row["id"])


def resolved_subject_id(row):
    """coalesce(choice.subject_id, session.subject_id) in Python."""
    return row["choice_subject_id"] if row["choice_subject_id"] is not None else row["session_subject_id"]


_seq = [0]


def _sid() -> str:
    _seq[0] += 1
    return f"session-{_seq[0]:04d}"


def sess(date_, class_type, subject, *, status=None, start=None, end=None,
         cancelled=False, deactivated=False, extra=False, designation=None,
         slot=None, choice=None, outcome=None):
    """One RAW ClassSession row as the unified query projects it (before
    _apply_outcome_to_row, which every scan applies)."""
    return {
        "id": _sid(),
        "date": date_,
        "class_type": class_type,
        "status": status,
        "is_cancelled": cancelled,
        "is_deactivated": deactivated,
        "is_extra": extra,
        "designation": designation,
        "elective_slot": slot if choice is None else slot,
        "session_subject_id": subject["id"],
        "slot": slot,
        "choice_subject_id": choice,
        "subject_id": subject["id"] if choice is None else choice,
        "subject_code": SUBJECTS[subject["id"] if choice is None else choice]["code"],
        "subject_name": SUBJECTS[subject["id"] if choice is None else choice]["name"],
        "start_time": start,
        "end_time": end,
        "outcome_type": outcome,
    }


def apply_outcomes(rows):
    """Each scan applied the occurrence-outcome rule to its own row copies;
    the unified layer applies it once. Same rows -> same rule -> same result."""
    return [AttendanceRepository._apply_outcome_to_row(dict(r)) for r in rows]


def mondays(count, start):
    return [start + timedelta(days=7 * i) for i in range(count)]


def build_universe(records_by_date, *, include_straggler=True):
    """The shared physical schedule with per-student attendance records.
    `records_by_date`: {date: AttendanceStatus} for BCS-501 past lectures.
    Elective slot sessions carry the ANCHOR subject with the slot marker;
    the student's resolution appears via `choice_subject_id` (None for A)."""
    rows = []

    # BCS-501 past lectures (4 Mondays: A and B record different states)
    for i, d in enumerate(mondays(4, date(2026, 9, 7))):
        st = records_by_date.get(d)
        rows.append(sess(d, ClassType.LECTURE, S501, status=st,
                         start=time(9, 0), end=time(9, 50)))
    # BCS-501 today: one pending lecture + one attended tutorial
    rows.append(sess(TODAY, ClassType.LECTURE, S501, start=time(9, 0), end=time(9, 50)))
    rows.append(sess(TODAY, ClassType.TUTORIAL, S501, status=AttendanceStatus.ATTENDED,
                     start=time(10, 0), end=time(10, 50)))
    # BCS-501 future inside the quiz window (pending) and beyond the horizon
    rows.append(sess(QUIZ_HORIZON, ClassType.LECTURE, S501, start=time(9, 0), end=time(9, 50)))
    rows.append(sess(QUIZ_HORIZON + timedelta(days=3), ClassType.LECTURE, S501,
                     start=time(9, 0), end=time(9, 50)))
    # cancelled lecture with a stale mark (cancellation wins) + deactivated extra
    rows.append(sess(date(2026, 9, 22), ClassType.LECTURE, S501,
                     status=AttendanceStatus.MISSED, cancelled=True,
                     start=time(9, 0), end=time(9, 50)))
    rows.append(sess(date(2026, 9, 23), ClassType.LECTURE, S501,
                     status=AttendanceStatus.ATTENDED, extra=True, deactivated=True,
                     start=time(11, 0), end=time(11, 50)))
    # student-scoped CANCELLED outcome on a regular-looking session
    rows.append(sess(date(2026, 9, 29), ClassType.LECTURE, S501,
                     status=AttendanceStatus.MISSED,
                     outcome=OccurrenceOutcomeType.CANCELLED,
                     start=time(9, 0), end=time(9, 50)))

    # BCS-502: A-only, NOT quiz-applicable (must be inert for the snapshot)
    rows.append(sess(date(2026, 9, 9), ClassType.LECTURE, S502,
                     status=AttendanceStatus.ATTENDED, start=time(11, 0), end=time(11, 50)))

    # DE-I slot sessions (anchor subject + slot marker; 4 past + 1 in window)
    for d in mondays(4, date(2026, 9, 7)):
        rows.append(sess(d, ClassType.LECTURE, S054, slot=ElectiveSlot.ELECTIVE_I,
                         start=time(12, 0), end=time(12, 50)))
    rows.append(sess(date(2026, 10, 12), ClassType.LECTURE, S054,
                     slot=ElectiveSlot.ELECTIVE_I, start=time(12, 0), end=time(12, 50)))

    # DE-II slot session TODAY + one past
    rows.append(sess(TODAY, ClassType.LECTURE, S058, slot=ElectiveSlot.ELECTIVE_II,
                     start=time(14, 0), end=time(14, 50)))
    rows.append(sess(date(2026, 9, 8), ClassType.LECTURE, S058,
                     slot=ElectiveSlot.ELECTIVE_II, start=time(14, 0), end=time(14, 50)))

    # BCS-551 labs: attended 2-period block, today pending block,
    # cancelled block without records, mid-sem designated block
    rows += [
        sess(date(2026, 9, 10), ClassType.PRACTICAL, S551,
             status=AttendanceStatus.ATTENDED, start=time(13, 0), end=time(14, 0)),
        sess(date(2026, 9, 10), ClassType.PRACTICAL, S551,
             start=time(14, 0), end=time(15, 0)),
        sess(TODAY, ClassType.PRACTICAL, S551, start=time(13, 0), end=time(14, 0)),
        sess(TODAY, ClassType.PRACTICAL, S551, start=time(14, 0), end=time(15, 0)),
        sess(date(2026, 9, 17), ClassType.PRACTICAL, S551, cancelled=True,
             start=time(13, 0), end=time(14, 0)),
        sess(date(2026, 9, 17), ClassType.PRACTICAL, S551, cancelled=True,
             start=time(14, 0), end=time(15, 0)),
        sess(date(2026, 9, 24), ClassType.PRACTICAL, S551,
             status=AttendanceStatus.ATTENDED, designation=SessionDesignation.MID_SEM_PRACTICAL,
             start=time(13, 0), end=time(14, 0)),
        sess(date(2026, 9, 24), ClassType.PRACTICAL, S551,
             designation=SessionDesignation.MID_SEM_PRACTICAL,
             start=time(14, 0), end=time(15, 0)),
    ]

    if include_straggler:
        # pre-semester straggler: inside B's unbounded counts, outside scan A's
        # [scan_start, today] window and outside every builder's own bounds
        rows.append(sess(date(2026, 8, 20), ClassType.LECTURE, S501,
                         status=AttendanceStatus.ATTENDED, start=time(9, 0), end=time(9, 50)))
    return rows


def per_student_universe(student_id, choices, records_501):
    """The shared physical schedule with THIS student's data attached:
    BCS-501 lecture records and the per-student elective resolution
    (slot rows resolve via choice_subject_id; None for anchor students)."""
    rows = []
    for r in build_universe(records_501):
        r = dict(r)
        if r["slot"] is not None:
            chosen = choices.get(r["slot"])
            r["choice_subject_id"] = chosen
            resolved = chosen if chosen is not None else r["session_subject_id"]
            r["subject_id"] = resolved
            r["subject_code"] = SUBJECTS[resolved]["code"]
            r["subject_name"] = SUBJECTS[resolved]["name"]
        rows.append(r)
    return rows


# ---------------------------------------------------------------------------
# OLD pipeline: the three SQL scans mirrored as Python filters (see module
# docstring for the exact per-query semantics being mirrored)
# ---------------------------------------------------------------------------

def old_scan_a(universe, enrolled_ids):
    rows = [
        r for r in universe
        if SCAN_START <= r["date"] <= TODAY and resolved_subject_id(r) in enrolled_ids
    ]
    rows.sort(key=order_key)
    return group_practical_occurrences(rows)


def old_scan_b(universe, enrolled_ids):
    rows = [
        r for r in universe
        if r["date"] <= TODAY and resolved_subject_id(r) in enrolled_ids
    ]
    rows.sort(key=order_key)
    return collapse_count_rows(rows, include_subject=True)


def old_scan_c(universe, subject_ids, global_start, global_end):
    rows = [
        r for r in universe
        if global_start <= r["date"] <= global_end
        and (r["session_subject_id"] in subject_ids
             or (r["slot"] is not None and r["choice_subject_id"] in subject_ids))
    ]
    rows.sort(key=order_key)
    return rows


def new_unified(universe):
    rows = [r for r in universe if r["date"] <= UNIFIED_END]
    rows.sort(key=order_key)
    return apply_outcomes(rows)


# ---------------------------------------------------------------------------
# Section runners (real production code on both sides)
# ---------------------------------------------------------------------------

def run_sections(rows, summaries_map, today=TODAY):
    svc = DashboardService(None)
    subjects = [s for s in _subjects_list() if s.id in summaries_map]
    summaries = [(s, summaries_map[s.id]) for s in subjects]
    overall = svc._build_overall(rows, today, SEMESTER_START)
    weekly = svc._build_weekly(rows, today, summaries)
    attention = svc._build_attention_required(subjects, summaries)
    return overall, weekly, attention


_SUBJECT_OBJECTS = None


def _subjects_list():
    from types import SimpleNamespace
    global _SUBJECT_OBJECTS
    if _SUBJECT_OBJECTS is None:
        from app.schemas.academic import SubjectCategory

        def obj(code):
            s = SimpleNamespace(
                id=next(k for k, v in SUBJECTS.items() if v["code"] == code),
                code=code, name=SUBJECTS[next(k for k, v in SUBJECTS.items() if v["code"] == code)]["name"],
                category=SubjectCategory.THEORY if code != "BCS-551" else SubjectCategory.LAB,
            )
            s.attendance_applicable = True
            s.quiz_applicable = s.id in QUIZ_IDS
            return s
        _SUBJECT_OBJECTS = [obj(c) for c in ("BCS-501", "BCS-502", "BCS-503", "BCS-054", "BCS-052", "BCS-058", "BCS-055", "BCS-551")]
    return _SUBJECT_OBJECTS


def mid_sems_for(rows):
    """Simulate get_mid_sem_sessions: designated PRACTICAL sessions per subject."""
    out = {}
    for r in rows:
        if r.get("designation") == SessionDesignation.MID_SEM_PRACTICAL and r["class_type"] == ClassType.PRACTICAL:
            out.setdefault(r["subject_id"], (r["id"], r["date"]))
    return out


def compare_student(universe, enrolled_ids):
    # ---- OLD pipeline -----------------------------------------------------
    old_a = old_scan_a(apply_outcomes(list(universe)), enrolled_ids)
    old_b = old_scan_b(apply_outcomes(list(universe)), enrolled_ids)
    subjects = [s for s in _subjects_list() if s.id in enrolled_ids]
    applicable = [s for s in subjects if s.attendance_applicable]
    mid_sems = mid_sems_for([r for r in old_a])
    summaries_old = AttendanceService.build_subject_summaries(applicable, old_b, mid_sems)

    # ---- NEW pipeline -----------------------------------------------------
    unified = new_unified(universe)
    rows_new, counts_new = DashboardService._derive_legacy_inputs(
        unified, enrolled_ids, TODAY
    )
    summaries_new = AttendanceService.build_subject_summaries(
        applicable, counts_new, mid_sems_for(rows_new)
    )

    # ---- Section equivalence ----------------------------------------------
    overall_old, weekly_old, attention_old = run_sections(old_a, summaries_old)
    overall_new, weekly_new, attention_new = run_sections(rows_new, summaries_new)
    assert overall_old == overall_new
    assert weekly_old == weekly_new
    assert attention_old == attention_new
    assert summaries_old == summaries_new

    # ---- Quiz-window count equivalence (per subject, both windows) ---------
    from app.services.eligibility_service import EligibilityService
    svc = EligibilityService(None)
    quiz_subjects = [s for s in subjects if s.quiz_applicable]
    windowed = EligibilityService._quiz_windows_by_subject(
        quiz_subjects, 2, [], SEMESTER_START, EFFECTIVE_BY_SUBJECT
    )
    effective = EFFECTIVE_BY_SUBJECT
    # OLD: scan C over its own OR-attribution + bounds, then bucket per window
    if windowed:
        global_start = min(w["window_start"] for _, wi, wii in windowed for w in (wi, wii))
        global_end = max(w["window_end"] for _, wi, wii in windowed for w in (wi, wii))
    else:
        global_start = global_end = None
    old_c = old_scan_c(apply_outcomes(list(universe)), QUIZ_IDS, global_start, global_end) \
        if global_start is not None else []
    old_counts = {
        subject.id: {
            "raw_counts": EligibilityService._bucket_window_counts(old_c, subject.id, wi),
            "cumulative_raw_counts": EligibilityService._bucket_window_counts(old_c, subject.id, wii),
        }
        for subject, wi, wii in windowed
    }
    # NEW: bucket straight from the unified rows
    new_counts = svc._quiz_window_counts_from_rows(
        quiz_subjects, 2, [], SEMESTER_START, effective, unified
    )
    assert old_counts == new_counts
    return old_a, rows_new, old_b, counts_new, old_counts, new_counts


def test_student_a_anchor_electives_equivalence():
    universe = per_student_universe(STUDENT_A, CHOICES_A, {
        date(2026, 9, 7): AttendanceStatus.ATTENDED,
        date(2026, 9, 14): AttendanceStatus.ATTENDED,
        date(2026, 9, 21): AttendanceStatus.MISSED,
        date(2026, 9, 28): AttendanceStatus.ATTENDED,
    })
    compare_student(universe, ENROLLED_A)


def test_student_b_choice_electives_equivalence():
    universe = per_student_universe(STUDENT_B, CHOICES_B, {
        date(2026, 9, 7): AttendanceStatus.MISSED,
        date(2026, 9, 14): AttendanceStatus.ATTENDED,
        date(2026, 9, 21): AttendanceStatus.ATTENDED,
        date(2026, 9, 28): AttendanceStatus.MISSED,
    })
    compare_student(universe, ENROLLED_B)


def test_empty_universe_equivalence():
    compare_student([], ENROLLED_A)


def test_no_sessions_for_enrolled_subject_equivalence():
    # A subject with a session but a student who is not enrolled anywhere it
    # resolves to, plus the elective-attribution anomaly: a slot session whose
    # student choice points at an UN-enrolled subject while the anchor itself
    # IS enrolled. Old scan C includes it (session_subject_id branch); the
    # enrollment-joined scans A/B exclude it (resolved = the un-enrolled
    # choice). The unified path must reproduce BOTH behaviors — this case
    # exists to prove the Python scoping did not flatten that difference.
    universe = [
        sess(date(2026, 10, 12), ClassType.LECTURE, S054,
             slot=ElectiveSlot.ELECTIVE_I, choice=S056["id"],
             start=time(12, 0), end=time(12, 50)),
    ]
    compare_student(universe, ENROLLED_A)
