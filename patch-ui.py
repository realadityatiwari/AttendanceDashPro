import re

file_path = 'js/ui.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update import
content = content.replace(
    "import { computeSubjectStats, calcForecastImpact, getAttendanceData, getSubjectStatus, pctColor, barColor, dimColor } from './attendance-engine.js';",
    "import { computeSubjectStats, computeOverallStats, calcForecastImpact, getAttendanceData, getSubjectStatus, pctColor, barColor, dimColor } from './attendance-engine.js';"
)

# 2. Update buildHeroCard
build_hero_card_old = """export function buildHeroCard(rows, label, quizDate) {
  const totalClasses         = rows.reduce((s, r) => s + r.totComb, 0);
  const totalSubj            = rows.length;
  const totalMustAtt         = rows.reduce((s, r) => s + r.optResult.addL + r.optResult.addT, 0);
  const totalSkips           = rows.reduce((s, r) => s + r.optResult.skipL_budget + r.optResult.skipT_budget, 0);
  const forecastVals         = rows.map(r => r.forecastAvgPct).filter(v => v !== null);
  const overallForecastAvg   = forecastVals.length > 0
    ? forecastVals.reduce((a, b) => a + b, 0) / forecastVals.length
    : null;
  const overallStatus        = getSubjectStatus(overallForecastAvg);
  const dateStr              = quizDate.toLocaleDateString('en-US', {day:'numeric', month:'short', year:'numeric'});
  const valColor             = overallForecastAvg !== null ? pctColor(overallForecastAvg) : 'var(--text3)';
  const valDisplay           = overallForecastAvg !== null ? overallForecastAvg.toFixed(1) + '%' : '—';"""

build_hero_card_new = """export function buildHeroCard(overallStats, label, quizDate) {
  const { totalMustAttend, totalSafeSkips, forecastOverallAttendance } = overallStats;
  const overallStatus        = getSubjectStatus(forecastOverallAttendance);
  const dateStr              = quizDate.toLocaleDateString('en-US', {day:'numeric', month:'short', year:'numeric'});
  const valColor             = forecastOverallAttendance !== null ? pctColor(forecastOverallAttendance) : 'var(--text3)';
  const valDisplay           = forecastOverallAttendance !== null ? forecastOverallAttendance.toFixed(1) + '%' : '—';"""

content = content.replace(build_hero_card_old, build_hero_card_new)

# In buildHeroCard return HTML, replace variables
content = content.replace("${totalMustAtt}", "${totalMustAttend}")

# 3. Update buildStatsRow
build_stats_row_old = """export function buildStatsRow(rows) {
  const totalClasses = rows.reduce((s, r) => s + r.totComb, 0);
  const totalSubj    = rows.length;
  const totalMustAtt = rows.reduce((s, r) => s + r.optResult.addL + r.optResult.addT, 0);
  const totalSkips   = rows.reduce((s, r) => s + r.optResult.skipL_budget + r.optResult.skipT_budget, 0);"""

build_stats_row_new = """export function buildStatsRow(overallStats) {
  const { totalClasses, totalSubjects, totalMustAttend, totalSafeSkips } = overallStats;"""

content = content.replace(build_stats_row_old, build_stats_row_new)
content = content.replace("${totalSubj}", "${totalSubjects}")
content = content.replace("${totalMustAtt}", "${totalMustAttend}")
content = content.replace("${totalSkips}", "${totalSafeSkips}")

# 4. Update renderPanel
render_panel_old = """export function renderPanel(quizIdx, liveData = getAttendanceData(getTimetable().quiz_dates[quizIdx].date), isMobile = false) {
  const {label, date: quizDate} = getTimetable().quiz_dates[quizIdx];

  // Compute all stats in ONE pass (single source of truth)
  const rows = getTimetable().subjects.map(({code, name, tag}) =>
    computeSubjectStats(code, name, tag, liveData[code])
  );"""

render_panel_new = """export function renderPanel(quizIdx, liveData = getAttendanceData(getTimetable().quiz_dates[quizIdx].date), isMobile = false, overallStats = null) {
  const {label, date: quizDate} = getTimetable().quiz_dates[quizIdx];

  // Compute all stats in ONE pass (single source of truth)
  const rows = getTimetable().subjects.map(({code, name, tag}) =>
    computeSubjectStats(code, name, tag, liveData[code])
  );
  if (!overallStats) {
    overallStats = computeOverallStats(rows);
  }"""

content = content.replace(render_panel_old, render_panel_new)

content = content.replace("const heroHTML  = buildHeroCard(rows, label, quizDate);", "const heroHTML  = buildHeroCard(overallStats, label, quizDate);")
content = content.replace("const statsHTML = buildStatsRow(rows);", "const statsHTML = buildStatsRow(overallStats);")

# 5. Update recalculateAndRender
recalculate_old = """    // Pre-compute rows for hero + stats
    const {label, date: quizDate} = getTimetable().quiz_dates[currentQuiz];
    const rows = getTimetable().subjects.map(({code, name, tag}) =>
      computeSubjectStats(code, name, tag, liveData[code])
    );
    const heroHTML  = buildHeroCard(rows, label, quizDate);
    const statsHTML = buildStatsRow(rows);"""

recalculate_new = """    // Pre-compute rows for hero + stats
    const {label, date: quizDate} = getTimetable().quiz_dates[currentQuiz];
    const rows = getTimetable().subjects.map(({code, name, tag}) =>
      computeSubjectStats(code, name, tag, liveData[code])
    );
    const overallStats = computeOverallStats(rows);
    const heroHTML  = buildHeroCard(overallStats, label, quizDate);
    const statsHTML = buildStatsRow(overallStats);"""

content = content.replace(recalculate_old, recalculate_new)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
