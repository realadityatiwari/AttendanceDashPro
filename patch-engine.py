import os

file_path = 'js/attendance-engine.js'
with open(file_path, 'a', encoding='utf-8') as f:
    f.write('''
/* ═══════════════════════════════════════════════════════════════════════
   OVERALL ATTENDANCE ENGINE
   Single source of truth for dashboard-wide statistics.
═══════════════════════════════════════════════════════════════════════ */
export function computeOverallStats(subjectStats) {
  let totalSubjects = 0;
  let totalClasses = 0;
  let totalCompleted = 0;
  let totalPending = 0;
  let totalAttended = 0;
  let totalMissed = 0;
  let totalMustAttend = 0;
  let totalSafeSkips = 0;

  for (const r of subjectStats) {
    totalSubjects++;
    totalClasses += r.totComb;
    totalCompleted += r.completedL + r.completedT;
    totalPending += r.pendingL + r.pendingT;
    totalAttended += r.attL_done + r.attT_done;
    totalMissed += r.missL_done + r.missT_done;
    totalMustAttend += r.optResult.addL + r.optResult.addT;
    totalSafeSkips += r.optResult.skipL_budget + r.optResult.skipT_budget;
  }

  const currentOverallAttendance = totalCompleted > 0 
    ? (totalAttended / totalCompleted) * 100 
    : null;

  const forecastOverallAttendance = totalClasses > 0 
    ? ((totalAttended + totalPending) / totalClasses) * 100 
    : null;

  return {
    totalSubjects,
    totalClasses,
    totalCompleted,
    totalPending,
    totalAttended,
    totalMissed,
    totalMustAttend,
    totalSafeSkips,
    currentOverallAttendance,
    forecastOverallAttendance
  };
}
''')
