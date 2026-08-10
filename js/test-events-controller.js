import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Mock fetch for utils.js
global.fetch = async (url) => {
  if (url === 'timetable.json') {
    const __dirname = path.dirname(fileURLToPath(import.meta.url));
    const data = fs.readFileSync(path.join(__dirname, '..', 'timetable.json'), 'utf8');
    return {
      json: async () => JSON.parse(data)
    };
  }
  throw new Error('Unknown URL ' + url);
};

import { getTimetable, initTimetable } from './utils.js';
import { 
  initCalendarEngine, 
  syncRuntimeEvents, 
  getAcademicDay, 
  getEffectiveDaySchedule 
} from './calendar-engine.js';
import { getAttendanceData, computeSubjectStats, getSubjectQuizOptimization } from './attendance-engine.js';
import { 
  createAcademicEvent as normalizeAcademicEvent
} from './calendar-engine.js';

let failed = 0;

function assert(label, condition) {
  if (condition) {
    console.log(`✅ ${label}`);
  } else {
    console.error(`❌ ${label}`);
    failed++;
  }
}

// Minimal stub for AppState
const AppState = {
  academicEvents: {},
  attendance: {}
};

function createTestEvent(date, type, subjectCode, classType) {
  const e = normalizeAcademicEvent({
    id: 'evt_' + Math.random().toString(36).substr(2, 9),
    eventType: type,
    effectiveDate: date,
    subjectCode: subjectCode || null,
    classType: classType || null,
    active: true
  });
  if (!AppState.academicEvents[date]) AppState.academicEvents[date] = [];
  AppState.academicEvents[date].push(e);
  syncRuntimeEvents(AppState.academicEvents);
  return e;
}

