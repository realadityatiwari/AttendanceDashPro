import { loadStates, clearStates, AppState, saveLaboratoryStates } from './storage.js';
import { getTimetable, formatTodayHeader, getLocalDateString, getTodayString, isScheduledClass, formatHistoryDate, CLASS_TYPES, normalizeClassType, getMergedDaySchedule } from './utils.js';
import { computeSubjectStats, computeOverallStats, computeCurrentOverallAttendance, computeForecastOverallAttendance, calcForecastImpact, getAttendanceData, getSubjectStatus, pctColor, barColor, dimColor } from './attendance-engine.js';
import { computeLaboratoryDashboard } from './laboratory-engine.js';
import { computeQuizDashboard } from './quiz-engine.js';
import {
  dateContext, MODE, isSimulationMode, getActiveDate, getActiveDateString,
  selectDate, selectDateByString, resetToToday,
  getEffectiveStates, logClassState, classifyDate, deriveMode
} from './dateContext.js';

export let currentQuiz = 0;

/* ═══════════════════════════════════════════════════════════════════════
   DATE NAVIGATOR
   Replaces the empty dropdown. Builds the "Viewing:" label, the mode badge,
   and the option menu (Yesterday / Today / Tomorrow / Pick Date…). All date
   changes flow through selectDate() so mode + persistence are always correct.
══════════════════════════════════════════════════════════════════════ */

/** Renders the mode badge (LIVE MODE / SIMULATION MODE (Not Saved)). */
export function updateModeBadge() {
  const badge = document.getElementById('modeBadge');
  if (!badge) return;
  if (dateContext.mode === MODE.SIMULATION) {
    badge.textContent = 'SIMULATION MODE · NOT SAVED';
    badge.className = 'mode-badge mode-sim';
    badge.style.display = 'inline-flex';
    badge.setAttribute('role', 'status');
    badge.setAttribute('aria-live', 'polite');
  } else {
    badge.textContent = 'LIVE MODE';
    badge.className = 'mode-badge mode-live';
    badge.style.display = 'inline-flex';
    badge.setAttribute('role', 'status');
    badge.setAttribute('aria-live', 'polite');
  }
}

/** Rebuilds the "Viewing:" label + selected date summary. */
export function updateViewingLabel() {
  const label   = document.getElementById('viewingLabel');
  const dateEl  = document.getElementById('viewingDate');
  if (!dateEl) return;
  const d = dateContext.selectedDate;
  const dName = d.toLocaleDateString('en-US', { weekday: 'long' });
  const dStr  = d.toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: 'numeric' });
  if (label) label.textContent = `Viewing: ${dName} • ${dStr}`;
  dateEl.textContent = `${dName} • ${dStr}`;
  const navTrigger = document.getElementById('navTriggerLabel');
  if (navTrigger) navTrigger.textContent = formatTodayHeader(d);
  // Update mobile date label
  const mobileLabel = document.getElementById('mobileDateLabel');
  if (mobileLabel) mobileLabel.textContent = formatTodayHeader(d);
}

/**
 * Builds the Date Navigator control (button showing current date + dropdown
 * menu). Keeps the currently-selected option highlighted. Past/Today →
 * LIVE in the menu; Tomorrow/Future → SIMULATION.
 */
export function renderDateNavigator() {
  const nav = document.getElementById('dateNavigator');
  if (!nav) return;

  const opts = buildNavigatorOptions();
  const menuId = 'dateNavMenu';

  nav.innerHTML = `
    <button class="nav-trigger theme-btn" id="dateNavTrigger" aria-haspopup="true" aria-expanded="false" aria-controls="${menuId}">
      <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
      <span id="navTriggerLabel">${formatTodayHeader(dateContext.selectedDate)}</span>
      <svg class="nav-caret" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10l5 5 5-5z"/></svg>
    </button>
    <div class="nav-menu" id="${menuId}" role="menu" hidden>
      ${opts.map(o => `
        <button class="nav-item ${o.active ? 'active' : ''}" role="menuitem" data-nav="${o.action}" ${o.dateStr ? `data-date="${o.dateStr}"` : ''}>
          <span class="nav-item-ico" aria-hidden="true">${o.icon}</span>
          <span class="nav-item-label">${o.label}</span>
          <span class="nav-item-mode ${o.modeClass}">${o.modeText}</span>
        </button>`).join('')}
      <div class="nav-sep"></div>
      <div class="nav-picker">
        <label class="nav-picker-label" for="datePickerInput">Pick Date…</label>
        <input type="date" id="datePickerInput" class="nav-picker-input"
               min="${getLocalDateString(getTimetable().start_date)}"
               value="${getActiveDateString()}"
               aria-label="Pick a date" />
      </div>
    </div>`;

  bindNavigatorEvents();
}

function buildNavigatorOptions() {
  const today = new Date();
  const yesterday = new Date(); yesterday.setDate(today.getDate() - 1);
  const tomorrow  = new Date(); tomorrow.setDate(today.getDate() + 1);

  const yMode = deriveMode(yesterday);
  const tMode = deriveMode(today);
  const tmMode = deriveMode(tomorrow);

  const selStr = getActiveDateString();

  return [
    {
      action: 'yesterday', icon: '◀', label: 'Yesterday',
      dateStr: getLocalDateString(yesterday),
      active: getLocalDateString(yesterday) === selStr,
      modeText: 'Live', modeClass: 'nav-mode-live'
    },
    {
      action: 'today', icon: '●', label: 'Today',
      dateStr: getLocalDateString(today),
      active: getLocalDateString(today) === selStr,
      modeText: 'Live', modeClass: 'nav-mode-live'
    },
    {
      action: 'tomorrow', icon: '▶', label: 'Tomorrow',
      dateStr: getLocalDateString(tomorrow),
      active: getLocalDateString(tomorrow) === selStr,
      modeText: 'Sim', modeClass: 'nav-mode-sim'
    }
  ];
}

function bindNavigatorEvents() {
  const trigger = document.getElementById('dateNavTrigger');
  const menu    = document.getElementById('dateNavMenu');
  if (!trigger || !menu) return;

  const open  = () => { menu.hidden = false; trigger.setAttribute('aria-expanded', 'true'); };
  const close = () => { menu.hidden = true;  trigger.setAttribute('aria-expanded', 'false'); };

  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.hidden ? open() : close();
  });

  menu.addEventListener('click', (e) => {
    const item = e.target.closest('[data-nav]');
    if (!item) return;
    const action = item.getAttribute('data-nav');
    const dateStr = item.getAttribute('data-date');
    if (action === 'yesterday' || action === 'today' || action === 'tomorrow') {
      selectDateByString(dateStr);
      close();
      afterDateChange();
    }
  });

  const picker = document.getElementById('datePickerInput');
  if (picker) {
    picker.addEventListener('change', () => {
      if (picker.value) {
        selectDateByString(picker.value);
        close();
        afterDateChange();
      }
    });
  }

  // Close on outside click / Escape (keyboard accessible).
  document.addEventListener('click', () => { if (!menu.hidden) close(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !menu.hidden) { close(); trigger.focus(); }
  });
}

/** Central post-change refresh used by all navigator interactions. */
function afterDateChange() {
  updateModeBadge();
  updateViewingLabel();
  recalculateAndRender();
}

export function getImpactTooltipHTML(impact) {
  if (!impact || impact.curAvg === null) return '';
  const diff = impact.newAvg - impact.curAvg;
  const dir  = diff > 0.005 ? '↑' : diff < -0.005 ? '↓' : '→';
  const eligHTML = impact.stillEligible
    ? '<span class="tt-safe">Still Eligible</span>'
    : '<span class="tt-unsafe">Not Eligible</span>';
  return `
    <div class="tt-lbl">Forecast Average</div>
    <div><span class="tt-old">${impact.curAvg.toFixed(1)}%</span> <span class="tt-arr">${dir}</span> <span class="tt-new">${impact.newAvg.toFixed(1)}%</span></div>
    <div>${eligHTML}</div>
  `;
}

