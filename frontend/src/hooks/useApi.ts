import useSWR from 'swr';
import { apiFetch } from '@/lib/api';
import {
  StudentProfile,
  SubjectResponse,
  TimetableEntryResponse,
  AcademicDayResponse,
  SubjectAttendanceSummary,
  EligibilityResult,
  CurrentQuizCycle,
  AttendanceHistoryResponse,
  AttendanceHistoryParams,
  AcademicEventResponse,
  EventsParams,
  AcademicEventPayload,
  CalendarMonthResponse,
  LaboratoryExperimentResponse,
  LaboratoryRecordResponse,
  LaboratoryRecordCreatePayload,
  LaboratoryRecordUpdatePayload,
  LaboratoryExperimentCreatePayload,
  LaboratoryExperimentUpdatePayload,
  LaboratorySummary,
  LaboratoryActivityResponse,
  DashboardSummaryResponse,
  DailySessionsResponse,
  AttendanceMutationRequest,
  AnalyticsOverviewResponse,
  UserPreferences,
  UserPreferencesUpdate
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

export function useCurrentQuizCycle() {
  // Canonical backend answer for the date-aware default tab (Phase 7.2); the
  // page never recomputes schedule semantics client-side.
  const { data, error, isLoading, mutate } = useSWR<CurrentQuizCycle>(
    '/api/v1/quiz-eligibility/current-cycle',
    fetcher,
    STANDARD_CACHE
  );
  return {
    currentCycle: data,
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

export function useEvents(params: EventsParams = {}) {
  // One logical request per filter combination; the backend applies date/active
  // semantics server-side (Phase 6.1 contract). Type grouping is presentation
  // only and happens in the page.
  const query = new URLSearchParams();
  (Object.entries(params) as [string, string | number | boolean | undefined][]).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  const queryString = query.toString();
  const url = queryString ? `/api/v1/events?${queryString}` : "/api/v1/events";
  const { data, error, isLoading, mutate } = useSWR<AcademicEventResponse[]>(url, fetcher, STANDARD_CACHE);
  return {
    events: data,
    isLoading,
    isError: error,
    mutate
  };
}

// Admin event mutations (Phase 6.5). Each call returns the created/updated/
// deactivated AcademicEventResponse; the server enforces ADMIN (403 for
// students). Callers revalidate the events + calendar SWR caches after a
// successful mutation — there is no separate event cache.
export function useEventMutations() {
  const createEvent = async (payload: AcademicEventPayload): Promise<AcademicEventResponse> => {
    return apiFetch('/api/v1/events', { method: 'POST', body: JSON.stringify(payload) });
  };

  const updateEvent = async (eventId: string, payload: Partial<AcademicEventPayload>): Promise<AcademicEventResponse> => {
    return apiFetch(`/api/v1/events/${eventId}`, { method: 'PATCH', body: JSON.stringify(payload) });
  };

  const deactivateEvent = async (eventId: string): Promise<AcademicEventResponse> => {
    return apiFetch(`/api/v1/events/${eventId}`, { method: 'DELETE' });
  };

  return { createEvent, updateEvent, deactivateEvent };
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

export function useLabSummary(subjectCode: string | null) {
  const { data, error, isLoading, mutate } = useSWR<LaboratorySummary>(
    subjectCode ? `/api/v1/laboratory/${subjectCode}/summary` : null,
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

export function useLabActivity(subjectCode: string | null) {
  const { data, error, isLoading, mutate } = useSWR<LaboratoryActivityResponse>(
    subjectCode ? `/api/v1/laboratory/${subjectCode}/activity` : null,
    fetcher,
    STANDARD_CACHE
  );
  return {
    activity: data,
    isLoading,
    isError: error,
    mutate
  };
}

// Phase 9.2.1 laboratory mutations (student self-tracking + admin catalog).
// Returns the created/updated object; errors carry the backend detail string.
export function useLabMutations() {
  const createRecord = async (subjectCode: string, payload: LaboratoryRecordCreatePayload) => {
    return apiFetch(`/api/v1/laboratory/${subjectCode}/records`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }) as Promise<LaboratoryRecordResponse>;
  };

  const updateRecord = async (subjectCode: string, recordId: string, payload: LaboratoryRecordUpdatePayload) => {
    return apiFetch(`/api/v1/laboratory/${subjectCode}/records/${recordId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    }) as Promise<LaboratoryRecordResponse>;
  };

  const deleteRecord = async (subjectCode: string, recordId: string) => {
    return apiFetch(`/api/v1/laboratory/${subjectCode}/records/${recordId}`, {
      method: 'DELETE'
    });
  };

  const createExperiment = async (subjectCode: string, payload: LaboratoryExperimentCreatePayload) => {
    return apiFetch(`/api/v1/laboratory/${subjectCode}/experiments`, {
      method: 'POST',
      body: JSON.stringify(payload)
    }) as Promise<LaboratoryExperimentResponse>;
  };

  const updateExperiment = async (subjectCode: string, experimentId: string, payload: LaboratoryExperimentUpdatePayload) => {
    return apiFetch(`/api/v1/laboratory/${subjectCode}/experiments/${experimentId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    }) as Promise<LaboratoryExperimentResponse>;
  };

  const deleteExperiment = async (subjectCode: string, experimentId: string) => {
    return apiFetch(`/api/v1/laboratory/${subjectCode}/experiments/${experimentId}`, {
      method: 'DELETE'
    }) as Promise<LaboratoryExperimentResponse>;
  };

  return { createRecord, updateRecord, deleteRecord, createExperiment, updateExperiment, deleteExperiment };
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

export function useAnalyticsOverview() {
  // Phase 8.1 analytics read model (authenticated, enrollment-scoped): overall
  // current/forecast, pending count, weekly series, per-subject analytics — all
  // backend-derived. The frontend renders these fields and never recomputes
  // attendance/forecast/safe-skip mathematics.
  const { data, error, isLoading, mutate } = useSWR<AnalyticsOverviewResponse>(
    '/api/v1/analytics/overview',
    fetcher,
    STANDARD_CACHE
  );
  return {
    overview: data,
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

// Phase 10D user preferences (GET/PUT /api/v1/student/preferences). The SWR
// key is gated on `enabled` so the preferences are fetched when the Settings
// modal is opened (or when a caller first needs them), never unconditionally
// at shell mount. STORAGE/PREFERENCE DATA ONLY — nothing consumes the values
// until Phase 11.
export function usePreferences(enabled = true) {
  const { data, error, isLoading, mutate } = useSWR<UserPreferences>(
    enabled ? '/api/v1/student/preferences' : null,
    fetcher,
    STANDARD_CACHE
  );
  return {
    preferences: data,
    isLoading,
    isError: error,
    mutate
  };
}

// Phase 10D preference save (PUT, full-object replacement). Returns the
// server's complete preference object; callers update the SWR cache with it
// (mutate(saved, false)) so no extra round-trip is needed after a save.
export function usePreferenceMutation() {
  const savePreferences = async (payload: UserPreferencesUpdate): Promise<UserPreferences> => {
    return apiFetch('/api/v1/student/preferences', {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  };

  return { savePreferences };
}
