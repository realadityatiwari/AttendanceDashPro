# AttendanceDash Pro — Phase 21D.2: Production Database Connection Compatibility Audit

Status: **COMPLETE** — pre-migration audit. No production database accessed,
no secrets accessed/generated, no mutation performed.

## 1. Audit Objective

Before any mutation of the new Supabase production database, verify the
repository's PostgreSQL connection handling is compatible with:

- SQLAlchemy async engine + asyncpg
- Supabase Session Pooler (port 5432, user `postgres.<ref>`)
- Render Free Web Service
- SSL/TLS-required PostgreSQL connectivity

## 2. Current Connection Architecture

```text
FastAPI (uvicorn)
  └─ SQLAlchemy 2.0.52 async engine (create_async_engine, session.py)
       └─ asyncpg 0.31.0 (postgresql+asyncpg:// dialect)
            └─ DATABASE_URI from app.core.config.Settings (env-driven)
                 └─ Render env var → Supabase Session Pooler (port 5432, SSL required)

Alembic (env.py)
  └─ reads settings.DATABASE_URI → same dialect/URL (async_engine_from_config)
```

| Component | File | Role |
|---|---|---|
| Config | `backend/app/core/config.py` | `DATABASE_URI` from env; production guard rejects localhost hosts |
| Engine | `backend/app/db/session.py` | `create_async_engine(settings.DATABASE_URI, echo=False, future=True)` |
| Alembic | `backend/alembic/env.py` | `config.set_main_option("sqlalchemy.url", settings.DATABASE_URI)` |
| Dockerfile | `backend/Dockerfile` | runs migrations as a separate one-shot step; app starts after |
| Blueprint | `render.yaml` | `DATABASE_URI` marked `sync: false` (secret) |

## 3. Exact Findings

### A. DATABASE_URI format the application expects

`postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>?<query-params>`

- Driver: `postgresql+asyncpg` (SQLAlchemy asyncpg dialect)
- Host/port/user/db: fully env-driven via `DATABASE_URI`
- Query params: passed **verbatim** to `asyncpg.connect(**kwargs)`

### B. SQLAlchemy postgresql+asyncpg dialect usage — CORRECT

- `backend/app/db/session.py:4-8` uses `create_async_engine(settings.DATABASE_URI)`
  with the standard `postgresql+asyncpg://` dialect.
- No custom pool class, no unsupported options.
- `backend/alembic/env.py:25` uses the same URL via `async_engine_from_config`
  (Alembic and app share identical connection semantics).

### C. SSL handling — **CONFIGURATION DEFECT FOUND (documentation only)**

**Verified against installed drivers (SQLAlchemy 2.0.52, asyncpg 0.31.0):**

- `asyncpg.connect()` signature accepts `ssl=` (and `direct_tls=`), **NOT
  `sslmode=`** — `sslmode` is only parsed when asyncpg receives a raw DSN
  string, which SQLAlchemy does not use.
- SQLAlchemy's asyncpg dialect `create_connect_args()` does
  `opts.update(url.query)` — every URL query param becomes an
  `asyncpg.connect()` keyword.
- Therefore `?sslmode=require` → `asyncpg.connect(sslmode="require")` →
  **`TypeError: unexpected keyword argument 'sslmode'`** at connect time.
- The correct asyncpg-native form is **`?ssl=require`** (asyncpg accepts
  `ssl` as bool / SSLContext / string: `'require'`, `'verify-ca'`,
  `'verify-full'`, etc.).

**Files that previously documented `?sslmode=require` (now corrected):**
- `backend/.env.example` (production DATABASE_URI comment)
- `docs/phase_21/phase_21d1_config_hardening.md` (env contract + DB section)
- `docs/phase_21/phase_21d2_provisioning_runbook.md` (Supabase init steps)

**No application code needed changing** — the URL is env-driven; only the
documented contract was wrong.

### D. Supabase Session Pooler (port 5432) compatibility — COMPATIBLE

- The user's stated Session Pooler connection (host `aws-0-ap-south-1.pooler.supabase.com`,
  port 5432, user `postgres.<ref>`, db `postgres`) parses correctly through
  SQLAlchemy's asyncpg dialect (verified: host/port/user/db all resolved).
- SSL is mandatory on Supabase; `?ssl=require` satisfies it.
- **Port 5432** is the Session Pooler (PgBouncer session-mode) endpoint.

### E. PgBouncer / prepared-statement compatibility — NO CHANGE REQUIRED

- Supabase **Session Pooler** runs PgBouncer in **session mode**: each client
  connection is pinned to one server connection for the session, so asyncpg's
  server-side prepared statements remain valid.
- SQLAlchemy's asyncpg dialect implements `prepared_statement_cache_size`
  (default 100) — compatible with session-mode PgBouncer.
- **The transaction pooler (port 6543)** would require
  `?pgbouncer=true` and possibly `prepared_statement_cache_size=0` — but the
  chosen architecture uses the Session Pooler (5432), so **no adjustment is
  needed**. This is documented in the runbook.

