
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
global.fetch = async (url) => {
  if (url === 'timetable.json') {
    const data = fs.readFileSync('timetable.json', 'utf8');
    return { json: async () => JSON.parse(data) };
  }
  throw new Error('Unknown URL ' + url);
};
import { initTimetable, getTimetable } from './js/utils.js';
import { getAttendanceData } from './js/attendance-engine.js';
import { initCalendarEngine, syncRuntimeEvents, getSubjectEventDeltas, getAcademicDay } from './js/calendar-engine.js';

async function test() {
  await initTimetable();
  const timetable = getTimetable();
  const timelines = timetable.subjects.map(s => {
    return {
      subjectCode: s.code,
      commencementDate: timetable.start_date,
      milestones: timetable.quiz_dates.map((q, idx) => ({
        milestoneId: 'q'+(idx+1),
        type: 'QUIZ',
        date: q.date,
        metadata: { quizCycle: idx + 1 }
      }))
    };
  });
  timelines.forEach(tl => {
    tl.milestones.unshift({
      milestoneId: 'm0',
      type: 'FIRST_LECTURE',
      date: tl.commencementDate,
      metadata: {}
    });
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

  const baseData = getAttendanceData('2026-08-17');
  const baseLecTot = baseData['BCS-501'].counts.L.tot;

  syncRuntimeEvents({
    '2026-07-20': [{
      id: 'evt1',
      eventType: 'EXTRA_LECTURE',
      subjectCode: 'BCS-501',
      classType: 'L',
      effectiveDate: '2026-07-20',
      active: true
    }]
  });

  const modifiedData = getAttendanceData('2026-08-17');
  const modLecTot = modifiedData['BCS-501'].counts.L.tot;
  console.log('Base:', baseLecTot, 'Mod:', modLecTot);
}
test();

