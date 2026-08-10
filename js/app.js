import { initTimetable, getTimetable } from './utils.js';
import { initCalendarEngine, syncRuntimeEvents } from './calendar-engine.js';
import { auth } from './firebase.js';
import { AppState, fetchCloudStates, getLocalAttendance, clearLocalAttendance, triggerCloudSync, initLocalState, persistLocalState, isProfileComplete } from './storage.js';
import { recalculateAndRender, updateThemeBtn, renderDateNavigator, renderBottomSheetDateNav, renderAcademicEvents } from './ui.js';
import { createAcademicEvent, updateAcademicEvent, archiveAcademicEventController, toggleAcademicEvent } from './events-controller.js';
import { AcademicEventRegistry } from './calendar-engine.js';

import { loginUser, signupUser, logoutUser } from './auth.js';
import { validateSignupForm, validateRollNumber, validatePassword } from './validation.js';
import * as UI from './ui.js';
import { initFeedbackSystem } from './feedback.js';
import { initPWA } from './pwa.js';

console.log("[app.js] Module loaded");

async function handleAppLogin() {
  console.log("[app.js] handleAppLogin clicked");
  const roll = document.getElementById('loginRoll').value.trim();
  const pass = document.getElementById('loginPass').value;
  
  const errDiv = document.getElementById('authError');
  errDiv.style.display = 'none';

  if (!roll || !pass) {
    console.log("[app.js] Login failed: empty fields");
    errDiv.textContent = "Please fill in both fields.";
    errDiv.style.display = 'block';
    return;
  }
  
  console.log("[app.js] Attempting login for", roll);
  try {
    const res = await loginUser(roll, pass);
    if (!res.success) {
      console.error("[app.js] Login failed:", res.error);
      errDiv.textContent = res.error;
      errDiv.style.display = 'block';
    } else {
      console.log("[app.js] Login success");
    }
  } catch (e) {
    console.error("[app.js] Login exception:", e);
  }
}

async function handleAppSignup() {
  console.log("[app.js] handleAppSignup clicked");
  const name = document.getElementById('signupName').value.trim();
  const roll = document.getElementById('signupRoll').value.trim();
  const pass = document.getElementById('signupPass').value;
  const passConfirm = document.getElementById('signupPassConfirm').value;
  
  const errDiv = document.getElementById('authError');
  errDiv.style.display = 'none';

  const valid = validateSignupForm(name, roll, pass, passConfirm);
  if (!valid.valid) {
    console.log("[app.js] Signup validation failed:", valid.message);
    errDiv.textContent = valid.message;
    errDiv.style.display = 'block';
    return;
  }
  
  console.log("[app.js] Attempting signup for", roll);
  try {
    const res = await signupUser(name, roll, pass);
    if (!res.success) {
      console.error("[app.js] Signup error:", res.error);
      errDiv.textContent = res.error;
      errDiv.style.display = 'block';
    } else {
      console.log("[app.js] Signup success");
      // The auth-state listener may have rendered before signupUser populated
      // AppState.profile. Re-render the header and dismiss a prematurely shown
      // recovery modal so the fresh account shows its real name immediately.
      updateProfileUI();
      if (isProfileComplete(AppState.profile)) {
        document.getElementById('profileRecoveryModal').style.display = 'none';
      }
    }
  } catch(e) {
    console.error("[app.js] Signup exception:", e);
  }
}

async function handleAppLogout() {
  console.log("[app.js] handleAppLogout clicked");
  await logoutUser();
}

function toggleAuthView(e) {
  if (e) e.preventDefault();
  console.log("[app.js] toggleAuthView triggered");
  const login = document.getElementById('loginView');
  const signup = document.getElementById('signupView');
  const errDiv = document.getElementById('authError');
  errDiv.style.display = 'none';
  
  if (login.style.display !== 'none') {
    login.style.display = 'none';
    signup.style.display = 'block';
  } else {
    login.style.display = 'block';
    signup.style.display = 'none';
  }
}

function handleMigrationImport() {
  console.log("[app.js] handleMigrationImport clicked");
  const localData = getLocalAttendance();
  if (localData) {
    import('./storage.js').then(({ saveStates }) => {
      saveStates(localData);
      clearLocalAttendance();
      document.getElementById('migrationModal').style.display = 'none';
      recalculateAndRender();
    }).catch(e => console.error("[app.js] Migration import error:", e));
  }
}

