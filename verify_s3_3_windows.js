import fs from 'fs';
import { 
  initCalendarEngine, 
  getQuizWindow
} from './js/calendar-engine.js';
import { getTimetable } from './js/utils.js';

let failed = 0;
function assert(label, condition) {
  if (condition) {
    console.log(`✅ ${label}`);
  } else {
    console.error(`❌ ${label}`);
    failed++;
  }
}

const timetable = JSON.parse(fs.readFileSync('./timetable.json', 'utf8'));

// Inject policies if not parsed properly by utils (mock for calendar engine)
const calendarData = {
  calendarId: '2026-SEM5',
  semesterId: 'sem5',
  semesterStart: timetable.start_date,
  semesterEnd: '2026-12-31', // Mock end
  defaultWeekends: [0], // Sunday
  events: [],
  subjectTimelines: timetable.subjects.map(subj => {
    const commencement = subj.timeline ? subj.timeline.commencementDate : timetable.start_date;
    const milestones = subj.timeline ? [...subj.timeline.milestones] : timetable.quiz_dates.map((q, i) => ({
      type: 'QUIZ',
      milestoneId: `q${i+1}`,
      date: q.date,
      metadata: { quizCycle: i + 1 }
    }));
    
    milestones.unshift({
      milestoneId: 'm0',
      type: 'FIRST_LECTURE',
      date: commencement,
      metadata: {}
    });
    
    return {
      subjectCode: subj.code,
      commencementDate: commencement,
      milestones
    };
  }),
  policies: timetable.policies
};

initCalendarEngine(calendarData);

console.log("--- BNC-501 (Custom Timeline) ---");
const bncQ1 = getQuizWindow('BNC-501', 1);
assert("BNC-501 Q1 start == commencement (2026-07-20)", bncQ1.windowStart === '2026-07-20');
assert("BNC-501 Q1 end == day before Q1 (2026-08-18)", bncQ1.windowEnd === '2026-08-18');

const bncQ2 = getQuizWindow('BNC-501', 2);
assert("BNC-501 Q2 start == Q1 date (2026-08-19)", bncQ2.windowStart === '2026-08-19');
assert("BNC-501 Q2 end == day before Q2 (2026-09-15)", bncQ2.windowEnd === '2026-09-15');

const bncQ3 = getQuizWindow('BNC-501', 3);
assert("BNC-501 Q3 start == Q2 date (2026-09-16)", bncQ3.windowStart === '2026-09-16');
assert("BNC-501 Q3 end == day before Q3 (2026-10-22)", bncQ3.windowEnd === '2026-10-22');


console.log("--- BCS-058 (Global Timeline) ---");
const bcsQ1 = getQuizWindow('BCS-058', 1);
assert("BCS-058 Q1 start == global commencement (2026-07-15)", bcsQ1.windowStart === '2026-07-15');
assert("BCS-058 Q1 end == day before Q1 (2026-08-16)", bcsQ1.windowEnd === '2026-08-16');

const bcsQ2 = getQuizWindow('BCS-058', 2);
assert("BCS-058 Q2 start == Q1 date (2026-08-17)", bcsQ2.windowStart === '2026-08-17');
assert("BCS-058 Q2 end == day before Q2 (2026-09-13)", bcsQ2.windowEnd === '2026-09-13');

const bcsQ3 = getQuizWindow('BCS-058', 3);
assert("BCS-058 Q3 start == Q2 date (2026-09-14)", bcsQ3.windowStart === '2026-09-14');
assert("BCS-058 Q3 end == day before Q3 (2026-10-20)", bcsQ3.windowEnd === '2026-10-20');

if (failed > 0) {
  console.error(`❌ ${failed} tests failed`);
  process.exit(1);
} else {
  console.log("✅ All window boundary tests passed!");
}
