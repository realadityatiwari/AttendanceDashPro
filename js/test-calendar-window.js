import { 
  initCalendarEngine, 
  getSubjectTimeline,
  getSubjectMilestones,
  getPreviousMilestone,
  getNextMilestone,
  getAttendanceWindow,
  getQuizWindow,
  getWindowTeachingDays,
  getRemainingTeachingDays
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

const mockCalendarBase = {
  calendarId: '2024-SEM5',
  semesterId: 'sem5',
  semesterStart: '2024-01-01',
  semesterEnd: '2024-05-31',
  defaultWeekends: [0, 6],
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
      eventId: 'emer1',
      type: 'EMERGENCY_CLOSURE',
      startDate: '2024-01-15', // Mon
      endDate: '2024-01-15', 
      isWorkingDay: false,
      metadata: {}
    }
  ],
  policies: {}
};

// Base valid timelines
const timelines = [
  {
    subjectCode: 'CS101', // Starts on semester start
    commencementDate: '2024-01-01',
    completionDate: '2024-05-31',
    milestones: [
      { milestoneId: 'm1', type: 'FIRST_LECTURE', date: '2024-01-01', metadata: {} },
      { milestoneId: 'm2', type: 'QUIZ', date: '2024-01-20', metadata: { quizCycle: 1 } },
      { milestoneId: 'm3', type: 'QUIZ', date: '2024-02-20', metadata: { quizCycle: 2 } },
      { milestoneId: 'm4', type: 'SURPRISE_QUIZ', date: '2024-03-01', metadata: {} }
    ]
  },
  {
    subjectCode: 'CS102', // Starts after semester start
    commencementDate: '2024-01-05',
    completionDate: '2024-05-31',
    milestones: [
      { milestoneId: 'n1', type: 'FIRST_LECTURE', date: '2024-01-05', metadata: {} },
      { milestoneId: 'n2', type: 'QUIZ', date: '2024-01-20', metadata: { quizCycle: 1 } }
    ]
  },
  {
    subjectCode: 'CS103', // No milestones
    commencementDate: '2024-01-01',
    completionDate: '2024-05-31',
    milestones: []
  },
  {
    subjectCode: 'CS104', // Future first lecture
    commencementDate: '2024-12-01',
    completionDate: '2024-12-31',
    milestones: [
      { milestoneId: 'p1', type: 'FIRST_LECTURE', date: '2024-12-01', metadata: {} },
      { milestoneId: 'p2', type: 'QUIZ', date: '2024-12-15', metadata: { quizCycle: 1 } }
    ]
  }
];

console.log("--- Initializing Engine for Timeline Tests ---");
initCalendarEngine({ ...mockCalendarBase, subjectTimelines: timelines });

console.log("--- Executing Window Tests ---");

// 1. Subject starts after semester start
const windowCS102 = getQuizWindow('CS102', 1);
assert("Subject starts after semester start", windowCS102.windowStart === '2024-01-05');

// 2. Subject starts on semester start
const windowCS101 = getQuizWindow('CS101', 1);
assert("Subject starts on semester start", windowCS101.windowStart === '2024-01-01');

// 3. Subject has no milestones
assert("Subject has no milestones", getSubjectMilestones('CS103').length === 0);

// 4. Subject has multiple quiz cycles
const windowCS101_q2 = getQuizWindow('CS101', 2);
assert("Subject has multiple quiz cycles", windowCS101_q2.windowEnd === '2024-02-19'); // One day before 2024-02-20

// 5. Attendance window ends exactly one day before quiz
assert("Attendance window ends exactly one day before quiz", windowCS101.windowEnd === '2024-01-19');

// 6. Public holiday inside window
assert("Public holiday inside window correctly counted", windowCS101.holidayCount >= 1); // 2024-01-10 is in window

// 7. Working Saturday inside window
// Window is 2024-01-01 to 2024-01-19. Sat 13th is working.
// So there are 2 weekends (6th, 7th) and (14th), 13th is working.
// Normal Mon-Fri from 1st to 19th is 15 days.
// 10th is hol (-1) = 14. 15th is emer (-1) = 13.
// 13th is workSat (+1) = 14 working days.
assert("Working Saturday included in teaching days", windowCS101.workingDays === 14);

