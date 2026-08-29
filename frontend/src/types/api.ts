export interface StudentProfile {
  id: string;
  // Authorization role (Phase 6.5): "STUDENT" or "ADMIN". Backend is
  // authoritative; this drives admin-control visibility only.
  role: string;
  display_name: string;
  roll_number: string | null;
  section_name: string | null;
  subsection_name?: string | null;
  elective_i?: string | null;
  elective_ii?: string | null;
  program?: string | null;
  semester_name?: string | null;
  academic_session?: string | null;
  semester_start?: string | null;
  semester_end?: string | null;
  first_quiz_date?: string | null;
}

// --- Phase 10D user preferences (GET/PUT /api/v1/student/preferences) ---
// Phase 11 wiring: `class_reminders` gates the CLASS_REMINDER notifications
// (bell icon / notification center). `auto_mark_present` and `week_starts_on`
// remain STORAGE/PREFERENCE DATA ONLY: no attendance is auto-marked and no
// calendar/analytics week calculation changes.
export type WeekStart = "SUNDAY" | "MONDAY";

export interface UserPreferences {
  class_reminders: boolean;
  auto_mark_present: boolean;
  week_starts_on: WeekStart;
  created_at?: string | null;
  updated_at?: string | null;
}

// PUT payload — full-object replacement; all three fields are required and
// user_id is never sent (the backend owns the identity from the JWT).
export interface UserPreferencesUpdate {
  class_reminders: boolean;
  auto_mark_present: boolean;
  week_starts_on: WeekStart;
}

export enum SubjectCategory {
  // Backend contract (app.models.enums.SubjectCategory): the API emits only
  // "theory" and "lab" — no other categories exist.
  THEORY = "theory",
  LAB = "lab",
}

export interface SubjectResponse {
  id: string;
  code: string;
  name: string;
  tag: string | null;
  /** Phase 23.5: the authoritative DB-backed catalog slot marker.
      NULL = common/practical (non-elective) subject. Additive/optional. */
  elective_slot?: ElectiveSlot | null;
  category: SubjectCategory;
  quiz_applicable: boolean;
  attendance_applicable: boolean;
}

export enum ElectiveSlot {
  ELECTIVE_I = "ELECTIVE_I",
  ELECTIVE_II = "ELECTIVE_II",
}

/** Phase 23.6/23.7: subject-specific occurrence outcome types.
    MODIFIED / SURPRISE_QUIZ / EXTRA_* / CANCELLED / null. */
export enum OccurrenceOutcomeType {
  EXTRA_LECTURE = "EXTRA_LECTURE",
  EXTRA_TUTORIAL = "EXTRA_TUTORIAL",
  EXTRA_PRACTICAL = "EXTRA_PRACTICAL",
  SURPRISE_QUIZ = "SURPRISE_QUIZ",
  CANCELLED = "CANCELLED",
  MODIFIED = "MODIFIED",
}

export enum ClassType {
  LECTURE = "L",
  TUTORIAL = "T",
  PRACTICAL = "P",
  PRACTICAL2 = "P2" // legacy alias, not returned by the current backend
}

export interface TimetableEntryResponse {
  id: string;
  day_of_week: number;
  class_type: ClassType;
  subject: SubjectResponse;
  /** Phase 22.4: the logical Departmental Elective slot this shared entry
      belongs to (ELECTIVE_I / ELECTIVE_II), or null for regular entries. */
  elective_slot: ElectiveSlot | null;
}

export enum AttendanceStatus {
  ATTENDED = "Attended",
  MISSED = "Missed",
  PENDING = "Pending"
}

export interface AttendanceRecord {
  date: string; // ISO format date string
  subject_code: string;
  class_type: ClassType;
  status: AttendanceStatus;
}

export interface AttendanceHistoryItem {
  id: string;
  date: string; // YYYY-MM-DD, local calendar date
  start_time: string | null;
  end_time: string | null;
  subject_code: string;
  subject_name: string;
  class_type: ClassType;
  status: AttendanceStatus;
  is_cancelled: boolean;
  is_extra: boolean;
  // Phase 9.1: session designation ("MID_SEM_PRACTICAL") — additive
  // presentation field; never used in any attendance calculation.
  designation: string | null;
  marked_at: string | null;
  // Phase 23.10: effective occurrence state for the student's resolved
  // concrete subject. outcome_type is the canonical occurrence outcome
  // (MODIFIED / SURPRISE_QUIZ / EXTRA_* / CANCELLED / null); elective_slot
  // marks the shared DE slot (null for non-elective). Presentation-only.
  outcome_type?: OccurrenceOutcomeType | null;
  elective_slot?: ElectiveSlot | null;
}

