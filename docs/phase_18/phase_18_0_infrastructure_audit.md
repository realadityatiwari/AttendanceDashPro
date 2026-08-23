# AttendanceDash Pro — Phase 18.0 Production Infrastructure Audit

Date: 2026-08-23 · Scope: READ-ONLY repository-wide production infrastructure audit · Status: **COMPLETE & FROZEN**

> Read-only audit. No files modified, no deployment, no cloud resources, no
> database mutations, no commit.

## 1. Governance Boundaries

Phase 17 decisions honored: JWT production-secret guard, NO MIGRATION REQUIRED,
verified backup/restore, retention 7 daily / 4 weekly / 3 monthly, rotation and
production runbook deferred to infrastructure. Alembic head confirmed:
**`e1f2a3b4c5d6`** (single head, unchanged, not applied).

## 2. Frontend Audit

| Item | Finding |
|---|---|
| Next.js | 16.3.0 (exact pin); minimal `next.config.ts`; **SSR — requires Node runtime, not static-hostable** |
| React / Node | 19.2.8 / Node 20.9+ required (Next 16); no `engines` field (should be added) |
| Package manager | npm (package-lock.json) |
| Build / start | `npm run build` (15/15 routes PASS) / `npm run start` |
| PWA (Phase 13) | `public/manifest.json`, `service-worker.js`, `public/icons/*.svg` — served by Next runtime |
| Public env | `NEXT_PUBLIC_API_URL` only (client bundle); dev fallback `127.0.0.1:8080` must be overridden in production |
| Auth storage | JWT in localStorage (Phase 16 documented limitation) |
| Verdict | Requires Node SSR host (Vercel or self-hosted Node/Docker) |

## 3. Backend Audit

| Item | Finding |
|---|---|
| Python / FastAPI / Uvicorn | 3.13 / ≥0.115 / ≥0.30; pydantic 2, sqlalchemy 2, asyncpg, alembic |
| Startup | `uvicorn app.main:app`; **no production worker count configured** |
| Health | `GET /health` → 200 JSON (liveness/readiness ready) |
| Env vars | `DATABASE_URI`, `BACKEND_CORS_ORIGINS`, `APP_ENV`, `JWT_*`, `SECURITY_HSTS_ENABLED`, rate-limit vars |
| JWT guard | ✅ production rejects dev/short secrets; error never prints secret |
| CORS | Env-driven explicit origins; must be overridden in production |
| Proxy assumptions | **None** — rate limiter keys on `request.client.host`; requires `--proxy-headers` + trusted proxy boundary |
| Logging | stdout (app/core/logging.py); 500s + auth failures logged |
| Migrations | Alembic reads `DATABASE_URI` from settings (env.py) |
| Verdict | App code production-ready; needs infra wiring (workers, proxy headers, secrets, migrations-on-deploy) |

## 4. PostgreSQL Audit

- Current: `docker-compose.yml` postgres:16, port 55432, named volume `attendancedash_data`
- Alembic: single head `e1f2a3b4c5d6`; URL from env; upgrade/downgrade supported
- Backup: `backup_database.ps1` (pg_dump -Fc via Docker) → `backups/` (gitignored) — verified
- Restore: `restore_database.ps1` (-TestSwitch → isolated container) — verified
- Retention: 7 daily / 4 weekly / 3 monthly documented; automated rotation deferred
- Production: DB must stay private; backend on private network; managed PG or Docker PG on VPS both viable

## 5. Backup + Retention Design (deferred to 18C)

Scheduled creation, 7/4/3 rotation, integrity smoke check, encryption (provider SSE or age/gpg), off-host object storage, failure notification, RPO ≤ 24h, RTO ≤ 30 min. Not implemented in 18.0.

## 6. Security-Sensitive Environment Variables

| Variable | Class |
|---|---|
| `NEXT_PUBLIC_API_URL` | public (client bundle) |
| `DATABASE_URI`, `JWT_SECRET_KEY`, PostgreSQL creds | secret |
| `BACKEND_CORS_ORIGINS`, `APP_ENV`, `JWT_*`, `SECURITY_HSTS_ENABLED`, rate-limit vars | deployment-specific |
| TLS certs, backup/storage creds | secret (later phase) |

Dev defaults relied on today: `DATABASE_URI` (postgres/postgres), CORS localhost, dev JWT default (guarded). All must be overridden in production. **No secrets printed in this report.**

