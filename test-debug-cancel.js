
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
import { initCalendarEngine, addAcademicEvent } from './js/calendar-engine.js';
async function run() {
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
    semesterId: 'current',
    semesterStart: getTimetable().start_date,
    semesterEnd: '2026-12-31',
    defaultWeekends: [0, 6],
    subjectTimelines: timelines,
    policies: {},
    events: []
  });
  console.log('BEFORE:', getAttendanceData('2026-08-17')['BCS-501'].counts.L.tot);
  addAcademicEvent({ id: 'evt2', eventType: 'CLASS_CANCELLED', subjectCode: 'BCS-501', classType: 'L', effectiveDate: '2026-07-27', active: true });
  console.log('AFTER:', getAttendanceData('2026-08-17')['BCS-501'].counts.L.tot);
}
run();

