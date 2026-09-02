import useSWR from 'swr';
import { apiFetch, PROFILE_KEY, NOTIFICATIONS_KEY } from '@/lib/api';
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
  UserPreferencesUpdate,
  NotificationsResponse,
  NotificationItem,
  NotificationUpdate,
  PushSubscriptionCreate,
  PushSubscriptionResponse,
  FeedbackAdminListResponse,
  AdminFeedbackParams,
  AdminIdentity,
  AdminDashboardResponse,
  AdminStudentListResponse,
  AdminStudentDetail,
  AdminStudentParams,
  SubsectionDropdownResponse,
  ElectiveDropdownResponse,
  AssignSubsectionRequest,
  CorrectElectiveRequest,
  SetStudentStatusRequest
} from '@/types/api';

// Fetcher function that wraps apiFetch for SWR
const fetcher = (url: string) => apiFetch(url);

// Caching strategies
//
// Phase C (2026-08-31): resource-aware policies replace the old universal
// STANDARD_CACHE to avoid the refetch storm on PWA foreground transitions.
// Each category documents its freshness trade-off.

const LONG_CACHE = {
  revalidateOnFocus: false,
  revalidateIfStale: false,
  dedupingInterval: 3600000 // 1 hour
};

// INTERACTIVE: resources the user sees directly and wants reasonably fresh.
// Refetch on focus (one request, not a storm); dedup within 60s.
// Used for: profile, dashboard summary, daily sessions, quiz cycle, subject
// summary, quiz eligibility, calendar day.
const INTERACTIVE_CACHE = {
  revalidateOnFocus: true,
  revalidateIfStale: true,
  dedupingInterval: 60000,
};

// SEMI_STATIC: resources that change infrequently or are only viewed on
// explicit navigation. Never refetch on focus (silent PWA transitions).
// Revalidate on mount (navigation) with a 5-minute dedupe to avoid repeated
// fetches on back-to-back page visits.
// Used for: analytics overview, calendar month, events, attendance history,
// lab records/summary/activity, preferences.
const SEMI_STATIC_CACHE = {
  revalidateOnFocus: false,
  revalidateIfStale: true,
  dedupingInterval: 300000, // 5 minutes
};

// DASHBOARD: the Home summary is the primary view the user sees on return.
// Controlled focus revalidation with a moderate dedupe (2 minutes) so
// returning to the app refreshes it without a simultaneous storm.
const DASHBOARD_CACHE = {
  revalidateOnFocus: true,
  revalidateIfStale: true,
  dedupingInterval: 120000, // 2 minutes
};

// STANDARD_CACHE: legacy policy, kept for Admin Portal hooks (out of scope)
// and for useNotifications (Phase B backend TTL cache makes focus revalidation
// cheap). Do not change — Admin Portal is not part of this phase.
const STANDARD_CACHE = {
  revalidateOnFocus: true,
  dedupingInterval: 60000
};