/* ═══════════════════════════════════════════════════════════════════════
   NEED-TEXT & VISUAL HELPERS
═══════════════════════════════════════════════════════════════════════ */
export function getRemainingRequirementText(optResult) {
  if (optResult.infeasible) {
    return `<div class="subj-need-text danger">⚡ Ineligible — impossible to reach 75%</div>`;
  }
  if (optResult.addL === 0 && optResult.addT === 0) {
    return `<div class="subj-need-text safe">✓ Already Safe — attend any remaining</div>`;
  }
  const parts = [];
  if (optResult.addL > 0) parts.push(`${optResult.addL} Lecture${optResult.addL > 1 ? 's' : ''}`);
  if (optResult.addT > 0) parts.push(`${optResult.addT} Tutorial${optResult.addT > 1 ? 's' : ''}`);
  return `<div class="subj-need-text warning">Need ${parts.join(' & ')} more to qualify</div>`;
}

export function getProgressRowHTML(label, pct, valStr) {
  if (pct === null) return '';
  const w     = Math.min(100, Math.max(0, pct)).toFixed(1);
  const color = barColor(pct);
  return `
    <div class="subj-stat-row">
      <div class="subj-stat-label">
        <span>${label}</span>
        <span class="val">${valStr} (${pct.toFixed(1)}%)</span>
      </div>
      <div class="subj-progress-track">
        <div class="subj-progress-bar" style="width:${w}%;background-color:${color}"></div>
      </div>
    </div>
  `;
}

export function makeSkipBudgetVisual(remaining, missed, type) {
  if (type === 'T' && remaining === null) {
    return `<span class="badge-na">—</span>`;
  }
  const rem = Math.max(0, remaining || 0);
  const mis = Math.max(0, missed    || 0);
  if (rem === 0 && mis === 0) {
    return `<span class="badge badge-zero">0 left</span>`;
  }
  let squares = '';
  for (let i = 0; i < rem; i++) {
    squares += `<span class="budget-square filled" style="background:var(--green)"></span>`;
  }
  for (let i = 0; i < mis; i++) {
    squares += `<span class="budget-square empty" style="border:1px solid var(--border2);background:var(--red-dim)"></span>`;
  }
  return `
    <div style="display:inline-flex;align-items:center;gap:3px;justify-content:center;">
      <div style="display:inline-flex;gap:2.5px;align-items:center;margin-right:5px;">${squares}</div>
      <span class="num" style="font-size:11px;color:${rem > 0 ? 'var(--green)' : 'var(--text3)'}">${rem} left</span>
    </div>
  `;
}

export function makePctCell(pct, isAvg = false, label = '') {
  if (pct === null) return `<td class="pct-cell"${label ? ` data-label="${label}"` : ''}><span class="badge-na">—</span></td>`;
  // Clamp display value to [0, 100] for safety
  const display = Math.min(100, Math.max(0, pct));
  const w   = display.toFixed(1);
  const col = barColor(pct);
  const fmtPct = v => v.toFixed(2);
  const inner = `
    <span class="pct-val" style="color:${col}">${fmtPct(display)}%</span>
    <div class="pct-bar-wrap"><div class="pct-bar" style="width:${w}%;background:${col}"></div></div>
  `;
  if (isAvg) {
    const dimCol = dimColor(pct);
    return `<td class="pct-cell"${label ? ` data-label="${label}"` : ''}><div class="avg-cell" style="background:${dimCol};border-radius:8px;padding:6px 10px;display:inline-block;min-width:66px">
      <span class="pct-val" style="color:${col}">${fmtPct(display)}%</span>
      <div class="pct-bar-wrap"><div class="pct-bar" style="width:${w}%;background:${col}"></div></div>
    </div></td>`;
  }
  return `<td class="pct-cell"${label ? ` data-label="${label}"` : ''}>${inner}</td>`;
}

/* ═══════════════════════════════════════════════════════════════════════
   RENDER PANEL — refactored into sub-functions (each ≤ 50 lines)
═══════════════════════════════════════════════════════════════════════ */

/** Build the Attendance Analytics section (replaces legacy hero card). */

export function buildHeroCard(overallStats, erpStats, forecastStats, label, quizDate) {
  const { totalMustAttend, totalSafeSkips, totalClasses, totalSubjects } = overallStats;
  const dateStr = quizDate.toLocaleDateString('en-US', {day:'numeric', month:'short', year:'numeric'});

  // ── Section 1: Current Overall ───────────────────────────────────────────
  const curPct      = erpStats.percentage;
  const curColor    = curPct !== null ? pctColor(curPct) : 'var(--text3)';
  const curDisplay  = curPct !== null ? erpStats.formattedPercentage + '%' : '\u2014';
  const curFraction = curPct !== null
    ? `${erpStats.attended} / ${erpStats.conducted} Classes`
    : 'No classes conducted yet';

  // ── Section 2: Forecast Overall ──────────────────────────────────────────
  const fcPct      = forecastStats.percentage;
  const fcColor    = fcPct !== null ? pctColor(fcPct) : 'var(--text3)';
  const fcDisplay  = fcPct !== null ? forecastStats.formattedPercentage + '%' : '\u2014';
  const remaining  = forecastStats.remainingClasses ?? 0;
  const fcFraction = fcPct !== null
    ? `${forecastStats.attended} / ${forecastStats.conducted} Classes`
    : 'No classes scheduled';
  const remainingLine = remaining > 0
    ? `<div style="font-size:11px;color:var(--accent);margin-top:3px;font-variant-numeric:tabular-nums;">+${remaining} Remaining Classes</div>`
    : (fcPct !== null
      ? `<div style="font-size:11px;color:var(--green);margin-top:3px;">Semester completed</div>`
      : '');

  return `
    <div class="hero-card">
      <div class="hero-left">
        <div class="hero-label">Attendance Analytics</div>
        <div class="hero-title">${label} \u00b7 ${dateStr}</div>
      </div>
      <div style="display:flex;align-items:stretch;gap:0;">
        <div style="text-align:right;padding-right:24px;border-right:1px solid var(--border);">
          <div style="font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--text3);margin-bottom:4px;">Current</div>
          <div class="hero-val" style="color:${curColor}">${curDisplay}</div>
          <div class="hero-label" style="margin-top:2px;">Overall Attendance</div>
          <div style="font-size:11px;color:var(--text3);margin-top:3px;font-variant-numeric:tabular-nums;">${curFraction}</div>
        </div>
        <div style="text-align:right;padding-left:24px;">
          <div style="font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--text3);margin-bottom:4px;">Forecast</div>
          <div class="hero-val" style="color:${fcColor}">${fcDisplay}</div>
          <div class="hero-label" style="margin-top:2px;">If All Remaining Attended</div>
          <div style="font-size:11px;color:var(--text3);margin-top:3px;font-variant-numeric:tabular-nums;">${fcFraction}</div>
          ${remainingLine}
        </div>
      </div>
      <div class="hero-right">
        <div class="hero-item">
          <div class="hero-item-label">Must Attend</div>
          <div class="hero-item-val" style="color:var(--accent)">${totalMustAttend}</div>
          <div class="hero-item-sub">remaining classes</div>
        </div>
        <div class="hero-item">
          <div class="hero-item-label">Safe Skips Left</div>
          <div class="hero-item-val" style="color:var(--green)">${totalSafeSkips}</div>
          <div class="hero-item-sub">maximum skips</div>
        </div>
        <div class="hero-item">
          <div class="hero-item-label">Total Classes</div>
          <div class="hero-item-val">${totalClasses}</div>
          <div class="hero-item-sub">across ${totalSubjects} subjects</div>
        </div>
      </div>
    </div>`;
}


