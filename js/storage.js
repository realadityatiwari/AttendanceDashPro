import { auth, db } from './firebase.js';

export const AppState = {
  profile: {},
  attendance: {},
  history: [],
  settings: {
    theme: 'dark',
    simulationMode: false
  },
  isDirty: false
};

let cloudSyncTimeout = null;

// ====================================================
// LOCAL PERSISTENCE
// ====================================================

export function initLocalState(uid) {
  try {
    const raw = localStorage.getItem(`app_state_${uid}`);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        if (parsed.attendance && typeof parsed.attendance === 'object' && !Array.isArray(parsed.attendance)) {
          AppState.attendance = parsed.attendance;
        }
        if (parsed.settings && typeof parsed.settings === 'object' && !Array.isArray(parsed.settings)) {
          AppState.settings = { ...AppState.settings, ...parsed.settings };
        }
        if (parsed.profile && typeof parsed.profile === 'object' && !Array.isArray(parsed.profile)) {
          AppState.profile = { ...AppState.profile, ...parsed.profile };
        }
        console.log("[storage.js] Local state hydrated successfully.");
      }
    }
  } catch (e) {
    console.error("[storage.js] Failed to parse local state. Using defaults.", e);
  }
}

export function persistLocalState(uid) {
  if (!uid) return;
  try {
    localStorage.setItem(`app_state_${uid}`, JSON.stringify(AppState));
  } catch (e) {
    console.error("[storage.js] Failed to persist local state:", e);
  }
}

export function loadStates() {
  return AppState.attendance;
}

export function saveStates(states) {
  AppState.attendance = states;
  AppState.isDirty = true;
  
  if (auth.currentUser) {
    persistLocalState(auth.currentUser.uid);
    triggerCloudSync();
  }
}

export function clearStates() {
  AppState.attendance = {};
  AppState.isDirty = true;
  
  if (auth.currentUser) {
    persistLocalState(auth.currentUser.uid);
    triggerCloudSync(true); // explicitly pass isResetting = true
  }
}

// ====================================================
// CLOUD SYNCHRONIZATION
// ====================================================

function isPlainObject(val) {
  return val !== null && typeof val === 'object' && !Array.isArray(val);
}

export async function fetchCloudStates() {
  if (!auth.currentUser) return false;
  const uid = auth.currentUser.uid;
  let stateChanged = false;

  try {
    const doc = await db.collection('students').doc(uid).get();
    if (doc.exists) {
      const data = doc.data();
      
      console.log("[PROFILE 1] Firestore:", data.profile);
      
      // Safe merge: Attendance
      if (isPlainObject(data.attendance)) {
        AppState.attendance = { ...AppState.attendance, ...data.attendance };
        stateChanged = true;
      }
      
      // Safe merge: Settings
      if (isPlainObject(data.settings)) {
        AppState.settings = { ...AppState.settings, ...data.settings };
        stateChanged = true;
      }
      
      // Safe merge: Profile
      if (isPlainObject(data.profile)) {
        console.log("[PROFILE 2] Local Before Merge:", AppState.profile);
        
        AppState.profile = { ...AppState.profile, ...data.profile };
        
        console.log("[PROFILE 3] Local After Merge:", AppState.profile);
        stateChanged = true;
      }
      
      if (stateChanged) {
        persistLocalState(uid);
      }
      
      return stateChanged;
    } else {
      // Cloud document doesn't exist. Let's upload local state if it's not empty.
      if (Object.keys(AppState.attendance).length > 0) {
        AppState.isDirty = true;
        triggerCloudSync();
      }
      return false;
    }
  } catch (err) {
    console.error("[storage.js] Failed to fetch cloud states:", err);
    return false;
  }
}

export function isProfileComplete(profile) {
  return profile && 
         typeof profile.name === 'string' && profile.name.trim() !== '' &&
         typeof profile.rollNumber === 'string' && profile.rollNumber.trim() !== '';
}

function hasAttendanceData(attendance) {
  return attendance && Object.keys(attendance).length > 0;
}

function isValidSettings(settings) {
  return settings && Object.keys(settings).length > 0;
}

export function triggerCloudSync(isResetting = false) {
  if (!auth.currentUser) return;
  const uid = auth.currentUser.uid;
  
  // IMMEDIATELY persist local state. This ensures that modifications made outside
  // of normal attendance flow (e.g. Profile creation during signup) are securely 
  // saved to localStorage before any network delays or page unloads.
  persistLocalState(uid);
  
  if (cloudSyncTimeout) clearTimeout(cloudSyncTimeout);
  
  cloudSyncTimeout = setTimeout(async () => {
    try {
      const payload = {};

      if (isProfileComplete(AppState.profile)) {
        payload.profile = AppState.profile;
      }

      if (isValidSettings(AppState.settings)) {
        payload.settings = AppState.settings;
      }

      // Defensive guard: Never upload an empty attendance object unless explicitly resetting.
      // This allows the profile and settings to sync normally for new users without 
      // accidentally wiping cloud attendance data if local state failed to hydrate.
      if (isResetting || hasAttendanceData(AppState.attendance)) {
        payload.attendance = AppState.attendance;
      }

      if (Object.keys(payload).length > 0) {
        await db.collection('students').doc(uid).set(payload, { merge: true });
      }
      
      AppState.isDirty = false;
      persistLocalState(uid); // persist again to clear isDirty flag
      console.log("[storage.js] Cloud sync complete.");
    } catch (err) {
      console.error("[storage.js] Cloud sync failed", err);
    }
  }, 1000);
}

// ====================================================
// LEGACY MIGRATION (V1 -> V2)
// ====================================================

export function getLocalAttendance() {
  try {
    const raw = localStorage.getItem('attendance_tracker_states');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Object.keys(parsed).length > 0) return parsed;
    }
  } catch (e) {
    return null;
  }
  return null;
}

export function clearLocalAttendance() {
  localStorage.removeItem('attendance_tracker_states');
  localStorage.removeItem('attendance_tracker_version');
}