## 7. Docker / Container Audit

- No Dockerfiles for frontend or backend; only dev `docker-compose.yml` (PostgreSQL).
- No reverse-proxy config, healthchecks, restart policies, or resource limits.
- Needed: backend + frontend Dockerfiles, production compose, reverse proxy, healthchecks, restart policies, private networking.

## 8. Hosting Options

| Option | Frontend | Backend | PostgreSQL | Cost | Complexity | Fit |
|---|---|---|---|---|---|---|
| A. Vercel + Fly/Railway + Neon | Vercel | container | managed | ~$10–25/mo | Low | High |
| B. **Single VPS (Docker)** | Docker Next.js | Docker FastAPI | Docker PG | ~$6–12/mo | Medium | **High (recommended)** |
| C. All-managed | Vercel | Render | Supabase | ~$15–30/mo | Lowest | High |
| D. Full serverless | Vercel | unsuitable (asyncpg) | managed | varies | High | Low |

**Recommended: Option B — single small VPS with Docker Compose.** Fixed cost,
Postgres stays private on the same host, PWA/SSR works, matches the existing
Docker-based dev workflow, simplest ops for a student-scale app. Option A is the
managed fallback.

## 9. Production Environment Contract

| Variable | Component | Required | Secret? | Example/Placeholder | Purpose |
|---|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Frontend | ✅ | No | `https://app.example.com` | Client API base URL |
| `DATABASE_URI` | Backend | ✅ | Yes | `postgresql+asyncpg://app:•••@db:5432/attendancedash` | DB connection |
| `JWT_SECRET_KEY` | Backend | ✅ | Yes | `<64-hex random>` | Token signing |
| `JWT_ALGORITHM` | Backend | ✅ | No | `HS256` | Algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Backend | ✅ | No | `480` | Token lifetime |
| `BACKEND_CORS_ORIGINS` | Backend | ✅ | No | `["https://app.example.com"]` | Allowed origins |
| `APP_ENV` | Backend | ✅ | No | `production` | Env mode + JWT guard |
| `SECURITY_HSTS_ENABLED` | Backend | ✅ | No | `true` | HSTS (HTTPS only) |
| `LOGIN/REGISTER_*` limits | Backend | optional | No | defaults | Rate limiting |
| `POSTGRES_USER/PASSWORD/DB` | DB | ✅ | Yes | `<strong creds>` | DB credentials |

`.env.example` files exist for both components; Phase 18 implementation should
extend them with production placeholders (no real secrets).

## 10. Recommended Topology

```text
                    Internet
                       │ HTTPS :443 (Caddy/nginx, TLS termination)
                ┌──────▼──────────┐
                │ VPS — Docker    │  private network
                │  ┌───────────┐  │  :3000
                │  │ Next.js   │◄─┼── proxy /app/*
                │  │ (SSR+PWA) │  │
                │  └─────┬─────┘  │
                │        │ :8000  │  HTTPS /api/* → FastAPI
                │  ┌─────▼─────┐  │
                │  │ FastAPI   │  │
                │  └─────┬─────┘  │  private:5432
                │  ┌─────▼─────┐  │
                │  │ PostgreSQL│  │  (no public port)
                │  └───────────┘  │
                └─────────────────┘
Backup path: PostgreSQL → pg_dump -Fc (daily) → encrypted → off-host storage
```

Requirements: DB never public; backend→DB over private network; migrations as a
one-shot pre-deploy step (Phase 18D); `--proxy-headers`/trusted proxy for real
client IPs (rate limiter); production CORS + APP_ENV + secrets via env/secret
manager.

## 11. Phase 18 Implementation Plan

- **18A** — Dockerfiles + production compose (backend, frontend, DB, reverse proxy, healthchecks, restart policies, private networking)
- **18B** — Environment & secret management + extended `.env.example` contracts + proxy-header trust
- **18C** — Backup automation (rotation 7/4/3, encryption, off-host storage, notification) + production runbook
- **18D** — Deployment verification (migrations-on-deploy, health checks, CORS/HTTPS verification)

## 12. Database Mutation

**ZERO.** No SQL executed beyond read-only Alembic head confirmation.

## 13. Git

**No commit made. No push performed.** Frozen systems untouched; no browser testing.