/** Build one accordion-style subject card for mobile. */
export function buildMobileSubjectCard(r) {
  const avgColor = r.currentAvgPct !== null ? pctColor(r.currentAvgPct) : 'var(--text3)';
  const avgDisplay = r.currentAvgPct !== null ? r.currentAvgPct.toFixed(1) + '%' : '—';

  const lecRow = r.completedL > 0
    ? `<div class="mobile-subj-stat">
        <div class="mobile-subj-stat-header"><span>Lecture</span><span>${r.currentLecPct.toFixed(2)}%</span></div>
        <div class="mobile-subj-progress"><div class="mobile-subj-progress-bar" style="width:${Math.min(100, Math.max(0, r.currentLecPct)).toFixed(1)}%;background-color:${barColor(r.currentLecPct)}"></div></div>
      </div>`
    : '';

  const tutRow = r.totT > 0
    ? (r.completedT > 0
      ? `<div class="mobile-subj-stat">
          <div class="mobile-subj-stat-header"><span>Tutorial</span><span>${r.currentTutPct.toFixed(2)}%</span></div>
          <div class="mobile-subj-progress"><div class="mobile-subj-progress-bar" style="width:${Math.min(100, Math.max(0, r.currentTutPct)).toFixed(1)}%;background-color:${barColor(r.currentTutPct)}"></div></div>
        </div>`
      : `<div class="mobile-subj-stat"><div class="mobile-subj-stat-header"><span>Tutorial</span><span>—</span></div></div>`)
    : '';

  const avgRow = r.currentAvgPct !== null
    ? `<div class="mobile-subj-stat">
        <div class="mobile-subj-stat-header"><span>Average</span><span style="color:${avgColor}">${r.currentAvgPct.toFixed(2)}%</span></div>
        <div class="mobile-subj-progress"><div class="mobile-subj-progress-bar" style="width:${Math.min(100, Math.max(0, r.currentAvgPct)).toFixed(1)}%;background-color:${barColor(r.currentAvgPct)}"></div></div>
      </div>`
    : '';

  const forecastRow = r.forecastAvgPct !== null
    ? `<div class="mobile-subj-stat">
        <div class="mobile-subj-stat-header"><span>Forecast</span><span style="color:${pctColor(r.forecastAvgPct)}">${r.forecastAvgPct.toFixed(1)}%</span></div>
        <div class="mobile-subj-progress"><div class="mobile-subj-progress-bar" style="width:${Math.min(100, Math.max(0, r.forecastAvgPct)).toFixed(1)}%;background-color:${barColor(r.forecastAvgPct)}"></div></div>
      </div>`
    : '';

  const opt = r.optResult;
  const mustAttend = opt.addL + opt.addT;
  const safeSkips = opt.skipL_budget + opt.skipT_budget;
  const needText = getRemainingRequirementText(opt);
  const needClass = opt.infeasible ? 'danger' : (opt.addL === 0 && opt.addT === 0 ? 'safe' : 'warning');

  const totalCls = ` ${r.totL + r.totT}`;
  const attendedCls = ` ${r.attL_done + r.attT_done}`;

  return `
    <div class="mobile-subj-card" data-subj-code="${r.code}">
      <button class="mobile-subj-header" aria-expanded="false" aria-controls="msubj-${r.code}">
        <div class="mobile-subj-left">
          <div class="mobile-subj-code">${r.code}</div>
          <div class="mobile-subj-name">${r.name}</div>
          <div class="mobile-subj-avg-row">
            <span class="mobile-subj-avg-val" style="color:${avgColor}">${avgDisplay}</span>
            <span class="mobile-subj-avg-label">Average</span>
          </div>
        </div>
        <div class="mobile-subj-right">
          <span class="status-badge ${r.status.cls}">${r.status.text}</span>
          <svg class="mobile-subj-arrow" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10l5 5 5-5z"/></svg>
        </div>
      </button>
      <div class="mobile-subj-body" id="msubj-${r.code}" hidden>
        <div class="mobile-subj-body-inner">
          <div class="mobile-subj-stats">
            <div class="mobile-subj-stat-section">
              <div class="subj-stat-section-label">Current</div>
              ${lecRow}${tutRow}${avgRow}
            </div>
            <div class="subj-stat-section" style="margin-top:8px;">
              <div class="subj-stat-section-label">Forecast (if all pending attended)</div>
              ${forecastRow}
            </div>
            <div class="mobile-subj-need ${needClass}">${needText.replace(/^<div class="subj-need-text[^"]*">/, '').replace(/<\/div>$/, '')}</div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px;padding-top:8px;border-top:1px solid var(--border);">
              <div class="mobile-subj-stat">
                <div class="mobile-subj-stat-header"><span>Must Attend</span><span style="color:var(--accent)">${mustAttend}</span></div>
              </div>
              <div class="mobile-subj-stat">
                <div class="mobile-subj-stat-header"><span>Safe Skips</span><span style="color:var(--green)">${safeSkips}</span></div>
              </div>
              <div class="mobile-subj-stat">
                <div class="mobile-subj-stat-header"><span>Total Classes</span><span>${totalCls}</span></div>
              </div>
              <div class="mobile-subj-stat">
                <div class="mobile-subj-stat-header"><span>Attended</span><span>${attendedCls}</span></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>`;
}

/** Build one stacked attendance card for mobile (replaces table rows). */
export function buildMobileAttendanceCard(r) {
  const avgCol = r.currentAvgPct !== null ? pctColor(r.currentAvgPct) : 'var(--text3)';
  const opt = r.optResult;
  const mustAttend = opt.addL + opt.addT;
  const safeSkips = opt.skipL_budget + opt.skipT_budget;

  const lecVal = r.currentLecPct !== null ? r.currentLecPct.toFixed(2) + '%' : '—';
  const tutVal = r.currentTutPct !== null ? r.currentTutPct.toFixed(2) + '%' : (r.totT > 0 ? '—' : 'N/A');
  const avgVal = r.currentAvgPct !== null ? r.currentAvgPct.toFixed(2) + '%' : '—';
  const fcastVal = r.forecastAvgPct !== null ? r.forecastAvgPct.toFixed(1) + '%' : '—';
  const fcastCol = r.forecastAvgPct !== null ? pctColor(r.forecastAvgPct) : 'var(--text3)';

  return `
    <div class="mobile-att-card">
      <div class="mobile-att-card-header">
        <div class="mobile-att-card-code">${r.code}</div>
        <div class="mobile-att-card-name">${r.name}</div>
      </div>
      <div class="mobile-att-card-grid">
        <div class="mobile-att-item">
          <span class="mobile-att-label">Lecture %</span>
          <span class="mobile-att-value ${r.currentLecPct !== null ? (r.currentLecPct >= 75 ? 'green' : 'amber') : 'muted'}">${lecVal}</span>
        </div>
        <div class="mobile-att-item">
          <span class="mobile-att-label">Tutorial %</span>
          <span class="mobile-att-value ${r.currentTutPct !== null ? (r.currentTutPct >= 75 ? 'green' : 'amber') : 'muted'}">${tutVal}</span>
        </div>
        <div class="mobile-att-item">
          <span class="mobile-att-label">Average %</span>
          <span class="mobile-att-value" style="color:${avgCol}">${avgVal}</span>
        </div>
        <div class="mobile-att-item">
          <span class="mobile-att-label">Must Attend</span>
          <span class="mobile-att-value accent">${mustAttend}</span>
        </div>
        <div class="mobile-att-item">
          <span class="mobile-att-label">Safe Skips</span>
          <span class="mobile-att-value green">${safeSkips}</span>
        </div>
        <div class="mobile-att-item">
          <span class="mobile-att-label">Forecast</span>
          <span class="mobile-att-value" style="color:${fcastCol}">${fcastVal}</span>
        </div>
      </div>
    </div>`;
}

