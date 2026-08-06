import { 
  initCalendarEngine, 
  getAcademicDay, 
  getCalendarEventsByType, 
  getPreviousWorkingDay, 
  getNextWorkingDay, 
  getTeachingDaysBetween, 
  getWorkingDaysUntil, 
  getPolicy,
  addAcademicEvent,
  archiveAcademicEvent,
  syncRuntimeEvents,
  getSubjectEventDeltas
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

function expectThrow(label, fn) {
  try {
    fn();
    console.error(`❌ ${label} (Expected to throw but didn't)`);
    failed++;
  } catch (e) {
    console.log(`✅ ${label} (Threw as expected)`);
  }
}

// Dummy Calendar Data for testing
const mockCalendar = {
  calendarId: '2024-SEM5',
  semesterId: 'sem5',
  semesterStart: '2024-01-01', // Monday
  semesterEnd: '2024-05-31',
  defaultWeekends: [0, 6], // Sun, Sat
  events: [
    {
      eventId: 'pub1',
      type: 'PUBLIC_HOLIDAY',
      startDate: '2024-01-10', // Wed
      endDate: '2024-01-10',
      isWorkingDay: false,
      metadata: {}
    },
    {
      eventId: 'workSat1',
      type: 'WORKING_SATURDAY',
      startDate: '2024-01-13', // Sat
      endDate: '2024-01-13',
      isWorkingDay: true,
      substitutionScheduleOverride: 'MONDAY',
      metadata: {}
    },
    {
      eventId: 'override1',
      type: 'WORKING_DAY_OVERRIDE',
      startDate: '2024-01-15', // Mon -> Non working override? Let's say it's working day but changed schedule
      endDate: '2024-01-15',
      isWorkingDay: true,
      substitutionScheduleOverride: 'TUESDAY',
      metadata: {}
    },
    {
      eventId: 'emer1',
      type: 'EMERGENCY_CLOSURE',
      startDate: '2024-01-20', // Sat
      endDate: '2024-01-20', // Emergency closure overrides a working saturday!
      isWorkingDay: false,
      metadata: {}
    },
    {
      eventId: 'workSat2',
      type: 'WORKING_SATURDAY',
      startDate: '2024-01-20', // Sat
      endDate: '2024-01-20',
      isWorkingDay: true,
      metadata: {}
    },
    {
      eventId: 'quiz1',
      type: 'QUIZ_DAY',
      startDate: '2024-01-25',
      endDate: '2024-01-25',
      isWorkingDay: true,
      metadata: { quizCycle: 1 }
    }
  ],
  policies: {
    quiz: { targetPercentage: 70 },
    attendance: { targetPercentage: 75 }
  }
};

console.log("--- Initializing Engine ---");
initCalendarEngine(mockCalendar);

console.log("--- Executing Tests ---");

// 1. Normal weekday
const normalDay = getAcademicDay('2024-01-08'); // Monday
assert("Normal weekday is teaching day", normalDay.metadata.isTeachingDay === true);
assert("Normal weekday dayType is WORKING_DAY", normalDay.dayType === 'WORKING_DAY');

// 2. Weekend
const weekend = getAcademicDay('2024-01-07'); // Sunday
assert("Weekend is not teaching day", weekend.metadata.isTeachingDay === false);

// 3. Public holiday
const pubHol = getAcademicDay('2024-01-10');
assert("Public holiday is not teaching day", pubHol.metadata.isTeachingDay === false);
assert("Public holiday event attached", pubHol.events[0].type === 'PUBLIC_HOLIDAY');

// 4. Working Saturday
const workSat = getAcademicDay('2024-01-13'); // Saturday but overridden
assert("Working Saturday is teaching day", workSat.metadata.isTeachingDay === true);
assert("Working Saturday has override flag", workSat.metadata.isOverride === true);
assert("Working Saturday has correct substitution", workSat.metadata.substitutionScheduleOverride === 'MONDAY');

// 5. Working day override
const workOvr = getAcademicDay('2024-01-15');
assert("Working day override substitution correct", workOvr.metadata.substitutionScheduleOverride === 'TUESDAY');
assert("Working day override has override flag", workOvr.metadata.isOverride === true);

// 6. Multiple overlapping events (Emergency Closure vs Working Saturday on 2024-01-20)
const overlap = getAcademicDay('2024-01-20');
assert("Emergency Closure overrides Working Saturday", overlap.metadata.isTeachingDay === false);
assert("Emergency Closure dominant", overlap.events[0].type === 'EMERGENCY_CLOSURE');

// 7. Previous working day
const prev = getPreviousWorkingDay('2024-01-11'); // 11th is Thursday. 10th is Pub Hol. 9th is Tuesday.
assert("Previous working day skips holidays", prev === '2024-01-09');

// 8. Next working day
const nxt = getNextWorkingDay('2024-01-12'); // 12th is Friday. 13th is Working Sat.
assert("Next working day resolves Working Saturdays", nxt === '2024-01-13');

// 9. Working day counting
const startCount = getWorkingDaysUntil('2024-01-03'); // 1st, 2nd, 3rd (Mon, Tue, Wed)
assert("getWorkingDaysUntil counts correctly", startCount === 3);

// 10. Teaching day counting
const rangeCount = getTeachingDaysBetween('2024-01-08', '2024-01-14');
// 8(Mon), 9(Tue), 10(Wed-Hol), 11(Thu), 12(Fri), 13(Sat-Work), 14(Sun-Off)
// Days: 8, 9, 11, 12, 13 = 5 days
assert("getTeachingDaysBetween counts accurately", rangeCount.length === 5);

// 11. Policy retrieval
const q1Pol = getPolicy('quiz');
assert('Policy Resolution: Returns specified targetPercentage', q1Pol.targetPercentage === 70);

// Runtime Event Tests
console.log('--- Runtime Academic Events Tests ---');
syncRuntimeEvents({});

// 1. Extra Lecture
addAcademicEvent({
  id: 'e1',
  eventType: 'EXTRA_LECTURE',
  effectiveDate: '2024-01-08',
  subjectCode: 'CS101',
  classType: 'L'
});
assert('Event API: getSubjectEventDeltas returns +1 for Extra Lecture', getSubjectEventDeltas('2024-01-08', 'CS101', 'L') === 1);
assert('Event API: getSubjectEventDeltas returns 0 for wrong subject', getSubjectEventDeltas('2024-01-08', 'CS102', 'L') === 0);
assert('Event API: getSubjectEventDeltas returns 0 for wrong type', getSubjectEventDeltas('2024-01-08', 'CS101', 'T') === 0);

// 2. Class Cancelled
addAcademicEvent({
  id: 'e2',
  eventType: 'CLASS_CANCELLED',
  effectiveDate: '2024-01-09',
  subjectCode: 'CS101',
  classType: 'L'
});
assert('Event API: getSubjectEventDeltas returns -1 for Cancelled Class', getSubjectEventDeltas('2024-01-09', 'CS101', 'L') === -1);

// 3. Multiple events on same day (Cancel + Extra)
addAcademicEvent({
  id: 'e3',
  eventType: 'EXTRA_TUTORIAL',
  effectiveDate: '2024-01-09',
  subjectCode: 'CS101',
  classType: 'T'
});
assert('Event API: Multiple events resolve independently by type (L = -1)', getSubjectEventDeltas('2024-01-09', 'CS101', 'L') === -1);
assert('Event API: Multiple events resolve independently by type (T = +1)', getSubjectEventDeltas('2024-01-09', 'CS101', 'T') === 1);

// 4. Overruled by Closure
addAcademicEvent({
  id: 'e4',
  eventType: 'EMERGENCY_CLOSURE',
  effectiveDate: '2024-01-09',
  isWorkingDay: false
});
assert('Event API: High priority global closure skips standard math and yields 0 delta', getSubjectEventDeltas('2024-01-09', 'CS101', 'L') === 0);

// 5. Remove event
archiveAcademicEvent('e2', '2024-01-09'); // Archive CLASS_CANCELLED
// Now only EXTRA_TUTORIAL and EMERGENCY_CLOSURE exist
// But wait, EMERGENCY_CLOSURE still suppresses it mathematically.
assert('Event API: High priority closure still rules', getSubjectEventDeltas('2024-01-09', 'CS101', 'T') === 0);

console.log('--- Calendar Engine Tests Complete ---');

// 12. Invalid calendar
expectThrow("Init throws on missing semesterStart", () => {
  initCalendarEngine({ ...mockCalendar, semesterStart: null });
});

// 13. Invalid events
expectThrow("Init throws on invalid event date", () => {
  initCalendarEngine({ 
    ...mockCalendar, 
    events: [{ eventId: 'bad', type: 'FESTIVAL_HOLIDAY', startDate: 'not-a-date', endDate: '2024-01-01', isWorkingDay: false }] 
  });
});

// 14. Duplicate IDs
expectThrow("Init throws on duplicate event IDs", () => {
  initCalendarEngine({
    ...mockCalendar,
    events: [
      { eventId: 'dup1', type: 'SEMINAR', startDate: '2024-01-01', endDate: '2024-01-01', isWorkingDay: true },
      { eventId: 'dup1', type: 'SEMINAR', startDate: '2024-01-02', endDate: '2024-01-02', isWorkingDay: true }
    ]
  });
});

// 15. getCalendarEventsByType
const quizEvents = getCalendarEventsByType('QUIZ_DAY');
assert("getCalendarEventsByType returns correct events", quizEvents.length === 1 && quizEvents[0].eventId === 'quiz1');

if (failed > 0) {
  console.error(`\n❌ ${failed} tests failed.`);
  process.exit(1);
} else {
  console.log(`\n✅ All tests passed successfully!`);
}
