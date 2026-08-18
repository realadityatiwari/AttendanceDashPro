"""
Phase 3 verification — End-to-end quiz event -> eligibility propagation.

Proves the full downstream chain against the real database through the REAL
Events API (committed POST / PATCH / DELETE mutations; exact-id cleanup in the
finally block restores the frozen baseline):

  Events -> active QUIZ_DAY date -> quiz cycle/window -> L/T session counts
         -> Lecture % -> Tutorial % -> (Lecture % + Tutorial %) / 2
         -> Criterion I / Criterion II -> Must Attend / Safe Skip
         -> Final eligibility

  1.  CREATE:     POST /api/v1/events a QUIZ_DAY for BCS-502 on 09-14 (future,
                  inside the Q1-Q2 gap). The new quiz becomes cycle 2
                  (positional re-ranking: 09-21 -> cycle 3, 10-16 -> cycle 4).
                  Every hop of the chain for cycle 2 and the re-ranked cycle 3
                  is compared against a DB-derived reference (calendar-engine
                  windows, attendance-repo counts with quiz-day exclusion,
                  (L% + T%) / 2, per-criterion optimizer, OR-combined final).
  2.  RESCHEDULE: PATCH start_date 09-14 -> 09-16. Stale 09-14 gone; window
                  [08-31, 09-15] drives counts/percentages/average/Must
                  Attend/Safe Skip/final — all update to the new reference.
                  quiz_schedules projection untouched (no stale schedule).
  3.  DEACTIVATE: DELETE /api/v1/events/{id} (soft). Quiz leaves active
                  eligibility; cycle 2 reverts to 09-21 (recalculated),
                  windows recompute, and the payloads return to the exact
                  baseline bodies; no unrelated subject changes.
  4.  REACTIVATE: PATCH active=true. Quiz and every dependent calculation
                  return — cycle-2 payload byte-equal to the reschedule state.
  5.  ISOLATION:  BCS-501 / BCS-503 / BNC-501 eligibility payloads (cycles
                  1-3) byte-identical across all four lifecycle states.
  6.  OPTION-A:   a quiz-day-shaped ClassSession (LECTURE, no timetable link,
                  not extra) inserted inside the cycle-2 window: subject
                  attendance +1 and Track shows it, while eligibility L/T
                  totals stay equal to the quiz-day-excluded reference.
  7.  BASELINE:   exact restore (events/sessions/cancelled/extra/records/
                  enrollments/subjects/quizzes/users; 18 active quiz events
                  == 18 SCHEDULED projection 1:1).

Documented design boundary (asserted, not a failure): the product defines
exactly three quiz cycles (quiz_cycles Quiz1..Quiz3); a 4th effective quiz
date exists at the derivation level, but the eligibility API returns 404 for
cycle 4 (no persisted policy row).

Usage:
    python scripts/verify_phase_3_quiz_eligibility_propagation.py
"""
import asyncio
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path
import math

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User, Section
from app.models.event import AcademicEvent
from app.models.timetable import ClassSession
from app.models.attendance import AttendanceRecord
from app.models.academic import StudentEnrollment, Subject, Semester
from app.models.quiz import QuizSchedule, ScheduleStatus
from app.models.enums import AttendanceStatus, ClassType, EventType
from app.repositories.quiz_repo import QuizRepository
from app.repositories.attendance_repo import AttendanceRepository
from app.repositories.calendar_repo import CalendarRepository
from app.engines.attendance_engine import optimize_attendance, normalize_class_type
from app.engines.calendar_engine import (
    get_attendance_window, get_cumulative_attendance_window, DEFAULT_WEEKENDS,
)
from app.schemas.academic import Subject as SubjectSchema, Milestone, Timeline
from app.schemas.attendance import EligibilityState
from sqlalchemy import select, func, delete

SUBJECT = "BCS-502"
ISOLATION_SUBJECTS = ["BCS-501", "BCS-503", "BNC-501"]
CREATE_DATE = date(2026, 9, 14)
MOVE_DATE = date(2026, 9, 16)
SHAPED_DATE = date(2026, 9, 3)

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def eqf(a, b) -> bool:
    """Float equality that treats two Nones as equal."""
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, abs_tol=1e-9)


def combined_pct(lec_pct, tut_pct):
    if tut_pct is None:
        return lec_pct
    if lec_pct is None:
        return None
    return (lec_pct + tut_pct) / 2.0