/** Build one subject card HTML from computed stats. */
export function buildSubjectCard(r) {
  const currentLecRow = r.completedL > 0
    ? getProgressRowHTML('Lecture', r.currentLecPct, `${r.attL_done} / ${r.completedL}`)
    : `<div class="subj-stat-row"><div class="subj-stat-label"><span>Lecture</span><span class="val">—</span></div></div>`;

  const currentTutRow = r.totT > 0
    ? (r.completedT > 0
        ? getProgressRowHTML('Tutorial', r.currentTutPct, `${r.attT_done} / ${r.completedT}`)
        : `<div class="subj-stat-row"><div class="subj-stat-label"><span>Tutorial</span><span class="val">—</span></div></div>`)
    : '';

  const currentAvgRow  = r.currentAvgPct !== null
    ? getProgressRowHTML('Average', r.currentAvgPct, `${r.currentAvgPct.toFixed(1)}%`)
    : '';

  // forecastLecStr: attended so far + if all pending are attended
  const forecastLecStr = `${r.attL_done + r.pendingL} / ${r.totL}`;
  const forecastTutStr = r.totT > 0 ? `${r.attT_done + r.pendingT} / ${r.totT}` : '';

  const forecastLecRow = getProgressRowHTML('Lecture',          r.forecastLecPct, forecastLecStr);
  const forecastTutRow = r.totT > 0 ? getProgressRowHTML('Tutorial', r.forecastTutPct, forecastTutStr) : '';
  const forecastAvgRow = getProgressRowHTML('Forecast Average', r.forecastAvgPct,
    r.forecastAvgPct !== null ? `${r.forecastAvgPct.toFixed(1)}%` : '—');

  return `
    <div class="subj-card">
      <div class="subj-card-header">
        <span class="subj-card-code">${r.code}</span>
        <span class="status-badge ${r.status.cls}">${r.status.text}</span>
      </div>
      <div class="subj-card-name">${r.name}</div>
      <div class="subj-card-stats">
        <div class="subj-stat-section">
          <div class="subj-stat-section-label">Current</div>
          ${currentLecRow}${currentTutRow}${currentAvgRow}
        </div>
        <div class="subj-stat-section">
          <div class="subj-stat-section-label">Forecast (if all pending attended)</div>
          ${forecastLecRow}${forecastTutRow}${forecastAvgRow}
        </div>
      </div>
      ${getRemainingRequirementText(r.optResult)}
    </div>`;
}

/** Build the summary stats row (4 cards at top of panel). */
export function buildStatsRow(overallStats) {
  const { totalClasses, totalSubjects, totalMustAttend, totalSafeSkips } = overallStats;

  return `
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-label">Total Classes</div>
        <div class="stat-val">${totalClasses}</div>
        <div class="stat-sub">across ${totalSubjects} subjects</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Must Attend Rem.</div>
        <div class="stat-val" style="color:var(--accent)">${totalMustAttend}</div>
        <div class="stat-sub">additional classes needed</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Safe Skips Rem.</div>
        <div class="stat-val" style="color:var(--green)">${totalSafeSkips}</div>
        <div class="stat-sub">maximum remaining skips</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Target</div>
        <div class="stat-val" style="color:var(--amber)">75%</div>
        <div class="stat-sub">average (L% + T%) / 2</div>
      </div>
    </div>`;
}

/* ═══════════════════════════════════════════════════════════════════════
   QUIZ DASHBOARD UI
   Pure rendering layer — consumes QuizDashboardModel. No calculations.
═══════════════════════════════════════════════════════════════════════ */


/** Renders a single percentage stat row for the quiz card. */
function buildQuizPctRow(label, pct) {
  if (pct === null) {
    return `<div class="quiz-pct-row"><span class="quiz-pct-label">${label}</span><span class="quiz-pct-na">—</span></div>`;
  }
  const col = pctColor(pct);
  const w   = Math.min(100, Math.max(0, pct)).toFixed(1);
  return `
    <div class="quiz-pct-row">
      <span class="quiz-pct-label">${label}</span>
      <div class="quiz-pct-right">
        <span class="quiz-pct-val" style="color:${col}">${pct.toFixed(1)}%</span>
        <div class="quiz-pct-track"><div class="quiz-pct-bar" style="width:${w}%;background:${col}"></div></div>
      </div>
    </div>`;
}

/** Builds one quiz subject card from a QuizDashboardModel subject entry. */
export function buildQuizSubjectCard(item) {
  const { subject, eligibility } = item;
  const cls = `quiz-${eligibility.status}`;
  const label = eligibility.statusLabel;

  if (!eligibility.applicable) {
    return `
      <div class="quiz-subj-card quiz-subj-card--na">
        <div class="quiz-subj-header">
          <span class="subj-card-code">${subject.code}</span>
          <span class="status-badge ${cls}">${label}</span>
        </div>
        <div class="quiz-subj-name">${subject.name}</div>
        <div class="quiz-na-message">This laboratory subject does not participate in quiz eligibility.</div>
      </div>`;
  }

  const { lecturePercentage, tutorialPercentage, average, required, displayDeficit } = eligibility;

  const deficitLine = displayDeficit
    ? `<div class="quiz-deficit">${displayDeficit}</div>`
    : '';

  const requiredLine = `
    <div class="quiz-pct-row quiz-required-row">
      <span class="quiz-pct-label">Required</span>
      <span class="quiz-required-val">${required}%</span>
    </div>`;

  return `
    <div class="quiz-subj-card">
      <div class="quiz-subj-header">
        <span class="subj-card-code">${subject.code}</span>
        <span class="status-badge ${cls}">${label}</span>
      </div>
      <div class="quiz-subj-name">${subject.name}</div>
      <div class="quiz-subj-stats">
        ${buildQuizPctRow('Lecture', lecturePercentage)}
        ${buildQuizPctRow('Tutorial', tutorialPercentage)}
        ${buildQuizPctRow('Average', average)}
        ${requiredLine}
      </div>
      ${deficitLine}
    </div>`;
}

/** Builds the summary header card for the quiz dashboard. */
export function buildQuizSummaryCard(summary) {
  return `
    <div class="quiz-summary-card">
      <div class="quiz-summary-header">
        <h2 class="quiz-summary-title">Quiz Eligibility</h2>
        <span class="quiz-summary-sub">First Quiz · Min ${summary.requiredAverage}% Average</span>
      </div>
      <div class="quiz-summary-stats">
        <div class="quiz-summary-stat">
          <div class="quiz-summary-val" style="color:var(--green)">${summary.eligible}</div>
          <div class="quiz-summary-label">Eligible</div>
        </div>
        <div class="quiz-summary-stat">
          <div class="quiz-summary-val" style="color:var(--amber)">${summary.needsAttendance}</div>
          <div class="quiz-summary-label">Needs Attendance</div>
        </div>
        <div class="quiz-summary-stat">
          <div class="quiz-summary-val" style="color:var(--text3)">${summary.notApplicable}</div>
          <div class="quiz-summary-label">Not Applicable</div>
        </div>
        <div class="quiz-summary-stat">
          <div class="quiz-summary-val" style="color:var(--accent)">${summary.requiredAverage}%</div>
          <div class="quiz-summary-label">Required Average</div>
        </div>
      </div>
    </div>`;
}