function handleMigrationDiscard() {
  console.log("[app.js] handleMigrationDiscard clicked");
  clearLocalAttendance();
  document.getElementById('migrationModal').style.display = 'none';
}

function checkMigration() {
  console.log("[app.js] checkMigration called");
  const localData = getLocalAttendance();
  if (localData) {
    console.log("[app.js] Migration data found, showing modal");
    document.getElementById('migrationModal').style.display = 'flex';
  } else {
    console.log("[app.js] No migration data found");
  }
}

function checkProfileRecovery() {
  console.log("[RECOVERY 1] checkProfileRecovery called");
  console.log("[RECOVERY 2] Profile:", AppState.profile);
  console.log("[RECOVERY 3] isProfileComplete:", isProfileComplete(AppState.profile));
  if (!isProfileComplete(AppState.profile)) {
    console.log("[RECOVERY 4] Showing modal");
    document.getElementById('profileRecoveryModal').style.display = 'flex';
  }
}

export function saveProfile(profile) {
  if (!profile.name || profile.name.trim() === '') {
    return { success: false, error: 'Full Name is required.' };
  }
  const rollValidation = validateRollNumber(profile.rollNumber);
  if (!rollValidation.valid) {
    return { success: false, error: rollValidation.message };
  }

  // Update AppState
  AppState.profile = {
    ...AppState.profile,
    name: profile.name.trim(),
    rollNumber: profile.rollNumber.trim()
  };

  // Persist locally
  if (auth.currentUser) {
    persistLocalState(auth.currentUser.uid);
  }

  // Trigger cloud sync
  triggerCloudSync();

  // Refresh UI
  updateProfileUI();

  return { success: true };
}

function updateProfileUI(profileArg) {
  console.log("[PROFILE 5] Rendering:", AppState.profile);
  console.log("[PROFILE 5] Before DOM update:", {
      profileName: document.getElementById("profileName")?.textContent,
      profileRoll: document.getElementById("profileRoll")?.textContent,
      profileViewName: document.getElementById("profileViewName")?.textContent,
      profileViewRoll: document.getElementById("profileViewRoll")?.textContent
  });
  
  const nameEl = document.getElementById('profileName');
  const rollEl = document.getElementById('profileRoll');
  
  const name = AppState.profile.name || "Student";
  const roll = AppState.profile.rollNumber || "Roll No";
  
  if (nameEl) nameEl.textContent = name;
  if (rollEl) rollEl.textContent = roll;
  
  // Sync profile view
  const pvName = document.getElementById('profileViewName');
  const pvRoll = document.getElementById('profileViewRoll');
  const pvInit = document.getElementById('profileInitial');
  if (pvName) pvName.textContent = name;
  if (pvRoll) pvRoll.textContent = roll;
  if (pvInit) pvInit.textContent = name[0].toUpperCase();
  // Sync profile theme label
  const theme = document.documentElement.getAttribute('data-theme') || 'dark';
  const label = document.getElementById('profileThemeLabel');
  if (label) label.textContent = theme === 'dark' ? 'Dark Mode' : 'Light Mode';
  
  console.log("[PROFILE 5] After DOM update:", {
      profileName: document.getElementById("profileName")?.textContent,
      profileRoll: document.getElementById("profileRoll")?.textContent,
      profileViewName: document.getElementById("profileViewName")?.textContent,
      profileViewRoll: document.getElementById("profileViewRoll")?.textContent
  });
}

/**
 * Extracts independent subject timelines from the core timetable.
 * Designed to separate Weekly Schedule Data from Academic Event Data,
 * preparing for a future migration to a standalone academic-calendar.json.
 */
function buildSubjectTimelines(timetable, academicCalendar = null) {
  // If an external academic calendar is provided in the future, parse it here.
  // For now, we process the embedded 'timeline' overrides or fallback to global.

  const timelines = timetable.subjects.map(s => {
    // All quiz-applicable subjects must have a subject-specific timeline in timetable.json.
    // Lab subjects without quiz milestones are still allowed to have partial timelines.
    if (s.timeline) {
      return {
        subjectCode: s.code,
        commencementDate: s.timeline.commencementDate || timetable.start_date,
        milestones: s.timeline.milestones ? [...s.timeline.milestones] : []
      };
    }

    // Subjects with no timeline at all (e.g., bare lab subjects with no milestones):
    // return an empty-milestone timeline so the engine can still compute attendance windows.
    return {
      subjectCode: s.code,
      commencementDate: timetable.start_date,
      milestones: []
    };
  });

  // Inject logical FIRST_LECTURE milestone at commencement
  timelines.forEach(tl => {
    tl.milestones.unshift({
      milestoneId: 'm0',
      type: 'FIRST_LECTURE',
      date: tl.commencementDate,
      metadata: {}
    });
  });

  return timelines;
}