def aggregate(raw_counts) -> dict:
    out = {
        'L': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
        'T': {'tot': 0, 'att': 0, 'miss': 0, 'pending': 0},
    }
    for class_type_str, status in raw_counts:
        t = normalize_class_type(class_type_str.value)
        if t not in out:
            continue
        out[t]['tot'] += 1
        if status == AttendanceStatus.ATTENDED:
            out[t]['att'] += 1
        elif status == AttendanceStatus.MISSED:
            out[t]['miss'] += 1
        else:
            out[t]['pending'] += 1
    return out


def _pct(counts) -> float | None:
    return (counts['att'] / counts['tot'] * 100.0) if counts['tot'] > 0 else None


def total_deficit(opt) -> int:
    return opt.lecture_deficit + opt.tutorial_deficit


async def reference_chain(db, user_id, subject, effective_dates, cycle, semester_start) -> dict:
    """DB-derived expected eligibility for one cycle — the independent
    reference the API payload is compared against hop by hop."""
    events = await CalendarRepository(db).get_all_events()
    milestones = [
        Milestone(milestone_id=f"q{cyc}", date=d, type="QUIZ",
                  metadata={"quizCycle": cyc}) for cyc, d in effective_dates]
    domain = SubjectSchema(
        code=subject.code, name="", category="theory",
        quiz_applicable=True, attendance_applicable=True,
        timeline=Timeline(commencement_date=semester_start, milestones=milestones),
    )
    cycle_model = await QuizRepository(db).get_quiz_cycle_with_policy(cycle)
    required = cycle_model.policy.lecture_threshold
    window_i = get_attendance_window(domain, f"q{cycle}", events, DEFAULT_WEEKENDS)
    window_ii = get_cumulative_attendance_window(domain, f"q{cycle}", events, DEFAULT_WEEKENDS)
    attendance_repo = AttendanceRepository(db)
    counts_i = aggregate(await attendance_repo.get_subject_counts_between(
        user_id, subject.id, window_i["window_start"], window_i["window_end"],
        exclude_quiz_day=True))
    counts_ii = aggregate(await attendance_repo.get_subject_counts_between(
        user_id, subject.id, window_ii["window_start"], window_ii["window_end"],
        exclude_quiz_day=True))

    lec_pct = _pct(counts_i['L'])
    tut_pct = _pct(counts_i['T'])
    avg = combined_pct(lec_pct, tut_pct)
    lec_pct_ii = _pct(counts_ii['L'])
    tut_pct_ii = _pct(counts_ii['T'])
    avg_ii = combined_pct(lec_pct_ii, tut_pct_ii)

    opt_i = optimize_attendance(
        counts_i['L']['tot'], counts_i['L']['att'], counts_i['L']['miss'], counts_i['L']['pending'],
        counts_i['T']['tot'], counts_i['T']['att'], counts_i['T']['miss'], counts_i['T']['pending'],
        required)
    opt_ii = optimize_attendance(
        counts_ii['L']['tot'], counts_ii['L']['att'], counts_ii['L']['miss'], counts_ii['L']['pending'],
        counts_ii['T']['tot'], counts_ii['T']['att'], counts_ii['T']['miss'], counts_ii['T']['pending'],
        required)

    def best_avg(counts):
        l, t = counts['L'], counts['T']
        return combined_pct(
            (l['att'] + l['pending']) / l['tot'] * 100.0 if l['tot'] > 0 else None,
            (t['att'] + t['pending']) / t['tot'] * 100.0 if t['tot'] > 0 else None,
        )

    crit_i_pass = avg is not None and avg >= required
    crit_ii_pass = avg_ii is not None and avg_ii >= required
    best_i, best_ii = best_avg(counts_i), best_avg(counts_ii)
    if crit_i_pass or crit_ii_pass:
        state = EligibilityState.ELIGIBLE
    elif (best_i is not None and best_i >= required) or (best_ii is not None and best_ii >= required):
        state = EligibilityState.RECOVERABLE
    else:
        state = EligibilityState.NOT_ELIGIBLE
    top = opt_i if total_deficit(opt_i) <= total_deficit(opt_ii) else opt_ii

    return {
        "quiz_date": next((d for c, d in effective_dates if c == cycle), None),
        "window_start": window_i["window_start"],
        "window_end": window_i["window_end"],
        "counts_i": counts_i,
        "counts_ii": counts_ii,
        "lec_pct": lec_pct,
        "tut_pct": tut_pct,
        "avg": avg,
        "avg_ii": avg_ii,
        "required": required,
        "opt_i": opt_i,
        "opt_ii": opt_ii,
        "top": top,
        "crit_i_pass": crit_i_pass,
        "crit_ii_pass": crit_ii_pass,
        "state": state,
    }


