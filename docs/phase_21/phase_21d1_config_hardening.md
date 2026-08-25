# AttendanceDash Pro — Phase 21D.1: Production Configuration Hardening

Status: **COMPLETE & FROZEN** — repository prepared for the ₹0 beta
architecture (Vercel + Render + Supabase). No deployment, no cloud resources,
no production database, no secrets created, no commit.

## 1. Objective

Harden the repository's configuration so the approved ₹0 public-beta
architecture (Vercel Hobby → Next.js → Render Free → FastAPI → Supabase
Free PostgreSQL) can be provisioned in Phase 21D.2 without code changes or
security regressions. Configuration only — no deployment.

## 2. Configuration Baseline (read-only inspection)

| Area | Finding |
|---|---|
| `frontend/src/lib/api.ts` | `NEXT_PUBLIC_API_URL \|\| "http://127.0.0.1:8080"` — **production could silently fall back to localhost** (defect, fixed) |
| `frontend/next.config.ts` | `output: "standalone"` — SSR preserved; Vercel-compatible (no middleware/route handlers/server actions to break) |
| `backend/Dockerfile` | Hardcoded `--port 8000` + healthcheck on `127.0.0.1:8000` — **ignored Render's PORT** (defect, fixed) |
| `backend/app/core/config.py` | Phase 17/18B production guards already present (JWT secret, DB host, CORS localhost rejection) ✅ |
| `backend/app/main.py` | CORS env-driven; global 500 handler; security headers; `GET /health` (no auth, no DB) ✅ |
| `backend/alembic/env.py` | Reads `settings.DATABASE_URI` — provider-agnostic, Supabase-compatible ✅ |
| `backend/app/db/session.py` | Standard `create_async_engine(settings.DATABASE_URI)` — portable ✅ |
| Env files | `.env`, `.env.local`, `deploy/.env.prod` all gitignored; only `.env.example` files tracked ✅ |
| Health endpoint | `GET /health` → 200 `{"status":"ok"}` — no auth, no DB, no secrets — ideal for Render health checks ✅ |

## 3. Production Environment Contract

### A. Frontend — public variables

| Variable | Consumer | Required | Secret | Example (prod) | Dev source | Provider | Browser-safe |
|---|---|---|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | `api.ts` | ✅ | No (public by design) | `https://your-api.onrender.com` | `http://127.0.0.1:8080` | Vercel env var | Yes (inlined at build) |

### B. Backend — secret variables

| Variable | Consumer | Required | Secret | Example (prod) | Dev source | Provider |
|---|---|---|---|---|---|---|
| `DATABASE_URI` | `db/session.py`, `alembic/env.py` | ✅ | **Yes** | `postgresql+asyncpg://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres?ssl=require` | `postgresql+asyncpg://postgres:postgres@localhost:55432/attendancedash` | Render (secret env) |
| `JWT_SECRET_KEY` | `config.py`, `security.py` | ✅ | **Yes** | 64-char random hex | dev default (guarded) | Render (secret env) |
| `BACKEND_CORS_ORIGINS` | `main.py` (CORS) | ✅ | No (value is public origin) | `["https://your-project.vercel.app"]` | localhost:3100 | Render env |
| `APP_ENV` | `config.py` | ✅ | No | `production` | `development` | Render env |
| `JWT_ALGORITHM` | `config.py` | optional | No | `HS256` | `HS256` | Render env |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `config.py` | optional | No | `480` | `480` | Render env |
| `UVICORN_WORKERS` | Dockerfile CMD | optional | No | `1` | `1` | Render env |
| `SECURITY_HSTS_ENABLED` | `main.py` | optional | No | `true` (Render+Vercel HTTPS) | `false` | Render env |
| `PORT` | Dockerfile CMD | Render-supplied | No | Render injects | `8000` (default) | Render auto |

### C. Backend — non-secret configuration

All in section B marked "No" — these are deployment-specific values, not
secrets. They are safe in env vars but must not be embedded in client code.

## 4. Frontend Configuration

- **Change**: `frontend/src/lib/api.ts` now throws at module load if
  `NODE_ENV=production` and `NEXT_PUBLIC_API_URL` is missing or points to
  localhost/127.0.0.1/0.0.0.0. **No more silent localhost fallback in
  production.**
- **Vercel compatibility confirmed**: `output: "standalone"` is SSR-compatible
  and works with Vercel's Next.js builder. No middleware/route handlers/server
  actions exist, so nothing breaks on Vercel. **No `vercel.json` needed** —
  the framework auto-detects Next.js; the standalone output is handled by
  Vercel's builder.

## 5. Backend Configuration