export function useProfile() {
  const { data, error, isLoading, mutate } = useSWR<StudentProfile>(PROFILE_KEY, fetcher, INTERACTIVE_CACHE);
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
    INTERACTIVE_CACHE
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
    INTERACTIVE_CACHE
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
    INTERACTIVE_CACHE
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
    INTERACTIVE_CACHE
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
  const { data, error, isLoading, mutate } = useSWR<AttendanceHistoryResponse>(url, fetcher, SEMI_STATIC_CACHE);
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
  const { data, error, isLoading, mutate } = useSWR<AcademicEventResponse[]>(url, fetcher, SEMI_STATIC_CACHE);
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
    { ...SEMI_STATIC_CACHE, keepPreviousData: true }
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
    SEMI_STATIC_CACHE
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
    SEMI_STATIC_CACHE
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
    SEMI_STATIC_CACHE
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
    DASHBOARD_CACHE
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
    SEMI_STATIC_CACHE
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
    INTERACTIVE_CACHE
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
    SEMI_STATIC_CACHE
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

// Phase 11D notification inbox (GET /api/v1/notifications). The SWR key is
// gated on `enabled` so the inbox is fetched only when the bell (always) or
// the notification center (on open) needs it — never unconditionally. One
// logical request per revalidation; the bell and the center share the same
// key, so SWR dedupes them. Phase 11C-P5: the key is the canonical
// NOTIFICATIONS_KEY so the service-worker invalidation signal, bell-open
// mutate, and PATCH reconciliation all target the same cache entry.
export function useNotifications(enabled = true) {
  const { data, error, isLoading, mutate } = useSWR<NotificationsResponse>(
    enabled ? NOTIFICATIONS_KEY : null,
    fetcher,
    STANDARD_CACHE
  );
  return {
    notifications: data,
    isLoading,
    isError: error,
    mutate
  };
}

// Phase 11D notification state mutation (PATCH /api/v1/notifications/{id}).
// Returns the server's updated NotificationItem; callers update the SWR cache
// with it (mutate(updated, false)) so the bell badge and the center stay in
// sync without extra round-trips. Repeating the same transition is a no-op
// success on the backend (idempotent).
export function useNotificationMutation() {
  const updateNotification = async (
    notificationId: string,
    payload: NotificationUpdate
  ): Promise<NotificationItem> => {
    return apiFetch(`/api/v1/notifications/${notificationId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  };

  return { updateNotification };
}

// Phase 11C-P2 push-subscription registration/unregistration. Both endpoints
// are authenticated on the backend and the owner is always derived from the
// JWT — the client never sends a user_id. Registration is idempotent
// (DB-enforced UNIQUE(endpoint)): calling it repeatedly for the same browser
// subscription can never create duplicates.
export function usePushSubscriptionMutations() {
  const registerPushSubscription = async (
    payload: PushSubscriptionCreate
  ): Promise<PushSubscriptionResponse> => {
    return apiFetch('/api/v1/push-subscriptions', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  };

  const deletePushSubscription = async (subscriptionId: string): Promise<void> => {
    return apiFetch(`/api/v1/push-subscriptions/${subscriptionId}`, {
      method: 'DELETE'
    });
  };

  return { registerPushSubscription, deletePushSubscription };
}

// Phase 21B admin feedback review (GET /api/v1/feedback/admin).
// Admin-only on the backend (require_admin); calling it as a STUDENT returns
// 403 and is surfaced through isError. The frontend link is role-gated at the
// UX layer only — the backend remains the authorization boundary.
export function useAdminFeedback(params: AdminFeedbackParams = {}) {
  const query = new URLSearchParams();
  if (params.page && params.page > 1) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.feedback_type) query.set("feedback_type", params.feedback_type);
  const qs = query.toString();
  const key = qs ? `/api/v1/feedback/admin?${qs}` : "/api/v1/feedback/admin";
  const { data, error, isLoading, mutate } = useSWR<FeedbackAdminListResponse>(key, fetcher, STANDARD_CACHE);
  return { feedback: data, isLoading, isError: error, mutate };
}

// Phase 24.1 Admin Portal identity (GET /api/v1/admin/me). DB-authoritative
// roles/scopes for shell/navigation PRESENTATION only — never an
// authorization boundary. STUDENT (no effective admin role) → 403, surfaced
// through isError with the preserved status.
export function useAdminMe() {
  const { data, error, isLoading, mutate } = useSWR<AdminIdentity>('/api/v1/admin/me', fetcher, STANDARD_CACHE);
  return { identity: data, isLoading, isError: error, mutate };
}

// Phase 24.2 HEAD_ADMIN dashboard (GET /api/v1/admin/dashboard). Read-only
// operational overview; require_head_admin server-side — scoped admins
// receive 403 (isError.status === 403) and are never silently elevated.
export function useAdminDashboard() {
  const { data, error, isLoading, mutate } = useSWR<AdminDashboardResponse>('/api/v1/admin/dashboard', fetcher, STANDARD_CACHE);
  return { dashboard: data, isLoading, isError: error, mutate };
}

// Phase 24.3 scoped student list/search (GET /api/v1/admin/students).
// Read-only. Scope is resolved server-side from the acting admin's active
// scopes (HEAD all / CLASS assigned sections / ELECTIVE choice-roster /
// SUBSECTION inert-empty); the frontend never supplies a scope parameter.
// One logical SWR key per (q, page, page_size) combination.
export function useAdminStudents(params: AdminStudentParams = {}) {
  const query = new URLSearchParams();
  if (params.q && params.q.trim()) query.set("q", params.q.trim());
  if (params.page && params.page > 1) query.set("page", String(params.page));
  if (params.page_size && params.page_size !== 20) query.set("page_size", String(params.page_size));
  const qs = query.toString();
  const key = qs ? `/api/v1/admin/students?${qs}` : "/api/v1/admin/students";
  const { data, error, isLoading, mutate } = useSWR<AdminStudentListResponse>(key, fetcher, STANDARD_CACHE);
  return { students: data, isLoading, isError: error, mutate };
}

// Phase 24.3 scoped student detail (GET /api/v1/admin/students/{id}).
// Read-only academic context; out-of-scope or nonexistent students return 404
// (surfaced through isError with the preserved status).
export function useAdminStudentDetail(studentId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<AdminStudentDetail>(
    studentId ? `/api/v1/admin/students/${studentId}` : null,
    fetcher,
    STANDARD_CACHE
  );
  return { student: data, isLoading, isError: error, mutate };
}

// Phase 24.4 Admin Portal student management (write)
export function useSectionSubsections(sectionId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<SubsectionDropdownResponse[]>(
    sectionId ? `/api/v1/admin/sections/${sectionId}/subsections` : null,
    fetcher,
    STANDARD_CACHE
  );
  return { subsections: data, isLoading, isError: error, mutate };
}

export function useSemesterElectives(semesterId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<ElectiveDropdownResponse[]>(
    semesterId ? `/api/v1/admin/semesters/${semesterId}/electives` : null,
    fetcher,
    STANDARD_CACHE
  );
  return { electives: data, isLoading, isError: error, mutate };
}

export function useAdminStudentMutations() {
  const assignSubsection = async (studentId: string, payload: AssignSubsectionRequest): Promise<AdminStudentDetail> => {
    return apiFetch(`/api/v1/admin/students/${studentId}/subsection`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  };

  const correctElective = async (studentId: string, payload: CorrectElectiveRequest): Promise<AdminStudentDetail> => {
    return apiFetch(`/api/v1/admin/students/${studentId}/electives`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  };

  const setStudentStatus = async (studentId: string, payload: SetStudentStatusRequest): Promise<AdminStudentDetail> => {
    return apiFetch(`/api/v1/admin/students/${studentId}/status`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    });
  };

  return { assignSubsection, correctElective, setStudentStatus };
}

// ===========================================================================
// Phase 24.5 — Academic Structure Management (HEAD_ADMIN only)
// ===========================================================================

import type {
  AcademicSessionResponse,
  CreateSessionRequest,
  UpdateSessionRequest,
  SessionActivationResponse,
  SemesterResponse,
  CreateSemesterRequest,
  UpdateSemesterRequest,
  SemesterMutationResponse,
  SectionResponse,
  CreateSectionRequest,
  UpdateSectionRequest,
  SectionMutationResponse,
  SubsectionAdminResponse,
  CreateSubsectionRequest,
  UpdateSubsectionRequest,
} from '@/types/api';

export function useAdminSessions() {
  const { data, error, isLoading, mutate } = useSWR<AcademicSessionResponse[]>(
    '/api/v1/admin/structure/sessions',
    fetcher,
    STANDARD_CACHE
  );
  return { sessions: data, isLoading, isError: error, mutate };
}

export function useAdminSemesters(sessionId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<SemesterResponse[]>(
    sessionId ? `/api/v1/admin/structure/sessions/${sessionId}/semesters` : null,
    fetcher,
    STANDARD_CACHE
  );
  return { semesters: data, isLoading, isError: error, mutate };
}

export function useAdminSections(semesterId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<SectionResponse[]>(
    semesterId ? `/api/v1/admin/structure/semesters/${semesterId}/sections` : null,
    fetcher,
    STANDARD_CACHE
  );
  return { sections: data, isLoading, isError: error, mutate };
}

export function useAdminSubsectionsStructure(sectionId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<SubsectionAdminResponse[]>(
    sectionId ? `/api/v1/admin/structure/sections/${sectionId}/subsections` : null,
    fetcher,
    STANDARD_CACHE
  );
  return { subsections: data, isLoading, isError: error, mutate };
}

export function useAdminStructureMutations() {
  // Sessions
  const createSession = async (payload: CreateSessionRequest): Promise<AcademicSessionResponse> =>
    apiFetch('/api/v1/admin/structure/sessions', { method: 'POST', body: JSON.stringify(payload) });

  const updateSession = async (sessionId: string, payload: UpdateSessionRequest): Promise<AcademicSessionResponse> =>
    apiFetch(`/api/v1/admin/structure/sessions/${sessionId}`, { method: 'PATCH', body: JSON.stringify(payload) });

  const activateSession = async (sessionId: string): Promise<SessionActivationResponse> =>
    apiFetch(`/api/v1/admin/structure/sessions/${sessionId}/activate`, { method: 'POST' });

  const deactivateSession = async (sessionId: string): Promise<SessionActivationResponse> =>
    apiFetch(`/api/v1/admin/structure/sessions/${sessionId}/deactivate`, { method: 'POST' });

  // Semesters
  const createSemester = async (sessionId: string, payload: CreateSemesterRequest): Promise<SemesterMutationResponse> =>
    apiFetch(`/api/v1/admin/structure/sessions/${sessionId}/semesters`, { method: 'POST', body: JSON.stringify(payload) });

  const updateSemester = async (semesterId: string, payload: UpdateSemesterRequest): Promise<SemesterMutationResponse> =>
    apiFetch(`/api/v1/admin/structure/semesters/${semesterId}`, { method: 'PATCH', body: JSON.stringify(payload) });

  // Sections
  const createSection = async (semesterId: string, payload: CreateSectionRequest): Promise<SectionMutationResponse> =>
    apiFetch(`/api/v1/admin/structure/semesters/${semesterId}/sections`, { method: 'POST', body: JSON.stringify(payload) });

  const updateSection = async (sectionId: string, payload: UpdateSectionRequest): Promise<SectionMutationResponse> =>
    apiFetch(`/api/v1/admin/structure/sections/${sectionId}`, { method: 'PATCH', body: JSON.stringify(payload) });

  // Subsections
  const createSubsection = async (sectionId: string, payload: CreateSubsectionRequest): Promise<SubsectionAdminResponse> =>
    apiFetch(`/api/v1/admin/structure/sections/${sectionId}/subsections`, { method: 'POST', body: JSON.stringify(payload) });

  const updateSubsection = async (subsectionId: string, payload: UpdateSubsectionRequest): Promise<SubsectionAdminResponse> =>
    apiFetch(`/api/v1/admin/structure/subsections/${subsectionId}`, { method: 'PATCH', body: JSON.stringify(payload) });

  return {
    createSession, updateSession, activateSession, deactivateSession,
    createSemester, updateSemester,
    createSection, updateSection,
    createSubsection, updateSubsection,
  };
}

// ===========================================================================
// Phase 24.6 — Curriculum & Subject Management
// ===========================================================================

import type {
  AdminSubjectListResponse,
  AdminSubjectDetail,
  CreateSubjectRequest,
  UpdateSubjectRequest,
  SubjectMutationResponse,
} from '@/types/api';

export function useAdminSubjects() {
  const { data, error, isLoading, mutate } = useSWR<AdminSubjectListResponse>(
    '/api/v1/admin/subjects',
    fetcher,
    STANDARD_CACHE
  );
  return { subjects: data, isLoading, isError: error, mutate };
}

export function useAdminSubjectDetail(subjectId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<AdminSubjectDetail>(
    subjectId ? `/api/v1/admin/subjects/${subjectId}` : null,
    fetcher,
    STANDARD_CACHE
  );
  return { subject: data, isLoading, isError: error, mutate };
}

export function useAdminSubjectMutations() {
  const createSubject = async (payload: CreateSubjectRequest): Promise<SubjectMutationResponse> =>
    apiFetch('/api/v1/admin/subjects', { method: 'POST', body: JSON.stringify(payload) });

  const updateSubject = async (subjectId: string, payload: UpdateSubjectRequest): Promise<SubjectMutationResponse> =>
    apiFetch(`/api/v1/admin/subjects/${subjectId}`, { method: 'PATCH', body: JSON.stringify(payload) });

  return { createSubject, updateSubject };
}

// ===========================================================================
// Phase 24.7 — Admin Timetable Management
// ===========================================================================

import type {
  TimetableEntryAdminListResponse,
  CreateTimetableEntryRequest,
  UpdateTimetableEntryRequest,
  DuplicateTimetableEntryRequest,
  TimetableEntryMutationResponse,
} from '@/types/api';

export function useAdminTimetableEntries(params?: Record<string, string>) {
  const query = params ? new URLSearchParams(params).toString() : '';
  const key = query ? `/api/v1/admin/timetable?${query}` : '/api/v1/admin/timetable';
  const { data, error, isLoading, mutate } = useSWR<TimetableEntryAdminListResponse>(
    key,
    fetcher,
    STANDARD_CACHE
  );
  return { entries: data?.items, total: data?.total ?? 0, isLoading, isError: error, mutate };
}

export function useAdminTimetableMutations() {
  const createEntry = async (payload: CreateTimetableEntryRequest): Promise<TimetableEntryMutationResponse> =>
    apiFetch('/api/v1/admin/timetable', { method: 'POST', body: JSON.stringify(payload) });

  const updateEntry = async (entryId: string, payload: UpdateTimetableEntryRequest): Promise<TimetableEntryMutationResponse> =>
    apiFetch(`/api/v1/admin/timetable/${entryId}`, { method: 'PATCH', body: JSON.stringify(payload) });

  const deactivateEntry = async (entryId: string): Promise<TimetableEntryMutationResponse> =>
    apiFetch(`/api/v1/admin/timetable/${entryId}/deactivate`, { method: 'POST' });

  const duplicateEntry = async (entryId: string, payload: DuplicateTimetableEntryRequest): Promise<TimetableEntryMutationResponse> =>
    apiFetch(`/api/v1/admin/timetable/${entryId}/duplicate`, { method: 'POST', body: JSON.stringify(payload) });

  return { createEntry, updateEntry, deactivateEntry, duplicateEntry };
}

// ===========================================================================
// Phase 24.8 — Admin Quiz Schedule Manager
// ===========================================================================

import type {
  AdminQuizScheduleListResponse,
  AdminQuizCycleListResponse,
  CreateQuizScheduleRequest,
  UpdateQuizScheduleRequest,
  QuizScheduleMutationResponse,
} from '@/types/api';

export function useAdminQuizSchedules(params?: Record<string, string>) {
  const query = params ? new URLSearchParams(params).toString() : '';
  const key = query ? `/api/v1/admin/quizzes?${query}` : '/api/v1/admin/quizzes';
  const { data, error, isLoading, mutate } = useSWR<AdminQuizScheduleListResponse>(
    key,
    fetcher,
    STANDARD_CACHE
  );
  return { schedules: data?.items, total: data?.total ?? 0, isLoading, isError: error, mutate };
}

export function useAdminQuizCycles() {
  const { data, error, isLoading } = useSWR<AdminQuizCycleListResponse>(
    '/api/v1/admin/quiz-cycles',
    fetcher,
    STANDARD_CACHE
  );
  return { cycles: data?.items, total: data?.total ?? 0, isLoading, isError: error };
}

export function useAdminQuizMutations() {
  const createSchedule = async (payload: CreateQuizScheduleRequest): Promise<QuizScheduleMutationResponse> =>
    apiFetch('/api/v1/admin/quizzes', { method: 'POST', body: JSON.stringify(payload) });

  const updateSchedule = async (scheduleId: string, payload: UpdateQuizScheduleRequest): Promise<QuizScheduleMutationResponse> =>
    apiFetch(`/api/v1/admin/quizzes/${scheduleId}`, { method: 'PATCH', body: JSON.stringify(payload) });

  return { createSchedule, updateSchedule };
}

// ===========================================================================
// Phase 24.9 — Admin Event Manager
// ===========================================================================

import type {
  AdminEventListResponse,
  AdminEventMutationResponse,
  CreateAdminEventRequest,
  UpdateAdminEventRequest,
} from '@/types/api';

export function useAdminEvents(params?: Record<string, string>) {
  const query = params ? new URLSearchParams(params).toString() : '';
  const key = query ? `/api/v1/admin/events?${query}` : '/api/v1/admin/events';
  const { data, error, isLoading, mutate } = useSWR<AdminEventListResponse>(
    key,
    fetcher,
    STANDARD_CACHE
  );
  return { events: data?.items, total: data?.total ?? 0, isLoading, isError: error, mutate };
}

export function useAdminEventMutations() {
  const createEvent = async (payload: CreateAdminEventRequest): Promise<AdminEventMutationResponse> =>
    apiFetch('/api/v1/admin/events', { method: 'POST', body: JSON.stringify(payload) });

  const updateEvent = async (eventId: string, payload: UpdateAdminEventRequest): Promise<AdminEventMutationResponse> =>
    apiFetch(`/api/v1/admin/events/${eventId}`, { method: 'PATCH', body: JSON.stringify(payload) });

  const deactivateEvent = async (eventId: string): Promise<AdminEventMutationResponse> =>
    apiFetch(`/api/v1/admin/events/${eventId}`, { method: 'DELETE' });

  return { createEvent, updateEvent, deactivateEvent };
}

// ===========================================================================
// Phase 24.11 — Admin & Scope Management (HEAD_ADMIN only)
// ===========================================================================

import type {
  AdminUserListResponse,
  AdminUserDetail,
  AdminScopeMutationResponse,
  AssignScopeRequest,
  UpdateScopeActiveRequest,
} from '@/types/api';

export function useAdminUsers() {
  const { data, error, isLoading, mutate } = useSWR<AdminUserListResponse>(
    '/api/v1/admin/admins',
    fetcher,
    STANDARD_CACHE
  );
  return { admins: data?.items, total: data?.total ?? 0, isLoading, isError: error, mutate };
}

export function useAdminUserDetail(userId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<AdminUserDetail>(
    userId ? `/api/v1/admin/admins/${userId}` : null,
    fetcher,
    STANDARD_CACHE
  );
  return { admin: data, isLoading, isError: error, mutate };
}

// ===========================================================================
// Phase 24.12 — Attendance admin & analytics (READ-ONLY)
// ===========================================================================

import type {
  AdminSectionAttendanceListResponse,
  AdminSubjectAttendanceListResponse,
} from '@/types/api';

export function useAdminAttendanceSections() {
  const { data, error, isLoading, mutate } = useSWR<AdminSectionAttendanceListResponse>(
    '/api/v1/admin/attendance/sections',
    fetcher,
    STANDARD_CACHE
  );
  return { data, isLoading, isError: error, mutate };
}

export function useAdminAttendanceSubjects() {
  const { data, error, isLoading, mutate } = useSWR<AdminSubjectAttendanceListResponse>(
    '/api/v1/admin/attendance/subjects',
    fetcher,
    STANDARD_CACHE
  );
  return { data, isLoading, isError: error, mutate };
}

export function useAdminStudentAttendance(studentId: string | null) {
  const { data, error, isLoading, mutate } = useSWR<AnalyticsOverviewResponse>(
    studentId ? `/api/v1/admin/attendance/students/${studentId}` : null,
    fetcher,
    STANDARD_CACHE
  );
  return { data, isLoading, isError: error, mutate };
}

export function useAdminScopeMutations() {
  const assignScope = async (userId: string, payload: AssignScopeRequest): Promise<AdminScopeMutationResponse> =>
    apiFetch(`/api/v1/admin/admins/${userId}/scopes`, { method: 'POST', body: JSON.stringify(payload) });

  const setScopeActive = async (userId: string, scopeId: string, active: boolean): Promise<AdminScopeMutationResponse> =>
    apiFetch(`/api/v1/admin/admins/${userId}/scopes/${scopeId}`, {
      method: 'PATCH', body: JSON.stringify({ active } satisfies UpdateScopeActiveRequest),
    });

  return { assignScope, setScopeActive };
}
