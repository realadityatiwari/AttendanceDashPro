export interface StudentProfile {
  id: string;
  firebase_uid: string;
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
  date: string;
  subject_code: string;
  class_type: ClassType;
  status: AttendanceStatus;
  marked_at: string;
}

export interface AttendanceHistoryResponse {
  items: AttendanceHistoryItem[];
  total_count: number;
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
}

export interface OptimizationResult {
  lecture_deficit: number;
  tutorial_deficit: number;
  safe_skip_lecture: number;
  safe_skip_tutorial: number;
  is_reachable: boolean;
}

export interface EligibilityResult {
  quiz_cycle: number;
  subject_code: string;
  window_start: string;
  window_end: string;
  
  lecture_threshold: number | null;
  combined_threshold: number | null;
  
  is_eligible: boolean;
  optimization: OptimizationResult | null;
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
  MID_SEMESTER_BREAK = "MID_SEMESTER_BREAK"
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
  active: boolean;
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
