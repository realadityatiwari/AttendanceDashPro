# AttendanceDash Pro — Phase 21D.2: Provider Provisioning & Environment Wiring

Status: **BLOCKED — provider access unavailable (operator action required)**
No provider resources created. No deployment. No production database. No
secrets created. No fabricated project IDs, URLs, or credentials.

## 1. Phase Objective

Provision the three approved free-tier providers (Vercel Hobby, Render Free
Web Service, Supabase Free PostgreSQL), wire environment variables, initialize
a NEW production database schema (Alembic), and verify minimal connectivity.

## 2. Provisioning Blocked — Exact Blocker

| Blocker | Evidence |
|---|---|
| **No Vercel access** | `vercel` CLI not installed; no `VERCEL_TOKEN` in environment; no `.vercel/` state |
| **No Render access** | `render` CLI not installed; no `RENDER_API_KEY` in environment; no `.render/` state |
| **No Supabase access** | `supabase` CLI not installed; no `SUPABASE_ACCESS_TOKEN` in environment; no `supabase/` config |
| **No GitHub automation access** | `gh` CLI not installed; no `GH_TOKEN` |

All three providers require either an interactive browser login (account
creation + OAuth) or an operator-created API token. This is an **operator
action** — the coding agent has no legitimate path to create provider
accounts or obtain tokens on the user's behalf.

**Per phase rule:** when provider authentication is unavailable, do NOT invent
success. Record the blocker and the exact manual actions instead.

## 3. What Is Already Prepared (Phase 21D.1, repository-ready)

| Item | Location | Ready |
|---|---|---|
| Render blueprint | `render.yaml` | ✅ (docker build, healthCheckPath, env placeholders, secret markers) |
| Backend Dockerfile (PORT-aware) | `backend/Dockerfile` | ✅ (`--port ${PORT:-8000}`, healthcheck reads PORT) |
| Frontend production URL guard | `frontend/src/lib/api.ts` | ✅ (refuses localhost/missing in production) |
| Production env contract | `docs/phase_21/phase_21d1_config_hardening.md` | ✅ |
| Env examples | `frontend/.env.example`, `backend/.env.example` | ✅ |
| Migration-on-deploy contract | 21D.1 report §8 | ✅ |

## 4. Operator Provisioning Runbook (manual steps, in deployment order)

### Step 1 — Supabase Free project

1. Sign in at https://supabase.com → New project.
2. Plan: **Free**. Project name: `attendance-dash-beta`.
3. Region: choose **South Asia / India** if listed (e.g. `ap-south-1`
   Mumbai); otherwise nearest available (e.g. `ap-southeast-1` Singapore) —
   documented decision: closest to target users.
4. Database password: generate a strong random one (do not reuse any dev
   password). Record it in the operator's password manager only.
5. Note the **project reference** (e.g. `abcdefghijklmnopqrst`).
6. **Do not** enable any paid add-ons, backups, or compute upgrades.
7. Copy the connection string from Settings → Database → Connection string →
   **Session pooler** (port 6543, `?sslmode=require`).

### Step 2 — Initialize production schema (Alembic)

1. Export the pooler URL (with `+asyncpg` driver):
   `postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres?sslmode=require`
2. From `backend/`:
   ```
   DATABASE_URI=<url above> python -m alembic upgrade head
   ```
3. Expected: migration chain applies to head `e1f2a3b4c5d6`; only schema +
   `alembic_version` rows created. No application data.
4. Verify the target is Supabase (not the local dev DB) before running.

### Step 3 — Render Free Web Service

1. Sign in at https://render.com → New → Web Service → connect the GitHub
   repo (or use Blueprint `render.yaml` via New → Blueprint).
2. Plan: **Free**. Service name: `attendancedash-api`.
3. Build: Docker (uses `./backend/Dockerfile`).
4. Health check path: `/health`.
5. Render injects `PORT` automatically.

