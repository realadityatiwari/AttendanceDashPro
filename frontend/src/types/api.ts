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