/**
 * Builds the full quiz dashboard section — summary card + subject grid.
 * Consumes a QuizDashboardModel directly. Zero business logic inside.
 */
export function buildQuizDashboardSection(quizModel) {
  const summaryHTML  = buildQuizSummaryCard(quizModel.summary);
  const subjectsHTML = quizModel.subjects.map(buildQuizSubjectCard).join('');
  return `
    <section class="quiz-dashboard-section" aria-label="Quiz Eligibility Dashboard">
      ${summaryHTML}
      <div class="quiz-subj-grid">${subjectsHTML}</div>
    </section>`;
}

/** Build one table row HTML from computed stats. */
/* ═══════════════════════════════════════════════════════════════════════
   LABORATORY DASHBOARD UI
   Pure rendering layer — consumes LaboratoryDashboardModel. No calculations.
═══════════════════════════════════════════════════════════════════════ */

export function buildLaboratorySubjectCard(item) {
  const {
    subject,
    completedExperiments,
    remainingExperiments,
    currentExperiment,
    attendancePercentage,
    progressPercentage,
    activeMilestones,
    nextMilestone
  } = item;
  
  const pColor = pctColor(progressPercentage);
  const pw = Math.min(100, Math.max(0, progressPercentage)).toFixed(1);
  
  const aColor = pctColor(attendancePercentage);
  const aw = Math.min(100, Math.max(0, attendancePercentage)).toFixed(1);

  // Milestone line
  let milestoneHTML = '';
  if (nextMilestone) {
    milestoneHTML = `
      <div class="lab-milestone" style="margin-top:12px;padding:8px;background:var(--bg2);border-radius:6px;font-size:12px;color:var(--text2);">
        <span style="color:var(--accent);">Next Milestone:</span> ${nextMilestone.label} (Need ${nextMilestone.remainingRequired} more)
      </div>`;
  } else if (activeMilestones.length > 0) {
    const lastMs = activeMilestones[activeMilestones.length - 1];
    milestoneHTML = `
      <div class="lab-milestone" style="margin-top:12px;padding:8px;background:var(--bg2);border-radius:6px;font-size:12px;color:var(--green);">
        <span style="color:var(--green);">✓ Reached:</span> ${lastMs.label}
      </div>`;
  }

  return `
    <div class="quiz-subj-card">
      <div class="quiz-subj-header">
        <span class="subj-card-code">${subject.code}</span>
        <span class="status-badge active-attended">Exp ${currentExperiment}</span>
      </div>
      <div class="quiz-subj-name">${subject.name}</div>
      <div class="quiz-subj-stats" style="margin-top: 12px;">
        <div class="quiz-pct-row">
          <span class="quiz-pct-label">Progress</span>
          <div class="quiz-pct-right">
            <span class="quiz-pct-val" style="color:${pColor}">${completedExperiments} / ${completedExperiments + remainingExperiments}</span>
            <div class="quiz-pct-track"><div class="quiz-pct-bar" style="width:${pw}%;background:${pColor}"></div></div>
          </div>
        </div>
        <div class="quiz-pct-row">
          <span class="quiz-pct-label">Attendance</span>
          <div class="quiz-pct-right">
            <span class="quiz-pct-val" style="color:${aColor}">${attendancePercentage.toFixed(1)}%</span>
            <div class="quiz-pct-track"><div class="quiz-pct-bar" style="width:${aw}%;background:${aColor}"></div></div>
          </div>
        </div>
      </div>
      ${milestoneHTML}
    </div>`;
}

export function buildLaboratorySummaryCard(summary) {
  return `
    <div class="quiz-summary-card">
      <div class="quiz-summary-header">
        <h2 class="quiz-summary-title">Laboratory Tracker</h2>
        <span class="quiz-summary-sub">Track practical sessions & signatures</span>
      </div>
      <div class="quiz-summary-stats">
        <div class="quiz-summary-stat">
          <div class="quiz-summary-val" style="color:var(--green)">${summary.totalCompletedExperiments}</div>
          <div class="quiz-summary-label">Completed Exps</div>
        </div>
        <div class="quiz-summary-stat">
          <div class="quiz-summary-val" style="color:var(--accent)">${summary.milestonesReached}</div>
          <div class="quiz-summary-label">Milestones Reached</div>
        </div>
        <div class="quiz-summary-stat">
          <div class="quiz-summary-val" style="color:var(--text3)">${summary.totalLabSubjects}</div>
          <div class="quiz-summary-label">Lab Subjects</div>
        </div>
      </div>
    </div>`;
}

export function buildLaboratoryDashboardSection(labModel) {
  if (!labModel || labModel.subjects.length === 0) return '';
  const summaryHTML  = buildLaboratorySummaryCard(labModel.summary);
  const subjectsHTML = labModel.subjects.map(buildLaboratorySubjectCard).join('');
  return `
    <section class="quiz-dashboard-section" aria-label="Laboratory Dashboard">
      ${summaryHTML}
      <div class="quiz-subj-grid">${subjectsHTML}</div>
    </section>`;
}

export function buildTableRow(r) {
  const opt      = r.optResult;
  const tutBadge = r.totT === 0
    ? `<td data-label="Must T"><span class="badge-na">N/A</span></td>`
    : `<td data-label="Must T"><span class="badge badge-must">${opt.addT}</span></td>`;
  const tutSkip  = r.totT === 0
    ? `<td data-label="Skip T"><span class="badge-na">—</span></td>`
    : `<td data-label="Skip T">${makeSkipBudgetVisual(opt.skipT_budget, r.missT_done, 'T')}</td>`;
  const tagHTML  = r.tag ? `<div><span class="s-elec">${r.tag}</span></div>` : '';

  const currentTutCell  = r.totT > 0 ? makePctCell(r.currentTutPct, false, 'Tut %')  : `<td data-label="Tut %"><span class="badge-na">N/A</span></td>`;
  const forecastTutCell = r.totT > 0 ? makePctCell(r.forecastTutPct, false, 'Tut %') : `<td data-label="Tut %"><span class="badge-na">N/A</span></td>`;

  return `<tr>
    <td class="left" data-label="Subject">
      <div class="s-code">${r.code}</div>
      <div class="s-name">${r.name}</div>
      ${tagHTML}
    </td>
    <td data-label="Lectures"><span class="num">${r.totL}</span></td>
    <td data-label="Tutorials">${r.totT > 0 ? `<span class="num">${r.totT}</span>` : `<span class="badge-na">—</span>`}</td>
    <td data-label="Combined"><span class="num-combined">${r.totComb}</span></td>
    <th class="sep-col"></th>
    <td data-label="Must L"><span class="badge badge-must">${opt.addL}</span></td>
    ${tutBadge}
    <td data-label="Min total"><span class="num-muted">${opt.addL + opt.addT}</span></td>
    <th class="sep-col"></th>
    ${makePctCell(r.currentLecPct, false, 'Lec %')}
    ${currentTutCell}
    ${makePctCell(r.currentAvgPct, true, 'Avg %')}
    <th class="sep-col"></th>
    ${makePctCell(r.forecastLecPct, false, 'Lec %')}
    ${forecastTutCell}
    ${makePctCell(r.forecastAvgPct, true, 'Avg %')}
    <th class="sep-col"></th>
    <td data-label="Skip L">${makeSkipBudgetVisual(opt.skipL_budget, r.missL_done, 'L')}</td>
    ${tutSkip}
    <td data-label="Total skip"><span class="num-muted">${opt.skipL_budget + opt.skipT_budget}</span></td>
  </tr>`;
}

