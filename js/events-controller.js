import { AppState, triggerCloudSync, persistLocalState } from './storage.js';
import { createAcademicEvent as normalizeAcademicEvent, syncRuntimeEvents, validateAcademicEvent } from './calendar-engine.js';
import { recalculateAndRender } from './ui.js';
import { auth } from './firebase.js';

function generateId() {
  return 'evt_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
}

/**
 * Common pipeline for ALL academic event mutations.
 *
 * Atomicity model:
 *  1. Snapshot AppState.academicEvents before mutation.
 *  2. Run mutationFn() — modifies AppState.academicEvents in-place.
 *  3. If mutationFn throws, AppState is NOT modified (exception thrown before any write).
 *     All mutation functions must validate before writing.
 *  4. Sync runtime Calendar state from updated AppState.
 *  5. Persist locally. If this fails, revert AppState to snapshot + revert runtime.
 *  6. Trigger cloud sync (async, best-effort; local state is authoritative on refresh).
 *  7. Recalculate and render.
 *
 * Invariant: UI state = AppState = runtime Calendar state after any successful mutation.
 * On failure: AppState and runtime are both reverted to pre-mutation snapshot.
 */
function processEventMutation(mutationFn) {
  // Snapshot AppState.academicEvents for rollback.
  const snapshot = JSON.parse(JSON.stringify(AppState.academicEvents));

  try {
    mutationFn();
  } catch (err) {
    // mutationFn failed: AppState was not written, so no rollback needed.
    console.error("[EventsController] Mutation validation/logic failed:", err);
    return { success: false, error: err.message };
  }

  // Synchronize Calendar Engine runtime state from the now-mutated AppState.
  syncRuntimeEvents(AppState.academicEvents);
  AppState.isDirty = true;

  // Persist locally. Revert on failure.
  if (auth && auth.currentUser) {
    try {
      persistLocalState(auth.currentUser.uid);
    } catch (persistErr) {
      // Local persistence failed — revert AppState and runtime to snapshot.
      console.error("[EventsController] Persistence failed, reverting state:", persistErr);
      AppState.academicEvents = snapshot;
      AppState.isDirty = false;
      syncRuntimeEvents(AppState.academicEvents); // revert runtime
      return { success: false, error: 'Local persistence failed. Changes reverted.' };
    }
  }

  // Cloud sync is async and best-effort. Local is authoritative.
  triggerCloudSync();
  recalculateAndRender();
  return { success: true };
}

/**
 * Creates and persists a new academic event.
 * Validates, normalizes via Calendar Engine, then inserts into AppState.
 */
export function createAcademicEvent(rawEvent) {
  return processEventMutation(() => {
    validateAcademicEvent(rawEvent);

    // Check uniqueness (active event with same type, date, subject, classType)
    const existingDateEvents = AppState.academicEvents[rawEvent.effectiveDate] || [];
    const isDuplicate = existingDateEvents.some(e =>
      e.active &&
      e.eventType === rawEvent.eventType &&
      e.subjectCode === rawEvent.subjectCode &&
      e.classType === rawEvent.classType
    );
    if (isDuplicate) {
      throw new Error('An active event of this type already exists on this date.');
    }

    const newEventData = {
      ...rawEvent,
      id: generateId(),
      version: 1,
      createdAt: new Date().toISOString(),
      source: 'USER',
      active: true,
      archived: false
    };

    // Use the Calendar Engine's pure normalizer to create the frozen event object.
    const createdEvent = normalizeAcademicEvent(newEventData);

    if (!AppState.academicEvents[createdEvent.effectiveDate]) {
      AppState.academicEvents[createdEvent.effectiveDate] = [];
    }
    AppState.academicEvents[createdEvent.effectiveDate].push(createdEvent);
  });
}

/**
 * Updates an existing academic event (optionally moving it to a new date).
 */
export function updateAcademicEvent(updatedRawEvent, originalDate) {
  return processEventMutation(() => {
    validateAcademicEvent(updatedRawEvent);

    const history = updatedRawEvent.history ? [...updatedRawEvent.history] : [];
    history.push({
      action: 'Edited',
      timestamp: new Date().toISOString(),
      user: 'system'
    });
    updatedRawEvent.history = history;

    // Remove from old date slot if the date has changed
    if (originalDate && originalDate !== updatedRawEvent.effectiveDate) {
      if (AppState.academicEvents[originalDate]) {
        AppState.academicEvents[originalDate] = AppState.academicEvents[originalDate]
          .filter(e => e.id !== updatedRawEvent.id);
      }
    }

    const updatedEvent = normalizeAcademicEvent(updatedRawEvent);

    if (!AppState.academicEvents[updatedEvent.effectiveDate]) {
      AppState.academicEvents[updatedEvent.effectiveDate] = [];
    }
    const idx = AppState.academicEvents[updatedEvent.effectiveDate].findIndex(e => e.id === updatedEvent.id);
    if (idx >= 0) {
      AppState.academicEvents[updatedEvent.effectiveDate][idx] = updatedEvent;
    } else {
      AppState.academicEvents[updatedEvent.effectiveDate].push(updatedEvent);
    }
  });
}

/**
 * Toggles the active/disabled state of an event.
 */
export function toggleAcademicEvent(eventId, dateString, isActive) {
  return processEventMutation(() => {
    if (!AppState.academicEvents[dateString]) throw new Error('Date not found');
    const idx = AppState.academicEvents[dateString].findIndex(e => e.id === eventId);
    if (idx < 0) throw new Error('Event not found');

    const event = AppState.academicEvents[dateString][idx];
    const newHistory = [...event.history, {
      action: isActive ? 'Enabled' : 'Disabled',
      timestamp: new Date().toISOString(),
      user: 'system'
    }];
    const updatedRawEvent = { ...event, active: isActive, history: newHistory };
    AppState.academicEvents[dateString][idx] = normalizeAcademicEvent(updatedRawEvent);
  });
}

/**
 * Archives (soft-deletes) an event. Archived events are excluded from Calendar Engine lookups.
 */
export function archiveAcademicEventController(eventId, dateString) {
  return processEventMutation(() => {
    if (!AppState.academicEvents[dateString]) throw new Error('Date not found');
    const idx = AppState.academicEvents[dateString].findIndex(e => e.id === eventId);
    if (idx < 0) throw new Error('Event not found');

    const event = AppState.academicEvents[dateString][idx];
    const newHistory = [...event.history, {
      action: 'Archived',
      timestamp: new Date().toISOString(),
      user: 'system'
    }];
    const updatedRawEvent = { ...event, archived: true, active: false, history: newHistory };
    AppState.academicEvents[dateString][idx] = normalizeAcademicEvent(updatedRawEvent);
  });
}