- **Change**: `backend/Dockerfile` CMD now uses `--port ${PORT:-8000}` and the
  healthcheck reads `PORT` (default 8000). Render's injected `PORT` is honored;
  local Docker Compose still uses 8000. **Verified** by running the image with
  `PORT=18080` — `/health` returned 200 on that port.
- Existing Phase 17/18B production guards (JWT secret, DB host, CORS
  localhost) remain authoritative. No changes to business logic, JWT
  semantics, or auth.

## 6. CORS Configuration

- Already env-driven via `BACKEND_CORS_ORIGINS` (list).
- Development: `["http://localhost:3100","http://127.0.0.1:3100"]`
- Production: exact Vercel origin, e.g. `["https://your-project.vercel.app"]`
  — supplied via Render env var; the production guard rejects localhost
  origins when `APP_ENV=production`.
- No `*`, no unrestricted origins. Credentials (`allow_credentials=True`)
  preserved; explicit origins only.

## 7. Database Configuration

- Standard SQLAlchemy `create_async_engine(settings.DATABASE_URI)` with
  `asyncpg` — fully portable to Supabase or any PostgreSQL.
- Supabase connection: `postgresql+asyncpg://...@...:5432/postgres?ssl=require`
  (Session Pooler port 5432; asyncpg-native `ssl=require` — `sslmode=` is NOT
  a valid asyncpg keyword and would crash; verified against installed
  asyncpg 0.31.0 / SQLAlchemy 2.0.52).
- Alembic `env.py` reads `settings.DATABASE_URI` — migrations run against
  whatever DB the env points to. **No provider-specific dependency added.**
- Development DB untouched; production DB not created.

## 8. Migration Strategy (migration-on-deploy contract)

- Desired sequence: migrate → then serve.
- **Recommended for Render single-instance beta**: run `alembic upgrade head`
  as a **one-shot pre-deploy step** (Render Blueprint `preDeployCommand` or a
  manual one-time command after the first service deploy), NOT inside the
  container start command. Rationale:
  - Render Free is single-instance → no multi-instance migration race.
  - Keeping migrations out of the CMD means a migration failure does not
    incorrectly start the app (the deploy fails visibly).
  - Health checks (`/health`, no DB) can run before/independent of migrations
    without misleading results.
- Documented in `render.yaml` blueprint comments for Phase 21D.2 wiring.

## 9. Secret Handling

- Audit result: no real secrets in tracked files. The only tracked occurrence
  of the dev JWT default is in `config.py` (the guarded default),
  `.env.example` files, and the CI integrity check (which greps for it) — all
  legitimate.
- `frontend/.env.local` (NEXT_PUBLIC_API_URL dev value) — gitignored.
- `backend/.env` (DATABASE_URI dev value) — gitignored.
- `deploy/.env.prod` — gitignored.
- No credential rotation required for tracked files (nothing leaked).
- Production secrets will be created ONLY in provider dashboards during
  Phase 21D.2 — never committed.

## 10. Health Check

- `GET /health` — existing, unauthenticated, no DB access, returns
  `{"status":"ok"}`. **Reused** for Render's `healthCheckPath: /health`.
  No duplicate health system created.

## 11. Render Configuration

