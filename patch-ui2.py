import re

file_path = 'js/ui.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace recalculateAndRender
recalculate_old = """export function recalculateAndRender() {
  const targetDate  = getActiveDate();
  const liveData    = getAttendanceData(getTimetable().quiz_dates[currentQuiz].date, getEffectiveStates());
  const isMobile    = window.innerWidth < 768;

  renderTodayClasses(targetDate, liveData);
  renderHistoryLog();
  // Also render into mobile history list
  const mobileList = document.getElementById('mobileHistoryList');
  if (mobileList) {
    const desktopList = document.getElementById('historyList');
    if (desktopList) {
      mobileList.innerHTML = desktopList.innerHTML;
    }
  }

  // Render panels (mobile version skips hero/stats/table)
  document.getElementById('panels').innerHTML = renderPanel(currentQuiz, liveData, isMobile);

  if (isMobile) {
    // Pre-compute rows for hero + stats
    const {label, date: quizDate} = getTimetable().quiz_dates[currentQuiz];
    const rows = getTimetable().subjects.map(({code, name, tag}) =>
      computeSubjectStats(code, name, tag, liveData[code])
    );
    const overallStats = computeOverallStats(rows);
    const heroHTML  = buildHeroCard(overallStats, label, quizDate);
    const statsHTML = buildStatsRow(overallStats);

    // Insert hero + stats into mobile container (positioned before Today's Classes in HTML)
    const heroContainer = document.getElementById('mobileHeroContainer');
    if (heroContainer) {
      heroContainer.innerHTML = heroHTML + statsHTML;
    }

    // Setup accordion + formula toggle (only on first run per render)
    setupMobileAccordion();
    initFormulaToggle();
  }

  updateModeBadge();
  updateViewingLabel();

}"""

recalculate_new = """export function recalculateAndRender() {
  const targetDate  = getActiveDate();
  const liveData    = getAttendanceData(getTimetable().quiz_dates[currentQuiz].date, getEffectiveStates());
  const isMobile    = window.innerWidth < 768;

  renderTodayClasses(targetDate, liveData);
  renderHistoryLog();
  // Also render into mobile history list
  const mobileList = document.getElementById('mobileHistoryList');
  if (mobileList) {
    const desktopList = document.getElementById('historyList');
    if (desktopList) {
      mobileList.innerHTML = desktopList.innerHTML;
    }
  }

  // PRE-COMPUTE subject rows and overall stats ONCE here
  const {label, date: quizDate} = getTimetable().quiz_dates[currentQuiz];
  const rows = getTimetable().subjects.map(({code, name, tag}) =>
    computeSubjectStats(code, name, tag, liveData[code])
  );
  const overallStats = computeOverallStats(rows);

  // Render panels (mobile version skips hero/stats/table)
  document.getElementById('panels').innerHTML = renderPanel(rows, overallStats, label, quizDate, isMobile);

  if (isMobile) {
    const heroHTML  = buildHeroCard(overallStats, label, quizDate);
    const statsHTML = buildStatsRow(overallStats);

    // Insert hero + stats into mobile container (positioned before Today's Classes in HTML)
    const heroContainer = document.getElementById('mobileHeroContainer');
    if (heroContainer) {
      heroContainer.innerHTML = heroHTML + statsHTML;
    }

    // Setup accordion + formula toggle (only on first run per render)
    setupMobileAccordion();
    initFormulaToggle();
  }

  updateModeBadge();
  updateViewingLabel();

}"""

if recalculate_old in content:
    content = content.replace(recalculate_old, recalculate_new)
else:
    print("Could not find recalculateAndRender string")

# Replace renderPanel
render_panel_old = """export function renderPanel(quizIdx, liveData = getAttendanceData(getTimetable().quiz_dates[quizIdx].date), isMobile = false, overallStats = null) {
  const {label, date: quizDate} = getTimetable().quiz_dates[quizIdx];

  // Compute all stats in ONE pass (single source of truth)
  const rows = getTimetable().subjects.map(({code, name, tag}) =>
    computeSubjectStats(code, name, tag, liveData[code])
  );
  if (!overallStats) {
    overallStats = computeOverallStats(rows);
  }"""

render_panel_new = """export function renderPanel(rows, overallStats, label, quizDate, isMobile = false) {"""

if render_panel_old in content:
    content = content.replace(render_panel_old, render_panel_new)
else:
    print("Could not find renderPanel string")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
