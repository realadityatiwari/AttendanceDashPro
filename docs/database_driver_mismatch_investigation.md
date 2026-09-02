# Database Driver Mismatch Investigation — `psycopg2` — Final Root Cause & Fix

**AttendanceDash Pro · 2026-09-02 · INVESTIGATION → IMPLEMENTATION COMPLETE**

> Investigation and permanent fix for the `InvalidRequestError: The asyncio
> extension requires an async driver to be used. The loaded 'psycopg2' is
> not async.` raised at `backend/app/db/session.py:4`.

---

## 1. Traceback Path

```
uvicorn main.py:440 → config.load_app() → import_from_string("app.main:app")
→ app/main.py:7 import api_router
→ app/api/api.py:2 import auth endpoint
→ app/api/v1/endpoints/auth.py:16 from app.api.dependencies.deps import get_db
→ app/api/dependencies/deps.py:8 from app.db.session import AsyncSessionLocal
→ app/db/session.py:4 engine = create_async_engine(settings.DATABASE_URI, ...)
→ sqlalchemy/ext/asyncio/engine.py:121 AsyncEngine(sync_engine)
→ InvalidRequestError: loaded 'psycopg2' is not async
```

The error originates at `backend/app/db/session.py:4`. No other `create_engine`
or `create_async_engine` call exists in the application source (excluding scripts
and alembic).

---

## 2. Settings Resolution Chain

`app/core/config.py:94` instantiates `Settings()` with:

| Priority | Source | Value |
|---|---|---|
| 1. Class default | `config.py:15` | `postgresql+asyncpg://postgres:postgres@localhost:55432/attendancedash` |
| 2. `.env` file | `backend/.env` | `postgresql+asyncpg://postgres:postgres@localhost:55432/attendancedash` |
| 3. Process env var | `$env:DATABASE_URI` | `postgresql://postgres.zwkdiervvtjalaazscdv:...@aws-0-ap-south-1.pooler.supabase.com:5432/postgres` |

pydantic-settings v2 priority: **init args > env vars > dotenv file > defaults**.
The process-level env var **wins**, overriding both the class default and
`backend/.env`.

---

## 3. Effective `DATABASE_URI` at Runtime

| Component | Value |
|---|---|
| Scheme | `postgresql` (bare — no `+asyncpg` driver suffix) |
| Resolved driver | `psycopg2` (sync) |
| Host | `aws-0-ap-south-1.pooler.supabase.com` |
| Port | `5432` |
| Database | `postgres` |

SQLAlchemy maps bare `postgresql://` to the **sync psycopg2** dialect. When
`create_async_engine` receives this URL, it cannot wrap a sync engine.

---

## 4. The Earlier Fix Attempt (HKCU Cleanup) Was INSUFFICIENT

**What was tried**: `Remove-Item -Path 'HKCU:\Environment' -Name 'DATABASE_URI' -Force`
removed the stale `DATABASE_URI` from the Windows persistent user-level registry.

**Why it did NOT solve the crash**: registry (User + Machine scopes) is indeed
where Windows stores persistent environment variables, and the command correctly
cleaned them. However, removing a registry entry does **NOT** update the
in-memory environment block of already-running processes. The environment block
of a process is snapshotted at creation time and is an in-memory copy. Every
child spawned from that process tree — including `Start-Process` from
`start-dev.ps1`, and even fresh `-NoProfile` child shells — inherits the stale
value from the parent's in-memory environment block, not from the registry.

**Confirmation**: both fresh shells confirmed the stale value persisted:
```
[Environment]::GetEnvironmentVariable('DATABASE_URI','User')    → empty
[Environment]::GetEnvironmentVariable('DATABASE_URI','Machine') → empty
powershell.exe -NoProfile -Command '$env:DATABASE_URI'          → bare Supabase URL
pwsh -NoProfile -Command '$env:DATABASE_URI'                    → bare Supabase URL
```

The value was set at some point (likely during Phase 21D/22.2 Supabase migration
work via `setx` or manual registry edit), baked into the terminal session's
environment block, and survived the registry cleanup because Windows never
propagates registry changes backward to already-running processes.

---

## 5. Origin of the Overriding Env Var

- **Location (original persistent source)**: `HKCU:\Environment\DATABASE_URI`
  (Windows persistent user environment variable, set via `setx` or System
  Properties). Now cleaned.
- **Location (actual active source)**: The in-memory environment block of the
  currently-running terminal/IDE process tree (inherited by all descendants).
- **Likely origin**: Phase 21D/22.2 Supabase session pooler URL used during
  production migration work. The bare `postgresql://` scheme matches the format
  Supabase provides in its dashboard connection strings.
- **Propagation**: `start-dev.ps1` uses `Start-Process` with `-WorkingDirectory
  $backendDir`. `Start-Process` inherits the current shell's environment, which
  includes the stale value from the process tree. No `.vscode/launch.json`,
  `.vscode/settings.json`, PowerShell profile, Windows Terminal profile, VS Code
  `terminal.integrated.env.windows`, or other startup mechanism sets
  `DATABASE_URI`.

