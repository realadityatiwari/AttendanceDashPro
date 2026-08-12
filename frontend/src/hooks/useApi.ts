import useSWR from 'swr';
import { apiFetch } from '@/lib/api';
import {
  StudentProfile,
  SubjectResponse,
  TimetableEntryResponse,
  AcademicDayResponse,
  SubjectAttendanceSummary,
  EligibilityResult,
  AttendanceHistoryResponse
} from '@/types/api';

// Fetcher function that wraps apiFetch for SWR
const fetcher = (url: string) => apiFetch(url);

export function useProfile() {
  const { data, error, isLoading, mutate } = useSWR<StudentProfile>('/api/v1/student/me', fetcher);
  return {
    profile: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useSubjects() {
  const { data, error, isLoading, mutate } = useSWR<SubjectResponse[]>('/api/v1/subjects', fetcher);
  return {
    subjects: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useTimetable() {
  const { data, error, isLoading, mutate } = useSWR<TimetableEntryResponse[]>('/api/v1/timetable', fetcher);
  return {
    timetable: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useCalendarDay(date: string) {
  // If date is empty, we don't fetch
  const { data, error, isLoading, mutate } = useSWR<AcademicDayResponse>(
    date ? `/api/v1/calendar/${date}` : null,
    fetcher
  );
  return {
    calendarDay: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useSubjectSummary(subjectCode: string | null) {
  const { data, error, isLoading, mutate } = useSWR<SubjectAttendanceSummary>(
    subjectCode ? `/api/v1/attendance/summary/${subjectCode}` : null,
    fetcher
  );
  return {
    summary: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useQuizEligibility(subjectCode: string | null, cycle: number | null) {
  const { data, error, isLoading, mutate } = useSWR<EligibilityResult>(
    subjectCode && cycle !== null ? `/api/v1/quiz-eligibility/${subjectCode}/${cycle}` : null,
    fetcher
  );
  return {
    eligibility: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useAttendanceHistory() {
  const { data, error, isLoading, mutate } = useSWR<AttendanceHistoryResponse>('/api/v1/attendance/history', fetcher);
  return {
    history: data,
    isLoading,
    isError: error,
    mutate
  };
}
