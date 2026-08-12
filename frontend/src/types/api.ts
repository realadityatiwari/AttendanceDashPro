export interface StudentProfile {
  id: string;
  firebase_uid: string;
  display_name: string;
  roll_number: string | null;
  section_name: string | null;
}

export enum SubjectCategory {
  CORE = "CORE",
  ELECTIVE = "ELECTIVE",
  LAB = "LAB",
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
  PRACTICAL = "P1", // using strings as they map to enum in backend
  PRACTICAL2 = "P2"
}

export interface TimetableEntryResponse {
  id: string;
  day_of_week: number;
  class_type: ClassType;
  subject: SubjectResponse;
}

export enum AttendanceStatus {
  ATTENDED = "ATTENDED",
  MISSED = "MISSED",
  PENDING = "PENDING"
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
  HOLIDAY = "HOLIDAY",
  EXTRA_CLASS = "EXTRA_CLASS",
  EXAM = "EXAM",
  OTHER = "OTHER"
}

export interface AcademicEventResponse {
  id: string;
  title: string;
  description: string | null;
  event_type: EventType;
  start_date: string;
  end_date: string;
  is_holiday: boolean;
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
  NONE = "NONE",
  DONE = "DONE",
  PENDING_REWORK = "PENDING_REWORK"
}

export interface LaboratoryExperimentResponse {
  id: string;
  subject_id: string;
  experiment_number: number;
  title: string;
}

export interface LaboratoryRecordResponse {
  id: string;
  student_id: string;
  experiment_id: string;
  signature_status: SignatureStatus;
  date_conducted: string | null;
  marks: number | null;
  remarks: string | null;
}