### Step 4 — Render environment variables (in Render dashboard)

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URI` | Supabase pooler URL (secret) |
| `JWT_SECRET_KEY` | **newly generated** random 64-hex (secret; never commit/reuse) |
| `JWT_ALGORITHM` | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `480` |
| `BACKEND_CORS_ORIGINS` | exact Vercel URL — set AFTER Vercel exists (Step 6) |
| `UVICORN_WORKERS` | `1` |
| `SECURITY_HSTS_ENABLED` | `true` |
| `PORT` | platform-provided (do not set) |

Generate the JWT secret with:
`python -c "import secrets; print(secrets.token_hex(32))"` — never print it
into the report/repo.

### Step 5 — Verify Render `/health`

`curl https://<service>.onrender.com/health` → HTTP 200 `{"status":"ok"}`.
Record the actual Render HTTPS URL.

### Step 6 — Vercel Hobby project

1. Sign in at https://vercel.com → Add New → Project → import the GitHub
   repo. Framework auto-detected: Next.js. Root: `frontend/`.
2. Plan: **Hobby**.
3. Set env var (Production/Preview/Development):
   `NEXT_PUBLIC_API_URL=https://<render-service>.onrender.com`
   (the real Render URL from Step 5).
4. No backend secrets go in Vercel. Only `NEXT_PUBLIC_API_URL`.
5. Deploy → record the actual Vercel HTTPS URL (`https://<project>.vercel.app`).

### Step 7 — Wire Render CORS to the real Vercel URL

In Render dashboard, update:
`BACKEND_CORS_ORIGINS=["https://<vercel-project>.vercel.app"]`
(exact origin; no wildcard, no localhost). Restart/redeploy Render.

### Step 8 — Minimal connectivity verification

1. `GET https://<render>.onrender.com/health` → 200.
2. `POST https://<render>.onrender.com/api/v1/auth/login` (invalid creds) →
   401 (proves the API + DB path initializes without leaking).
3. Vercel build passes with the real `NEXT_PUBLIC_API_URL` (no localhost
   fallback; the 21D.1 guard enforces this).
4. No data seeded; no dev data imported.

## 5. Free-Tier Guardrail

All three providers must remain on Free plans. Do NOT accept paid upgrades,
paid database compute, paid backups, domains, TLS purchases, or observability
add-ons. If a provider insists on payment, STOP and report.

## 6. Environment Wiring Reference (from 21D.1 contract)

See `docs/phase_21/phase_21d1_config_hardening.md` §3 for the authoritative
production environment contract (frontend public / backend secret / backend
config).

## 7. Frozen Systems

No application, engine, schema, migration, auth, or model changes were made.
This phase made no code changes at all.

## 8. Files Created

- `docs/phase_21/phase_21d2_provisioning_runbook.md` (this document)

## 9. Files Modified

- Governance: `MASTER_ROADMAP.md`, `implementation_plan.md`, `task.md`,
  `walkthrough.md` (21D.2 BLOCKED record)

## 10. Verification Performed

| Check | Result |
|---|---|
| Provider CLI availability (vercel/render/supabase/gh) | ❌ none installed |
| Provider tokens in environment | ❌ none |
| Provider state dirs (`~/.vercel`, `.render`, `supabase/`) | ❌ none |
| Repo provider metadata | only `render.yaml` (config, not provisioned) |
| Fabricated resources | NONE (none created, none claimed) |

## 11. Database Mutation

Development DB: INSERT = 0 · UPDATE = 0 · DELETE = 0 · ALTER = 0 · DROP = 0
Production DB: **NOT CREATED** (no schema, no migration, no data)

## 12. Cloud Resources Created

**ZERO.**

## 13. Production Deployment Status

**NOT DEPLOYED.** No Vercel/Render/Supabase project exists. No public
application is running.

## 14. Known Risks / Limitations

1. Provisioning cannot proceed until the operator supplies provider access
   (accounts/API tokens) or performs the runbook steps directly.
2. Render cold start (~1 min) and Supabase Free pause-after-1-week remain
   accepted beta limitations.
3. Supabase Free has no automatic backups — beta limitation.
4. The operator must generate a new production `JWT_SECRET_KEY` and must not
   reuse the dev secret.
5. Region choice depends on what Supabase lists for the operator's account.

## 15. Next Authorized Slice

**PHASE 21D.3 — BETA PRODUCTION VALIDATION & LAUNCH GATE** (after 21D.2
provisioning is completed by the operator and reported back).
