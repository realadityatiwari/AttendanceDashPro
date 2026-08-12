import asyncio
import json
import os
import sys
from datetime import date, datetime, time

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db.session import AsyncSessionLocal
from app.models.academic import AcademicSession, Semester, Subject
from app.models.timetable import TimetableEntry
from app.models.quiz import QuizCycle, EligibilityPolicy, QuizSchedule, ScheduleStatus
from app.models.enums import SubjectCategory, ClassType
from sqlalchemy import select

TIMETABLE_PATH = os.path.join(os.path.dirname(__file__), '../../timetable.json')

def parse_time(t_str: str) -> time:
    """Parse '09:00 AM' into datetime.time"""
    return datetime.strptime(t_str, "%I:%M %p").time()

def normalize_class_type(type_str: str) -> ClassType:
    type_str = type_str.strip().upper()
    if type_str.startswith('L'):
        return ClassType.LECTURE
    elif type_str.startswith('T'):
        return ClassType.TUTORIAL
    elif type_str.startswith('P'):
        return ClassType.PRACTICAL
    return ClassType.LECTURE # Fallback

async def seed_baseline():
    print("Loading timetable.json...")
    with open(TIMETABLE_PATH, 'r') as f:
        data = json.load(f)

    async with AsyncSessionLocal() as db:
        # 1. Academic Session
        session_name = "2026-27"
        stmt = select(AcademicSession).filter_by(name=session_name)
        result = await db.execute(stmt)
        acad_session = result.scalars().first()
        if not acad_session:
            acad_session = AcademicSession(
                name=session_name,
                start_date=date.fromisoformat(data['start_date']),
                end_date=date.fromisoformat(data['end_date'])
            )
            db.add(acad_session)
            await db.flush()
            print(f"Created AcademicSession: {session_name}")

        # 2. Semester
        semester_name = "V Semester"
        stmt = select(Semester).filter_by(name=semester_name, session_id=acad_session.id)
        result = await db.execute(stmt)
        semester = result.scalars().first()
        if not semester:
            semester = Semester(
                name=semester_name,
                session_id=acad_session.id,
                start_date=date.fromisoformat(data['start_date']),
                end_date=date.fromisoformat(data['end_date'])
            )
            db.add(semester)
            await db.flush()
            print(f"Created Semester: {semester_name}")

        # 3. Quiz Cycles & Policies
        quiz_cycles_data = data['quiz_cycles']
        quiz_targets = data['policies']['quiz']
        cycles = {}
        for q_data in quiz_cycles_data:
            idx = q_data['cycle']
            label = q_data['label']
            target_key = f"quiz{idx}"
            target_pct = quiz_targets.get(target_key, quiz_targets.get("default", {"targetPercentage": 75}))["targetPercentage"]
            
            stmt = select(QuizCycle).filter_by(cycle_number=idx)
            result = await db.execute(stmt)
            qc = result.scalars().first()
            if not qc:
                qc = QuizCycle(cycle_number=idx, label=label)
                db.add(qc)
                await db.flush()
                
                policy = EligibilityPolicy(
                    quiz_cycle_id=qc.id,
                    lecture_threshold=float(target_pct),
                    combined_threshold=float(target_pct)
                )
                db.add(policy)
                await db.flush()
                print(f"Created QuizCycle {idx} with target {target_pct}%")
            cycles[f"q{idx}"] = qc

        # 4. Subjects
        subject_map = {}
        for subj in data['subjects']:
            stmt = select(Subject).filter_by(code=subj['code'])
            result = await db.execute(stmt)
            subject = result.scalars().first()
            if not subject:
                subject = Subject(
                    code=subj['code'],
                    name=subj['name'],
                    tag=subj.get('tag'),
                    category=SubjectCategory.THEORY if subj['category'] == 'theory' else SubjectCategory.LAB,
                    quiz_applicable=subj.get('quizApplicable', True),
                    attendance_applicable=subj.get('attendanceApplicable', True),
                    semester_id=semester.id
                )
                db.add(subject)
                await db.flush()
                print(f"Created Subject: {subject.code}")
            subject_map[subject.code] = subject

            # 5. Subject Quiz Schedules (Milestones)
            if subject.quiz_applicable and 'timeline' in subj and 'milestones' in subj['timeline']:
                for cycle_key, qc in cycles.items():
                    stmt = select(QuizSchedule).filter_by(subject_id=subject.id, quiz_cycle_id=qc.id)
                    result = await db.execute(stmt)
                    if not result.scalars().first():
                        # Find milestone
                        ms = next((m for m in subj['timeline']['milestones'] if m.get('milestoneId') == cycle_key), None)
                        
                        schedule_date = None
                        status = ScheduleStatus.UNRESOLVED
                        
                        if ms and ms.get('date'):
                            schedule_date = date.fromisoformat(ms['date'])
                            status = ScheduleStatus.SCHEDULED
                        
                        # Explicit rule: BCS-054 Quiz III is officially unresolved
                        if subject.code == 'BCS-054' and qc.cycle_number == 3:
                            schedule_date = None
                            status = ScheduleStatus.UNRESOLVED
                        
                        schedule = QuizSchedule(
                            subject_id=subject.id,
                            quiz_cycle_id=qc.id,
                            date=schedule_date,
                            schedule_status=status
                        )
                        db.add(schedule)
                        await db.flush()
                        print(f"  Created QuizSchedule for {subject.code} Cycle {qc.cycle_number} -> {status.value}")

        # 6. Timetable Entries
        time_slots = data['time_slots']
        for day, classes in data['day_schedule'].items():
            for idx, cls in enumerate(classes):
                subj = subject_map.get(cls['s'])
                if not subj:
                    continue
                
                # Convert to enum
                ctype = ClassType.LECTURE
                if cls['t'] == 'T': ctype = ClassType.TUTORIAL
                if cls['t'].startswith('P'): ctype = ClassType.PRACTICAL
                
                slot = time_slots[idx]
                t_start, t_end = slot.split(' - ')
                
                stmt = select(TimetableEntry).filter_by(
                    subject_id=subj.id,
                    day_of_week=int(day),
                    start_time=parse_time(t_start),
                    end_time=parse_time(t_end)
                )
                result = await db.execute(stmt)
                if not result.scalars().first():
                    entry = TimetableEntry(
                        subject_id=subj.id,
                        day_of_week=int(day),
                        start_time=parse_time(t_start),
                        end_time=parse_time(t_end),
                        class_type=ctype
                    )
                    db.add(entry)
                    print(f"Created TimetableEntry {subj.code} on Day {day}")

        await db.commit()
        print("Seed baseline completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_baseline())