export interface HistorySummary {
  total: number;
  attended: number;
  missed: number;
  pending: number;
  cancelled: number;
  pct: number | null;
}

export interface AttendanceHistoryResponse {
  semester_start: string | null;
  semester_end: string | null;
  range_start: string | null;
  range_end: string | null;
  items: AttendanceHistoryItem[];
  total_count: number;
  summary: HistorySummary;
}

export type HistoryStatusFilter = "" | AttendanceStatus | "Cancelled";

export interface AttendanceHistoryParams {
  subject_code?: string;
  status?: HistoryStatusFilter;
  date_from?: string;
  date_to?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface DailySessionResponse {
  id: string;
  date: string;
  start_time: string | null;
  end_time: string | null;
  subject_code: string;
  subject_name: string;
  class_type: ClassType;
  status: AttendanceStatus;
  is_cancelled: boolean;
  is_extra: boolean;
  // Phase 9.1: session designation ("MID_SEM_PRACTICAL") — additive
  // presentation field from ClassSession.designation; never used in any
  // attendance calculation.
  designation: string | null;
  // Option-C quiz-day context: True when the subject has an ACTIVE QUIZ_DAY
  // event on this date. Presentation-only — never an attendance calculation.
  is_quiz_day: boolean;
  // Phase 23.10: effective occurrence state for the student's resolved
  // concrete subject. outcome_type is the canonical occurrence outcome
  // (MODIFIED / SURPRISE_QUIZ / EXTRA_* / CANCELLED / null); elective_slot
  // marks the shared DE slot (null for non-elective). Presentation-only.
  outcome_type?: OccurrenceOutcomeType | null;
  elective_slot?: ElectiveSlot | null;
}

export interface DailySessionsResponse {
  date: string;
  sessions: DailySessionResponse[];
}

export interface AttendanceMutationRequest {
  class_session_id: string;
  status: AttendanceStatus;
}

export interface ClassCounts {
  total: number;
  attended: number;
  missed: number;
  pending: number;
}

export interface SubjectAttendanceSummary {
  subject_code: string;
  lecture: ClassCounts;
  tutorial: ClassCounts;
  practical: ClassCounts;
  
  current_lecture_pct: number | null;
  current_tutorial_pct: number | null;
  current_avg_pct: number | null;
  
  forecast_lecture_pct: number | null;
  forecast_tutorial_pct: number | null;
  forecast_avg_pct: number | null;

  // Phase 8.1 additive analytics (Phase 8.2 consumes; the frontend never
  // computes these): practical attendance % uses the canonical class-session
  // pipeline; the subject-level 75% optimization is the attendance engine's
  // own optimizer (must-attend = *_deficit, safe-skip = safe_skip_*).
  current_practical_pct: number | null;
  forecast_practical_pct: number | null;
  optimization: OptimizationResult | null;

  // Attendance UI refinement (backend-emitted, additive): the required
  // attendance target the subject optimizer reasons about (75) and the
  // canonical current status band (SAFE | WATCH | CRITICAL | null). The
  // frontend renders these and never recomputes banding. The Attendance page
  // consumes `health` (Phase 8.2), NOT this legacy status.
  required_pct: number;
  status: "SAFE" | "WATCH" | "CRITICAL" | null;

  // Phase 8.2 Attendance Health: canonical 4-state classification of the
  // subject's OVERALL attendance, emitted by the backend (HEALTHY >= 75,
  // WATCH 65-<75, AT_RISK 60-<65, CRITICAL <60; null when nothing recorded).
  // React never bands attendance.
  health: "HEALTHY" | "WATCH" | "AT_RISK" | "CRITICAL" | null;