### F. Alembic compatibility — COMPATIBLE

- `alembic/env.py` reads `settings.DATABASE_URI` (same URL as the app).
- Migrations run with the same `postgresql+asyncpg` dialect and the same SSL
  behavior. Verified: Alembic head `e1f2a3b4c5d6` single-head, chain intact.
- Alembic `alembic.ini` has a dev fallback URL, but `env.py` overrides it —
  production migrations will target the Supabase URL.

### G. Render environment — SAFE

- `render.yaml` defines `DATABASE_URI` with `sync: false` (secret entered in
  the Render dashboard, never committed).
- The Dockerfile runs the app after the one-shot migration step; `PORT` is
  platform-provided.
- Render's HTTPS + env-var injection provides a safe path for the secret
  connection URL.

## 4. SQLAlchemy/asyncpg Compatibility Conclusion

**COMPATIBLE** — the dialect/engine/URL plumbing is correct. The only defect
was the documented `?sslmode=` parameter, which asyncpg rejects; corrected to
`?ssl=require`.

## 5. SSL Conclusion

Use **`?ssl=require`** in `DATABASE_URI` for Supabase. `?sslmode=` is NOT a
valid asyncpg keyword and would fail at connect. Local development does not
need an SSL param (Docker PostgreSQL, no TLS).

## 6. Supabase Session Pooler Conclusion

COMPATIBLE as configured (port 5432, session-mode PgBouncer, `?ssl=require`).
No pool/prepared-statement changes required.

## 7. PgBouncer / Prepared-Statement Conclusion

Session-mode PgBouncer supports prepared statements — SQLAlchemy asyncpg
default (`prepared_statement_cache_size=100`) is safe. The transaction pooler
(6543) would need `?pgbouncer=true` / cache tuning, but it is not the chosen
endpoint.

## 8. Alembic Compatibility Conclusion

COMPATIBLE — same URL/dialect/SSL as the app; head `e1f2a3b4c5d6` verified.

## 9. Render Compatibility Conclusion

COMPATIBLE — `DATABASE_URI` secret via `sync: false`, migration as one-shot
pre-deploy step, `PORT` platform-provided.

## 10. Files Inspected

- `backend/app/core/config.py`
- `backend/app/db/session.py`
- `backend/alembic/env.py`
- `backend/alembic.ini`
- `backend/requirements.txt`
- `backend/Dockerfile`
- `render.yaml`
- `backend/.env.example`
- `frontend/.env.example`
- `docs/phase_21/phase_21d1_config_hardening.md`
- `docs/phase_21/phase_21d2_provisioning_runbook.md`
- Installed driver sources: SQLAlchemy `asyncpg.py` dialect, asyncpg
  `connect_utils.py` (SSLMode parsing)

## 11. Files Changed

| File | Change |
|---|---|
| `backend/.env.example` | DATABASE_URI production comment: `?sslmode=require` → `?ssl=require`, port 6543 → 5432 |
| `docs/phase_21/phase_21d1_config_hardening.md` | Same correction in the env contract table + DB section |
| `docs/phase_21/phase_21d2_provisioning_runbook.md` | Same correction in Supabase/Alembic steps |
| `docs/phase_21/phase_21d2_database_connection_audit.md` | NEW — this audit |

## 12. Verification Performed

| Check | Result |
|---|---|
| `asyncpg.connect()` signature — `sslmode` absent, `ssl` present | ✅ (confirmed defect root cause) |
| `create_connect_args()` with `?sslmode=require` — flows verbatim | ✅ (would crash) |
| `create_connect_args()` with `?ssl=require` — `ssl='require'` kwarg | ✅ PASS |
| Full Session Pooler URL parse (host/port/user/db/ssl) | ✅ PASS |
| `python -m compileall backend/app backend/alembic` | ✅ PASS |
| Alembic head single `e1f2a3b4c5d6` | ✅ PASS |
| `git diff --check` | ✅ PASS |

**No connection to any database was made.** All engine/URL checks were
construction-only with a REDACTED placeholder password.

## 13. Database Safety

Application/dev DB:
INSERT = 0 · UPDATE = 0 · DELETE = 0 · ALTER = 0 · DROP = 0

Production DB:
**NOT ACCESSED · NOT MIGRATED · NOT MUTATED**

## 14. Secrets

- **NO secrets were accessed or generated** in this audit.
- Placeholder password `REDACTED` used in all connection-string examples.
- The real Supabase password remains known only to the operator; it must be
  entered in the Render dashboard (never committed).

## 15. Next Authorized Action

Proceed with the 21D.2 operator provisioning runbook (already prepared):
1. Create the Supabase project (Session Pooler, port 5432).
2. Run `alembic upgrade head` with `?ssl=require` in `DATABASE_URI`.
3. Provision Render + wire env vars; verify `/health`.
4. Provision Vercel; wire `NEXT_PUBLIC_API_URL`; set Render CORS.
5. Verify connectivity.
