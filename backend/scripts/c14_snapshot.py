"""
Chunk 14 — read-only snapshot for the elective-enrollment data repair.

For each tracked user (2401220100027, 9999999999999, 8888888888888) captures:
  - user id / roll number
  - StudentElectiveChoice rows (slot -> subject code)
  - StudentEnrollment rows (code, elective_slot, enrollment_type)
  - enrollment count, quiz-applicable subject count
  - API /api/v1/subjects codes (as the app resolves them)
  - dashboard overall + total_theory
  - Quiz III eligibility per enrolled quiz-applicable subject
  - AttendanceRecord dependency count per enrolled subject (safety check)

NO mutations. Run: python scripts/c14_snapshot.py
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models.academic import StudentEnrollment, StudentElectiveChoice, Subject
from app.models.attendance import AttendanceRecord
from app.models.quiz import QuizSchedule
from sqlalchemy import select

ROLLS = ["2401220100027", "9999999999999", "8888888888888"]


def tok(user):
    return {"Authorization": f"Bearer {create_access_token(str(user.id), user.roll_number)}"}


async def main() -> None:
    async with AsyncSessionLocal() as db:
        users = {u.roll_number: u for u in
                 (await db.execute(select(User).where(User.roll_number.in_(ROLLS)))).scalars().all()}
        subjects = {s.id: s for s in (await db.execute(select(Subject))).scalars().all()}
        quiz_codes = {str(q.subject_id) for q in (await db.execute(select(QuizSchedule))).scalars().all()}
        # session -> subject map, for attendance-dependency counting
        from app.models.timetable import ClassSession
        sess_subject = {sid: str(subj_id) for sid, subj_id in
                        (await db.execute(select(ClassSession.id, ClassSession.subject_id))).all()}
        rec_rows = (await db.execute(select(AttendanceRecord.user_id, AttendanceRecord.class_session_id))).all()
        rec_by_user_subject = {}
        for uid, csid in rec_rows:
            subj = sess_subject.get(csid)
            if subj:
                rec_by_user_subject[(str(uid), subj)] = rec_by_user_subject.get((str(uid), subj), 0) + 1

        for roll in ROLLS:
            u = users.get(roll)
            print(f"\n=== USER {roll} ===")
            if u is None:
                print("  NOT FOUND")
                continue
            print(f"  id={u.id} role={getattr(u.role, 'value', u.role)}")

            choices = (await db.execute(
                select(StudentElectiveChoice).where(StudentElectiveChoice.user_id == u.id))).scalars().all()
            print("  choices:")
            for c in choices:
                sc = subjects.get(c.subject_id)
                print(f"    {getattr(c.elective_slot, 'value', c.elective_slot)} -> "
                      f"{sc.code if sc else c.subject_id}")

            enrollments = (await db.execute(
                select(StudentEnrollment).where(StudentEnrollment.user_id == u.id))).scalars().all()
            quiz_applicable = 0
            print(f"  enrollments ({len(enrollments)}):")
            for e in enrollments:
                sc = subjects.get(e.subject_id)
                slot = getattr(sc.elective_slot, "value", None) if sc else None
                is_quiz = str(e.subject_id) in quiz_codes and (sc is not None and not str(sc.code).startswith("BCS-55"))
                if is_quiz:
                    quiz_applicable += 1
                # attendance dependency safety check (records by THIS user on
                # sessions of this subject)
                dep = rec_by_user_subject.get((str(u.id), str(e.subject_id)), 0)
                print(f"    {sc.code if sc else e.subject_id} slot={slot} "
                      f"type={getattr(e.enrollment_type, 'value', e.enrollment_type)} quiz={is_quiz} "
                      f"dep_records={dep}")

            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                r = await client.get("/api/v1/subjects", headers=tok(u))
                codes = sorted(s["code"] for s in r.json()) if r.status_code == 200 else f"HTTP {r.status_code}"
                print(f"  /subjects ({r.status_code}): {codes}")
                rd = await client.get("/api/v1/dashboard/summary", headers=tok(u))
                if rd.status_code == 200:
                    dj = rd.json()
                    ov = dj.get("overall", {})
                    qs = dj.get("quiz_snapshot", {}) or {}
                    print(f"  dashboard: total_theory={qs.get('total_theory')} "
                          f"quiz_cycle={qs.get('quiz_cycle')} eligible={qs.get('eligible')} "
                          f"attention={qs.get('attention')} not_eligible={qs.get('not_eligible')} "
                          f"attended={ov.get('attended')} recorded={ov.get('recorded')}")
                else:
                    print(f"  dashboard: HTTP {rd.status_code}")
                ra = await client.get("/api/v1/analytics/overview", headers=tok(u))
                if ra.status_code == 200:
                    aj = ra.json()
                    print(f"  analytics: subjects={[s.get('subject_code') for s in aj.get('subjects', [])]}")
                else:
                    print(f"  analytics: HTTP {ra.status_code}")
                # Quiz III eligibility for each enrolled quiz-applicable subject
                elig = []
                for e in enrollments:
                    sc = subjects.get(e.subject_id)
                    if sc is None:
                        continue
                    is_quiz = str(e.subject_id) in quiz_codes and not str(sc.code).startswith("BCS-55")
                    if not is_quiz:
                        continue
                    rq = await client.get(f"/api/v1/quiz-eligibility/{sc.code}/3", headers=tok(u))
                    if rq.status_code == 200:
                        b = rq.json()
                        elig.append(f"{sc.code}(window {b.get('window_start')}..{b.get('window_end')})")
                    else:
                        elig.append(f"{sc.code}(HTTP {rq.status_code})")
                print(f"  quiz-III: {elig}")
    print("\n(snapshot only — nothing was modified)")


if __name__ == "__main__":
    asyncio.run(main())
