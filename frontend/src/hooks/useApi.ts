import useSWR from 'swr';
import { apiFetch } from '@/lib/api';
import {
  StudentProfile,
  SubjectResponse,
  TimetableEntryResponse,
  AcademicDayResponse,
  SubjectAttendanceSummary,
  EligibilityResult,
  AttendanceHistoryResponse,
  AttendanceHistoryParams,
  AcademicEventResponse,
  CalendarMonthResponse,
  LaboratoryExperimentResponse,
  LaboratoryRecordResponse,
  DashboardSummaryResponse,
  DailySessionsResponse,
  AttendanceMutationRequest
} from '@/types/api';

// Fetcher function that wraps apiFetch for SWR
const fetcher = (url: string) => apiFetch(url);

// Caching strategies
const LONG_CACHE = {
  revalidateOnFocus: false,
  revalidateIfStale: false,
  dedupingInterval: 3600000 // 1 hour
};

const STANDARD_CACHE = {
  revalidateOnFocus: true,
  dedupingInterval: 60000 // 1 minute
};

export function useProfile() {
  const { data, error, isLoading, mutate } = useSWR<StudentProfile>('/api/v1/student/me', fetcher, STANDARD_CACHE);
  return {
    profile: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useSubjects() {
  const { data, error, isLoading, mutate } = useSWR<SubjectResponse[]>('/api/v1/subjects', fetcher, LONG_CACHE);
  return {
    subjects: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useTimetable() {
  const { data, error, isLoading, mutate } = useSWR<TimetableEntryResponse[]>('/api/v1/timetable', fetcher, LONG_CACHE);
  return {
    timetable: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useCalendarDay(date: string) {
  const { data, error, isLoading, mutate } = useSWR<AcademicDayResponse>(
    date ? `/api/v1/calendar/${date}` : null,
    fetcher,
    STANDARD_CACHE
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
    fetcher,
    STANDARD_CACHE
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
    fetcher,
    STANDARD_CACHE
  );
  return {
    eligibility: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useAttendanceHistory(params: AttendanceHistoryParams = {}) {
  const query = new URLSearchParams();
  (Object.entries(params) as [string, string | number | undefined][]).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const queryString = query.toString();
  const url = queryString ? `/api/v1/attendance/history?${queryString}` : "/api/v1/attendance/history";
  const { data, error, isLoading, mutate } = useSWR<AttendanceHistoryResponse>(url, fetcher, STANDARD_CACHE);
  return {
    history: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useEvents() {
  const { data, error, isLoading, mutate } = useSWR<AcademicEventResponse[]>('/api/v1/events', fetcher, STANDARD_CACHE);
  return {
    events: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useCalendarMonth(year: number, month: number) {
  // Stable SWR key per requested month — changing month naturally fetches and
  // caches the correct backend read model, one logical request per month.
  // keepPreviousData retains the last loaded month while the next one fetches,
  // so the grid never blanks during navigation.
  const { data, error, isLoading, mutate } = useSWR<CalendarMonthResponse>(
    `/api/v1/calendar?year=${year}&month=${month}`,
    fetcher,
    { ...STANDARD_CACHE, keepPreviousData: true }
  );
  return {
    calendarMonth: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useLabExperiments(subjectCode: string | null) {
  const { data, error, isLoading, mutate } = useSWR<LaboratoryExperimentResponse[]>(
    subjectCode ? `/api/v1/laboratory/${subjectCode}/experiments` : null,
    fetcher,
    LONG_CACHE
  );
  return {
    experiments: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useLabRecords(subjectCode: string | null) {
  const { data, error, isLoading, mutate } = useSWR<LaboratoryRecordResponse[]>(
    subjectCode ? `/api/v1/laboratory/${subjectCode}/records` : null,
    fetcher,
    STANDARD_CACHE
  );
  return {
    records: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useDashboardSummary() {
  const { data, error, isLoading, mutate } = useSWR<DashboardSummaryResponse>(
    '/api/v1/dashboard/summary',
    fetcher,
    STANDARD_CACHE
  );
  return {
    summary: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useDailySessions(dateStr: string | null) {
  const { data, error, isLoading, mutate } = useSWR<DailySessionsResponse>(
    dateStr ? `/api/v1/attendance/daily/${dateStr}` : null,
    fetcher,
    STANDARD_CACHE
  );
  return {
    dailySessions: data,
    isLoading,
    isError: error,
    mutate
  };
}

export function useMutateAttendance() {
  const mutateAttendance = async (request: AttendanceMutationRequest) => {
    return apiFetch('/api/v1/attendance', {
      method: 'POST',
      body: JSON.stringify(request)
    });
  };

  return { mutateAttendance };
}