/** Main render orchestrator — assembles all sub-sections. */
export function renderPanel(rows, overallStats, erpStats, forecastStats, label, quizDate, quizModel, labModel, isMobile = false) {

  if (isMobile) {
    const mobileCardsHTML = rows.map(r => buildMobileSubjectCard(r)).join('');
    const mobileAttHTML = rows.map(r => buildMobileAttendanceCard(r)).join('');

    return `
      <div class="subject-grid mobile-subj-grid">${mobileCardsHTML}</div>
      <div class="mobile-section-title">Attendance Overview</div>
      <div class="mobile-att-cards">${mobileAttHTML}</div>
      <div class="opt-note">
        <span class="opt-note-icon">⚡</span>
        <div>
          <b>Optimisation note:</b> The "Must Attend" values are found by exhaustive search over all valid
          integer combinations of (attended lectures, attended tutorials), minimising total classes attended
          while satisfying <b>(Lec% + Tut%) / 2 ≥ 75%</b>. On ties, the combination with the
          <b>fewest lectures attended</b> (maximum lecture skips) is chosen — this is why subjects with
          tutorials show 50% lecture attendance paired with 100% tutorial attendance as the optimal minimum.
          <br><br>
          <b>Forecast %</b> assumes all remaining (pending) classes are attended. <b>Current %</b> is based only on
          completed (attended or missed) classes and excludes all pending classes.
        </div>
      </div>`;
  }

  const labSectionHTML = labModel ? buildLaboratoryDashboardSection(labModel) : "";
    const heroHTML      = buildHeroCard(overallStats, erpStats, forecastStats, label, quizDate);
  const cardsHTML     = rows.map(buildSubjectCard).join('');
  const statsHTML     = buildStatsRow(overallStats);
  const rowsHTML      = rows.map(buildTableRow).join('');
  const quizSectionHTML = quizModel ? buildQuizDashboardSection(quizModel) : '';
  const labSectionHTML = labModel ? buildLaboratoryDashboardSection(labModel) : '';


  return `
    ${heroHTML}
    ${quizSectionHTML
    ${labSectionHTML}}
    <div class="subject-grid">${cardsHTML}</div>
    ${statsHTML}
    <div class="table-card">
      <div class="table-scroll">
        <table class="att" role="table" aria-label="${label} attendance requirements">
          <thead>
            <tr class="grp-row">
              <th class="left" rowspan="2" style="min-width:180px;padding:10px 12px">Subject</th>
              <th colspan="3" class="grp-total">Total Classes</th>
              <th class="sep-col" rowspan="2"></th>
              <th colspan="3" class="grp-must">Must Attend (Remaining)</th>
              <th class="sep-col" rowspan="2"></th>
              <th colspan="3" class="grp-must">Current %</th>
              <th class="sep-col" rowspan="2"></th>
              <th colspan="3" class="grp-must">Forecast %</th>
              <th class="sep-col" rowspan="2"></th>
              <th colspan="3" class="grp-skip">Can Skip (Remaining Safe Skips)</th>
            </tr>
            <tr class="sub-row">
              <th>Lectures</th><th>Tutorials</th><th>Combined</th>
              <th class="sub-must">Must L</th><th class="sub-must">Must T</th><th class="sub-must">Min total</th>
              <th class="sub-must">Lec %</th><th class="sub-must">Tut %</th><th class="sub-must">Avg %</th>
              <th class="sub-must">Lec %</th><th class="sub-must">Tut %</th><th class="sub-must">Avg %</th>
              <th class="sub-skip">Skip L</th><th class="sub-skip">Skip T</th><th class="sub-skip">Total skip</th>
            </tr>
          </thead>
          <tbody>${rowsHTML}</tbody>
        </table>
      </div>
      <div class="legend">
        <span class="legend-item"><span class="legend-dot" style="background:var(--accent)"></span> Must Attend (blue badge)</span>
        <span class="legend-item"><span class="legend-dot" style="background:var(--green)"></span> Can Skip / Safe Skips (green badge)</span>
        <span class="legend-item"><span class="legend-dot" style="background:var(--text3)"></span> Zero / Not Applicable</span>
        <span class="legend-item"><span class="legend-dot" style="background:var(--amber)"></span> Below 75% threshold</span>
      </div>
    </div>
    <div class="opt-note">
      <span class="opt-note-icon">⚡</span>
      <div>
        <b>Optimisation note:</b> The "Must Attend" values are found by exhaustive search over all valid
        integer combinations of (attended lectures, attended tutorials), minimising total classes attended
        while satisfying <b>(Lec% + Tut%) / 2 ≥ 75%</b>. On ties, the combination with the
        <b>fewest lectures attended</b> (maximum lecture skips) is chosen — this is why subjects with
        tutorials show 50% lecture attendance paired with 100% tutorial attendance as the optimal minimum.
        <br><br>
        <b>Forecast %</b> assumes all remaining (pending) classes are attended. <b>Current %</b> is based only on
        completed (attended or missed) classes and excludes all pending classes.
      </div>
    </div>`;
}

/* ═══════════════════════════════════════════════════════════════════════
   LOGGING INTERFACE
═══════════════════════════════════════════════════════════════════════ */

/**
 * Log or update attendance for one class.
 * Blocks future-date logging unless simulation mode is active.
 */
export function logExperiment(subjectCode, expNumber, dateConducted) {
  if (!AppState.laboratory) AppState.laboratory = {};
  if (!AppState.laboratory[subjectCode]) AppState.laboratory[subjectCode] = [];
  
  let exp = AppState.laboratory[subjectCode].find(e => e.experimentNumber === parseInt(expNumber, 10));
  if (!exp) {
    exp = { experimentNumber: parseInt(expNumber, 10), signatureStatus: 'pending' };
    AppState.laboratory[subjectCode].push(exp);
  }
  
  exp.dateConducted = dateConducted;
  saveLaboratoryStates(AppState.laboratory);
  recalculateAndRender();
}

export function logAttendance(dateStr, subjectCode, type, newState) {
  if (!isScheduledClass(dateStr, subjectCode, type) || !['Attended', 'Missed', 'Pending'].includes(newState)) {
    console.warn('[logAttendance] Blocked invalid class or state.');
    return;
  }

  // All writes flow through the date context so persistence vs. temporary
  // memory (simulation) is decided in exactly one place.
  const ok = logClassState(dateStr, subjectCode, type, newState);
  if (!ok) {
    console.warn('[logAttendance] Write rejected by date context.');
    return;
  }
  recalculateAndRender();
}