def chain_matches(body: dict, ref: dict) -> bool:
    """Compare the API eligibility body against the reference chain (every hop)."""
    c = body["lecture"]
    t = body["tutorial"]
    opt_i = body["criterion_i"]["optimization"]
    opt_ii = body["criterion_ii"]["optimization"]
    return (
        body["quiz_date"] == ref["quiz_date"].isoformat()
        and body["window_start"] == ref["window_start"].isoformat()
        and body["window_end"] == ref["window_end"].isoformat()
        and (c["total"], c["attended"], c["missed"], c["pending"]) == (
            ref["counts_i"]["L"]["tot"], ref["counts_i"]["L"]["att"],
            ref["counts_i"]["L"]["miss"], ref["counts_i"]["L"]["pending"])
        and (t["total"], t["attended"], t["missed"], t["pending"]) == (
            ref["counts_i"]["T"]["tot"], ref["counts_i"]["T"]["att"],
            ref["counts_i"]["T"]["miss"], ref["counts_i"]["T"]["pending"])
        and eqf(body["lecture_pct"], ref["lec_pct"])
        and eqf(body["tutorial_pct"], ref["tut_pct"])
        and eqf(body["average_pct"], ref["avg"])
        and eqf(body["criterion_i"]["value"], ref["avg"])
        and eqf(body["criterion_ii"]["value"], ref["avg_ii"])
        and body["criterion_i"]["passed"] == ref["crit_i_pass"]
        and body["criterion_ii"]["passed"] == ref["crit_ii_pass"]
        and eqf(body["criterion_i"]["threshold"], ref["required"])
        and eqf(body["criterion_ii"]["threshold"], ref["required"])
        and opt_i["lecture_deficit"] == ref["opt_i"].lecture_deficit
        and opt_i["tutorial_deficit"] == ref["opt_i"].tutorial_deficit
        and opt_i["safe_skip_lecture"] == ref["opt_i"].safe_skip_lecture
        and opt_i["safe_skip_tutorial"] == ref["opt_i"].safe_skip_tutorial
        and opt_ii["lecture_deficit"] == ref["opt_ii"].lecture_deficit
        and opt_ii["tutorial_deficit"] == ref["opt_ii"].tutorial_deficit
        and opt_ii["safe_skip_lecture"] == ref["opt_ii"].safe_skip_lecture
        and opt_ii["safe_skip_tutorial"] == ref["opt_ii"].safe_skip_tutorial
        and body["optimization"]["lecture_deficit"] == ref["top"].lecture_deficit
        and body["optimization"]["tutorial_deficit"] == ref["top"].tutorial_deficit
        and body["optimization"]["safe_skip_lecture"] == ref["top"].safe_skip_lecture
        and body["optimization"]["safe_skip_tutorial"] == ref["top"].safe_skip_tutorial
        and body["final_criterion"]["passed"] == (ref["crit_i_pass"] or ref["crit_ii_pass"])
        and body["state"] == ref["state"].value
        and body["is_eligible"] == (ref["state"] == EligibilityState.ELIGIBLE)
        and body["recoverable"] == (ref["state"] == EligibilityState.RECOVERABLE)
    )


async def effective_dates(db, subject_id) -> list:
    return await QuizRepository(db).get_effective_quiz_dates_for_subject(subject_id)


