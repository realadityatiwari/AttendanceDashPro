import { getAcademicDay, getEffectiveDaySchedule, AcademicEventRegistry, getTodayString } from './calendar-engine.js';
import { getTimetable } from './utils.js';
import { CLASS_TYPES, normalizeClassType } from './utils.js';
import { isSimulationMode } from './dateContext.js';

/**
 * Builds the view model for the Daily Attendance UI.
 * Combines static timetable, runtime events, and live attendance state.
 */
function buildDailyViewModel(dateStr, effectiveStates) {
  const academicDay = getAcademicDay(dateStr);
  const classes = getEffectiveDaySchedule(dateStr);
  const isToday = dateStr === getTodayString();
  const isFuture = dateStr > getTodayString();
  const isBlocked = isFuture && !isSimulationMode();
  const timetable = getTimetable();

  const vm = {
    dateStr,
    isToday,
    isFuture,
    isBlocked,
    isWorkingDay: academicDay.isWorkingDay,
    closureReason: academicDay.events[0] ? (academicDay.events[0].metadata?.reason || academicDay.events[0].eventType) : 'No scheduled classes on this date.',
    summary: {
      total: 0,
      completed: 0,
      pending: 0,
      present: 0,
      absent: 0
    },
    classes: []
  };

  if (!vm.isWorkingDay || !classes || classes.length === 0) {
    return vm;
  }

  classes.forEach(c => {
    const subj = timetable.subjects.find(s => s.code === c.s);
    const subjName = subj ? subj.name : c.s;
    const classId = `${dateStr}:${c.s}:${c.t}`;
    const currState = effectiveStates[classId] || 'Pending';
    const timeSlot = c.mergedTimeSlot || 'TBD';
    const normalizedType = normalizeClassType(c.t);
    const typeLabel = CLASS_TYPES[normalizedType]?.label ?? c.t;

    let uiStatus = 'Upcoming';
    if (!isFuture) {
      if (currState === 'Attended') uiStatus = 'Present';
      else if (currState === 'Missed') uiStatus = 'Absent';
      else uiStatus = 'Not marked';
    }

    let eventLabel = null;
    if (c.isExtra) {
      eventLabel = 'Extra Class';
      if (c.t.includes('_extra_')) {
        // Try to find the exact event type if we had it, but generic is fine for now
        if (normalizedType === 'L') eventLabel = 'Extra Lecture';
        if (normalizedType === 'T') eventLabel = 'Extra Tutorial';
        if (normalizedType.startsWith('P')) eventLabel = 'Extra Practical';
        
        // Check surprise quiz
        if (c.mergedTimeSlot === 'Surprise Quiz') eventLabel = 'Surprise Quiz';
      }
    }

    vm.classes.push({
      classId,
      subjectCode: c.s,
      subjectName: subjName,
      classType: c.t,
      typeLabel,
      timeSlot,
      status: currState,
      uiStatus,
      isExtra: c.isExtra,
      eventLabel
    });

    vm.summary.total++;
    if (currState === 'Attended') {
      vm.summary.present++;
      vm.summary.completed++;
    } else if (currState === 'Missed') {
      vm.summary.absent++;
      vm.summary.completed++;
    } else {
      vm.summary.pending++;
    }
  });

  return vm;
}

/**
 * Renders the Daily Attendance UI into the specified container HTML.
 */
export function renderDailyAttendanceHTML(dateStr, effectiveStates) {
  const vm = buildDailyViewModel(dateStr, effectiveStates);

  if (!vm.isWorkingDay || vm.classes.length === 0) {
    return `
      <div class="today-empty">
        ${!vm.isWorkingDay ? vm.closureReason : 'No classes scheduled for this date.'}
      </div>
    `;
  }

  const completionPct = vm.summary.total > 0 ? Math.round((vm.summary.completed / vm.summary.total) * 100) : 0;

  let html = `
    <div class="daily-summary" style="display:none;">
    </div>
    <div class="daily-cards">
  `;

  vm.classes.forEach(c => {
    const disabledAttr = vm.isBlocked ? 'disabled title="Enable Simulation Mode to log future dates"' : '';
    const disabledStyle = vm.isBlocked ? 'opacity:0.4;cursor:not-allowed;' : '';
    
    const attActive = c.status === 'Attended' ? 'active-attended' : '';
    const missActive = c.status === 'Missed' ? 'active-missed' : '';
    const pendActive = c.status === 'Pending' ? 'active-pending' : '';

    const attPressed = c.status === 'Attended' ? 'true' : 'false';
    const missPressed = c.status === 'Missed' ? 'true' : 'false';

    const attTooltip = 'Mark as attended';
    const missTooltip = 'Mark as missed';
    const tooltipIdAtt = `tt-${vm.dateStr}-${c.subjectCode}-${c.classType}-att`.replace(/:/g, '-');
    const tooltipIdMiss = `tt-${vm.dateStr}-${c.subjectCode}-${c.classType}-miss`.replace(/:/g, '-');

    html += `
      <div class="today-row">
        <div class="today-row-left">
          <div class="today-row-subj">
            <span class="s-code">${c.subjectCode}</span>
            <span class="today-row-type">${c.typeLabel}</span>
            <span class="today-row-time">${c.timeSlot}</span>
          </div>
          <div class="today-row-name">${c.subjectName}</div>
        </div>
        <div class="today-row-actions">
          <div class="tooltip-wrap">
            <button class="action-btn ${attActive}" style="${disabledStyle}"
              ${disabledAttr}
              aria-pressed="${attPressed}"
              aria-describedby="${tooltipIdAtt}"
              aria-label="Mark ${c.subjectCode} ${c.typeLabel} as attended"
              data-action="logAttendance" data-date="${vm.dateStr}" data-s="${c.subjectCode}" data-t="${c.classType}" data-state="Attended">✓ Attended</button>
            <span id="${tooltipIdAtt}" role="tooltip" class="tooltip-text">${attTooltip}</span>
          </div>
          <div class="tooltip-wrap">
            <button class="action-btn ${missActive}" style="${disabledStyle}"
              ${disabledAttr}
              aria-pressed="${missPressed}"
              aria-describedby="${tooltipIdMiss}"
              aria-label="Mark ${c.subjectCode} ${c.typeLabel} as missed"
              data-action="logAttendance" data-date="${vm.dateStr}" data-s="${c.subjectCode}" data-t="${c.classType}" data-state="Missed">✕ Missed</button>
            <span id="${tooltipIdMiss}" role="tooltip" class="tooltip-text">${missTooltip}</span>
          </div>
          <button class="action-btn ${pendActive}"
            ${disabledAttr} style="${disabledStyle}" aria-label="Reset ${c.subjectCode} ${c.typeLabel} attendance status"
            data-action="logAttendance" data-date="${vm.dateStr}" data-s="${c.subjectCode}" data-t="${c.classType}" data-state="Pending">Reset</button>
        </div>
      </div>
    `;
  });

  html += `</div>`;
  return html;
}