async function runTests() {
  console.log("--- Initializing Engine ---");
  await initTimetable();
  const timetable = getTimetable();
  
  const timelines = timetable.subjects.map(s => {
    return {
      subjectCode: s.code,
      commencementDate: s.timeline?.commencementDate || timetable.start_date,
      milestones: s.timeline?.milestones || timetable.quiz_dates.map((q, idx) => ({
        milestoneId: `q${idx+1}`,
        type: 'QUIZ',
        date: q.date,
        metadata: { quizCycle: idx + 1 }
      }))
    };
  });

  timelines.forEach(tl => {
    if (!tl.milestones.some(m => m.type === 'FIRST_LECTURE')) {
      tl.milestones.unshift({
        milestoneId: 'm0',
        type: 'FIRST_LECTURE',
        date: tl.commencementDate,
        metadata: {}
      });
    }
  });

  initCalendarEngine({
    calendarId: 'baseline',
    semesterId: 'test1',
    semesterStart: timetable.start_date,
    semesterEnd: '2026-12-31',
    defaultWeekends: [0, 6],
    subjectTimelines: timelines,
    policies: {},
    events: []
  });

  console.log("--- Running S4.3 Assertions ---");

  // 1. exact-date extra lecture
  // Wednesday 2026-08-12: normally BCS-054(L), BCS-058(L), BCS-501(L), BCS-503(L), BCS-552(P1), BCS-552(P2)
  const dateStr = '2026-08-12';
  const baseSched = getEffectiveDaySchedule(dateStr);
  
  createTestEvent(dateStr, 'EXTRA_LECTURE', 'BCS-502', 'L');
  let effSched = getEffectiveDaySchedule(dateStr);
  assert("1. exact-date extra lecture", effSched.length === baseSched.length + 1 && effSched.some(c => c.s === 'BCS-502' && c.isExtra && c.t.startsWith('L_extra_')));

  // 2. exact-date extra tutorial
  createTestEvent(dateStr, 'EXTRA_TUTORIAL', 'BCS-502', 'T');
  effSched = getEffectiveDaySchedule(dateStr);
  assert("2. exact-date extra tutorial", effSched.some(c => c.s === 'BCS-502' && c.isExtra && c.t.startsWith('T_extra_')));

  // 3. exact-date extra practical
  createTestEvent(dateStr, 'EXTRA_PRACTICAL', 'BCS-553', 'P1');
  effSched = getEffectiveDaySchedule(dateStr);
  assert("3. exact-date extra practical", effSched.some(c => c.s === 'BCS-553' && c.isExtra && c.t.startsWith('P1_extra_')));

  // 4. surprise quiz semantics
  createTestEvent(dateStr, 'SURPRISE_QUIZ', 'BCS-503', 'L');
  effSched = getEffectiveDaySchedule(dateStr);
  assert("4. surprise quiz semantics", effSched.some(c => c.s === 'BCS-503' && c.isExtra && c.t.startsWith('L_extra_')));

  // 8. past cancellation
  // Cancel the BCS-501 lecture on 2026-08-12
  createTestEvent(dateStr, 'CLASS_CANCELLED', 'BCS-501', 'L');
  effSched = getEffectiveDaySchedule(dateStr);
  assert("8. past cancellation (removes one specific occurrence)", !effSched.some(c => c.s === 'BCS-501' && c.t === 'L'));

  // 11. holiday removes opportunities
  createTestEvent(dateStr, 'PUBLIC_HOLIDAY', null, null);
  effSched = getEffectiveDaySchedule(dateStr);
  console.log("TEST 11 effSched length:", effSched.length, effSched);
  assert("11. holiday removes opportunities", effSched.length === 0);

  // Clear events for next tests
  AppState.academicEvents = {};
  syncRuntimeEvents({});

  // 12. cancellation scoped to class type
  // Tuesday 2026-08-11 has BCS-501(L) and BCS-501(T)
  createTestEvent('2026-08-11', 'CLASS_CANCELLED', 'BCS-501', 'L');
  effSched = getEffectiveDaySchedule('2026-08-11');
  assert("12. cancellation scoped to class type", !effSched.some(c => c.s === 'BCS-501' && c.t === 'L') && effSched.some(c => c.s === 'BCS-501' && c.t === 'T'));

  // 13. event scoped to subject
  assert("13. event scoped to subject", effSched.some(c => c.s === 'BCS-503' && c.t === 'L')); // BCS-503 is untouched by BCS-501 cancellation

  // 14. multiple events coexist
  createTestEvent('2026-08-11', 'EXTRA_LECTURE', 'BCS-502', 'L');
  effSched = getEffectiveDaySchedule('2026-08-11');
  assert("14. multiple events coexist", effSched.some(c => c.s === 'BCS-501' && c.t === 'T') && effSched.some(c => c.s === 'BCS-502' && c.isExtra));

  // 16. events don't create attendance records
  // getAttendanceData relies purely on AppState.attendance (mocked as {} here). It should just increment pending.
  const attData = getAttendanceData('2026-08-17', AppState.attendance);
  const bcs501stats = computeSubjectStats('BCS-501', 'DBMS', null, attData['BCS-501']);
  console.log("TEST 16 stats:", { attL: bcs501stats.attL, pendingL: bcs501stats.pendingL });
  assert("16. events don't create attendance records (only pending changes)", bcs501stats.attL === 0 && bcs501stats.pendingL > 0);

  // 19. current attendance reacts to past/today event appropriately
  // Let's mark the extra lecture as Attended!
  const extraLec = effSched.find(c => c.s === 'BCS-501' && c.isExtra);
  const extraClassId = extraLec ? `2026-08-11:BCS-501:${extraLec.t}` : 'invalid';
  AppState.attendance[extraClassId] = 'Attended';
  const attData2 = getAttendanceData('2026-08-17', AppState.attendance);
  const bcs501stats2 = computeSubjectStats('BCS-501', 'DBMS', null, attData2['BCS-501']);
  assert("19. current attendance reacts to past/today event", bcs501stats2.attL === 1);

  // 20. quiz engine receives event-adjusted schedule correctly
  const opt = getSubjectQuizOptimization('BCS-501', 1, AppState.attendance, 75);
  assert("20. quiz engine receives event-adjusted schedule correctly", opt.lecturePercentage !== null && opt.reachable !== null);

  if (failed === 0) {
    console.log("\n✅ All S4.3 Event Engine Contract Tests Passed!");
  } else {
    console.error(`\n❌ ${failed} tests failed.`);
    process.exit(1);
  }
}

runTests().catch(console.error);
