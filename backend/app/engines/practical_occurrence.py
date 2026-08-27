"""
Practical occurrence grouping — Track lab attendance correction.

A two-hour laboratory block is scheduled in the timetable as TWO contiguous
one-hour periods (two TimetableEntry / ClassSession rows), but it represents
ONE laboratory attendance occurrence: one Present/Absent decision, one
AttendanceRecord, and it must be counted once in every denominator.

This module is the single, authoritative read-model grouping used by every
practical-attendance consumer (Track daily view, attendance summary/analytics
counting, History, Dashboard, calendar session counts), so no consumer can
define a lab differently from another. It is pure logic — no database access.

Occurrence rules (documented, authoritative, never heuristic):

- Members of one occurrence: PRACTICAL sessions of the SAME subject on the
  SAME date whose timetable periods are contiguous (member.end_time ==
  next.start_time, both timetable-bound). Sessions without timetable times
  (event-created extras) are always standalone occurrences. Non-contiguous
  practicals of the same subject/date are separate occurrences; unrelated
  subjects and different dates are never merged.
- Block status precedence (records are historical truth):
      ATTENDED  if ANY member has an ATTENDED record
      MISSED    elif ANY member has a MISSED record
      CANCELLED elif ANY member is cancelled (no records)
      PENDING   otherwise (no records, nothing cancelled)
  A recorded block is counted even if a DIFFERENT member of the same block
  was later cancelled — the student attended/logged the lab; the synchronizer
  never cancels attended sessions themselves.
- Counting: each occurrence contributes exactly ONE row with its block
  status. Cancelled occurrences (no records) are excluded from the
  denominator (cancelled != absent, never Pending). This is what removes the
  old per-period denominator inflation (a 2-hour lab counted as two).
- Representative session id: the first member by timetable start time (then
  id) among non-cancelled members, else the first member. Attendance
  mutation against the occurrence records ONE AttendanceRecord on that
  canonical session; the collapse absorbs any stray second mark without
  inflating counts.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.models.enums import AttendanceStatus, ClassType


def _contiguous(prev: Dict[str, Any], curr: Dict[str, Any]) -> bool:
    """True when `curr` is the next timetable period of `prev`'s lab block."""
    p_start, p_end = prev.get("start_time"), prev.get("end_time")
    c_start, c_end = curr.get("start_time"), curr.get("end_time")
    if p_start is None or p_end is None or c_start is None or c_end is None:
        # Event-created extras have no timetable times -> standalone occurrence.
        return False
    return p_end == c_start


def _subject_key(row: Dict[str, Any]):
    return row.get("subject_id") or row.get("subject_code")


def occurrence_is_cancelled(occ: Dict[str, Any]) -> bool:
    """
    Canonical "this occurrence counts as Cancelled (never pending/absent/
    attended)" rule — the single definition shared by every counting/filtering
    consumer (collapse_count_rows, history summary/filters, dashboard).

    - A non-cancelled occurrence is never counted as cancelled.
    - A cancelled PRACTICAL block keeps its frozen Phase 8/9 lab contract: a
      recorded block is historical truth and is counted by its record status;
      only a record-less cancelled block presents as Cancelled.
    - A cancelled LECTURE/TUTORIAL occurrence always presents as Cancelled:
      CLASS_CANCELLED class-reality propagates over stale marks (a mark
      entered before the cancellation was known), so a cancelled theory class
      never counts as an absence anywhere.
    - Phase 23.6: an ``occurrence_outcome`` of type CANCELLED for the
      student's subject is treated identically to a direct is_cancelled flag
      (the outcome is applied at the read layer, so the row's is_cancelled
      is already True when the student's subject has a CANCELLED outcome).
    """
    if not occ.get("is_cancelled"):
        return False
    if occ.get("class_type") == ClassType.PRACTICAL:
        return occ.get("status") is None
    return True


