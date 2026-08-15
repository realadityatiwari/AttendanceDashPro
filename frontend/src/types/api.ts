export interface StudentProfile {
  id: string;
  firebase_uid: string | null;
  // Authorization role (Phase 6.5): "STUDENT" or "ADMIN". Backend is
  // authoritative; this drives admin-control visibility only.
  role: string;
  display_name: string;
  roll_number: string | null;
  section_name: string | null;
  program?: string | null;
  semester_name?: string | null;
  academic_session?: string | null;
  semester_start?: string | null;
  semester_end?: string | null;
  first_quiz_date?: string | null;
}

export enum SubjectCategory {
  CORE = "CORE",
  ELECTIVE = "ELECTIVE",
  LAB = "lab",
  MANDATORY = "MANDATORY"
}

export interface SubjectResponse {
  id: string;
  code: string;
  name: string;
  tag: string | null;
  category: SubjectCategory;
  quiz_applicable: boolean;
  attendance_applicable: boolean;
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
  LAB_CANCELLED = "LAB_CANCELLED"
}

export interface AcademicEventResponse {
  id: string;
  event_type: EventType;
  start_date: string;
  end_date: string;
  subject_id: string | null;
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
export interface AcademicEventPayload {
  event_type: EventType;
  start_date: string;
  end_date: string;
  subject_id?: string | null;
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
  title: string;
}

export interface LaboratoryRecordResponse {
  id: string;
  user_id: string;
  experiment_id: string;
  signature_status: SignatureStatus;
  date_conducted: string | null;
  marks: number | null;
  remarks: string | null;
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