  // Phase 8.2 mid-semester practical designation (lab domain): the actual
  // scheduled PRACTICAL session designated as the subject's mid-sem, or null
  // when not designated. Never inferred from experiment counts/dates.
  mid_sem_session_id: string | null;
  mid_sem_session_date: string | null;
}

export interface OptimizationResult {
  lecture_deficit: number;
  tutorial_deficit: number;
  safe_skip_lecture: number;
  safe_skip_tutorial: number;
  is_reachable: boolean;
}

// --- Phase 8.1 analytics read model (GET /api/v1/analytics/overview) ---
// Every value is backend-derived from the canonical attendance engines; the
// frontend renders these fields and never re-implements attendance mathematics.

export interface OverallAnalytics {
  // ERP semantics: current = Σ attended / Σ recorded × 100 (recorded-only,
  // pending never converted to absent); forecast = Σ (attended + pending) /
  // Σ total × 100 (pending treated as attended). Cancelled excluded.
  current_pct: number | null;
  forecast_pct: number | null;
  attended: number;
  recorded: number;
  pending: number;
  cancelled: number;
  // Canonical 3-state current banding: SAFE | WATCH | CRITICAL | null.
  // AT-RISK is NOT defined and is never emitted.
  status: "SAFE" | "WATCH" | "CRITICAL" | null;
}

export interface WeeklyAnalyticsItem {
  // Monday-start week bucket. current_pct is null (a gap) when nothing was
  // recorded that week — render as a gap, never as 0%.
  week_start: string; // YYYY-MM-DD
  current_pct: number | null;
  attended: number;
  recorded: number;
  pending: number;
}

export interface AnalyticsSubjectItem extends SubjectAttendanceSummary {
  subject_name: string | null;
}

export interface AnalyticsOverviewResponse {
  as_of: string; // YYYY-MM-DD
  semester_start: string | null;
  semester_end: string | null;
  overall: OverallAnalytics;
  weekly: WeeklyAnalyticsItem[];
  subjects: AnalyticsSubjectItem[];
}

export enum EligibilityState {
  ELIGIBLE = "ELIGIBLE",
  RECOVERABLE = "RECOVERABLE",
  NOT_ELIGIBLE = "NOT_ELIGIBLE",
  UNRESOLVED = "UNRESOLVED",
}

export interface CriterionResult {
  name: string;
  value: number | null;
  threshold: number;
  passed: boolean;
  explanation: string;
  // That criterion's own Must Attend / Safe Skip, derived by the backend from
  // the criterion's counting window and the lecture/tutorial average formula.
  optimization?: OptimizationResult | null;
}

export interface FinalCriterionResult {
  combination: string;
  passed: boolean;
  explanation: string;
}

// Canonical "currently relevant" quiz cycle (Phase 7.2). The backend derives
// it solely from the authoritative quiz_schedules (next upcoming SCHEDULED
// quiz, else the latest resolved cycle, else the documented fallback Quiz I);
// the Quiz Eligibility page uses it only to preselect a default tab.
export interface CurrentQuizCycle {
  quiz_cycle: number;
  quiz_label: string | null;
  quiz_date: string | null;
  has_schedule: boolean;
  basis: "next_upcoming" | "latest_resolved" | "fallback";
}

export interface EligibilityResult {
  quiz_cycle: number;
  subject_code: string;
  subject_name: string | null;
  category: string | null;
  quiz_date: string | null;
  window_start: string;
  window_end: string;

  lecture_threshold: number | null;
  combined_threshold: number | null;
  required_percentage: number | null;

  lecture: ClassCounts;
  tutorial: ClassCounts;
  lecture_pct: number | null;
  tutorial_pct: number | null;
  average_pct: number | null;

  state: EligibilityState;
  recoverable: boolean;
  criterion_i: CriterionResult | null;
  criterion_ii: CriterionResult | null;
  final_criterion: FinalCriterionResult | null;