async function bootstrap() {
  console.log("[app.js] bootstrap called");
  try {
    await initTimetable();
    console.log("[app.js] Timetable initialized");

    const timetable = getTimetable();
    
    // Bridge: Initialize Calendar Engine dynamically
    const timelines = buildSubjectTimelines(timetable);

    initCalendarEngine({
      calendarId: 'default',
      semesterId: 'current',
      semesterStart: timetable.start_date,
      semesterEnd: timetable.end_date || '2030-12-31',
      defaultWeekends: [0, 6], // Sunday, Saturday
      events: [],
      subjectTimelines: timelines,
      policies: timetable.policies || {}
    });
    console.log("[app.js] Calendar Engine initialized");

    syncRuntimeEvents(AppState.academicEvents);
    console.log("[app.js] Runtime Academic Events synced");

    updateThemeBtn('dark');
  } catch (e) {
    console.error("[app.js] bootstrap initialization error:", e);
  }

  console.log("[app.js] Setting up auth state listener");
  auth.onAuthStateChanged(async (user) => {
    console.log("[app.js] Auth state changed, user:", user ? user.uid : "null");
    if (user) {
      document.getElementById('authContainer').style.display = 'none';
      // 1. Local-first hydration
      initLocalState(user.uid);
      console.log("[app.js] Local state loaded");

      // 2. Initial Render
      applyTheme(AppState.settings.theme || 'dark');
      document.getElementById('appShell').style.display = 'block';
      document.getElementById('bottomNav').style.display = 'flex';
      document.getElementById('fabMarkAttendance').style.display = 'flex';
      updateProfileUI();
      renderDateNavigator();
      
      document.body.classList.add('view-dashboard');
      document.querySelectorAll('.view-section').forEach(section => {
        section.style.display = section.id === 'dashboardView' ? 'block' : 'none';
      });
      recalculateAndRender();
      
      // 3. Cloud Sync (Background)
      try {
        const stateChanged = await fetchCloudStates();
        console.log("[app.js] Cloud states fetched");
        if (stateChanged) {
          // Re-sync Calendar Engine runtime events from the freshly hydrated AppState.
          // fetchCloudStates may have merged new academicEvents from Firestore.
          syncRuntimeEvents(AppState.academicEvents);
          applyTheme(AppState.settings.theme || 'dark');
          console.log("[PROFILE 4] Before Render:", AppState.profile);
          updateProfileUI();
          recalculateAndRender();
          console.log("[app.js] UI updated with merged cloud data");
        }
      } catch (e) {
        console.error("[app.js] fetchCloudStates failed:", e);
      }


      try {
        checkProfileRecovery();
      } catch (e) {
        console.error("[app.js] checkProfileRecovery failed:", e);
      }

      try {
        checkMigration();
      } catch (e) {
        console.error("[app.js] checkMigration failed:", e);
      }
    } else {
      document.getElementById('authContainer').style.display = 'block';
      document.getElementById('appShell').style.display = 'none';
      document.getElementById('bottomNav').style.display = 'none';
      document.getElementById('fabMarkAttendance').style.display = 'none';
    }
  });
}

/* ─── View Switching (Mobile Bottom Nav) ───────────────────────────── */
let currentView = 'dashboard';

function switchView(viewName) {
  if (viewName === currentView) return;
  currentView = viewName;

  // Update body class for CSS targeting
  document.body.classList.remove('view-dashboard', 'view-subjects', 'view-history', 'view-profile');
  document.body.classList.add(`view-${viewName}`);

  // Update nav tabs
  document.querySelectorAll('.nav-tab').forEach(tab => {
    const isActive = tab.getAttribute('data-view') === viewName;
    tab.classList.toggle('active', isActive);
    tab.setAttribute('aria-selected', String(isActive));
  });

  // Update view sections
  document.querySelectorAll('.view-section').forEach(section => {
    section.style.display = section.id === `${viewName}View` ? 'block' : 'none';
  });

  // Scroll to top on view change
  window.scrollTo({ top: 0, behavior: 'smooth' });

  console.log(`[app.js] Switched to view: ${viewName}`);
}

