import { computeLaboratoryDashboard } from './js/laboratory-engine.js';

let failed = 0;
function assert(label, condition) {
  if (condition) {
    console.log(`✅ ${label}`);
  } else {
    console.error(`❌ ${label}`);
    failed++;
  }
}

// Minimal mock timetable for lab subject
const mockTimetable = {
  subjects: [
    { code: 'LAB-1', category: 'lab' }
  ]
};

const dateConducted = '2026-08-01';

// We mock the rawLabState to have 1 experiment for LAB-1
const rawLabState = {
  'LAB-1': [
    {
      experimentNumber: 1,
      dateConducted: dateConducted,
      signatureStatus: 'signed'
    }
  ]
};

// Test cases
function runTest(testName, attendanceDataMap, expectedStatus, expectedIsCompleted) {
  const result = computeLaboratoryDashboard(rawLabState, attendanceDataMap, [], mockTimetable);
  const lab = result.subjects[0];
  const exp = lab.experiments[0]; // the first experiment

  assert(testName + ` (Status: ${exp.attendanceStatus} == ${expectedStatus})`, exp.attendanceStatus === expectedStatus);
  assert(testName + ` (Completed: ${exp.isCompleted} == ${expectedIsCompleted})`, exp.isCompleted === expectedIsCompleted);
}

// 1. No P1/P2 record
runTest("1. No P1/P2 record", {}, null, false);

// 2. Only P1 = Attended
runTest("2. Only P1 = Attended", { [`${dateConducted}:LAB-1:P1`]: 'Attended' }, 'Attended', true);

// 3. Only P2 = Attended
runTest("3. Only P2 = Attended", { [`${dateConducted}:LAB-1:P2`]: 'Attended' }, 'Attended', true);

// 4. Only P1 = Missed
runTest("4. Only P1 = Missed", { [`${dateConducted}:LAB-1:P1`]: 'Missed' }, 'Missed', false);

// 5. Only P2 = Missed
runTest("5. Only P2 = Missed", { [`${dateConducted}:LAB-1:P2`]: 'Missed' }, 'Missed', false);

// 6. Both P1 and P2 present (One Attended, One Missed) -> Prioritizes Attended
runTest("6. Both P1 and P2 present (Mix)", { [`${dateConducted}:LAB-1:P1`]: 'Attended', [`${dateConducted}:LAB-1:P2`]: 'Missed' }, 'Attended', true);
runTest("6b. Both P1 and P2 present (Both Attended)", { [`${dateConducted}:LAB-1:P1`]: 'Attended', [`${dateConducted}:LAB-1:P2`]: 'Attended' }, 'Attended', true);
runTest("6c. Both P1 and P2 present (Both Missed)", { [`${dateConducted}:LAB-1:P1`]: 'Missed', [`${dateConducted}:LAB-1:P2`]: 'Missed' }, 'Missed', false);

// 7. Both P1/P2 absent (same as 1, tested above)

// 8. Existing literal P record
runTest("8. Existing literal P record", { [`${dateConducted}:LAB-1:P`]: 'Attended' }, 'Attended', true);

// 9. Existing lecture attendance unaffected (Should be ignored by lab lookup)
runTest("9. Existing lecture attendance unaffected", { [`${dateConducted}:LAB-1:L`]: 'Attended', [`${dateConducted}:LAB-1:P1`]: 'Missed' }, 'Missed', false);

// 10. Existing tutorial attendance unaffected
runTest("10. Existing tutorial attendance unaffected", { [`${dateConducted}:LAB-1:T`]: 'Attended' }, null, false);

if (failed === 0) {
  console.log("\nAll Laboratory Correctness Verification Tests Passed!");
} else {
  console.log(`\n${failed} Tests Failed.`);
}
