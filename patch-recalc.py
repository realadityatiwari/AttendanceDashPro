import re

file_path = 'js/ui.js'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

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

# Actually, the string in the file lacks `const overallStats = computeOverallStats(rows);` because it was replaced previously but not exactly. Let's look at lines 862-868 from the file:
#     // Pre-compute rows for hero + stats
#     const {label, date: quizDate} = getTimetable().quiz_dates[currentQuiz];
#     const rows = getTimetable().subjects.map(({code, name, tag}) =>
#       computeSubjectStats(code, name, tag, liveData[code])
#     );
#     const heroHTML  = buildHeroCard(overallStats, label, quizDate);
#     const statsHTML = buildStatsRow(overallStats);

# I'll just use regex to replace the whole function

new_func = """export function recalculateAndRender() {
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

  // Render panels
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

content = re.sub(r'export function recalculateAndRender\(\) \{.*?\n\}', new_func, content, flags=re.DOTALL)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
