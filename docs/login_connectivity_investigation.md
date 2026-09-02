# Login Connectivity Investigation — "Unable to Reach the Server"

**AttendanceDash Pro · 2026-09-02 · INVESTIGATION → FIX COMPLETE**

> Investigation and fix for the login failure at `POST /api/v1/auth/login` returning
> 500 Internal Server Error with `relation "refresh_tokens" does not exist`.

---

## 1. Observed Symptom

The user reported seeing "Unable to reach the server. Check your connection and try again." on the login page at `http://localhost:3100/login`.

---

## 2. Exact Request URL/Path

Frontend login page (`frontend/src/app/(auth)/login/page.tsx`) calls `fetch()` directly (not `apiFetch`):

```
POST http://localhost:8080/api/v1/auth/login
Content-Type: application/json
{"roll_number": "<user-input>", "password": "<user-input>"}
```

The `API_BASE_URL` resolves from `NEXT_PUBLIC_API_URL=http://localhost:8080` (set in `frontend/.env.local`).

---

## 3. Does the Request Reach the Backend?

**YES.** Backend logs at `backend_out.log` confirm:

```
INFO: 127.0.0.1:2811 - "OPTIONS /api/v1/auth/login HTTP/1.1" 200 OK
...
INFO: 127.0.0.1:4009 - "POST /api/v1/auth/login HTTP/1.1" 500 Internal Server Error
INFO: 127.0.0.1:1762 - "POST /api/v1/auth/login HTTP/1.1" 500 Internal Server Error
```

The CORS preflight (OPTIONS) returns 200 with correct headers (`access-control-allow-origin: http://localhost:3100`, `allow-credentials: true`). The actual POST reaches the backend and returns 500.

---

## 4. Actual Failure Mechanism

The backend log shows the exact error:

```
sqlalchemy.exc.ProgrammingError: (asyncpg.exceptions.UndefinedTableError):
  relation "refresh_tokens" does not exist

[SQL: INSERT INTO refresh_tokens (user_id, token_hash, family_id, expires_at, ...)
  VALUES ($1::UUID, $2::VARCHAR, ...)]
```

The login endpoint (`backend/app/api/v1/endpoints/auth.py:124`) calls
`RefreshTokenService(db).issue(user)` on EVERY successful login, which INSERTs
a row into `refresh_tokens`. The table did not exist in the local dev database.

---

## 5. Root Cause

**The Phase 25.1 migration `a9b8c7d6e5f4` (add_refresh_tokens) had NOT been
applied to the local development database.** The local Docker PostgreSQL
(`attendancedashpro_db`, port 55432) was at Alembic revision `c4d5e6f7a8b9`,
not at head `a9b8c7d6e5f4`:

- `docker exec attendancedashpro_db psql -c "SELECT version_num FROM alembic_version"` → `c4d5e6f7a8b9`
- `alembic current` → `c4d5e6f7a8b9`
- `\dt` → no `refresh_tokens` table (23 tables, none was `refresh_tokens`)

This contradicts the task brief's claim that "Alembic is at a9b8c7d6e5f4 (head)"
and "The missing refresh_tokens migration was successfully applied." The
migration was likely applied to a different database (possibly the Supabase
production DB via the stale `DATABASE_URI` env var documented in Phase 26.7).

The login endpoint was added in Phase 25.1 and unconditionally requires
`refresh_tokens` — every valid login results in an INSERT. Without the table,
every login attempt fails with a 500 before the response is sent.

---

## 6. Frontend Message Mapping

The login page's error handler distinguishes between `Error` and `TypeError`:

- A 500 response with `{"detail": "Internal server error"}` → `new Error("Internal server error")` → shown as "Internal server error"
- A network-level fetch failure (backend unreachable, CORS blocked) → `TypeError` → shown as "Unable to reach the server. Check your connection and try again."

The user's reported "Unable to reach the server" message would come from the
TypeError branch, indicating a network-level failure at the time of their test.
The backend logs show requests DID reach the backend and returned 500, so the
network path was functional at that moment. The "Unable to reach the server"
message may be from a test performed before the backend was restarted after
the Phase 26.7 fix, or from a different browser session.

Regardless, the blocking failure was the 500 from the missing `refresh_tokens`
table — login could not succeed under any circumstances.

---

## 7. Files Changed

- No application code modified. The fix was a database migration only.

---

## 8. Fix Applied

```powershell
# Ensure stale DATABASE_URI env var (pointing to Supabase) does NOT redirect
# the migration to production. The stale env var must be removed.
Remove-Item Env:DATABASE_URI -ErrorAction SilentlyContinue

# Apply the pending migration to the local dev database (attendancedashpro_db:55432)
cd backend
alembic upgrade head
```

Output: `Running upgrade c4d5e6f7a8b9 -> a9b8c7d6e5f4, Phase 25.1: refresh-token session persistence`

After fix:
- `alembic current` → `a9b8c7d6e5f4 (head)`
- `\dt refresh_tokens` → `refresh_tokens | table` (exists)
- `POST /api/v1/auth/login` with bad credentials → `401 Unauthorized` with `{"detail":"Incorrect roll number or password"}` and full CORS headers
- Backend health endpoint → `HTTP 200`

No backend restart required — the running backend process (PID 22436) connects
to the same database and the table now exists for the next `INSERT`.

---

## 9. Why the Fix Is Correct

- The `refresh_tokens` table is required by the Phase 25.1 login endpoint
  (auth.py:124). The Alembic migration `a9b8c7d6e5f4` creates it with the
  exact schema expected by the INSERT statement.
- The migration is applied via the project's own Alembic framework — not a
  manual `CREATE TABLE` — preserving the canonical migration history.
- The stale `DATABASE_URI` env var was removed before running the migration,
  ensuring it targeted the local dev DB (55432) and not the Supabase production
  database documented in Phase 26.7.
- No application code, configuration, or architecture was changed.

---

## 10. Remaining Manual Browser Verification Required

The user should test login at `http://localhost:3100/login` with real credentials.
Expected behavior:
- Correct credentials: redirect to `/dashboard`, access token stored in localStorage.
- Incorrect credentials: show "Incorrect roll number or password" (not "Unable to reach the server").
- After login, verify the dashboard loads and data is displayed.

If "Unable to reach the server" still appears, the potential residual cause is
the `NEXT_PUBLIC_API_URL=http://localhost:8080` in `frontend/.env.local`:
`localhost` resolves to both `::1` (IPv6) and `127.0.0.1` (IPv4) on this machine,
but the backend binds only `127.0.0.1:8080` (IPv4). Most browsers try IPv6 first
and fall back to IPv4 (Happy Eyeballs), but inconsistent behavior could produce
intermittent network errors. Changing `frontend/.env.local` to
`NEXT_PUBLIC_API_URL=http://127.0.0.1:8080` (matching the `DEV_API_URL` fallback
in `frontend/src/lib/api.ts` and the `start-dev.ps1` backend bind address) would
eliminate this possibility. The frontend dev server must be restarted for the
change to take effect.