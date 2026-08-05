import { optimizeLive, optimize, calcAvgPct, OptimizationResult } from './js/attendance-engine.js';

let allPassed = true;
function assert(condition, message) {
  if (!condition) {
    console.error(`FAIL: ${message}`);
    allPassed = false;
  } else {
    console.log(`PASS: ${message}`);
  }
}

console.log("=== Testing Optimization Engine ===");
let res75 = optimizeLive(40, 10, 20, 5, 5, 1, 15, 4, 75);
assert(res75.reachable === true, "Should be reachable for 75%");
assert(res75.targetPercentage === 75, "Target should be 75");
assert(res75.lectureDeficit !== undefined, "Has lecture deficit");

let res70 = optimizeLive(40, 10, 20, 5, 5, 1, 15, 4, 70);
assert(res70.reachable === true, "Should be reachable for 70%");
assert(res70.targetPercentage === 70, "Target should be 70");

let resInf = optimizeLive(40, 0, 10, 20, 0, 0, 10, 0, 75); 
assert(resInf.reachable === false, "Should be infeasible");
assert(resInf.lectureDeficit === 10, "Should say must attend all 10");

if (allPassed) {
  console.log("All tests passed!");
  process.exit(0);
} else {
  console.error("Some tests failed!");
  process.exit(1);
}