def group_practical_occurrences(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Collapse contiguous same-subject/same-date PRACTICAL rows into ONE logical
    occurrence. Non-PRACTICAL rows pass through unchanged.

    Input rows MUST be ordered by (date, start_time, id) so contiguity is
    evaluated left-to-right; callers are responsible for the ordering.

    The returned occurrence dicts carry the same keys as the input rows, plus
    `member_ids` (the canonical session ids of the block). Fields are resolved
    as follows:

      id            representative session (first non-cancelled member, else
                    first member)
      start_time    earliest member start; end_time latest member end
      status        block status (None = PENDING; a cancelled-only block also
                    has status None and is_cancelled True)
      is_cancelled  True when ANY member is cancelled
      designation   the first non-null member designation (e.g. a mid-sem
                    designated session makes the whole block the mid-sem)
      is_extra      True when the (single) member is an extra
    """
    occurrences: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []

    def flush() -> None:
        if pending:
            occurrences.append(_collapse_block(pending))
            pending.clear()

    for row in rows:
        if row.get("class_type") != ClassType.PRACTICAL:
            flush()
            occurrences.append(row)
            continue
        if pending and (
            _subject_key(pending[-1]) != _subject_key(row)
            or pending[-1].get("date") != row.get("date")
            or not _contiguous(pending[-1], row)
        ):
            flush()
        pending.append(row)
    flush()
    return occurrences


def _collapse_block(members: List[Dict[str, Any]]) -> Dict[str, Any]:
    base = dict(members[0])
    statuses = [m.get("status") for m in members]

    block_status: Optional[AttendanceStatus] = None
    if any(s == AttendanceStatus.ATTENDED for s in statuses):
        block_status = AttendanceStatus.ATTENDED
    elif any(s == AttendanceStatus.MISSED for s in statuses):
        block_status = AttendanceStatus.MISSED
    # else: CANCELLED-only (is_cancelled=True, status None) or PENDING.

    any_cancelled = any(bool(m.get("is_cancelled")) for m in members)
    # Representative session id (the one attendance mutation targets):
    #   1. the first member WITH a record (so "Change" on a recorded block
    #      updates that canonical record), else
    #   2. the first CANCELLED member (a cancelled block must reject marking
    #      with the existing 409 — never silently mark a cancelled lab), else
    #   3. the first member.
    recorded_members = [m for m in members if m.get("status") is not None]
    cancelled_members = [m for m in members if m.get("is_cancelled")]
    if recorded_members:
        representative = recorded_members[0]
    elif cancelled_members:
        representative = cancelled_members[0]
    else:
        representative = members[0]

    # Counting-only rows (no session id columns) skip the identity fields;
    # read-model rows get the representative session + the member id list.
    if "id" in members[0]:
        base["id"] = representative["id"]
        base["member_ids"] = [m["id"] for m in members]
    base["is_cancelled"] = any_cancelled
    base["status"] = block_status
    base["designation"] = next(
        (m.get("designation") for m in members if m.get("designation")), None
    )
    # marked_at: the first member record timestamp (history surfaces it).
    base["marked_at"] = next(
        (m.get("marked_at") for m in members if m.get("marked_at") is not None), None
    )
    starts = [m["start_time"] for m in members if m.get("start_time") is not None]
    ends = [m["end_time"] for m in members if m.get("end_time") is not None]
    base["start_time"] = min(starts) if starts else None
    base["end_time"] = max(ends) if ends else None
    return base


def collapse_count_rows(
    rows: List[Dict[str, Any]],
    include_subject: bool = False,
) -> List[Tuple[Any, ...]]:
    """
    Project occurrence rows to the canonical counting shape the attendance
    engine consumes: (class_type, status) tuples, or
    (subject_id, class_type, status) when `include_subject`.

    Cancelled sessions are excluded exactly as the legacy queries did
    (`is_cancelled.is_(False)`): a cancelled non-P row is dropped; a cancelled
    P occurrence with no records is dropped (the whole lab was cancelled and
    never counts as Pending/Absent). A recorded occurrence is counted once
    with its block status (None status = PENDING). A cancelled LECTURE/
    TUTORIAL occurrence is always dropped — CLASS_CANCELLED propagates over
    stale marks (occurrence_is_cancelled).
    """
    out: List[Tuple[Any, ...]] = []
    for occ in group_practical_occurrences(rows):
        if occurrence_is_cancelled(occ):
            continue
        if include_subject:
            out.append((occ["subject_id"], occ["class_type"], occ.get("status")))
        else:
            out.append((occ["class_type"], occ.get("status")))
    return out