async def main() -> int:
    async with AsyncSessionLocal() as db:
        events_before = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
        sessions_before = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
        cancelled_before = (await db.execute(
            select(func.count()).select_from(ClassSession).where(ClassSession.is_cancelled.is_(True)))).scalar()
        extra_before = (await db.execute(
            select(func.count()).select_from(ClassSession).where(ClassSession.is_extra.is_(True)))).scalar()
        records_before = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
        enrollments_before = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
        subjects_before = (await db.execute(select(func.count()).select_from(Subject))).scalar()
        quizzes_before = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
        users_before = (await db.execute(select(func.count()).select_from(User))).scalar()
        quiz_events_before = (await db.execute(
            select(func.count()).select_from(AcademicEvent).where(
                AcademicEvent.event_type == EventType.QUIZ_DAY,
                AcademicEvent.active.is_(True)))).scalar()
        scheduled_before = (await db.execute(
            select(func.count()).select_from(QuizSchedule).where(
                QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED))).scalar()

        admin_user = (await db.execute(select(User).where(User.roll_number == "2401220100027"))).scalars().first()
        semester_start = date(2026, 7, 15)
        if admin_user.section_id:
            section = await db.get(Section, admin_user.section_id)
            if section:
                semester = await db.get(Semester, section.semester_id)
                if semester:
                    semester_start = semester.start_date

        subject_ids = {s.code: s.id for s in (await db.execute(select(Subject))).scalars().all()}
        subjects = {s.code: s for s in (await db.execute(select(Subject))).scalars().all()}
        subject_ids_for_shaped = subject_ids[SUBJECT]

        check("0. baseline: BCS-502 active quiz events = 08-31, 09-21, 10-16; "
              "no active event on 09-14/09-16; 18 active quiz events",
              await effective_dates(db, subject_ids[SUBJECT])
              == [(1, date(2026, 8, 31)), (2, date(2026, 9, 21)), (3, date(2026, 10, 16))]
              and quiz_events_before == 18 == scheduled_before,
              f"effective={await effective_dates(db, subject_ids[SUBJECT])}")

    admin_token = create_access_token(str(admin_user.id), admin_user.roll_number)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    test_event_id: uuid.UUID | None = None
    shaped_session_id: uuid.UUID | None = None
    shaped_date_ids: list = []

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # ---- baseline payloads (isolation + BCS-502 for later compare) ----
            isolation_pre = {}
            for code in ISOLATION_SUBJECTS:
                isolation_pre[code] = {}
                for cyc in (1, 2, 3):
                    r = await client.get(f"/api/v1/quiz-eligibility/{code}/{cyc}", headers=admin_headers)
                    isolation_pre[code][cyc] = r.json()
            baseline_bodies = {}
            for cyc in (1, 2, 3):
                r = await client.get(f"/api/v1/quiz-eligibility/{SUBJECT}/{cyc}", headers=admin_headers)
                baseline_bodies[cyc] = r.json()

            # ======================================================= 1. CREATE
            r = await client.post("/api/v1/events", headers=admin_headers, json={
                "event_type": "QUIZ_DAY",
                "start_date": CREATE_DATE.isoformat(),
                "end_date": CREATE_DATE.isoformat(),
                "subject_id": str(subject_ids[SUBJECT]),
                "note": "VerifyPhase3 — QUIZ_DAY BCS-502 09-14",
            })
            check("1. CREATE via the real Events API -> 201, event active",
                  r.status_code == 201 and r.json().get("active") is True,
                  f"status={r.status_code} {r.text[:200]}")
            if r.status_code == 201:
                test_event_id = uuid.UUID(r.json()["id"])
            if test_event_id is None:
                return 1

            ge = await client.get(f"/api/v1/events?date_from={CREATE_DATE.isoformat()}&date_to={CREATE_DATE.isoformat()}",
                                  headers=admin_headers)
            check("1b. the event is listed as active by the Events API",
                  ge.status_code == 200 and any(
                      e["id"] == str(test_event_id) and e["active"] for e in ge.json()),
                  f"events={[(e['id'], e['active']) for e in ge.json()]}")

            async with AsyncSessionLocal() as db:
                eff_created = await effective_dates(db, subject_ids[SUBJECT])
                sessions_after_create = (await db.execute(
                    select(func.count()).select_from(ClassSession))).scalar()
                materialized = (await db.execute(
                    select(ClassSession.id).where(
                        ClassSession.subject_id == subject_ids[SUBJECT],
                        ClassSession.date == CREATE_DATE,
                        ClassSession.timetable_entry_id.is_(None),
                        ClassSession.class_type == ClassType.LECTURE,
                        ~ClassSession.is_extra))).scalars().all()
            check("2. CREATE: positional re-ranking — new quiz = cycle 2 (09-14); "
                  "09-21 -> cycle 3; 10-16 -> cycle 4; the event materializes "
                  "its quiz-day occurrence (+1 session)",
                  eff_created == [(1, date(2026, 8, 31)), (2, CREATE_DATE),
                                  (3, date(2026, 9, 21)), (4, date(2026, 10, 16))]
                  and sessions_after_create == sessions_before + 1
                  and len(materialized) == 1,
                  f"effective={eff_created} sessions {sessions_before}->{sessions_after_create} "
                  f"materialized={len(materialized)}")

            async with AsyncSessionLocal() as db:
                ref = await reference_chain(db, admin_user.id, subjects[SUBJECT], eff_created, 2, semester_start)
            r = await client.get(f"/api/v1/quiz-eligibility/{SUBJECT}/2", headers=admin_headers)
            created_cycle2 = r.json()
            check("3. CREATE chain: cycle 2 (new quiz 09-14) — window/counts/"
                  "percentages/(L%+T%)/2/criteria/Must Attend/Safe Skip/final "
                  "== DB-derived reference",
                  r.status_code == 200 and chain_matches(created_cycle2, ref),
                  f"state={created_cycle2.get('state')} quiz={created_cycle2.get('quiz_date')} "
                  f"window={created_cycle2.get('window_start')}..{created_cycle2.get('window_end')} "
                  f"L={created_cycle2.get('lecture', {}).get('total')} "
                  f"T={created_cycle2.get('tutorial', {}).get('total')} "
                  f"avg={created_cycle2.get('average_pct')}")

            async with AsyncSessionLocal() as db:
                ref3 = await reference_chain(db, admin_user.id, subjects[SUBJECT], eff_created, 3, semester_start)
            r = await client.get(f"/api/v1/quiz-eligibility/{SUBJECT}/3", headers=admin_headers)
            created_cycle3 = r.json()
            check("4. CREATE chain: re-ranked cycle 3 (09-21) — window boundary "
                  "moved to [09-14, 09-20] and the whole chain == reference",
                  r.status_code == 200 and chain_matches(created_cycle3, ref3)
                  and created_cycle3["window_start"] == CREATE_DATE.isoformat()
                  and created_cycle3["window_end"] == "2026-09-20",
                  f"state={created_cycle3.get('state')} quiz={created_cycle3.get('quiz_date')} "
                  f"window={created_cycle3.get('window_start')}..{created_cycle3.get('window_end')} "
                  f"avg={created_cycle3.get('average_pct')}")

            r = await client.get(f"/api/v1/quiz-eligibility/{SUBJECT}/1", headers=admin_headers)
            check("5. CREATE: unaffected cycle 1 (08-31) unchanged from baseline",
                  r.status_code == 200 and r.json() == baseline_bodies[1],
                  f"state={r.json().get('state')} window={r.json().get('window_start')}")

            r = await client.get(f"/api/v1/quiz-eligibility/{SUBJECT}/4", headers=admin_headers)
            check("5b. documented boundary: 4th cycle (10-16) exists at the "
                  "derivation level but the API 404s (no QuizCycle policy row)",
                  r.status_code == 404, f"status={r.status_code}")

            # ---------------------------------------- 6. OPTION-A mini-scenario
            s_sum_pre = (await client.get(
                f"/api/v1/attendance/summary/{SUBJECT}?as_of_date=2026-09-10",
                headers=admin_headers)).json()
            async with AsyncSessionLocal() as db:
                shaped_session_id = uuid.uuid4()
                db.add(ClassSession(
                    id=shaped_session_id,
                    subject_id=subject_ids_for_shaped,
                    date=SHAPED_DATE,
                    class_type=ClassType.LECTURE,
                    is_extra=False,
                    is_cancelled=False,
                    timetable_entry_id=None,
                ))
                await db.commit()

            s_sum = (await client.get(
                f"/api/v1/attendance/summary/{SUBJECT}?as_of_date=2026-09-10",
                headers=admin_headers)).json()
            daily = (await client.get(
                f"/api/v1/attendance/daily/{SHAPED_DATE.isoformat()}",
                headers=admin_headers)).json()["sessions"]
            check("6. OPTION-A: quiz-day-shaped session counts toward subject "
                  "attendance (+1 L total) and appears in Track as its own "
                  "occurrence",
                  s_sum["lecture"]["total"] == s_sum_pre["lecture"]["total"] + 1
                  and any(occ["id"] == str(shaped_session_id)
                          and occ["subject_code"] == SUBJECT
                          and occ["start_time"] is None and not occ["is_extra"]
                          for occ in daily),
                  f"summary L tot={s_sum['lecture']['total']}(pre {s_sum_pre['lecture']['total']}) "
                  f"daily occurrences={[(o['id'][:8], o['start_time']) for o in daily]}")

            async with AsyncSessionLocal() as db:
                ref_with_shaped = await reference_chain(
                    db, admin_user.id, subjects[SUBJECT], eff_created, 2, semester_start)
            r = await client.get(f"/api/v1/quiz-eligibility/{SUBJECT}/2", headers=admin_headers)
            check("6b. OPTION-A: the shaped session is EXCLUDED from eligibility "
                  "L/T counts (chain still == quiz-day-excluded reference; "
                  "totals unchanged)",
                  r.status_code == 200 and chain_matches(r.json(), ref_with_shaped)
                  and r.json()["lecture"]["total"] == created_cycle2["lecture"]["total"],
                  f"L tot={r.json().get('lecture', {}).get('total')}(pre {created_cycle2['lecture']['total']})")

            # ------------------------------------------------ isolation checks
            iso_ok = True
            for code in ISOLATION_SUBJECTS:
                for cyc in (1, 2, 3):
                    r = await client.get(f"/api/v1/quiz-eligibility/{code}/{cyc}", headers=admin_headers)
                    if r.status_code != 200 or r.json() != isolation_pre[code][cyc]:
                        iso_ok = False
            check("6c. SUBJECT ISOLATION: BCS-501 / BCS-503 / BNC-501 payloads "
                  "unchanged by the CREATE + shaped-session",
                  iso_ok)

            # ==================================================== 2. RESCHEDULE
            r = await client.patch(f"/api/v1/events/{test_event_id}", headers=admin_headers, json={
                "start_date": MOVE_DATE.isoformat(),
                "end_date": MOVE_DATE.isoformat(),
            })
            check("7. RESCHEDULE via the real Events API (PATCH 09-14 -> 09-16) -> 200",
                  r.status_code == 200, f"status={r.status_code} {r.text[:200]}")

            async with AsyncSessionLocal() as db:
                eff_moved = await effective_dates(db, subject_ids[SUBJECT])
                schedule_dates = sorted((await db.execute(
                    select(QuizSchedule.date).where(QuizSchedule.subject_id == subject_ids[SUBJECT]))).scalars().all())
                shaped_old = (await db.execute(
                    select(ClassSession.id).where(
                        ClassSession.subject_id == subject_ids[SUBJECT],
                        ClassSession.date == CREATE_DATE,
                        ClassSession.timetable_entry_id.is_(None),
                        ClassSession.class_type == ClassType.LECTURE,
                        ~ClassSession.is_extra))).scalars().all()
                shaped_new = (await db.execute(
                    select(ClassSession.id).where(
                        ClassSession.subject_id == subject_ids[SUBJECT],
                        ClassSession.date == MOVE_DATE,
                        ClassSession.timetable_entry_id.is_(None),
                        ClassSession.class_type == ClassType.LECTURE,
                        ~ClassSession.is_extra))).scalars().all()
            ge_old = await client.get(f"/api/v1/events?date_from={CREATE_DATE.isoformat()}&date_to={CREATE_DATE.isoformat()}",
                                      headers=admin_headers)
            ge_new = await client.get(f"/api/v1/events?date_from={MOVE_DATE.isoformat()}&date_to={MOVE_DATE.isoformat()}",
                                      headers=admin_headers)
            check("7b. no stale quiz: old 09-14 gone, new 09-16 active, cycles "
                  "re-ranked, the stale materialized occurrence removed and the "
                  "new one materialized, quiz_schedules projection untouched",
                  eff_moved == [(1, date(2026, 8, 31)), (2, MOVE_DATE),
                                (3, date(2026, 9, 21)), (4, date(2026, 10, 16))]
                  and not any(e["subject_id"] == str(subject_ids[SUBJECT]) and e["active"]
                              for e in ge_old.json())
                  and any(e["id"] == str(test_event_id) and e["active"] for e in ge_new.json())
                  and len(shaped_old) == 0 and len(shaped_new) == 1
                  and schedule_dates == [date(2026, 8, 31), date(2026, 9, 21), date(2026, 10, 16)],
                  f"effective={eff_moved} shaped 09-14={len(shaped_old)} 09-16={len(shaped_new)} "
                  f"schedules={schedule_dates}")

            async with AsyncSessionLocal() as db:
                ref_moved = await reference_chain(db, admin_user.id, subjects[SUBJECT], eff_moved, 2, semester_start)
            r = await client.get(f"/api/v1/quiz-eligibility/{SUBJECT}/2", headers=admin_headers)
            moved_cycle2 = r.json()
            check("8. RESCHEDULE chain: new window [08-31, 09-15] drives updated "
                  "counts/percentages/average/Must Attend/Safe Skip/final == "
                  "reference; values changed from the CREATE state",
                  r.status_code == 200 and chain_matches(moved_cycle2, ref_moved)
                  and moved_cycle2["window_start"] == "2026-08-31"
                  and moved_cycle2["window_end"] == "2026-09-15"
                  and moved_cycle2 != created_cycle2,
                  f"state={moved_cycle2.get('state')} quiz={moved_cycle2.get('quiz_date')} "
                  f"window={moved_cycle2.get('window_start')}..{moved_cycle2.get('window_end')} "
                  f"L={moved_cycle2.get('lecture', {}).get('total')}(was {created_cycle2['lecture']['total']}) "
                  f"avg={moved_cycle2.get('average_pct')}")

            async with AsyncSessionLocal() as db:
                ref_moved3 = await reference_chain(db, admin_user.id, subjects[SUBJECT], eff_moved, 3, semester_start)
            r = await client.get(f"/api/v1/quiz-eligibility/{SUBJECT}/3", headers=admin_headers)
            check("8b. RESCHEDULE chain: re-ranked cycle 3 window boundary "
                  "[09-16, 09-20] == reference",
                  r.status_code == 200 and chain_matches(r.json(), ref_moved3)
                  and r.json()["window_start"] == MOVE_DATE.isoformat(),
                  f"window={r.json().get('window_start')}..{r.json().get('window_end')}")

            iso_ok = True
            for code in ISOLATION_SUBJECTS:
                for cyc in (1, 2, 3):
                    rr = await client.get(f"/api/v1/quiz-eligibility/{code}/{cyc}", headers=admin_headers)
                    if rr.status_code != 200 or rr.json() != isolation_pre[code][cyc]:
                        iso_ok = False
            check("9. SUBJECT ISOLATION: unchanged after RESCHEDULE",
                  iso_ok)

            # =================================================== 3. DEACTIVATE
            r = await client.delete(f"/api/v1/events/{test_event_id}", headers=admin_headers)
            check("10. DEACTIVATE via the real Events API (DELETE = soft) -> "
                  "200, active false",
                  r.status_code == 200 and r.json().get("active") is False,
                  f"status={r.status_code} active={r.json().get('active')}")

            async with AsyncSessionLocal() as db:
                eff_off = await effective_dates(db, subject_ids[SUBJECT])
            check("10b. the quiz disappears from active eligibility (cycle 2 "
                  "reverts to 09-21; 10-16 back to cycle 3; no stale 09-16)",
                  eff_off == [(1, date(2026, 8, 31)), (2, date(2026, 9, 21)),
                              (3, date(2026, 10, 16))],
                  f"effective={eff_off}")

            for cyc, name in ((2, "cycle 2 (09-21 recalculated)"), (3, "cycle 3 (10-16)")):
                r = await client.get(f"/api/v1/quiz-eligibility/{SUBJECT}/{cyc}", headers=admin_headers)
                check(f"11. DEACTIVATE chain: {name} — windows/counts/"
                      f"percentages/criteria/Must Attend/Safe Skip/final return "
                      f"to the exact baseline payload",
                      r.status_code == 200 and r.json() == baseline_bodies[cyc],
                      f"state={r.json().get('state')} quiz={r.json().get('quiz_date')} "
                      f"window={r.json().get('window_start')}..{r.json().get('window_end')}")

            r = await client.get(f"/api/v1/quiz-eligibility/{SUBJECT}/4", headers=admin_headers)
            check("11b. DEACTIVATE: the pushed-out cycle 4 has no effective quiz "
                  "and no policy row -> 404 (same documented boundary)",
                  r.status_code == 404, f"status={r.status_code}")

            iso_ok = True
            for code in ISOLATION_SUBJECTS:
                for cyc in (1, 2, 3):
                    rr = await client.get(f"/api/v1/quiz-eligibility/{code}/{cyc}", headers=admin_headers)
                    if rr.status_code != 200 or rr.json() != isolation_pre[code][cyc]:
                        iso_ok = False
            check("12. SUBJECT ISOLATION: unchanged after DEACTIVATE",
                  iso_ok)

            # =================================================== 4. REACTIVATE
            r = await client.patch(f"/api/v1/events/{test_event_id}", headers=admin_headers, json={
                "active": True,
            })
            check("13. REACTIVATE via the real Events API (PATCH active=true) -> "
                  "200, active true",
                  r.status_code == 200 and r.json().get("active") is True,
                  f"status={r.status_code}")

            async with AsyncSessionLocal() as db:
                eff_back = await effective_dates(db, subject_ids[SUBJECT])
            r = await client.get(f"/api/v1/quiz-eligibility/{SUBJECT}/2", headers=admin_headers)
            reactivated_cycle2 = r.json()
            check("13b. REACTIVATE chain: quiz and every dependent calculation "
                  "return — cycle-2 payload byte-equal to the reschedule state",
                  eff_back == [(1, date(2026, 8, 31)), (2, MOVE_DATE),
                               (3, date(2026, 9, 21)), (4, date(2026, 10, 16))]
                  and r.status_code == 200 and reactivated_cycle2 == moved_cycle2,
                  f"effective={eff_back} state={reactivated_cycle2.get('state')}")

            iso_ok = True
            for code in ISOLATION_SUBJECTS:
                for cyc in (1, 2, 3):
                    rr = await client.get(f"/api/v1/quiz-eligibility/{code}/{cyc}", headers=admin_headers)
                    if rr.status_code != 200 or rr.json() != isolation_pre[code][cyc]:
                        iso_ok = False
            check("14. SUBJECT ISOLATION: unchanged after REACTIVATE",
                  iso_ok)

    finally:
        # ------------------------------------------------------- exact cleanup
        async with AsyncSessionLocal() as db:
            if shaped_session_id is not None:
                ev_rows = (await db.execute(
                    select(AttendanceRecord).where(
                        AttendanceRecord.class_session_id == shaped_session_id))).scalars().all()
                for rec in ev_rows:
                    await db.delete(rec)
                await db.execute(delete(ClassSession).where(ClassSession.id == shaped_session_id))
            if test_event_id is not None:
                ev = await db.get(AcademicEvent, test_event_id)
                if ev is not None:
                    await db.delete(ev)
            await db.flush()
            # residue sweep: any quiz-day-shaped sessions this run could have
            # created on the three candidate dates (baseline has none).
            shaped_ids = (await db.execute(
                select(ClassSession.id).where(
                    ClassSession.subject_id == subject_ids[SUBJECT],
                    ClassSession.date.in_([CREATE_DATE, MOVE_DATE, SHAPED_DATE]),
                    ClassSession.timetable_entry_id.is_(None),
                    ClassSession.class_type == ClassType.LECTURE,
                    ~ClassSession.is_extra,
                ))).scalars().all()
            for sid in shaped_ids:
                recs = (await db.execute(
                    select(AttendanceRecord).where(AttendanceRecord.class_session_id == sid))).scalars().all()
                for rec in recs:
                    await db.delete(rec)
                await db.execute(delete(ClassSession).where(ClassSession.id == sid))
            await db.commit()

            events_after = (await db.execute(select(func.count()).select_from(AcademicEvent))).scalar()
            sessions_after = (await db.execute(select(func.count()).select_from(ClassSession))).scalar()
            cancelled_after = (await db.execute(
                select(func.count()).select_from(ClassSession).where(ClassSession.is_cancelled.is_(True)))).scalar()
            extra_after = (await db.execute(
                select(func.count()).select_from(ClassSession).where(ClassSession.is_extra.is_(True)))).scalar()
            records_after = (await db.execute(select(func.count()).select_from(AttendanceRecord))).scalar()
            enrollments_after = (await db.execute(select(func.count()).select_from(StudentEnrollment))).scalar()
            subjects_after = (await db.execute(select(func.count()).select_from(Subject))).scalar()
            quizzes_after = (await db.execute(select(func.count()).select_from(QuizSchedule))).scalar()
            users_after = (await db.execute(select(func.count()).select_from(User))).scalar()
            quiz_events_after = (await db.execute(
                select(func.count()).select_from(AcademicEvent).where(
                    AcademicEvent.event_type == EventType.QUIZ_DAY,
                    AcademicEvent.active.is_(True)))).scalar()
            scheduled_after = (await db.execute(
                select(func.count()).select_from(QuizSchedule).where(
                    QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED))).scalar()
            event_pairs = {(e.subject_id, e.start_date) for e in (
                await db.execute(select(AcademicEvent).where(
                    AcademicEvent.event_type == EventType.QUIZ_DAY,
                    AcademicEvent.active.is_(True)))).scalars().all()}
            schedule_pairs = {(s.subject_id, s.date) for s in (
                await db.execute(select(QuizSchedule).where(
                    QuizSchedule.schedule_status == ScheduleStatus.SCHEDULED,
                    QuizSchedule.date.is_not(None)))).scalars().all()}

        check("15. BASELINE: exact database restore after cleanup (no residue; "
              "projection still 1:1 with the 18 active quiz events)",
              (events_before, sessions_before, cancelled_before, extra_before,
               records_before, enrollments_before, subjects_before,
               quizzes_before, users_before)
              == (events_after, sessions_after, cancelled_after, extra_after,
                  records_after, enrollments_after, subjects_after,
                  quizzes_after, users_after)
              and quiz_events_before == quiz_events_after == scheduled_before == scheduled_after
              and event_pairs == schedule_pairs,
              f"events {events_before}->{events_after}, sessions {sessions_before}->{sessions_after}, "
              f"records {records_before}->{records_after}, quizzes {quizzes_before}->{quizzes_after}, "
              f"users {users_before}->{users_after}, quiz_events {quiz_events_before}->{quiz_events_after}, "
              f"scheduled {scheduled_before}->{scheduled_after}")

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))