  is_eligible: boolean;
  optimization: OptimizationResult | null;
  explanation: string | null;
  policy_ambiguity_notes: string | null;
}

export enum EventType {
  EXTRA_LECTURE = "EXTRA_LECTURE",
  EXTRA_TUTORIAL = "EXTRA_TUTORIAL",
  EXTRA_PRACTICAL = "EXTRA_PRACTICAL",
  CLASS_CANCELLED = "CLASS_CANCELLED",
  SURPRISE_QUIZ = "SURPRISE_QUIZ",
  QUIZ_DAY = "QUIZ_DAY",
  // Unified holiday (closure family): one user-facing event for any
  // non-working holiday day/range, with an optional reason/occasion note.
  HOLIDAY = "HOLIDAY",
  PUBLIC_HOLIDAY = "PUBLIC_HOLIDAY",
  INSTITUTE_HOLIDAY = "INSTITUTE_HOLIDAY",
  WORKING_DAY_OVERRIDE = "WORKING_DAY_OVERRIDE",
  WORKING_SATURDAY = "WORKING_SATURDAY",
  EMERGENCY_CLOSURE = "EMERGENCY_CLOSURE",
  FESTIVAL_HOLIDAY = "FESTIVAL_HOLIDAY",
  SEMESTER_BREAK = "SEMESTER_BREAK",
  MID_SEMESTER_BREAK = "MID_SEMESTER_BREAK",
  // Phase 9.1 laboratory events (event-driven, canonical pipeline):
  MID_SEM_PRACTICAL = "MID_SEM_PRACTICAL",
  LAB_CANCELLED = "LAB_CANCELLED",
  /** Phase 23.7: subject-scoped modified occurrence. The scheduled class
      happened but was modified (time/room/delivery). Not extra, not cancelled. */
  CLASS_MODIFIED = "CLASS_MODIFIED",
}

export interface AcademicEventResponse {
  id: string;
  event_type: EventType;
  start_date: string;
  end_date: string;
  subject_id: string | null;
  /** Phase 22.4: the logical Departmental Elective slot the event belongs to
      (null for regular events). A slot event is ONE shared row for all
      students; `resolved_subject_*` carries the effective subject resolved
      for the authenticated student (their selected elective, or the shared
      anchor for a user with no selection — e.g. ADMIN). */
  elective_slot: ElectiveSlot | null;
  resolved_subject_id: string | null;
  resolved_subject_code: string | null;
  resolved_subject_name: string | null;
  class_type: ClassType | null;
  is_working_day: boolean | null;
  substitution_schedule_override: string | null;
  // Phase 9.1: optional student-entered note/reason (additive metadata).
  note: string | null;
  active: boolean;
}

// Query parameters for GET /api/v1/events (Phase 6.1 read contract).
export interface EventsParams {
  active?: boolean;
  date_from?: string;
  date_to?: string;
  upcoming?: boolean;
}

// Admin mutation payloads for POST/PATCH /api/v1/events (Phase 6.5).
// Only fields the AcademicEvent model actually has. Server validation
// (event validation registry) remains authoritative.
// Phase 22.4: `elective_slot` scopes the event to a Departmental Elective
// logical slot (ADMIN-only; mutually exclusive with subject_id — the server
// stores the shared anchor subject and resolves per student on read).
export interface AcademicEventPayload {
  event_type: EventType;
  start_date: string;
  end_date: string;
  subject_id?: string | null;
  elective_slot?: ElectiveSlot | null;
  class_type?: ClassType | null;
  is_working_day?: boolean | null;
  substitution_schedule_override?: string | null;
  // Phase 9.1: optional note/reason for the event (additive metadata).
  note?: string | null;
  active?: boolean;
}

export interface AcademicDayResponse {
  date: string;
  is_working_day: boolean;
  day_type: string;
  is_teaching_day: boolean;
  original_day_of_week: string;
  substitution_schedule_override: string | null;
  events: AcademicEventResponse[];
}

// Calendar month read model (Phase 6.2 / Phase 6.3). The backend is the sole
// authority for working/non-working state, semester bounds, events, and
// session counts — the UI renders these fields and never recomputes them.
export interface CalendarDayItem extends AcademicDayResponse {
  non_working_reason: string | null;
  session_count: number;
}

export interface CalendarMonthResponse {
  year: number;
  month: number;
  semester_start: string | null;
  semester_end: string | null;
  effective_start: string | null;
  effective_end: string | null;
  days: CalendarDayItem[];
}

// Laboratory
export enum SignatureStatus {
  PENDING = "pending",
  SIGNED = "signed"
}

export interface LaboratoryExperimentResponse {
  id: string;
  subject_id: string;
  experiment_number: number;
  title: string | null;
  // Phase 9.2.1: optional per-experiment note + catalog flag. Deactivated
  // experiments are hidden from the curriculum endpoint.
  description: string | null;
  is_active: boolean;
}

// Phase 9.2.1 record create payload (student self-tracking). Signature is
// NEVER part of the payload — the backend forces PENDING.
export interface LaboratoryRecordCreatePayload {
  experiment_id: string;
  date_conducted?: string | null;
  class_session_id?: string | null;
  remarks?: string | null;
}

// Phase 9.2.1 record update payload. Students may only edit date/session/
// remarks of own PENDING records; admins sign with signature_status="signed".
export interface LaboratoryRecordUpdatePayload {
  date_conducted?: string | null;
  class_session_id?: string | null;
  remarks?: string | null;
  signature_status?: SignatureStatus | null;
}

// Phase 9.2.1 admin experiment catalog payloads.
export interface LaboratoryExperimentCreatePayload {
  experiment_number: number;
  title?: string | null;
  description?: string | null;
}

export interface LaboratoryExperimentUpdatePayload {
  title?: string | null;
  description?: string | null;
}

export interface LaboratoryRecordResponse {
  id: string;
  user_id: string;
  experiment_id: string;
  // Phase 9.2.1 additive fields: optional session linkage + audit trail.
  class_session_id: string | null;
  signature_status: SignatureStatus;
  date_conducted: string | null;
  signed_on: string | null;
  signed_by: string | null;
  created_by: string | null;
  updated_by: string | null;
  marks: number | null;
  remarks: string | null;
}

// Phase 9.2.1 summary (GET /laboratory/{code}/summary). Every value is
// backend-derived; the frontend renders and never recomputes attendance math.
export interface LaboratorySummary {
  subject_code: string;
  practical_attendance: {
    attended: number;
    missed: number;
    pending: number;
    total: number;
    current_practical_pct: number;
  };
  mid_sem: {
    designated: boolean;
    session_id: string | null;
    session_date: string | null;
    attendance_status: string | null;
  };
  experiment_progress: {
    catalog_available: boolean;
    total: number;
    signed: number;
    pending_self_tracked: number;
    // "X of Y experiments officially completed" when a catalog exists,
    // null otherwise (honest empty state — never a fabricated "0/10").
    advisory: string | null;
  };
}

// Phase 9.2.1 activity (GET /laboratory/{code}/activity): truthful
// chronological list of the subject's PRACTICAL sessions with attendance
// state and any experiment record linked to the session.
export interface LaboratoryActivityItem {
  id: string;
  date: string;
  class_type: ClassType;
  is_cancelled: boolean;
  is_extra: boolean;
  designation: string | null;
  attendance_status: string | null;
  experiments: LaboratoryRecordResponse[];
}

export interface LaboratoryActivityResponse {
  subject_code: string;
  items: LaboratoryActivityItem[];
}

// Dashboard (Phase 3 Home read model)
export enum DashboardClassStatus {
  ATTENDED = "ATTENDED",
  MISSED = "MISSED",
  PENDING = "PENDING",
  CANCELLED = "CANCELLED",
}

export type AttendanceStatusLabel = "SAFE" | "WATCH" | "CRITICAL";

export interface DashboardClassItem {
  session_id: string;
  subject_code: string;
  subject_name: string;
  class_type: ClassType;
  status: DashboardClassStatus;
  is_extra: boolean;
}

export interface TodaySection {
  date: string;
  is_working_day: boolean;
  is_teaching_day: boolean;
  day_note: string | null;
  classes: DashboardClassItem[];
  attended: number;
  total: number;
}

export interface OverallSection {
  semester_start: string | null;
  overall_pct: number | null;
  attended: number;
  recorded: number;
  pending: number;
  status: AttendanceStatusLabel | null;
  weekly_delta_pct: number | null;
}

export interface WeekDayItem {
  date: string;
  day_label: string;
  is_today: boolean;
  is_future: boolean;
  classes: number;
  attended: number;
  recorded: number;
}

export interface SubjectBrief {
  subject_code: string;
  subject_name: string;
  pct: number | null;
}

export interface WeeklySection {
  week_start: string;
  week_end: string;
  days: WeekDayItem[];
  weekly_pct: number | null;
  recorded: number;
  previous_week_pct: number | null;
  delta_pct: number | null;
  best_subject: SubjectBrief | null;
  needs_attention_subject: SubjectBrief | null;
}

export interface QuizSnapshotSection {
  quiz_cycle: number | null;
  quiz_label: string | null;
  quiz_date: string | null;
  threshold: number | null;
  eligible: number;
  attention: number;
  not_eligible: number;
  total_theory: number;
  has_snapshot: boolean;
}

export interface AttentionItem {
  subject_code: string;
  subject_name: string;
  current_pct: number | null;
  forecast_pct: number | null;
  status: "WATCH" | "CRITICAL";
}

export interface UpcomingEventItem {
  id: string;
  event_type: EventType;
  start_date: string;
  end_date: string;
  subject_code: string | null;
  subject_name: string | null;
  class_type: ClassType | null;
}

export interface DashboardSummaryResponse {
  generated_at: string;
  today: TodaySection;
  overall: OverallSection;
  weekly: WeeklySection;
  quiz_snapshot: QuizSnapshotSection;
  attention_required: AttentionItem[];
  upcoming_events: UpcomingEventItem[];
}

// --- Phase 11B/11D notifications (GET /api/v1/notifications, PATCH
// /api/v1/notifications/{id}) ---
// The backend persists the Phase 11A projection idempotently and owns all
// identity (JWT-derived user_id; client never sends user_id). The frontend
// renders the backend contract as-is and never computes notification logic.
export enum NotificationKind {
  CLASS_REMINDER = "CLASS_REMINDER",
  QUIZ_APPROACHING = "QUIZ_APPROACHING",
  ATTENDANCE_THRESHOLD = "ATTENDANCE_THRESHOLD",
  MUST_ATTEND = "MUST_ATTEND",
  SAFE_SKIP = "SAFE_SKIP",
  ACADEMIC_EVENT = "ACADEMIC_EVENT",
}

export interface NotificationItem {
  // Deterministic natural key (KIND:<occurrence_key>) — stable client key.
  id: string;
  kind: NotificationKind;
  // Occurrence date (YYYY-MM-DD; institution-local, server-generated).
  date: string;
  subject_code: string | null;
  subject_name: string | null;
  message: string;
  // Canonical source references (null when the kind has none).
  session_id: string | null; // CLASS_REMINDER
  quiz_cycle: number | null; // QUIZ_APPROACHING
  event_id: string | null; // ACADEMIC_EVENT
  // Persisted row id — the PATCH mutation target (null only pre-11B).
  notification_id: string | null;
  is_read: boolean;
}

export interface NotificationsResponse {
  items: NotificationItem[];
  as_of: string; // YYYY-MM-DD, institution-local server date
  unread_count: number;
}

// PATCH payload — read/dismiss state transitions. At least one field is
// required by the backend (empty body -> 422).
export interface NotificationUpdate {
  is_read?: boolean;
  is_dismissed?: boolean;
}

// ── Feedback (Phase 10C submission + Phase 21B admin review) ──────────────
export type FeedbackType = "BUG" | "SUGGESTION" | "QUESTION" | "PRAISE";

export interface FeedbackAdminItem {
  id: string;
  feedback_type: FeedbackType;
  message: string;
  context: string | null;
  created_at: string;
  roll_number: string;
  name: string;
}

export interface FeedbackAdminListResponse {
  items: FeedbackAdminItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AdminFeedbackParams {
  page?: number;
  page_size?: number;
  feedback_type?: FeedbackType | "";
}

// --- Phase 24.1 Admin Portal identity (GET /api/v1/admin/me) ---
// Presentation-only contract: the backend remains the authorization boundary.
// The frontend renders roles/scopes but never decides authorization from them.
export interface AdminScopeDescriptor {
  role: string;
  section_name?: string | null;
  subsection_name?: string | null;
  subject_code?: string | null;
  subject_name?: string | null;
}

export interface AdminIdentity {
  id: string;
  display_name: string;
  roll_number: string | null;
  roles: string[];
  is_global: boolean;
  scopes: AdminScopeDescriptor[];
}

// --- Phase 24.2 HEAD_ADMIN dashboard (GET /api/v1/admin/dashboard) ---
// Read-only, current-state overview. HEAD_ADMIN only (403 for scoped admins).
export interface AcademicOverview {
  active_session: string | null;
  session_start: string | null;
  session_end: string | null;
  active_session_count: number;
  semester_count: number;
  semester_name: string | null;
  semester_start: string | null;
  semester_end: string | null;
  section_count: number;
  program_count: number;
  subject_count: number;
  student_count: number;
}

export interface CurriculumOverview {
  theory_subjects: number;
  lab_subjects: number;
  elective_i_subjects: number;
  elective_ii_subjects: number;
  compulsory_enrollments: number;
  elective_enrollments: number;
}

export interface StudentOverview {
  total: number;
  placed: number;
  unplaced: number;
  subsection_assigned: number;
  subsection_unassigned: number;
  elective_choice_holders: number;
  elective_choices_total: number;
}

export interface ScheduleOverview {
  timetable_entry_count: number;
  class_session_total: number;
  class_sessions_cancelled: number;
  class_sessions_extra: number;
  sessions_today: number;
  upcoming_sessions: number;
  occurrence_outcomes: number;
}

export interface AdminUpcomingEvent {
  id: string;
  event_type: string;
  start_date: string;
  end_date: string;
  subject_code: string | null;
  elective_slot: string | null;
}

export interface EventsOverview {
  total_active: number;
  upcoming_active: number;
  upcoming: AdminUpcomingEvent[];
}

export interface QuizOverview {
  cycle_count: number;
  schedule_total: number;
  scheduled_dated: number;
  unresolved: number;
  cancelled: number;
  next_quiz_date: string | null;
}

export interface AttendanceOverview {
  total_records: number;
  attended: number;
  missed: number;
  recorded_pct: number | null;
  participants: number;
}

export interface AdminDashboardWarning {
  code: string;
  severity: "info" | "warning";
  message: string;
}

export interface AdminDashboardResponse {
  generated_at: string;
  academic: AcademicOverview;
  curriculum: CurriculumOverview;
  students: StudentOverview;
  schedule: ScheduleOverview;
  events: EventsOverview;
  quizzes: QuizOverview;
  attendance: AttendanceOverview;
  warnings: AdminDashboardWarning[];
}

// --- Phase 24.3 Admin Portal student management (read) ---
// GET /api/v1/admin/students (scoped list/search) and
// GET /api/v1/admin/students/{id} (scoped detail).
// Read-only. Scope is resolved server-side from the acting admin's active
// scopes — the frontend never supplies or trusts a scope parameter.
export interface AdminStudentSummary {
  id: string;
  roll_number: string;
  name: string;
  section_name: string | null;
  program: string | null;
  semester_name: string | null;
  subsection_name: string | null;
  is_placed: boolean;
  is_active: boolean;
}

export interface AdminStudentListResponse {
  items: AdminStudentSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AdminStudentParams {
  q?: string;
  page?: number;
  page_size?: number;
}

export type EnrollmentTypeLabel = "COMPULSORY" | "ELECTIVE";

export interface AdminStudentEnrollment {
  id: string;
  code: string;
  name: string;
  enrollment_type: EnrollmentTypeLabel;
}

export interface AdminStudentDetail {
  id: string;
  roll_number: string;
  name: string;
  is_active: boolean;
  section_id: string | null;
  section_name: string | null;
  program: string | null;
  semester_id: string | null;
  semester_name: string | null;
  semester_start: string | null;
  semester_end: string | null;
  academic_session_id: string | null;
  academic_session_name: string | null;
  subsection_id: string | null;
  subsection_name: string | null;
  is_placed: boolean;
  enrollments: AdminStudentEnrollment[];
  compulsory_subjects: AdminStudentEnrollment[];
  elective_subjects: AdminStudentEnrollment[];
  elective_choices: Record<string, string>;
  inconsistencies: string[];
  first_quiz_date: string | null;
}

export interface SubsectionDropdownResponse {
  id: string;
  name: string;
  max_strength: number | null;
  current_strength: number | null;
}

export interface ElectiveDropdownResponse {
  id: string;
  code: string;
  name: string;
  elective_slot: ElectiveSlot;
}

export interface AssignSubsectionRequest {
  subsection_id: string;
}

export interface CorrectElectiveRequest {
  slot: ElectiveSlot;
  subject_id: string;
}

export interface SetStudentStatusRequest {
  is_active: boolean;
}

// ===========================================================================
// Phase 24.5 — Academic Structure Management (HEAD_ADMIN only)
// ===========================================================================

export interface RegistrationWarning {
  code: string;   // e.g. "MULTI_SEMESTER" | "MULTI_SECTION"
  message: string;
}

export interface AcademicSessionResponse {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  semester_count: number;
}

export interface CreateSessionRequest {
  name: string;
  start_date: string;
  end_date: string;
}

export interface UpdateSessionRequest {
  name?: string;
  start_date?: string;
  end_date?: string;
}

export interface SessionActivationResponse {
  id: string;
  name: string;
  is_active: boolean;
  warnings: RegistrationWarning[];
}

export interface SemesterResponse {
  id: string;
  name: string;
  session_id: string;
  session_name: string;
  start_date: string;
  end_date: string;
  section_count: number;
}

export interface CreateSemesterRequest {
  name: string;
  start_date: string;
  end_date: string;
}

export interface UpdateSemesterRequest {
  name?: string;
  start_date?: string;
  end_date?: string;
}

export interface SemesterMutationResponse {
  semester: SemesterResponse;
  warnings: RegistrationWarning[];
}

export interface SectionResponse {
  id: string;
  name: string;
  program: string | null;
  semester_id: string;
  semester_name: string;
  subsection_count: number;
  student_count: number;
}

export interface CreateSectionRequest {
  name: string;
  program?: string | null;
}

export interface UpdateSectionRequest {
  name?: string;
  program?: string | null;
}

export interface SectionMutationResponse {
  section: SectionResponse;
  warnings: RegistrationWarning[];
}

export interface SubsectionAdminResponse {
  id: string;
  name: string;
  section_id: string;
  section_name: string;
  max_strength: number | null;
  student_count: number;
}

export interface CreateSubsectionRequest {
  name: string;
  max_strength?: number | null;
}

export interface UpdateSubsectionRequest {
  name?: string;
  max_strength?: number | null;
}

// ===========================================================================
// Phase 24.6 — Curriculum & Subject Management
// ===========================================================================

// GET /api/v1/admin/subjects (scoped list). Read scope is resolved
// server-side: HEAD all / CLASS own-semester / ELECTIVE exact subject /
// SUBSECTION inert. Writes (POST/PATCH) are HEAD_ADMIN only.
export interface AdminSubjectSummary {
  id: string;
  code: string;
  name: string;
  tag: string | null;
  elective_slot: ElectiveSlot | null;
  category: SubjectCategory;
  quiz_applicable: boolean;
  attendance_applicable: boolean;
  semester_id: string;
  semester_name: string;
  session_name: string;
  /** True for the frozen shared elective anchors (BCS-054 / BCS-058). */
  is_anchor: boolean;
  enrollment_count: number;
  elective_choice_count: number;
}

export interface AdminSubjectListResponse {
  items: AdminSubjectSummary[];
  total: number;
}

export interface AdminSubjectDetail extends AdminSubjectSummary {
  timetable_entry_count: number;
  class_session_count: number;
  quiz_schedule_count: number;
  lab_experiment_count: number;
  attendance_record_count: number;
}

export interface CreateSubjectRequest {
  code: string;
  name: string;
  tag?: string | null;
  elective_slot?: ElectiveSlot | null;
  category: SubjectCategory;
  quiz_applicable: boolean;
  attendance_applicable: boolean;
  semester_id: string;
}

// PATCH payload — `code` and `semester_id` are immutable after creation and
// are rejected with 409 by the backend if sent. `elective_slot` may be set,
// cleared (explicit null), or left unchanged (omit the field).
export interface UpdateSubjectRequest {
  code?: string;
  name?: string;
  tag?: string | null;
  elective_slot?: ElectiveSlot | null;
  category?: SubjectCategory;
  quiz_applicable?: boolean;
  attendance_applicable?: boolean;
  semester_id?: string;
}

export interface SubjectMutationResponse {
  subject: AdminSubjectDetail;
  warnings: RegistrationWarning[];
}
