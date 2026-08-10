import { getAcademicDay, getEffectiveDaySchedule, AcademicEventRegistry } from './calendar-engine.js';
import { getTimetable } from './utils.js';
import { CLASS_TYPES, normalizeClassType } from './utils.js';
import { getTodayString, isSimulationMode } from './dateContext.js';

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
      subjectName,
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
      <div class="daily-empty-state">
        <div class="daily-empty-icon">☕</div>
        <div class="daily-empty-title">${!vm.isWorkingDay ? 'Holiday / Closure' : 'You\\'re free today'}</div>
        <div class="daily-empty-sub">${!vm.isWorkingDay ? vm.closureReason : 'No classes scheduled for this date.'}</div>
      </div>
    `;
  }

  const completionPct = vm.summary.total > 0 ? Math.round((vm.summary.completed / vm.summary.total) * 100) : 0;

  let html = `
    <div class="daily-summary">
      <div class="daily-progress-text">${vm.summary.completed} / ${vm.summary.total} classes completed</div>
      <div class="daily-progress-bar">
        <div class="daily-progress-fill" style="width: ${completionPct}%"></div>
      </div>
    </div>
    <div class="daily-cards">
  `;

  vm.classes.forEach(c => {
    const disabledAttr = vm.isBlocked ? 'disabled title="Enable Simulation Mode to log future dates"' : '';
    const disabledClass = vm.isBlocked ? 'is-blocked' : '';
    
    const attActive = c.status === 'Attended' ? 'active' : '';
    const missActive = c.status === 'Missed' ? 'active' : '';

    let statusBadgeClass = 'status-pending';
    if (c.uiStatus === 'Present') statusBadgeClass = 'status-present';
    if (c.uiStatus === 'Absent') statusBadgeClass = 'status-absent';
    if (c.uiStatus === 'Upcoming') statusBadgeClass = 'status-upcoming';

    const eventBadge = c.eventLabel ? `<span class="daily-event-badge">${c.eventLabel}</span>` : '';

    html += `
      <div class="daily-card ${disabledClass}">
        <div class="daily-card-header">
          <div class="daily-card-tags">
            <span class="daily-subj-code">${c.subjectCode}</span>
            <span class="daily-type-code">${c.typeLabel}</span>
            ${eventBadge}
          </div>
          <div class="daily-status-badge ${statusBadgeClass}">${c.uiStatus}</div>
        </div>
        <div class="daily-card-main">
          <div class="daily-subj-name">${c.subjectName}</div>
          <div class="daily-time">${c.timeSlot}</div>
        </div>
        <div class="daily-card-actions">
          <div class="segmented-control">
            <button class="seg-btn ${attActive}" ${disabledAttr}
              aria-pressed="${c.status === 'Attended' ? 'true' : 'false'}"
              aria-label="Mark ${c.subjectCode} ${c.typeLabel} as attended"
              data-action="logAttendance" data-date="${vm.dateStr}" data-s="${c.subjectCode}" data-t="${c.classType}" data-state="Attended">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
              Present
            </button>
            <button class="seg-btn ${missActive}" ${disabledAttr}
              aria-pressed="${c.status === 'Missed' ? 'true' : 'false'}"
              aria-label="Mark ${c.subjectCode} ${c.typeLabel} as missed"
              data-action="logAttendance" data-date="${vm.dateStr}" data-s="${c.subjectCode}" data-t="${c.classType}" data-state="Missed">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              Absent
            </button>
          </div>
          <button class="daily-reset-btn" ${disabledAttr}
            aria-label="Reset ${c.subjectCode} ${c.typeLabel}"
            data-action="logAttendance" data-date="${vm.dateStr}" data-s="${c.subjectCode}" data-t="${c.classType}" data-state="Pending">
            Reset
          </button>
        </div>
      </div>
    `;
  });

  html += `</div>`;
  return html;
}
