
import fs from 'fs';
import { initTimetable, getTimetable } from './js/utils.js';
import { getAttendanceData } from './js/attendance-engine.js';
import { initCalendarEngine, addAcademicEvent, getSubjectEventDeltas } from './js/calendar-engine.js';
global.fetch = async (url) => {
  const data = fs.readFileSync('timetable.json', 'utf8');
  return { json: async () => JSON.parse(data) };
};

async function run() {
  await initTimetable();
  import('./js/test-attendance-engine.js').catch(e => console.error(e));
}
run();

