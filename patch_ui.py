import sys
content = open('c:/Coding/AttendanceDashPro/js/ui.js', 'r', encoding='utf-8').read()

# 1. Imports
imp_loc = content.find("import { computeQuizDashboard } from './quiz-engine.js';")
imp_insert = "import { computeLaboratoryDashboard } from './laboratory-engine.js';\n"
content = content[:imp_loc] + imp_insert + content[imp_loc:]

# 2. Add buildLaboratoryDashboardSection before buildTableRow
tbl_row_loc = content.find("export function buildTableRow(r) {")
lab_ui_code = """/* ═══════════════════════════════════════════════════════════════════════
   LABORATORY DASHBOARD UI
   Pure rendering layer — consumes LaboratoryDashboardModel. No calculations.
═══════════════════════════════════════════════════════════════════════ */

export function buildLaboratorySubjectCard(item) {
  const {
    subject,
    completedExperiments,
    remainingExperiments,
    currentExperiment,
    attendancePercentage,
    progressPercentage,
    activeMilestones,
    nextMilestone
  } = item;
  
  const pColor = pctColor(progressPercentage);
  const pw = Math.min(100, Math.max(0, progressPercentage)).toFixed(1);
  
  const aColor = pctColor(attendancePercentage);
  const aw = Math.min(100, Math.max(0, attendancePercentage)).toFixed(1);

  // Milestone line
  let milestoneHTML = '';
  if (nextMilestone) {
    milestoneHTML = `
      <div class="lab-milestone" style="margin-top:12px;padding:8px;background:var(--bg2);border-radius:6px;font-size:12px;color:var(--text2);">
        <span style="color:var(--accent);">Next Milestone:</span> ${nextMilestone.label} (Need ${nextMilestone.remainingRequired} more)
      </div>`;
  } else if (activeMilestones.length > 0) {
    const lastMs = activeMilestones[activeMilestones.length - 1];
    milestoneHTML = `
      <div class="lab-milestone" style="margin-top:12px;padding:8px;background:var(--bg2);border-radius:6px;font-size:12px;color:var(--green);">
        <span style="color:var(--green);">✓ Reached:</span> ${lastMs.label}
      </div>`;
  }

  return `
    <div class="quiz-subj-card">
      <div class="quiz-subj-header">
        <span class="subj-card-code">${subject.code}</span>
        <span class="status-badge active-attended">Exp ${currentExperiment}</span>
      </div>
      <div class="quiz-subj-name">${subject.name}</div>
      <div class="quiz-subj-stats" style="margin-top: 12px;">
        <div class="quiz-pct-row">
          <span class="quiz-pct-label">Progress</span>
          <div class="quiz-pct-right">
            <span class="quiz-pct-val" style="color:${pColor}">${completedExperiments} / ${completedExperiments + remainingExperiments}</span>
            <div class="quiz-pct-track"><div class="quiz-pct-bar" style="width:${pw}%;background:${pColor}"></div></div>
          </div>
        </div>
        <div class="quiz-pct-row">
          <span class="quiz-pct-label">Attendance</span>
          <div class="quiz-pct-right">
            <span class="quiz-pct-val" style="color:${aColor}">${attendancePercentage.toFixed(1)}%</span>
            <div class="quiz-pct-track"><div class="quiz-pct-bar" style="width:${aw}%;background:${aColor}"></div></div>
          </div>
        </div>
      </div>
      ${milestoneHTML}
    </div>`;
}

export function buildLaboratorySummaryCard(summary) {
  return `
    <div class="quiz-summary-card">
      <div class="quiz-summary-header">
        <h2 class="quiz-summary-title">Laboratory Tracker</h2>
        <span class="quiz-summary-sub">Track practical sessions & signatures</span>
      </div>
      <div class="quiz-summary-stats">
        <div class="quiz-summary-stat">
          <div class="quiz-summary-val" style="color:var(--green)">${summary.totalCompletedExperiments}</div>
          <div class="quiz-summary-label">Completed Exps</div>
        </div>
        <div class="quiz-summary-stat">
          <div class="quiz-summary-val" style="color:var(--accent)">${summary.milestonesReached}</div>
          <div class="quiz-summary-label">Milestones Reached</div>
        </div>
        <div class="quiz-summary-stat">
          <div class="quiz-summary-val" style="color:var(--text3)">${summary.totalLabSubjects}</div>
          <div class="quiz-summary-label">Lab Subjects</div>
        </div>
      </div>
    </div>`;
}

export function buildLaboratoryDashboardSection(labModel) {
  if (!labModel || labModel.subjects.length === 0) return '';
  const summaryHTML  = buildLaboratorySummaryCard(labModel.summary);
  const subjectsHTML = labModel.subjects.map(buildLaboratorySubjectCard).join('');
  return `
    <section class="quiz-dashboard-section" aria-label="Laboratory Dashboard">
      ${summaryHTML}
      <div class="quiz-subj-grid">${subjectsHTML}</div>
    </section>`;
}

"""
content = content[:tbl_row_loc] + lab_ui_code + content[tbl_row_loc:]

# 3. renderPanel - Add labModel
content = content.replace('export function renderPanel(rows, overallStats, erpStats, forecastStats, label, quizDate, quizModel, isMobile = false)', 'export function renderPanel(rows, overallStats, erpStats, forecastStats, label, quizDate, quizModel, labModel, isMobile = false)')

# Add to mobile
mob_insert_loc = content.find('const heroHTML      = buildHeroCard(')
content = content[:mob_insert_loc] + 'const labSectionHTML = labModel ? buildLaboratoryDashboardSection(labModel) : "";\n    ' + content[mob_insert_loc:]

# Add to desktop
desk_quiz = content.find("const quizSectionHTML = quizModel ? buildQuizDashboardSection(quizModel) : '';")
content = content[:desk_quiz] + "const quizSectionHTML = quizModel ? buildQuizDashboardSection(quizModel) : '';\n  const labSectionHTML = labModel ? buildLaboratoryDashboardSection(labModel) : '';\n" + content[desk_quiz+len("const quizSectionHTML = quizModel ? buildQuizDashboardSection(quizModel) : '';"):]

# Insert variable into desktop template
desk_html = content.find('${quizSectionHTML}')
content = content[:desk_html + 17] + '\n    ${labSectionHTML}' + content[desk_html + 17:]

# Insert variable into mobile template
content = content.replace('heroContainer.innerHTML = heroHTML + statsHTML + quizSectionHTML;', 'heroContainer.innerHTML = heroHTML + statsHTML + quizSectionHTML + (labModel ? buildLaboratoryDashboardSection(labModel) : "");')

# 4. recalculateAndRender
render_loc = content.find('// Render panels')
call_code = """// Laboratory Dashboard Model
  const labModel = computeLaboratoryDashboard(AppState.laboratory || {}, getEffectiveStates(), rows, getTimetable());

  """
content = content[:render_loc] + call_code + content[render_loc:]

content = content.replace('renderPanel(rows, overallStats, erpStats, forecastStats, label, quizDate, quizModel, isMobile)', 'renderPanel(rows, overallStats, erpStats, forecastStats, label, quizDate, quizModel, labModel, isMobile)')

with open('c:/Coding/AttendanceDashPro/js/ui.js', 'w', encoding='utf-8') as f:
    f.write(content)
