# AttendanceDash Pro — Phase 21D.0: Free Public Beta Deployment Architecture

Status: **COMPLETE & FROZEN** — architecture research, provider selection, and
recommendation. No deployment, no provisioning, no code changes, no commit.

## 1. Phase Status

**COMPLETE & FROZEN** (architecture/readiness assessment only). ₹0/month
architecture selected. No resources created, no secrets added, no deployment.

## 2. Objective

Design a ₹0/month deployment architecture for AttendanceDash Pro v1 Beta
(100–300 normal users) using the current PostgreSQL + FastAPI + JWT + Next.js
stack, without paid VPS, database, domain, or TLS.

## 3. Current Repository Architecture

| Layer | Technology | Version | Runtime Requirement |
|---|---|---|---|
| Frontend | **Next.js** | 16.3.0 | Server (SSR via `output: "standalone"`; no route handlers, middleware, or server actions; all pages are client components; server components only in root layout for metadata/fonts) |
| Backend | **FastAPI** | ≥0.115 | Python 3.13, uvicorn, Dockerfile |
| Database | **PostgreSQL** | 16 | 9.1 MB total (1.12 MB user data); 1 user; 162 attendance records |
| Auth | **JWT** | HS256 | localStorage-based (frontend) + PBKDF2 (backend) |
| PWA | **Phase 13** | — | `public/manifest.json` + `service-worker.js` + icons (static assets) |

**Key architectural fact**: the frontend is fundamentally a client-rendered app
wrapping a FastAPI backend. SSR is used only for the initial HTML shell,
metadata, and font loading. All data flows through client-side `apiFetch`
calls to the backend API. This means the app CAN run as static export if
desired, but the current `output: "standalone"` configuration requires a
Node runtime (Vercel supports this natively).

## 4. Free-Tier Requirements

| Constraint | Value |
|---|---|
| Monthly cost | **₹0** (hard constraint) |
| Users | 100–300 normal beta (not concurrent) |
| HTTPS | Required (provider subdomain acceptable) |
| Domain | Provider-generated URL (no paid domain) |
| Database | Persistent PostgreSQL |
| Backups | Best-effort; no paid-grade DR guarantee |
| CI/CD | Via provider Git integrations |
| Future scaling | Must be portable to paid infrastructure |

## 5. Provider Research (current official data, 2026-08-25)

### Vercel Hobby ($0/month)

| Feature | Limit |
|---|---|
| Function invocations | 1M/month (Fluid compute, 4 Active CPU hours + 360 GB-hr provisioned memory) |
| Fast Data Transfer | 100 GB/month |
| Edge Requests | 1M/month |
| Build & Deploy | Automatic CI/CD from GitHub, instant rollback, env vars, HTTPS |
| Next.js support | **Native** — works with `output: "standalone"` without changes |
| Provider URL | `{project}.vercel.app` (HTTPS automatic) |
| Developer seats | 1 |
| TOS note | Hobby is for personal/non-commercial use; a free student beta qualifies |

### Cloudflare Pages Free ($0/month)

| Feature | Limit |
|---|---|
| Builds | 500/month, 1 at a time, 20 min timeout |
| Files | 20,000 per site, 25 MiB max |
| Functions | Workers-based (counts toward Workers quota) |
| Next.js SSR | **NOT COMPATIBLE** — Pages Free is static-only; SSR requires Workers paid plan |
| Provider URL | `{project}.pages.dev` (HTTPS automatic) |
| Static export | Would require `output: "export"` in `next.config.ts` — a config change explicitly forbidden in 21D.0 |

### Render Free Web Service ($0/month)

| Feature | Limit |
|---|---|
| Compute | 512 MB RAM, 0.1 CPU, shared |
| Instance hours | 750/month (single instance, sleeps after 15 min idle, ~1 min cold start) |
| Bandwidth | 5 GB/month (Hobby workspace) |
| Docker | **Supported** — builds from existing `backend/Dockerfile` |
| HTTPS | Automatic — `{service}.onrender.com` |
| Env vars | Supported (including secret files) |
| Health checks | Supported |
| Custom domains | 2 included |
| Build minutes | 500/month (Hobby) |
| Free Postgres | **30-day limit — NOT suitable** (confirmed by pricing page) |
| Ephemeral FS | No persistent disk (free tier); disks cost $0.25/GB |

### Supabase Free ($0/month)

