/* ═══════════════════════════════════════════════════════════════════════
   DATE CONTEXT SYSTEM — single source of truth for which day is being
   viewed or simulated, and whether writes are persisted.

   Every module consumes this shared state instead of maintaining its own
   notion of "today / yesterday / tomorrow". The attendance engine and
   rendering layers read effective attendance from here, so there is no
   duplicated attendance logic for different date scenarios.
═══════════════════════════════════════════════════════════════════════ */

import { getTimetable } from './utils.js';
import { AppState, saveStates, loadStates } from './storage.js';
import { getTodayString } from './calendar-engine.js';

export const MODE = { LIVE: 'LIVE', SIMULATION: 'SIMULATION' };

/**
 * selectedDate   — the Date currently being viewed (as YYYY-MM-DD string)
 * mode           — MODE.LIVE or MODE.SIMULATION
 * simulationAttendance — temporary overlay of classId -> state, ONLY used
 *                        in simulation mode. Never written to Firebase.
 */
export const dateContext = {
  selectedDate: getTodayString(),
  mode: MODE.LIVE,
  simulationAttendance: {}
};

/* ─── Mode derivation ───────────────────────────────────────────────────
   The mode is a pure function of the selected date and is never set
   manually elsewhere:
     • Today .................. LIVE
     • Any past date .......... LIVE
     • Tomorrow ............... SIMULATION
     • Any future date ........ SIMULATION
══════════════════════════════════════════════════════════════════════ */
export function deriveMode(dateStr) {
  const selStr = dateStr || dateContext.selectedDate;
  const todayStr = getTodayString();
  return selStr > todayStr ? MODE.SIMULATION : MODE.LIVE;
}

/** Returns true if currently in simulation mode. */
export function isSimulationMode() {
  return dateContext.mode === MODE.SIMULATION;
}

/** Returns the local YYYY-MM-DD string for the selected date. */
export function getActiveDateString() {
  return dateContext.selectedDate;
}

/* ─── Effective attendance ──────────────────────────────────────────────
   Produces the classId -> state map that should drive all rendering and
   calculations. In LIVE mode this is exactly the persisted cloud/local
   states. In SIMULATION mode it is the persisted states overlaid with the
   in-memory simulationAttendance (simulation wins on conflict). The engine
   thus has ONE code path regardless of date.
══════════════════════════════════════════════════════════════════════ */
export function getEffectiveStates() {
  const base = loadStates();
  if (dateContext.mode === MODE.LIVE) {
    return { ...base };
  }
  return { ...base, ...dateContext.simulationAttendance };
}

/* ─── Date selection ────────────────────────────────────────────────────
   Single entry point for changing the viewed day. Recomputes mode and,
   when leaving simulation mode, discards the temporary overlay.
══════════════════════════════════════════════════════════════════════ */
export function selectDateByString(dateStr) {
  dateContext.selectedDate = dateStr;
  const newMode = deriveMode(dateStr);

  // Leaving simulation mode clears the temporary memory (nothing persisted).
  if (newMode !== MODE.SIMULATION) {
    dateContext.simulationAttendance = {};
  }
  dateContext.mode = newMode;
}

export function resetToToday() {
  selectDateByString(getTodayString());
}

/* ─── Logging through the context ───────────────────────────────────────
   ONE place that decides whether a write is persisted or kept in memory.
   • LIVE mode .......... persisted to cloud/local via saveStates()
   • SIMULATION mode .... only written to simulationAttendance (temp memory)
   No module calls saveStates() directly for logging anymore.
══════════════════════════════════════════════════════════════════════ */
export function logClassState(dateStr, subjectCode, type, newState) {
  const classId = `${dateStr}:${subjectCode}:${type}`;
  const valid = ['Attended', 'Missed', 'Pending'];

  if (!valid.includes(newState)) return false;
  // Guard: only the selected day may be logged through the context.
  if (dateStr !== getActiveDateString()) return false;

  if (dateContext.mode === MODE.SIMULATION) {
    // Temporary memory only — never persisted.
    if (newState === 'Pending') {
      delete dateContext.simulationAttendance[classId];
    } else {
      dateContext.simulationAttendance[classId] = newState;
    }
    return true;
  }

  // LIVE mode — persisted.
  const states = loadStates();
  if (newState === 'Pending') {
    delete states[classId];
  } else {
    states[classId] = newState;
  }
  saveStates(states);
  return true;
}

/* ─── Classifies a date relative to today (for the navigator UI) ──────── */
export function classifyDateStr(dStr) {
  const todayStr = getTodayString();
  if (dStr === todayStr) return 'today';
  if (dStr < todayStr)   return 'past';
  return 'future';
}