/* ═══════════════════════════════════════════════════════════════════════
   TODAY'S CLASSES RENDERER
═══════════════════════════════════════════════════════════════════════ */
export function renderTodayClasses(targetDate, quizLiveData) {
  const listContainer = document.getElementById('todayClassList');
  const dateLabel     = document.getElementById('todayDateLabel');
  if (!listContainer || !dateLabel) return;

  dateLabel.innerHTML = formatTodayHeader(targetDate);

  const dow         = targetDate.getDay();
  const monIdx      = (dow + 6) % 7; // Mon=0 … Sun=6
  const dateStr     = getLocalDateString(targetDate);
  const isWeekend   = dow === 0 || dow === 6;
  const targetNoon  = new Date(targetDate);
  targetNoon.setHours(12, 0, 0, 0);
  const semStart = getTimetable().start_date;
  const semEnd   = getTimetable().quiz_dates[getTimetable().quiz_dates.length - 1].date;
  const isWithinSemester = targetNoon >= semStart && targetNoon <= semEnd;

  if (isWeekend || !isWithinSemester || !getMergedDaySchedule(monIdx)) {
    listContainer.innerHTML = `<div class="today-empty">No scheduled classes on this date.</div>`;
    return;
  }

  const classes      = getMergedDaySchedule(monIdx);
  const states       = getEffectiveStates();
  const isFuture     = dateStr > getTodayString();
  const isBlocked    = isFuture && !isSimulationMode();

  // Get live attendance data for the currently selected quiz (for tooltips)
  listContainer.innerHTML = classes.map((c, idx) => {
    const subj       = getTimetable().subjects.find(s => s.code === c.s);
    const subjName   = subj ? subj.name : c.s;
    const classId    = `${dateStr}:${c.s}:${c.t}`;
    const currState  = states[classId] || 'Pending';
    const timeSlot   = c.mergedTimeSlot || 'TBD';
    const typeLabel  = CLASS_TYPES[normalizeClassType(c.t)]?.label ?? c.t;

    const attActive  = currState === 'Attended' ? 'active-attended' : '';
    const missActive = currState === 'Missed'   ? 'active-missed'   : '';
    const pendActive = currState === 'Pending'  ? 'active-pending'  : '';
    
    const attPressed = currState === 'Attended' ? 'true' : 'false';
    const missPressed = currState === 'Missed' ? 'true' : 'false';

    // Build tooltips showing forecast impact of each possible action
    const impactAtt  = quizLiveData
      ? getImpactTooltipHTML(calcForecastImpact(quizLiveData, c.s, c.t, currState, 'Attended'))
      : '';
    const impactMiss = quizLiveData
      ? getImpactTooltipHTML(calcForecastImpact(quizLiveData, c.s, c.t, currState, 'Missed'))
      : '';

    const attTooltip  = impactAtt  || 'Mark as attended';
    const missTooltip = impactMiss || 'Mark as missed';

    // Disabled state for future dates in normal mode
    const disabledAttr = isBlocked ? 'disabled title="Enable Simulation Mode to log future dates"' : '';
    const disabledStyle = isBlocked ? 'opacity:0.4;cursor:not-allowed;' : '';
    
    const tooltipIdAtt = `tt-${dateStr}-${c.s}-${c.t}-att`.replace(/:/g, '-');
    const tooltipIdMiss = `tt-${dateStr}-${c.s}-${c.t}-miss`.replace(/:/g, '-');

    return `
      <div class="today-row">
        <div class="today-row-left">
          <div class="today-row-subj">
            <span class="s-code">${c.s}</span>
            <span class="today-row-type">${typeLabel}</span>
            <span class="today-row-time">${timeSlot}</span>
          </div>
          <div class="today-row-name">${subjName}</div>
        </div>
        <div class="today-row-actions">
          <div class="tooltip-wrap">
            <button class="action-btn ${attActive}" style="${disabledStyle}"
              ${disabledAttr}
              aria-pressed="${attPressed}"
              aria-describedby="${tooltipIdAtt}"
              aria-label="Mark ${c.s} ${typeLabel} as attended"
              data-action="logAttendance" data-date="${dateStr}" data-s="${c.s}" data-t="${c.t}" data-state="Attended">✓ Attended</button>
            <span id="${tooltipIdAtt}" role="tooltip" class="tooltip-text">${attTooltip}</span>
          </div>
          <div class="tooltip-wrap">
            <button class="action-btn ${missActive}" style="${disabledStyle}"
              ${disabledAttr}
              aria-pressed="${missPressed}"
              aria-describedby="${tooltipIdMiss}"
              aria-label="Mark ${c.s} ${typeLabel} as missed"
              data-action="logAttendance" data-date="${dateStr}" data-s="${c.s}" data-t="${c.t}" data-state="Missed">✕ Missed</button>
            <span id="${tooltipIdMiss}" role="tooltip" class="tooltip-text">${missTooltip}</span>
          </div>
          <button class="action-btn ${pendActive}"
            ${disabledAttr} style="${disabledStyle}" aria-label="Reset ${c.s} ${typeLabel} attendance status"
            data-action="logAttendance" data-date="${dateStr}" data-s="${c.s}" data-t="${c.t}" data-state="Pending">Reset</button>
        </div>
      </div>`;
  }).join('');
}

/* ═══════════════════════════════════════════════════════════════════════
   HISTORY LOG RENDERER
═══════════════════════════════════════════════════════════════════════ */
export function renderHistoryLog() {
  const historyList  = document.getElementById('historyList');
  const historyCount = document.getElementById('historyCount');
  if (!historyList || !historyCount) return;

  const states = loadStates();
  const items  = [];

  Object.entries(states).forEach(([classId, state]) => {
    if (state !== 'Attended' && state !== 'Missed') return; // skip invalid/pending
    const parts = classId.split(':');
    if (parts.length !== 3) return; // guard against corrupt keys
    const [dateStr, sCode, type] = parts;
    if (!isScheduledClass(dateStr, sCode, type)) return;
    items.push({classId, dateStr, sCode, type, state});
  });

  // Sort newest first (lexicographic YYYY-MM-DD is correct)
  items.sort((a, b) => b.dateStr.localeCompare(a.dateStr) || a.classId.localeCompare(b.classId));

  historyCount.textContent = items.length;

  if (items.length === 0) {
    historyList.innerHTML = `<div class="today-empty">No logged attendance history yet.</div>`;
    return;
  }

  historyList.innerHTML = items.map(item => {
    const subj        = getTimetable().subjects.find(s => s.code === item.sCode);
    const subjName    = subj ? subj.name : item.sCode;
    const dateFmt     = formatHistoryDate(item.dateStr);
    const isAttended  = item.state === 'Attended';
    const badgeClass  = isAttended ? 'badge-skip' : 'badge-zero';
    const symbol      = isAttended ? '✓' : '✕';
    const typeLabel   = CLASS_TYPES[normalizeClassType(item.type)]?.label ?? item.type;

    return `
      <div class="history-row" style="display:flex;justify-content:space-between;align-items:center;padding:10px 14px;border-bottom:1px solid var(--border);font-size:12.5px;">
        <div style="display:flex;align-items:center;gap:12px;">
          <span class="badge ${badgeClass}" style="min-width:24px;height:24px;padding:0;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;">${symbol}</span>
          <div>
            <span style="font-weight:600;color:var(--text);">${dateFmt}</span>
            <span style="color:var(--text3);margin:0 6px;">•</span>
            <span style="color:var(--text2);"><strong style="font-family:'JetBrains Mono',monospace;color:var(--text);">${item.sCode}</strong> ${typeLabel}</span>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:10px;">
          <span style="color:var(--text3);font-size:11px;">${subjName}</span>
          <button class="theme-btn" style="padding:2px 6px;font-size:10px;"
            aria-label="Reset ${item.sCode} ${typeLabel} on ${dateFmt}"
            data-action="logAttendance" data-date="${item.dateStr}" data-s="${item.sCode}" data-t="${item.type}" data-state="Pending">Reset</button>
        </div>
      </div>`;
  }).join('');
}