// 8. Emergency closure inside window
// 15th is emergency closure
const windowDates = getWindowTeachingDays(windowCS101);
assert("Emergency closure inside window correctly excluded", !windowDates.includes('2024-01-15'));

// 9. Surprise quiz milestone
const surpriseWindow = getAttendanceWindow('CS101', 'm4');
assert("Surprise quiz milestone supported", surpriseWindow.windowEnd === '2024-02-29');

// 10. Future first lecture
const futureWindow = getQuizWindow('CS104', 1);
assert("Future first lecture works", futureWindow.windowStart === '2024-12-01');

// 11. Previous milestone lookup
assert("Previous milestone lookup", getPreviousMilestone('CS101', 'm2').type === 'FIRST_LECTURE');
assert("Previous milestone on first returns null", getPreviousMilestone('CS101', 'm1') === null);

// 12. Next milestone lookup
assert("Next milestone lookup", getNextMilestone('CS101', 'm2').type === 'QUIZ');
assert("Next milestone on last returns null", getNextMilestone('CS101', 'm4') === null);

// 13. Remaining teaching day calculation
// If today is 2024-01-10. Window end is 2024-01-19.
// Remaining: 11, 12, 13, 16, 17, 18, 19 (7 days)
// We can't mock today easily without dependency injection, but we can verify it doesn't crash 
// and returns 0 for a past window.
const remaining = getRemainingTeachingDays(windowCS101); // 2024-01-19 is past, so returns 0 today
assert("Remaining teaching day calculation resolves 0 for past", remaining === 0);

// 14. Invalid subject
expectThrow("Invalid subject throws", () => {
  getSubjectTimeline('INVALID_101');
});

// 15. Invalid milestone
expectThrow("Invalid milestone throws", () => {
  getAttendanceWindow('CS101', 'invalid_milestone');
});

// 16. Duplicate milestone IDs
expectThrow("Duplicate milestone IDs reject at init", () => {
  initCalendarEngine({
    ...mockCalendarBase,
    subjectTimelines: [{
      subjectCode: 'ERR1', commencementDate: '2024-01-01',
      milestones: [{ milestoneId: 'm1', type: 'QUIZ', date: '2024-01-10' }, { milestoneId: 'm1', type: 'QUIZ', date: '2024-01-11' }]
    }]
  });
});

// 17. Out-of-order milestones
expectThrow("Out-of-order milestones reject at init", () => {
  initCalendarEngine({
    ...mockCalendarBase,
    subjectTimelines: [{
      subjectCode: 'ERR2', commencementDate: '2024-01-01',
      milestones: [{ milestoneId: 'm1', type: 'QUIZ', date: '2024-01-15' }, { milestoneId: 'm2', type: 'FIRST_LECTURE', date: '2024-01-10' }]
    }]
  });
});

// Extra: Quiz before first lecture
expectThrow("Quiz before first lecture reject at init", () => {
  initCalendarEngine({
    ...mockCalendarBase,
    subjectTimelines: [{
      subjectCode: 'ERR3', commencementDate: '2024-01-01',
      milestones: [{ milestoneId: 'm1', type: 'QUIZ', date: '2024-01-10' }, { milestoneId: 'm2', type: 'FIRST_LECTURE', date: '2024-01-15' }]
    }]
  });
});

// Extra: Window end before window start
expectThrow("Window end before start throws", () => {
  // To trigger this, we need a valid engine state where a milestone date is <= commencementDate
  // We can bypass init by having a milestone date = commencementDate, then windowEnd = commencementDate - 1 day
  initCalendarEngine({
    ...mockCalendarBase,
    subjectTimelines: [{
      subjectCode: 'ERR4', commencementDate: '2024-01-05',
      milestones: [
        { milestoneId: 'm1', type: 'FIRST_LECTURE', date: '2024-01-05', metadata: {} },
        { milestoneId: 'm2', type: 'SURPRISE_QUIZ', date: '2024-01-05', metadata: {} }
      ]
    }]
  });
  getAttendanceWindow('ERR4', 'm2');
});


if (failed > 0) {
  console.error(`\n❌ ${failed} tests failed.`);
  process.exit(1);
} else {
  console.log(`\n✅ All Phase A2.2 tests passed successfully!`);
}
