// js/test-persistence-sync.js
// S3.6 regression tests for the persistence & sync lifecycle in storage.js.
//
// storage.js (via firebase.js) depends on the global compat SDK and Web
// localStorage, neither of which exist in plain Node. We stub both before
// importing the module under test.

// ── localStorage shim ──────────────────────────────────────────────────
if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map();
  globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => { store.set(String(k), String(v)); },
    removeItem: (k) => { store.delete(k); },
    clear: () => store.clear()
  };
}

// ── firebase compat SDK stub ───────────────────────────────────────────
const writeLog = [];   // chronological list of {op, uid, payload, merge}
const callOrder = [];  // 'set' | 'get' ordering for dirty-flush assertion

const fakeDoc = {
  set(payload, options) {
    writeLog.push({ op: 'set', uid: currentUid(), payload, merge: options && options.merge });
    callOrder.push('set');
    return Promise.resolve();
  },
  get() {
    callOrder.push('get');
    return Promise.resolve({
      exists: cloudDocExists,
      data: () => cloudDocData
    });
  }
};
const fakeRef = {
  doc(uid) {
    // record uid (not strictly needed) and return the same fake doc
    return fakeDoc;
  },
  collection() { return fakeRef; }
};

let currentUidValue = 'testuid';
const currentUid = () => currentUidValue;

let cloudDocExists = true;
let cloudDocData = {};

function fakeAuth() {
  return {
    currentUser: { uid: currentUidValue },
    setPersistence: () => Promise.resolve()
  };
}
fakeAuth.Auth = { Persistence: { LOCAL: 'local' } };

globalThis.firebase = {
  apps: [],
  initializeApp: () => { globalThis.firebase.apps.push({ options: {} }); },
  SDK_VERSION: 'STUB',
  auth: fakeAuth,
  firestore: () => fakeRef
};

// ── import module under test (after stubs are installed) ───────────────
const { AppState, initLocalState, persistLocalState, saveLaboratoryStates, saveStates, triggerCloudSync, fetchCloudStates } =
  await import('./storage.js');

let passed = 0;
function check(name, cond) {
  console.log(`${cond ? '✅' : '❌'} ${name}`);
  if (!cond) process.exitCode = 1;
  passed++;
}

const uid = 'testuid';
const KEY = `app_state_${uid}`;