/* ─── Bottom Sheet Open/Close ─────────────────────────────────────── */
function openBottomSheet() {
  const sheet = document.getElementById('bottomSheetDateNav');
  const overlay = document.getElementById('bottomSheetOverlay');
  if (sheet) {
    renderBottomSheetDateNav();
    sheet.style.display = 'block';
  }
  if (overlay) overlay.style.display = 'block';
  document.body.style.overflow = 'hidden';
}

function closeBottomSheet() {
  const sheet = document.getElementById('bottomSheetDateNav');
  const overlay = document.getElementById('bottomSheetOverlay');
  if (sheet) sheet.style.display = 'none';
  if (overlay) overlay.style.display = 'none';
  document.body.style.overflow = '';
}

/* ─── FAB Click ───────────────────────────────────────────────────── */
function handleFabClick() {
  switchView('dashboard');
  // Scroll to today's classes
  const el = document.getElementById('todayClassesCard');
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ─── Profile Theme Toggle ────────────────────────────────────────── */
function applyTheme(theme) {
  const html = document.documentElement;
  html.setAttribute('data-theme', theme);
  UI.updateThemeBtn(theme);
  const label = document.getElementById('profileThemeLabel');
  if (label) label.textContent = theme === 'dark' ? 'Dark Mode' : 'Light Mode';
  
  if (AppState.settings.theme !== theme) {
    AppState.settings.theme = theme;
    triggerCloudSync();
  }
}

function toggleProfileTheme() {
  const html = document.documentElement;
  const theme = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  applyTheme(theme);
}

function initDOMBindings() {
  console.log("[app.js] initDOMBindings called");
  const bindClick = (id, fn) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('click', fn);
      console.log(`[app.js] Successfully bound click to #${id}`);
    } else {
      console.error(`[app.js] Failed to bind click: element #${id} not found`);
    }
  };

  bindClick('btnLogin', handleAppLogin);
  bindClick('btnSignup', handleAppSignup);
  bindClick('linkToSignup', toggleAuthView);
  bindClick('linkToLogin', toggleAuthView);
  bindClick('btnMigrationDiscard', handleMigrationDiscard);
  bindClick('btnMigrationImport', handleMigrationImport);
  bindClick('btnLogout', handleAppLogout);

  bindClick('themeToggle', () => {
    console.log("[app.js] themeToggle clicked");
    const html = document.documentElement;
    const theme = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    applyTheme(theme);
  });

  bindClick('resetBtn', () => {
    console.log("[app.js] resetBtn clicked");
    if (confirm('Reset all attendance tracking data? This cannot be undone.')) {
      import('./storage.js').then(({ clearStates }) => {
        clearStates();
        UI.recalculateAndRender();
      }).catch(e => console.error(e));
    }
  });

  bindClick('historyToggle', () => {
    console.log("[app.js] historyToggle clicked");
    const content = document.getElementById('historyContent');
    const arrow   = document.getElementById('historyArrow');
    if (!content || !arrow) return;
    const isOpen = content.style.display !== 'none';
    content.style.display = isOpen ? 'none' : 'block';
    arrow.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(180deg)';
    document.getElementById('historyToggle').setAttribute('aria-expanded', String(!isOpen));
  });

  // ─── Bottom Nav ────────────────────────────────────────────────
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const view = tab.getAttribute('data-view');
      if (view) switchView(view);
    });
  });

  // ─── Mobile Date Trigger → Bottom Sheet ────────────────────────
  bindClick('mobileDateTrigger', openBottomSheet);

  // ─── Bottom Sheet Close ─────────────────────────────────────────
  bindClick('bottomSheetClose', closeBottomSheet);
  bindClick('bottomSheetOverlay', closeBottomSheet);

  // Close bottom sheet on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const sheet = document.getElementById('bottomSheetDateNav');
      if (sheet && sheet.style.display !== 'none') closeBottomSheet();
    }
  });

  // ─── FAB ────────────────────────────────────────────────────────
  bindClick('fabMarkAttendance', handleFabClick);

  // ─── Profile Actions ────────────────────────────────────────────
  bindClick('profileThemeToggle', toggleProfileTheme);
  bindClick('toolAcademicEvents', () => {
    switchView('events');
    renderAcademicEvents();
  });
  
  // ─── Academic Events Actions ─────────────────────────────────────────
  bindClick('btnNewEvent', () => {
    openEventForm();
  });
  
  bindClick('eventFormClose', () => {
    document.getElementById('eventFormOverlay').style.display = 'none';
    document.getElementById('eventFormSheet').style.display = 'none';
  });
  
  bindClick('btnEventCancel', () => {
    document.getElementById('eventFormOverlay').style.display = 'none';
    document.getElementById('eventFormSheet').style.display = 'none';
  });

  document.getElementById('academicEventForm')?.addEventListener('submit', (e) => {
    e.preventDefault();
    handleEventFormSubmit();
  });
  
  document.querySelectorAll('.events-filter-bar .tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.events-filter-bar .tab-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      renderAcademicEvents();
    });
  });

  bindClick('profileResetBtn', () => {
    console.log("[app.js] profileResetBtn clicked");
    if (confirm('Reset all attendance tracking data? This cannot be undone.')) {
      import('./storage.js').then(({ clearStates }) => {
        clearStates();
        UI.recalculateAndRender();
      }).catch(e => console.error(e));
    }
  });
  bindClick('profileLogoutBtn', handleAppLogout);

  bindClick('btnRecoverySignOut', handleAppLogout);
  bindClick('btnRecoverySave', () => {
    const errDiv = document.getElementById('recoveryError');
    errDiv.style.display = 'none';
    const nameVal = document.getElementById('recoveryName').value;
    const rollVal = document.getElementById('recoveryRoll').value;
    
    const res = saveProfile({ name: nameVal, rollNumber: rollVal });
    if (res.success) {
      document.getElementById('profileRecoveryModal').style.display = 'none';
    } else {
      errDiv.textContent = res.error;
      errDiv.style.display = 'block';
    }
  });

  initFeedbackSystem();
  initPWA();

  document.addEventListener('click', (e) => {
    const target = e.target.closest('[data-action]');
    if (!target) return;

    const action = target.getAttribute('data-action');
    console.log("[app.js] Global click delegate fired for action:", action);
    if (action === 'switchQuiz') {
      const quizId = parseInt(target.getAttribute('data-quiz'), 10);
      UI.switchQuiz(quizId, target);
    } else if (action === 'logLab') {
      const sCode = target.getAttribute('data-s');
      const expNo = target.getAttribute('data-exp');
      const date = prompt('Enter date conducted for Experiment ' + expNo + ' (YYYY-MM-DD):', UI.getTodayString());
      if (date) {
        UI.logExperiment(sCode, expNo, date);
      }
    } else if (action === 'toggleLabSignature') {
      const sCode = target.getAttribute('data-s');
      const expNo = target.getAttribute('data-exp');
      UI.toggleLabSignature(sCode, expNo);
    } else if (action === 'logAttendance') {
      const dateStr = target.getAttribute('data-date');
      const sCode = target.getAttribute('data-s');
      const type = target.getAttribute('data-t');
      const state = target.getAttribute('data-state');
      UI.logAttendance(dateStr, sCode, type, state);
    } else if (action === 'toggleEvent') {
      const id = target.getAttribute('data-id');
      const date = target.getAttribute('data-date');
      const active = target.getAttribute('data-active') === 'true';
      toggleAcademicEvent(id, date, !active);
    } else if (action === 'deleteEvent') {
      if (confirm('Are you sure you want to delete this event?')) {
        const id = target.getAttribute('data-id');
        const date = target.getAttribute('data-date');
        archiveAcademicEventController(id, date);
      }
    } else if (action === 'editEvent') {
      const id = target.getAttribute('data-id');
      const date = target.getAttribute('data-date');
      openEventForm(id, date);
    }
  });
  console.log("[app.js] Global event delegation set up");

  // Keyboard navigation for quiz tabs
  document.addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const tabsWrap = document.querySelector('.tabs-wrap');
    if (!tabsWrap || !tabsWrap.contains(document.activeElement)) return;
    const tabs = [...document.querySelectorAll('#quizTabs .tab-btn')];
    const current = tabs.indexOf(document.activeElement);
    if (current < 0) return;
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1
      : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    event.preventDefault();
    tabs[next].focus();
    UI.switchQuiz(next, tabs[next]);
  });

}

