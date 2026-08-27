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
from app.models.user import Section
from app.models.quiz import QuizCycle, EligibilityPolicy, QuizSchedule, ScheduleStatus
from app.models.enums import SubjectCategory, ClassType, ElectiveSlot

TIMETABLE_PATH = os.path.join(os.path.dirname(__file__), '../../timetable.json')

def tag_to_elective_slot(tag):
    """Phase 23.5: the authoritative catalog slot for a subject tag
    ('Elective-I' -> ELECTIVE_I, 'Elective-II' -> ELECTIVE_II, else None)."""
    if tag == "Elective-I":
        return ElectiveSlot.ELECTIVE_I
    if tag == "Elective-II":
        return ElectiveSlot.ELECTIVE_II
    return None

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
                    elective_slot=tag_to_elective_slot(subj.get('tag')),
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

                        schedule = QuizSchedule(
                            subject_id=subject.id,
                            quiz_cycle_id=qc.id,
                            date=schedule_date,
                            schedule_status=status
                        )
                        db.add(schedule)
                        await db.flush()
                        print(f"  Created QuizSchedule for {subject.code} Cycle {qc.cycle_number} -> {status.value}")

        # 6. Section — every timetable entry belongs to exactly one Section.
        # The current academic model is single-section per semester. Resolve
        # the Section for this semester; create it if absent (idempotent,
        # same convention as setup_single_user.py) so timetable entries
        # always carry a valid section_id.
        section_name = "CSE-51"
        stmt = select(Section).filter_by(semester_id=semester.id)
        sections = (await db.execute(stmt)).scalars().all()
        if len(sections) == 1:
            section = sections[0]
        elif len(sections) == 0:
            section = Section(name=section_name, semester_id=semester.id, program="CSE")
            db.add(section)
            await db.flush()
            print(f"Created Section: {section_name}")
        else:
            print(
                f"WARNING: {len(sections)} sections exist for semester "
                f"'{semester_name}'; cannot unambiguously assign timetable "
                "entries. Skipping timetable seeding."
            )
            section = None

        # 7. Timetable Entries
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
                    if section is None:
                        print("  Skipping TimetableEntry (no section assigned).")
                        continue
                    # Phase 22.3: mark the shared Department Elective slots from
                    # the subject's tag so the application can resolve them to
                    # each student's selection. Regular entries stay NULL.
                    elective_slot = None
                    if subj.tag == "Elective-I":
                        elective_slot = ElectiveSlot.ELECTIVE_I
                    elif subj.tag == "Elective-II":
                        elective_slot = ElectiveSlot.ELECTIVE_II
                    entry = TimetableEntry(
                        subject_id=subj.id,
                        day_of_week=int(day),
                        start_time=parse_time(t_start),
                        end_time=parse_time(t_end),
                        class_type=ctype,
                        section_id=section.id,
                        elective_slot=elective_slot
                    )
                    db.add(entry)
                    print(f"Created TimetableEntry {subj.code} on Day {day}")

        await db.commit()
        print("Seed baseline completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_baseline())
