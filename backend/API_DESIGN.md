# API Design Document (Phase 3)

This document maps out the FastAPI REST API surface for the AttendanceDash Pro domain engines. The API is strictly designed to serve existing frontend capabilities and application-level requirements without exposing internal database implementation details.

## Authentication Strategy

- **Provider**: Firebase Authentication.
- **Protocol**: HTTP Bearer Token (`Authorization: Bearer <ID_TOKEN>`).
- **Status (IMPLEMENTED / BLOCKED)**: The dependency boundary `get_current_user` is fully scaffolded in `deps.py`. It correctly blocks unauthenticated requests. However, because Firebase Admin credentials are not yet configured, token decoding intentionally fails with `501 Not Implemented` rather than faking insecure access.

## Authorization Strategy

All endpoints under `/api/v1` (except public health) resolve the authenticated Firebase user to a corresponding `User` entity in PostgreSQL. All database mutations and queries automatically scope to the authenticated `user_id`. No endpoint relies on trusting client-provided `?user_id=...` parameters.

## Endpoint Surface

### IMPLEMENTED

| Method | Endpoint | Purpose | Auth |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Application healthcheck (no DB required) | None |
| `GET` | `/api/v1/student/me` | Fetch the current user's profile and section | Firebase JWT |
| `GET` | `/api/v1/subjects` | Fetch the subjects enrolled by the student | Firebase JWT |
| `GET` | `/api/v1/timetable` | Fetch the recurring weekly timetable for the student's section | Firebase JWT |
| `GET` | `/api/v1/calendar/today` | Fetch the exact academic day resolution for today (accounting for events) | Firebase JWT |
| `GET` | `/api/v1/calendar/{date}` | Fetch the exact academic day resolution for a specific date | Firebase JWT |
| `GET` | `/api/v1/events` | Fetch all active academic events (holidays, extra classes) | Firebase JWT |
| `GET` | `/api/v1/attendance/summary/{subject_code}` | Fetch engine-computed stats (L/T/P percentages, safe skips) | Firebase JWT |
| `POST` | `/api/v1/attendance` | Mark/update attendance for a specific class session (`PENDING`, `ATTENDED`, `MISSED`) | Firebase JWT |
| `GET` | `/api/v1/quiz-eligibility/{subject_code}/{quiz_cycle}` | Evaluate quiz eligibility via policy rules (respecting UNRESOLVED dates) | Firebase JWT |
| `GET` | `/api/v1/laboratory/{subject_code}/experiments` | Fetch experiments list for a lab subject | Firebase JWT |
| `GET` | `/api/v1/laboratory/{subject_code}/records` | Fetch student's signature and progress records | Firebase JWT |

### PLANNED / DEFERRED

- **Data Migration**: Loading existing Firestore data to PostgreSQL is deferred to Phase 5.
- **Admin/Teacher API**: Out of scope for the current student-focused application.
- **Calendar Mutations**: Creating events (`POST /api/v1/events`) is deferred as students cannot create academic events.
- **Push Notifications**: Integrating Firebase Cloud Messaging logic.

## Error Behavior

Standard HTTP codes are strictly enforced:
- **`400 Bad Request`**: Malformed request or state error (e.g. User has no section).
- **`401 Unauthorized`**: Missing or invalid Firebase ID Token.
- **`403 Forbidden`**: Insufficient permissions (future scope).
- **`404 Not Found`**: Resource does not exist (e.g. Subject code not found, Class Session not found).
- **`422 Unprocessable Entity`**: Pydantic validation failure.
- **`501 Not Implemented`**: Scaffolding exists, but Firebase Admin lacks configuration.
- **`500 Internal Server Error`**: Unhandled exception (Raw SQL errors are never leaked).

## Important Domain Rules

1.  **Attendance Calculations**: The `POST /api/v1/attendance` endpoint only saves facts (`ATTENDED`, `MISSED`, `PENDING`). Percentages, optimization projections, and safe skips are strictly calculated on-the-fly by `attendance_engine.py` when `GET /api/v1/attendance/summary` is invoked.
2.  **Pending Attendance**: Class sessions that occur but lack an attendance record are explicitly counted as `PENDING`. They do not negatively impact current percentages but are assumed attended for forecast percentages.
3.  **Quiz Policy Ambiguity**: `BCS-054` Q3 is represented as `schedule_status="UNRESOLVED", date=None` in PostgreSQL. The API surfaces this safely by passing `None` through the Pydantic schemas, and returning `is_eligible=False` with `policy_ambiguity_notes` stating the quiz is unavailable.
4.  **CORS**: `allow_origins=["*"]` is strictly avoided. Allowed origins are configured via `BACKEND_CORS_ORIGINS` in `.env`.