| Feature | Limit |
|---|---|
| Database | 500 MB (Shared CPU, 500 MB RAM) |
| API requests | Unlimited |
| Monthly active users | 50,000 |
| Egress | 5 GB + 5 GB cached |
| Storage | 1 GB file storage |
| **Automatic backups** | **NOT included** (Pro plan has daily backups) |
| **Pause behavior** | Project pauses after 1 week of inactivity (2 active projects) |
| Provider URL | `{project}.supabase.co` (HTTPS automatic) |
| Custom domains | Not available on Free |
| Connection | Direct + pooler (`{project}.supabase.co:5432` or pooler) |

## 6. Provider Comparison

| Layer | Candidate | ₹0/ Compatible | Key Limitation | Decision |
|---|---|---|---|---|
| Frontend | **Vercel Hobby** | ✅ Yes | TOS (personal/non-commercial — acceptable for free beta); 1M function invocations, 100 GB transfer | **RECOMMENDED** |
| Frontend | Cloudflare Pages Free | ❌ | No SSR support; static export requires config change forbidden in 21D.0 | Rejected |
| Frontend | Render Static Site | ❌ | Static only; no Next.js SSR | Rejected |
| Backend | **Render Free Web Service** | ✅ Yes | 15-min sleep cold start; 5 GB bandwidth; 750 hours/month | **RECOMMENDED** |
| Backend | Railway | ❌ | No free tier (minimum $5/month) | Rejected |
| Backend | Fly.io | ⚠️ | Free allowances but requires credit card and billing | Not recommended for ₹0 |
| Backend | Oracle Cloud free VPS | ⚠️ | Free 2 AMD VMs but requires credit card + complex OCI setup | Not recommended (ops overhead) |
| Backend | Cloudflare Workers | ❌ | Incompatible with FastAPI/Python (V8/JS runtime only) | Rejected |
| Database | **Supabase Free** | ✅ Yes | 500 MB, 50k MAU, 5 GB egress; NO auto backups; pauses after 1 week idle | **RECOMMENDED** |
| Database | Render Postgres Free | ❌ | 30-day expiration | Rejected |

## 7. Recommended Architecture

```text
GitHub
   ↓  (auto-deploy from Git)
Vercel Hobby
   ↓  (Next.js SSR, HTTPS via *.vercel.app)
   ↓  HTTPS
Render Free Web Service
   ↓  (FastAPI, Docker, HTTPS via *.onrender.com)
   ↓  HTTPS/private connection
Supabase Free PostgreSQL
   ↓  (500 MB, 50k MAU, 5 GB egress)
   ↓  No automatic backups (manual pg_dump or GitHub Actions scheduled)
GitHub Actions (CI quality gate only — deployment gate stays disabled)
```

**Provider URLs (no purchased domain):**
- Frontend: `https://attendancedash-pro.vercel.app`
- Backend: `https://attendancedash-api.onrender.com`
- Database: `postgresql://{user}:{password}@db.{project}.supabase.co:5432/postgres`

## 8. Frontend Provider

**Vercel Hobby** ($0/month)

- **Compatibility**: perfect — Next.js 16 SSR with `output: "standalone"` works
  without any code change. No route handlers, middleware, or server actions
  needed. The existing build command (`npm run build`) and default Vercel
  Next.js builder handle the application.
- **Limits for 100–300 users**: 1M function invocations/month, 100 GB
  transfer. Most pages are prerendered as static HTML (client components);
  function invocations are minimal. **Reasonable under normal beta usage.**
- **Deployment method**: GitHub repo → Vercel project (auto-deploy on push).
  `NEXT_PUBLIC_API_URL` set as Vercel environment variable.
- **HTTPS**: automatic via `*.vercel.app` subdomain.
- **No changes needed**: the existing `next.config.ts` (`output: "standalone"`)
  and `package.json` are compatible with Vercel's Next.js builder.

## 9. Backend Provider

**Render Free Web Service** ($0/month)

- **Compatibility**: Dockerfile-based — the existing `backend/Dockerfile`
  builds and runs on Render. The startup command (uvicorn with `--proxy-headers
  --forwarded-allow-ips`) is compatible; Render's TLS termination works with
  the existing CORS/header configuration.
- **Limits**: 512 MB RAM, 0.1 CPU, 750 hours/month, **sleeps after 15 min
  idle → ~1 min cold start** on the next request. 5 GB bandwidth/month (Hobby
  workspace). **Acceptable for a beta — cold starts are a documented limitation.**
- **Cold-start mitigation**: Render pings the service periodically to keep it
  warm? Not natively free. Options: a free uptime monitor (e.g., UptimeRobot)
  pinging the health endpoint every 14 min prevents sleep. This is a 21D.1
  configuration item.