// ─── Event Form Logic ──────────────────────────────────────────
let currentEditOriginalDate = null;

function populateEventFormSelects() {
  const typeSelect = document.getElementById('eventType');
  const subjectSelect = document.getElementById('eventSubject');

  if (typeSelect.options.length === 0) {
    typeSelect.innerHTML = '<option value="">Select Type...</option>' + 
      Object.keys(AcademicEventRegistry).map(key => 
        `<option value="${key}">${AcademicEventRegistry[key].displayName}</option>`
      ).join('');
      
    typeSelect.addEventListener('change', () => {
      const type = typeSelect.value;
      const schema = AcademicEventRegistry[type];
      const subjCont = document.getElementById('eventSubjectContainer');
      const classCont = document.getElementById('eventClassTypeContainer');
      const classSelect = document.getElementById('eventClassType');
      
      if (schema) {
        subjCont.style.display = schema.requiresSubject ? 'block' : 'none';
        classCont.style.display = schema.requiresClassType ? 'block' : 'none';
        if (schema.requiresSubject) subjectSelect.required = true;
        else { subjectSelect.required = false; subjectSelect.value = ''; }
        
        if (schema.requiresClassType) {
          classSelect.required = true;
          classSelect.innerHTML = schema.allowedClassTypes.map(c => {
             const labels = { 'L': 'Lecture (L)', 'T': 'Tutorial (T)', 'P1': 'Practical (P1)', 'P2': 'Practical (P2)' };
             return `<option value="${c}">${labels[c] || c}</option>`;
          }).join('');
        } else {
          classSelect.required = false;
          classSelect.value = '';
        }
      }
    });
  }

  // Populate subjects dynamically from timetable
  import('./utils.js').then(({ getTimetable }) => {
    const timetable = getTimetable();
    subjectSelect.innerHTML = '<option value="">Select Subject...</option>' + 
      timetable.subjects.map(s => `<option value="${s.code}">${s.code} - ${s.name}</option>`).join('');
  });
}