- `render.yaml` blueprint created (provider-native):
  - Service `attendancedash-api`, runtime `docker`, free plan
  - `dockerContext: ./backend`, `dockerfilePath: ./backend/Dockerfile`
  - `healthCheckPath: /health`
  - Env vars: `APP_ENV=production`, `BACKEND_CORS_ORIGINS` (Vercel origin
    placeholder), `JWT_ALGORITHM=HS256`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=480`,
    `UVICORN_WORKERS=1`, `SECURITY_HSTS_ENABLED=true`;
    `DATABASE_URI` + `JWT_SECRET_KEY` marked `sync: false` (secret — set in
    Render dashboard).
  - `FORWARDED_ALLOW_IPS` intentionally left at Dockerfile default
    (`127.0.0.1`) — the rate limiter sees Render's proxy IP for all clients
    (coarse but secure; no spoofable X-Forwarded-For). A precise Render proxy
    CIDR may be set in 21D.2 if Render documents one.
- **PORT handling fixed** in Dockerfile (verified on `18080`).

## 12. Vercel Configuration

- No `vercel.json` created — Next.js auto-detection + existing
  `next.config.ts` are sufficient. No Vercel-specific app logic added.
- `NEXT_PUBLIC_API_URL` will be set in the Vercel project dashboard during
  21D.2 (build-time public variable).

## 13. GitHub / CI Configuration

- `.github/workflows/ci.yml` unchanged; deployment gate remains `if: false`.
- Vercel and Render both support Git auto-deploy independently — preferred
  over a custom deployment workflow. CI remains a quality gate only.
- 21D.2 will: create the provider projects, set env vars/secrets, and rely on
  provider Git integrations for deploy. CI deploy gate stays disabled until
  Phase 21D.5 (or operator decision).

## 14. VPS/Caddy Legacy Boundary

- `docker-compose.prod.yml`, `deploy/caddy/Caddyfile`, `deploy/backup/`,
  `frontend/Dockerfile` — **preserved** for the future paid/VPS path.
- **No application code depends on Caddy or Docker Compose** — verified:
  `main.py` has no proxy coupling; CORS/env are provider-agnostic.
- These artifacts become VPS-legacy infrastructure for the free architecture;
  nothing is deleted in 21D.1.

## 15. Security Review

| Check | Result |
|---|---|
| CORS production default | Env-driven exact origin; localhost rejected in production ✅ |
| JWT secret source | Env var; dev default rejected in production ✅ |
| JWT expiration | 480 min (8h) default, env-overridable ✅ |
| Debug mode | No debug flag exposed; global 500 handler returns generic message ✅ |
| Secret leakage | None in tracked files; error paths return generic messages ✅ |
| DB credentials | `DATABASE_URI` is a Render secret env var ✅ |
| Frontend/backend URL separation | `NEXT_PUBLIC_API_URL` (frontend) vs `DATABASE_URI` (backend) — no cross-exposure ✅ |
| HTTPS assumptions | HSTS opt-in (`SECURITY_HSTS_ENABLED`); Render+Vercel both HTTPS ✅ |
| Admin role resolution | DB-backed `require_admin` unchanged ✅ |
| Token handling | JWT in localStorage (existing architecture); `apiFetch` attaches Bearer ✅ |

## 16. Files Created

| File | Reason |
|---|---|
| `render.yaml` | Provider-native Render blueprint (docker build, health path, env placeholders, secret markers) |

## 17. Files Modified

| File | Change |
|---|---|
| `frontend/src/lib/api.ts` | Production guard: refuse localhost/absent `NEXT_PUBLIC_API_URL` when building for production |
| `backend/Dockerfile` | `--port ${PORT:-8000}` + healthcheck reads `PORT` — Render compatibility, Compose default preserved |
| `frontend/.env.example` | Production contract documented (Vercel/Render URLs) |
| `backend/.env.example` | Full production contract: Supabase DATABASE_URI shape, CORS, PORT, HSTS |
| Governance (4 docs) | 21D.1 status + records |

## 18. Frozen Areas Confirmed Untouched

- Attendance/eligibility/calendar/event/quiz engines — untouched.
- Authentication architecture, JWT semantics, `require_admin`, UserRole —
  untouched.
- DB schema, models, migrations — untouched (no new migration).
- Frontend routes/pages/PWA — untouched.
- Phase 21A.1 cleanup result — untouched.

## 19. Verification Performed

| Check | Result |
|---|---|
| `npx tsc --noEmit` | ✅ PASS |
| `python -m compileall backend/app backend/alembic` | ✅ PASS |
| `docker build backend/Dockerfile` | ✅ PASS |
| Runtime PORT test (`PORT=18080` → `/health` 200) | ✅ PASS |
| Secret-pattern scan (tracked files) | ✅ only legit (config default, examples, CI grep) |
| `git diff --check` | ✅ PASS |
| Render blueprint YAML | ✅ valid structure (placeholder env only) |

## 20. Database Mutation

INSERT = 0 · UPDATE = 0 · DELETE = 0 · ALTER = 0 · DROP = 0

## 21. Cloud Resources Created

**ZERO** (no Vercel project, no Render service, no Supabase project)

## 22. Production Deployment

**NOT PERFORMED**

## 23. Production Database

**NOT CREATED**

## 24. Production Secrets

**NOT CREATED**

## 25. Git

Commit: **NONE** · Push: **NONE**

## 26. Known Remaining Risks

1. Render cold start (~1 min after 15 min idle) — acceptable beta limitation;
   an uptime monitor pinging `/health` can mitigate (21D.2 operator option).
2. Supabase Free has no automatic backups — documented beta limitation;
   manual `pg_dump` via scheduled GitHub Actions is a possible 21D.3 item.
3. Rate limiter sees Render's proxy IP (coarse, single bucket) — safe, not
   precise; a documented Render proxy CIDR would improve this (21D.2).
4. `NEXT_PUBLIC_API_URL` guard throws at runtime (browser module load) if
   misconfigured — intended fail-loudly behavior; must be set correctly in
   Vercel during 21D.2.

## 27. Next Authorized Slice

**PHASE 21D.2 — PROVIDER PROJECT PROVISIONING & ENVIRONMENT WIRING** (create
Vercel/Render/Supabase projects, set secrets/env vars, first deployment
test).
