import { AppState, triggerCloudSync, persistLocalState } from './storage.js';
import { addAcademicEvent, archiveAcademicEvent, AcademicEventRegistry, validateAcademicEvent } from './calendar-engine.js';
import { recalculateAndRender } from './ui.js';
import { auth } from './firebase.js';

function generateId() {
  return 'evt_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
}

/**
 * Common pipeline for event mutations.
 */
function processEventMutation(mutationFn) {
  try {
    mutationFn();
    AppState.isDirty = true;
    if (auth && auth.currentUser) {
      persistLocalState(auth.currentUser.uid);
    }
    triggerCloudSync();
    recalculateAndRender();
    return { success: true };
  } catch (err) {
    console.error("[EventsController] Error mutating event:", err);
    return { success: false, error: err.message };
  }
}

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
      throw new Error("An active event of this type already exists on this date.");
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

    const createdEvent = addAcademicEvent(newEventData);
    
    if (!AppState.academicEvents[createdEvent.effectiveDate]) {
      AppState.academicEvents[createdEvent.effectiveDate] = [];
    }
    AppState.academicEvents[createdEvent.effectiveDate].push(createdEvent);
  });
}

export function updateAcademicEvent(updatedRawEvent, originalDate) {
  return processEventMutation(() => {
    validateAcademicEvent(updatedRawEvent);
    
    // We add a history entry for Edited
    const history = updatedRawEvent.history ? [...updatedRawEvent.history] : [];
    history.push({
      action: 'Edited',
      timestamp: new Date().toISOString(),
      user: 'system'
    });
    
    updatedRawEvent.history = history;

    // Remove from old date if changed
    if (originalDate && originalDate !== updatedRawEvent.effectiveDate) {
      if (AppState.academicEvents[originalDate]) {
        AppState.academicEvents[originalDate] = AppState.academicEvents[originalDate].filter(e => e.id !== updatedRawEvent.id);
      }
      archiveAcademicEvent(updatedRawEvent.id, originalDate);
    }

    const updatedEvent = addAcademicEvent(updatedRawEvent);
    
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

export function toggleAcademicEvent(eventId, dateString, isActive) {
  return processEventMutation(() => {
    if (!AppState.academicEvents[dateString]) throw new Error("Date not found");
    const idx = AppState.academicEvents[dateString].findIndex(e => e.id === eventId);
    if (idx < 0) throw new Error("Event not found");

    const event = AppState.academicEvents[dateString][idx];
    const action = isActive ? 'Enabled' : 'Disabled';
    const newHistory = [...event.history, {
      action: action,
      timestamp: new Date().toISOString(),
      user: 'system'
    }];
    
    const updatedRawEvent = {
      ...event,
      active: isActive,
      history: newHistory
    };

    const updatedEvent = addAcademicEvent(updatedRawEvent);
    AppState.academicEvents[dateString][idx] = updatedEvent;
  });
}

export function archiveAcademicEventController(eventId, dateString) {
  return processEventMutation(() => {
    if (!AppState.academicEvents[dateString]) throw new Error("Date not found");
    const idx = AppState.academicEvents[dateString].findIndex(e => e.id === eventId);
    if (idx < 0) throw new Error("Event not found");

    const archivedEvent = archiveAcademicEvent(eventId, dateString);
    if (archivedEvent) {
      AppState.academicEvents[dateString][idx] = archivedEvent;
    }
  });
}