---

## 6. Related Investigation Findings

| Check | Result |
|---|---|
| `backend/.env` content | Correct asyncpg URL (localhost:55432/attendancedash) |
| `backend/app/core/config.py` default | Correct asyncpg URL |
| `backend/alembic/env.py` normalization | Only applies to Alembic, not the app runtime |
| `backend/app/db/session.py` | Only one import chain to `settings.DATABASE_URI` |
| `backend/app/db/` directory | Only `session.py` and `base_class.py` — no alternate DB module |
| `Settings` class | Only one: `app/core/config.py:94` singleton |
| Process env `DATABASE_URI` | Stale bare Supabase URL (present) |
| User/Machine registry `DATABASE_URI` | BOTH empty (successfully cleaned) |
| `start-dev.ps1` | Did NOT set `DATABASE_URI`; inherited from shell → **NOW FIXED** |
| PowerShell profiles | None exist (all four `$PROFILE` paths: no files) |
| Windows Terminal `settings.json` | No env vars configured |
| VS Code `settings.json` | No `terminal.integrated.env.windows` or env vars |
| Docker compose files | Set `DATABASE_URI` only in production; not used locally |
| `.vscode/` | No launch.json or settings.json exists |
| `backend/scripts/` | Migration scripts use `DATABASE_URI_SOURCE/TARGET`, not `DATABASE_URI` |
| `psycopg2` in `.venv` | Present; not a bug. The bug is the bare URL scheme routing to it. |
| Fresh `-NoProfile` child shells | Inherit the stale value from the running process tree (proven) |

---

## 7. Final Root Cause

A stale `DATABASE_URI` environment variable (bare `postgresql://` Supabase URL)
was baked into the **in-memory environment block** of the long-lived terminal/IDE
process tree. The earlier HKCU registry cleanup was correct but insufficient:
removing a persistent env var from the registry does NOT mutate the environment
block of already-running processes. Every child process spawned from that tree —
including `Start-Process` from `start-dev.ps1`, and even fresh `-NoProfile`
child shells — inherits the stale value from the parent's in-memory environment.

pydantic-settings v2 precedence (env vars > `.env` file > defaults) then let
the inherited bare `postgresql://` URL win over `backend/.env`'s correct
`postgresql+asyncpg://` URL, routing SQLAlchemy to the sync `psycopg2` dialect.
`create_async_engine` rejects sync drivers → `InvalidRequestError`.

**Why the HKCU-only fix was insufficient**: the HKCU registry is the *persistent
store* for user env vars, read once at process creation. Deleting it does NOT
update the in-memory copy held by every running process in the session.
Windows does not provide a mechanism to retroactively update a running process's
environment block.

---

## 8. Fix Implemented

### Launcher-level env safeguard (`start-dev.ps1`)

The backend `Start-Process` block now saves `$env:DATABASE_URI`, removes it from
the process environment, starts the backend (which inherits a clean environment),
then restores the original value. The backend always resolves the intended local
asyncpg configuration from `backend/.env`, regardless of stale inherited values.

No application-level URL normalization was added. The fix is at the architectural
boundary where the stale value is injected (the launcher → child process
inheritance), not at the point where it is consumed (SQLAlchemy engine creation).

### BOM restoration

The file edit stripped the UTF-8 BOM. PowerShell 5.1 reads BOM-less `.ps1` files
as ANSI (Windows-1252), which garbles the multi-byte UTF-8 box-drawing characters
(─, ✔, ✘) and breaks script parsing. The BOM was restored via explicit
UTF-8-with-BOM encoding.

### Verification

1. With the stale `DATABASE_URI` env var present in the launching shell,
   `.\start-dev.ps1` launched the backend successfully (port 8080 listening).
2. `GET http://127.0.0.1:8080` → HTTP 200 `{"message":"AttendanceDash Pro API is running."}`.
3. `backend_err.log` shows clean startup — no `InvalidRequestError`, no `psycopg2`.
4. Direct Python check with env stripped (replicating the launcher's behavior):
   "scheme=postgresql+asyncpg", "host=localhost", "port=55432", "database=attendancedash".

### Files changed

- `start-dev.ps1` — only file modified (save/remove/restore of `$env:DATABASE_URI`).

---

## 9. Manual Action Remaining (Optional)

The stale `$env:DATABASE_URI` still exists in the current shell session. The
launcher fix makes it harmless for `.\start-dev.ps1`. To fully clear it from
the current session (recommended for cleanliness if running Python directly):

```powershell
Remove-Item Env:DATABASE_URI -ErrorAction SilentlyContinue
```

A new terminal session automatically starts with the clean registry environment
(since User/Machine stores are already empty) and no manual action is needed.