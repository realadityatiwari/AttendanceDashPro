import { computeOverallStats } from './js/attendance-engine.js';

const mockSubjectStats = [
  {
    totComb: 20,
    completedL: 10, completedT: 5,
    pendingL: 2, pendingT: 1,
    attL_done: 8, attT_done: 4,
    missL_done: 2, missT_done: 1,
    optResult: { addL: 2, addT: 1, skipL_budget: 3, skipT_budget: 1 }
  },
  {
    totComb: 10,
    completedL: 5, completedT: 0,
    pendingL: 5, pendingT: 0,
    attL_done: 4, attT_done: 0,
    missL_done: 1, missT_done: 0,
    optResult: { addL: 4, addT: 0, skipL_budget: 1, skipT_budget: 0 }
  }
];

const result = computeOverallStats(mockSubjectStats);
console.log(result);