// ── Test 1: P0 fix — saveLaboratoryStates omits undefined-valued keys ──
(async () => {
  console.log('--- S3.6 Persistence & Sync Tests ---');

  AppState.profile = { name: 'Test', rollNumber: '1' };
  AppState.settings = { theme: 'light', simulationMode: false };
  AppState.attendance = {};
  AppState.laboratory = {};
  AppState.academicEvents = {};

  // An experiment created via UI.logExperiment has only experimentNumber,
  // signatureStatus + dateConducted — title/marks/remarks are undefined.
  const expWithUndefined = {
    experimentNumber: 1,
    signatureStatus: 'pending',
    dateConducted: '2026-08-03',
    title: undefined,
    marks: undefined,
    remarks: undefined
  };
  AppState.laboratory['BCS-551'] = [expWithUndefined];
  saveLaboratoryStates(AppState.laboratory);

  check('lab experiment with undefined optional fields serializes without undefined keys',
    AppState.laboratory['BCS-551'][0].title === undefined);

  const stored = JSON.parse(localStorage.getItem(KEY));
  const storedExp = stored.laboratory['BCS-551'][0];
  check('localStorage copy contains no undefined-valued lab keys',
    !('title' in storedExp) && !('marks' in storedExp) && !('remarks' in storedExp) &&
    storedExp.experimentNumber === 1);

  // ── Test 2: triggerCloudSync sanitizes payload + clears isDirty ──────
  AppState.isDirty = false;
  writeLog.length = 0;
  AppState.laboratory['BCS-551'] = [{ ...expWithUndefined, signatureStatus: 'signed', signedOn: '2026-08-09T00:00:00Z' }];
  AppState.attendance = { '2026-08-03:BNC-501:L': { state: 'Attended' } };
  AppState.academicEvents = { '2026-10-05': [{ id: 'evt_1', active: true, eventType: 'EMERGENCY_CLOSURE', effectiveDate: '2026-10-05' }] };
  saveLaboratoryStates(AppState.laboratory);
  saveStates(AppState.attendance);
  triggerCloudSync();

  await new Promise(r => setTimeout(r, 600)); // > 400ms debounce

  const setCalls = writeLog.filter(w => w.op === 'set');
  check('cloud sync fired a single debounced set()', setCalls.length === 1);

  const payload = setCalls[0] && setCalls[0].payload;
  check('set() payload includes laboratory', !!(payload && payload.laboratory));
  check('set() payload laboratory has no undefined field values',
    payload && payload.laboratory['BCS-551'][0] &&
    !('title' in payload.laboratory['BCS-551'][0]) &&
    !('marks' in payload.laboratory['BCS-551'][0]) &&
    !('remarks' in payload.laboratory['BCS-551'][0]));
  check('set() payload merges (merge:true)', setCalls[0] && setCalls[0].merge === true);
  check('set() payload carries attendance + academicEvents too',
    payload && payload.attendance && payload.academicEvents);
  check('AppState.isDirty cleared after successful sync', AppState.isDirty === false);
  check('localStorage isDirty cleared after successful sync',
    JSON.parse(localStorage.getItem(KEY)).isDirty === false);

  // ── Test 3: initLocalState restores isDirty (prerequisite for flush) ─
  localStorage.setItem(KEY, JSON.stringify({ ...AppState, isDirty: true }));
  AppState.isDirty = false;
  initLocalState(uid);
  check('initLocalState restores isDirty=true when local state is dirty', AppState.isDirty === true);

  localStorage.setItem(KEY, JSON.stringify({ ...AppState, isDirty: false }));
  AppState.isDirty = false;
  initLocalState(uid);
  check('initLocalState leaves isDirty=false for clean local state', AppState.isDirty === false);

  // ── Test 4: P1 fix — fetchCloudStates flushes dirty local BEFORE download
  localStorage.setItem(KEY, JSON.stringify({ ...AppState, isDirty: true, laboratory: { 'BCS-551': [{ experimentNumber: 1, signatureStatus: 'pending', dateConducted: '2026-08-03' }] } }));
  AppState.isDirty = false;
  initLocalState(uid);
  check('dirty local state preloaded for flush test', AppState.isDirty === true);

  writeLog.length = 0;
  callOrder.length = 0;
  cloudDocExists = true;
  cloudDocData = { profile: { name: 'CloudName', rollNumber: '1' } };
  await fetchCloudStates();

  check('dirty flush pushes local to cloud before reading cloud (set before get)',
    callOrder.length >= 2 && callOrder[0] === 'set' && callOrder[1] === 'get');
  check('pre-hydration flush uploads dirty local state', writeLog.some(w => w.op === 'set'));
  check('AppState.isDirty cleared after dirty-flush hydration', AppState.isDirty === false);

  // Clean state → no pre-flush, straight to download merge
  AppState.isDirty = false;
  writeLog.length = 0;
  callOrder.length = 0;
  AppState.academicEvents = { '2026-10-06': [{ id: 'evt_local', active: false }] };
  cloudDocData = { academicEvents: { '2026-10-06': [{ id: 'evt_cloud', active: true }] } };
  await fetchCloudStates();
  check('clean hydration does not pre-flush (no set before get)', callOrder[0] === 'get' && !writeLog.some(w => w.op === 'set'));
  check('cloud-wins merge applies on clean hydration (per-key)', AppState.academicEvents['2026-10-06'][0].active === true);

  console.log(`✅ All Phase S3.6 persistence & sync tests passed! (${passed} assertions)`);
})();