- **Deployment method**: GitHub repo → Render Blueprint or manual web service
  (Docker build). Environment variables from Render Dashboard.
- **HTTPS**: automatic via `*.onrender.com`.
- **No changes needed**: the Dockerfile, requirements.txt, and startup command
  are all compatible.

## 10. Database Provider

**Supabase Free** ($0/month)

- **Storage**: 500 MB — the current database is 9.1 MB. Even with 300 users
  and a full semester of attendance records, the estimate is **well under
  50 MB**. 500 MB is more than adequate.
- **MAU**: 50,000 — the app uses its own JWT auth, not Supabase Auth. The MAU
  limit applies to Supabase Auth features, which are not used. **No issue.**
- **Egress**: 5 GB — the app's data volume is small (API responses are
  compact JSON). **Comfortable under normal usage.**
- **Pause behavior**: the project pauses after 1 week of inactivity. A
  minimal periodic connection (e.g., Render's health check pinging the
  backend, which connects to the DB) prevents this naturally.
- **Backup limitation**: **No automatic backups on Free.** This is a beta
  limitation. See §11.
- **Connection**: Supabase provides a connection string via the pooler
  (`{project}.supabase.co:6543` with PgBouncer) or direct
  (`{project}.supabase.co:5432`). The backend's `DATABASE_URI` env var
  needs to point to this connection string (21D.1 config).

## 11. Backup Strategy

**Beta backup limitation — no paid-grade disaster recovery guarantee.**

Under the ₹0 constraint:
- **Supabase Free does not provide automatic backups** (only Pro has daily
  backups retained for 7 days).
- A manual backup approach (Phase 21D.x): a scheduled GitHub Actions
  workflow that connects to the Supabase DB, runs `pg_dump -Fc`, and stores
  the artifact in a private GitHub repository or as a GitHub Actions
  artifact (90-day retention). This is **not production-grade disaster
  recovery** but provides a basic recovery option.
- The Phase 18C backup container (`deploy/backup/`) is VPS/Legacy — it runs
  inside the Docker compose network and cannot reach Supabase externally.
  It will be superseded by the GitHub Actions approach for the free
  architecture.
- **Expected recovery point objective (RPO)**: up to 24 h (if daily backup
  scheduled). **Recovery time objective (RTO)**: as long as it takes to
  restore from the dump to a new Supabase project.
- **Documented limitation accepted for beta.**

## 12. HTTPS / Domain

All three recommended providers supply HTTPS on their subdomains at no cost:

| Provider | URL | HTTPS method |
|---|---|---|
| Vercel | `https://attendancedash-pro.vercel.app` | Automatic (Let's Encrypt) |
| Render | `https://attendancedash-api.onrender.com` | Automatic (managed TLS) |
| Supabase | `https://db.{project}.supabase.co` | Automatic (managed TLS) |

The backend CORS origin must be set to the Vercel frontend URL.
The frontend `NEXT_PUBLIC_API_URL` must be set to the Render backend URL.
**No paid domain, no DNS purchase, no TLS certificate management required.**

## 13. Security

- **HTTPS**: all three provider URLs have automatic HTTPS.
- **Secrets**: Vercel and Render both support environment variables and
  secret files. JWT secret, database URL, and CORS origin are supplied at
  deployment time, never committed.
- **CORS**: restricted to the Vercel production origin (21D.1 config).
- **Database**: Supabase supports connection via password authentication
  (scram-sha-256). The connection string is a secret env var. The database
  is not publicly exposed beyond the Supabase network (SSL enforced).
- **Admin authorization**: existing `require_admin` (DB-backed) preserved.
- **JWT**: existing HS256 implementation unchanged. Secret injected via
  env var.
- **No credentials in Git**: all three providers inject secrets at runtime.

## 14. Capacity Target

**100–300 normal beta users.** The recommended architecture is adequate for
this range under normal usage:

| Metric | Estimate | Headroom |
|---|---|---|
| Database size (300 users, 1 semester) | ~40–50 MB | 500 MB limit → 10× headroom |
| API requests/day (300 users, 10–20 calls/user) | 3000–6000/day | 10M edge requests/month on Vercel; unlimited on Supabase; Render has no request limit (only bandwidth) |
| Bandwidth (API + frontend) | ~1–3 GB/month | 5 GB limit on Render (bandwidth shared with workspace); 100 GB on Vercel |
| Function invocations (Vercel) | mostly static (prerendered pages) | 1M/month Vercel Functions + 1M Edge Requests |
| Render compute hours | 750/month (always-on = 720h) | 30h buffer; cold start adds negligible time |
| Concurrent users | 10–20 at peak | 0.1 CPU + 512 MB RAM is adequate for lightweight API responses |

**Verdict**: reasonable target under normal beta usage. No bottleneck is
expected to be a hard blocker for 100–300 users.

## 15. Expected Bottlenecks

1. **Render cold start** (~1 min after 15 min idle). A free uptime monitor
   (e.g., UptimeRobot) pinging `https://attendancedash-api.onrender.com/health`
   every 14 minutes can prevent sleep. This is a 21D.1 operational item.
2. **Render 5 GB bandwidth** — if the beta exceeds 5 GB/month, the backend
   would be throttled. For a text/JSON API, 5 GB is generous (millions of
   requests). Frontend assets are served by Vercel (100 GB), not Render.
3. **Supabase pause after 1 week inactivity** — naturally prevented by the
   backend's periodic health checks (which connect to the DB).
4. **No automatic backups** — documented beta limitation.
5. **Render 0.1 CPU** — sufficient for lightweight API operations; a
   computationally expensive operation (e.g., reprocessing 300 users'
   eligibility) could be slow. Acceptable for beta.

## 16. Future Scaling Path

The architecture is designed to be portable to paid infrastructure without
code changes:

| Beta (₹0) | Production growth |
|---|---|
| Vercel Hobby → Vercel Pro ($20/mo) | More bandwidth, team seats, higher limits |
| Render Free → Render Starter ($7/mo) or Standard ($25/mo) | No sleep, 0.5–1 CPU, persistent disk, higher bandwidth |
| Supabase Free → Supabase Pro ($25/mo) | 8 GB database, auto backups, no pause, 100k MAU, custom domain |
| Manual GitHub Actions backup → Supabase Pro daily backups | Automatic 7-day backups |

The application code is provider-agnostic (standard Dockerfile, standard
Next.js, standard PostgreSQL). No provider-specific database features are
used. Migration to a different host or a VPS+Docker-Compose setup (Phase
18A) is straightforward.

## 17. Deployment Artifacts: Reused vs Legacy

| Artifact | Free Architecture | Status |
|---|---|---|
| `backend/Dockerfile` | **Reused** — Render builds from it | Keep |
| `frontend/Dockerfile` | Not used by Vercel (Vercel builds from source) | Keep for future VPS path |
| `docker-compose.prod.yml` | Not used (Vercel/Render/Supabase replace the compose stack) | Keep (VPS legacy path) |
| `deploy/caddy/Caddyfile` | Not used (Vercel + Render provide HTTPS) | Keep (VPS legacy path) |
| `deploy/backup/` | Not used (GitHub Actions backup replaces it) | Keep (VPS legacy path) |
| `.github/workflows/ci.yml` | **Reused** — quality gate; deployment gate stays disabled | Keep |
| `backend/.env.example` | **Reused** — template for production env vars | Keep |
| `deploy/.env.prod.example` | **Reused** — reference for provider env vars | Keep |

## 18. CI/CD

The existing `.github/workflows/ci.yml` quality gate is reused. The
deployment gate (`deploy` job) remains `if: ${{ false }}` (disabled).
Production deployment for the free architecture works through **provider
Git integrations** (Vercel auto-deploys from GitHub main branch; Render
auto-deploys from GitHub main branch). No CI/CD pipeline changes are
required for the beta.

Phase 21D.4 will wire the provider projects and secrets; 21D.5 will
enable the deployment gate.

## 19. Files Created

- `docs/phase_21/phase_21d0_free_beta_architecture.md` — this report

## 20. Files Modified

- `MASTER_ROADMAP.md` — Phase 21D.0 section added
- `implementation_plan.md` — Phase 21D.0 authoritative section
- `task.md` — Phase 21D.0 checklist
- `walkthrough.md` — Phase 21D.0 chronological entry

## 21. Database Mutation

INSERT = 0 · UPDATE = 0 · DELETE = 0 · ALTER = 0 · DROP = 0

## 22. Cloud Resources Created

**ZERO.** No Vercel project, no Render service, no Supabase project created
during this phase. This is a research-only phase.

## 23. Production Deployment

**NOT PERFORMED.**

## 24. Git

Commit: **NONE** · Push: **NONE**

## 25. Next Authorized Slice

**PHASE 21D.1 — Production Configuration Hardening** (create provider
projects, configure secrets, set up environment variables, wire CORS, test
deployment).