/* ═══════════════════════════════════════════════════════════════════════
   RECALCULATE & RENDER — master refresh
═══════════════════════════════════════════════════════════════════════ */
export function recalculateAndRender() {
  const targetDate  = getActiveDate();
  const liveData    = getAttendanceData(getTimetable().quiz_dates[currentQuiz].date, getEffectiveStates());
  const isMobile    = window.innerWidth < 768;

  renderTodayClasses(targetDate, liveData);
  renderHistoryLog();
  // Also render into mobile history list
  const mobileList = document.getElementById('mobileHistoryList');
  if (mobileList) {
    const desktopList = document.getElementById('historyList');
    if (desktopList) {
      mobileList.innerHTML = desktopList.innerHTML;
    }
  }

  // PRE-COMPUTE subject rows, overall stats, and ERP overall ONCE here
  const {label, date: quizDate} = getTimetable().quiz_dates[currentQuiz];
  const rows = getTimetable().subjects.map(({code, name, tag}) =>
    computeSubjectStats(code, name, tag, liveData[code])
  );
  const overallStats = computeOverallStats(rows);

  // ERP Overall Attendance — single source of truth, computed once
  const erpStats      = computeCurrentOverallAttendance(liveData, getTimetable().subjects);
  const forecastStats = computeForecastOverallAttendance(liveData, getTimetable().subjects);

  // Quiz Dashboard Model — computed once, passed into renderPanel
  const quizModel = computeQuizDashboard(rows, getTimetable());

  // Laboratory Dashboard Model
  const labModel = computeLaboratoryDashboard(AppState.laboratory || {}, getEffectiveStates(), rows, getTimetable());

  // Render panels
  document.getElementById('panels').innerHTML = renderPanel(rows, overallStats, erpStats, forecastStats, label, quizDate, quizModel, labModel, isMobile);

  if (isMobile) {
    const quizSectionHTML = buildQuizDashboardSection(quizModel);
    const heroHTML  = buildHeroCard(overallStats, erpStats, forecastStats, label, quizDate);
    const statsHTML = buildStatsRow(overallStats);

    // Insert hero + stats into mobile container (positioned before Today's Classes in HTML)
    const heroContainer = document.getElementById('mobileHeroContainer');
    if (heroContainer) {
      heroContainer.innerHTML = heroHTML + statsHTML + quizSectionHTML + (labModel ? buildLaboratoryDashboardSection(labModel) : "");
    }

    // Setup accordion + formula toggle (only on first run per render)
    setupMobileAccordion();
    initFormulaToggle();
  }

  updateModeBadge();
  updateViewingLabel();

}

/* ═══════════════════════════════════════════════════════════════════════
   MOBILE INTERACTION BINDINGS
   Formula card toggle · Subject card accordion
   ═══════════════════════════════════════════════════════════════════════ */

let formulaToggleBound = false;

function initFormulaToggle() {
  const toggle = document.getElementById('formulaToggle');
  const card   = document.getElementById('formulaCard');
  if (!toggle || !card) return;

  // Remove any existing listener to avoid duplicates
  if (formulaToggleBound) return;
  formulaToggleBound = true;

  // Start collapsed on mobile
  card.classList.add('collapsed');
  toggle.setAttribute('aria-expanded', 'false');
  toggle.querySelector('.formula-header-hint').textContent = 'Tap to Expand';

  toggle.addEventListener('click', () => {
    const isCollapsed = card.classList.toggle('collapsed');
    toggle.setAttribute('aria-expanded', String(!isCollapsed));
    toggle.querySelector('.formula-header-hint').textContent =
      isCollapsed ? 'Tap to Expand' : 'Tap to collapse';
  });
}

let accordionBound = false;

function setupMobileAccordion() {
  if (!accordionBound) {
    accordionBound = true;
    document.addEventListener('click', (e) => {
      const header = e.target.closest('.mobile-subj-header');
      if (!header) return;

      const card = header.closest('.mobile-subj-card');
      if (!card) return;

      const body = card.querySelector('.mobile-subj-body');
      if (!body) return;

      const isExpanded = card.classList.contains('expanded');

      // Close all other cards
      document.querySelectorAll('.mobile-subj-card.expanded').forEach(c => {
        if (c !== card) {
          c.classList.remove('expanded');
          c.querySelector('.mobile-subj-header').setAttribute('aria-expanded', 'false');
          const b = c.querySelector('.mobile-subj-body');
          if (b) b.hidden = true;
        }
      });

      // Toggle current
      if (isExpanded) {
        card.classList.remove('expanded');
        header.setAttribute('aria-expanded', 'false');
        body.hidden = true;
      } else {
        card.classList.add('expanded');
        header.setAttribute('aria-expanded', 'true');
        body.hidden = false;
      }
    });
  }
}

/* ═══════════════════════════════════════════════════════════════════════
   TAB SWITCHING
═══════════════════════════════════════════════════════════════════════ */

export function switchQuiz(idx, btn) {
  if (idx === currentQuiz) return;
  currentQuiz = idx;
  document.querySelectorAll('.tab-btn').forEach((b, i) => {
    b.classList.toggle('active', i === idx);
    b.setAttribute('aria-selected', i === idx ? 'true' : 'false');
  });
  recalculateAndRender();
}

/* ═══════════════════════════════════════════════════════════════════════
   THEME TOGGLE
═══════════════════════════════════════════════════════════════════════ */
const MOON_PATH = "M21 12.79A9 9 0 1 1 11.21 3a7 7 0 1 0 9.79 9.79z";
const SUN_PATH  = "M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42M12 5a7 7 0 1 0 0 14A7 7 0 0 0 12 5z";

export function updateThemeBtn(theme) {
  const iconPath = document.getElementById('themeIconPath');
  const label    = document.getElementById('themeLabel');
  if (!iconPath || !label) return;
  if (theme === 'dark') {
    iconPath.setAttribute('d', MOON_PATH);
    label.textContent = 'Dark';
  } else {
    iconPath.setAttribute('d', SUN_PATH);
    label.textContent = 'Light';
  }
}

/* ═══════════════════════════════════════════════════════════════════════
   BOTTOM SHEET DATE NAVIGATOR (for mobile)
   Renders the same date options as the dropdown into a bottom sheet.
═══════════════════════════════════════════════════════════════════════ */

export function renderBottomSheetDateNav() {
  const body = document.getElementById('bottomSheetBody');
  if (!body) return;

  const opts = buildNavigatorOptions();

  body.innerHTML = `
    ${opts.map(o => `
      <button class="sheet-nav-item ${o.active ? 'active' : ''}" data-nav="${o.action}" ${o.dateStr ? `data-date="${o.dateStr}"` : ''}>
        <span class="nav-item-ico" aria-hidden="true">${o.icon}</span>
        <span class="nav-item-label">${o.label}</span>
        <span class="nav-item-mode ${o.modeClass}">${o.modeText}</span>
      </button>`).join('')}
    <div class="nav-sep"></div>
    <div class="sheet-picker">
      <label class="sheet-picker-label" for="sheetDatePicker">Pick Date…</label>
      <input type="date" id="sheetDatePicker" class="sheet-picker-input"
             min="${getLocalDateString(getTimetable().start_date)}"
             value="${getActiveDateString()}"
             aria-label="Pick a date" />
    </div>`;

  // Reuse existing navigator event handlers
  body.addEventListener('click', (e) => {
    const item = e.target.closest('[data-nav]');
    if (!item) return;
    const action = item.getAttribute('data-nav');
    const dateStr = item.getAttribute('data-date');
    if (action === 'yesterday' || action === 'today' || action === 'tomorrow') {
      selectDateByString(dateStr);
      closeBottomSheet();
      afterDateChange();
    }
  });

  const picker = document.getElementById('sheetDatePicker');
  if (picker) {
    picker.addEventListener('change', () => {
      if (picker.value) {
        selectDateByString(picker.value);
        closeBottomSheet();
        afterDateChange();
      }
    });
  }
}

function closeBottomSheet() {
  const sheet = document.getElementById('bottomSheetDateNav');
  const overlay = document.getElementById('bottomSheetOverlay');
  if (sheet) sheet.style.display = 'none';
  if (overlay) overlay.style.display = 'none';
  document.body.style.overflow = '';
}

/* ═══════════════════════════════════════════════════════════════════════
   BUILT-IN TEST SUITE
   Run automatically on load. All results printed to console.
   No external dependencies required.
═══════════════════════════════════════════════════════════════════════ */