function openEventForm(id = null, date = null) {
  populateEventFormSelects();
  
  const form = document.getElementById('academicEventForm');
  form.reset();
  document.getElementById('eventSubjectContainer').style.display = 'none';
  document.getElementById('eventClassTypeContainer').style.display = 'none';
  
  if (id && date) {
    const event = AppState.academicEvents[date]?.find(e => e.id === id);
    if (event) {
      document.getElementById('eventFormTitle').textContent = 'Edit Event';
      document.getElementById('eventFormId').value = event.id;
      document.getElementById('eventType').value = event.eventType;
      document.getElementById('eventType').dispatchEvent(new Event('change')); // trigger display logic
      
      document.getElementById('eventDate').value = event.effectiveDate;
      if (event.subjectCode) document.getElementById('eventSubject').value = event.subjectCode;
      if (event.classType) document.getElementById('eventClassType').value = event.classType;
      
      currentEditOriginalDate = date;
    }
  } else {
    document.getElementById('eventFormTitle').textContent = 'New Event';
    document.getElementById('eventFormId').value = '';
    currentEditOriginalDate = null;
    
    // Set default date to today
    import('./ui.js').then(({ getTodayString }) => {
      document.getElementById('eventDate').value = getTodayString();
    });
  }
  
  document.getElementById('eventFormOverlay').style.display = 'block';
  document.getElementById('eventFormSheet').style.display = 'block';
}

window.openEventForm = openEventForm; // for index.html calls or global access if needed

function handleEventFormSubmit() {
  const id = document.getElementById('eventFormId').value;
  const eventType = document.getElementById('eventType').value;
  const effectiveDate = document.getElementById('eventDate').value;
  
  const schema = AcademicEventRegistry[eventType];
  const subjectCode = schema.requiresSubject ? document.getElementById('eventSubject').value : null;
  const classType = schema.requiresClassType ? document.getElementById('eventClassType').value : null;
  
  const rawEvent = { eventType, effectiveDate, subjectCode, classType };
  
  let res;
  if (id) {
    rawEvent.id = id;
    const originalEvent = AppState.academicEvents[currentEditOriginalDate]?.find(e => e.id === id);
    if (originalEvent) {
      rawEvent.history = originalEvent.history;
      rawEvent.version = (originalEvent.version || 1) + 1;
      rawEvent.active = originalEvent.active;
      rawEvent.archived = originalEvent.archived;
    }
    res = updateAcademicEvent(rawEvent, currentEditOriginalDate);
  } else {
    res = createAcademicEvent(rawEvent);
  }
  
  if (res.success) {
    document.getElementById('eventFormOverlay').style.display = 'none';
    document.getElementById('eventFormSheet').style.display = 'none';
  } else {
    alert('Error saving event: ' + res.error);
  }
}

let hasInit = false;
function doInit() {
  if (hasInit) return;
  hasInit = true;
  console.log("[app.js] DOM is ready, calling initDOMBindings");
  initDOMBindings();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', doInit);
} else {
  doInit();
}

bootstrap();
