# AttendanceDash Pro — Phase 18B: Environment & Secret Management

Status: Phase 18B — **COMPLETE**. Environment/secret contract for the Phase 18A
container architecture. Nothing deployed; no real secrets added.

## 1. Environment Variable Contract

### Frontend (public — inlined into the client bundle at build time)

| Variable | Required | Secret? | Purpose |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | yes | **No (public by design)** | API base URL the browser calls (through the proxy). Passed as a Docker build ARG only because Next.js inlines `NEXT_PUBLIC_*` at build time — it is not a secret. |

### Backend

| Variable | Required | Secret? | Purpose |
|---|---|---|---|
| `DATABASE_URI` | yes (compose builds it; can override) | **Yes** | Asyncpg connection string; must not reference localhost in production |
| `JWT_SECRET_KEY` | yes | **Yes** | HS256 signing secret; ≥ 20 chars; dev default rejected in production |
| `JWT_ALGORITHM` | no (default HS256) | no | Signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | no (default 480) | no | Access-token lifetime |
| `BACKEND_CORS_ORIGINS` | yes | no | JSON list of allowed frontend origins; localhost rejected in production |
| `APP_ENV` | yes (fixed `production` in compose) | no | Environment mode; activates the production guards |
| `SECURITY_HSTS_ENABLED` | no (default false) | no | HSTS (only with HTTPS) |
| `UVICORN_WORKERS` | no (default 1) | no | Uvicorn worker count |
| `FORWARDED_ALLOW_IPS` | no (default 172.28.0.0/24) | no | Trusted proxy CIDR for X-Forwarded-For |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS` / `REGISTER_*` | no (defaults) | no | Rate limiting |

### PostgreSQL

| Variable | Required | Secret? | Purpose |
|---|---|---|---|
| `POSTGRES_USER` | yes | no | DB user (used in compose interpolation; compose uses `:?` so missing values fail fast) |
| `POSTGRES_PASSWORD` | yes | **Yes** | DB password — never committed |
| `POSTGRES_DB` | no (default attendancedash) | no | DB name |

### Reverse proxy

| Variable | Required | Secret? | Purpose |
|---|---|---|---|
| `DOMAIN` | no (default app.example.com) | no | Caddy site address (placeholder until TLS phase) |
| `PROXY_NET_SUBNET` | no (default 172.28.0.0/24) | no | Pinned proxy network CIDR (must match FORWARDED_ALLOW_IPS) |

## 2. Public vs Secret

- **Public**: `NEXT_PUBLIC_API_URL` — intentionally embedded in the client bundle.
- **Secret**: `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `DATABASE_URI` credentials.
- **Deployment-specific (not secret)**: CORS origins, APP_ENV, JWT_ALGORITHM,
  expiry, HSTS flag, workers, rate-limit tuning, DOMAIN, proxy subnet.

## 3. Runtime Injection Model

- Secrets are injected **at container runtime** via Compose `environment:` blocks
  interpolated from `deploy/.env.prod` (`--env-file`).
- `docker-compose.prod.yml` uses `${VAR:?}` for required values — **compose fails
  fast** instead of silently using empty strings when a required secret is missing.
- The only build-time variable is `NEXT_PUBLIC_API_URL` (public by design).
- No secret is passed as a Docker build ARG. No secret is baked into an image.

## 4. Development vs Production Separation

| | Development | Production |
|---|---|---|
| Env file | `backend/.env` (gitignored) | `deploy/.env.prod` (gitignored) |
| Example | `backend/.env.example` (dev creds marked DEVELOPMENT ONLY) | `deploy/.env.prod.example` (placeholders) |
| Compose | `docker-compose.yml` (DB on 55432) | `docker-compose.prod.yml` (DB private) |
| APP_ENV | `development` | `production` (guards active) |

## 5. Secret Handling Rules

1. Never commit `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, or real `DATABASE_URI`
   credentials.
2. Never pass secrets through Docker build ARGs.
3. Never bake secrets into frontend client assets (`NEXT_PUBLIC_*` is public).
4. `deploy/.env.prod` and `backend/.env` are gitignored.
5. Example files contain placeholders only.
6. Startup/config never prints secret values (guards raise messages without values).
7. Production guards (Phase 17 + 18B): dev JWT secret, short secret, localhost
   DATABASE_URI, and localhost CORS origins all fail startup when
   `APP_ENV=production`.

## 6. Proxy Trust Boundary

```text
Internet → Caddy (only trusted proxy) → backend:8000
```

- Caddy sets `X-Forwarded-For` to the real client IP on every proxied request.
- Backend runs `uvicorn --proxy-headers --forwarded-allow-ips <CIDR>`.
- `FORWARDED_ALLOW_IPS` defaults to `172.28.0.0/24`, which matches the **pinned**
  `proxy-net` subnet in `docker-compose.prod.yml` (`PROXY_NET_SUBNET`).
- Uvicorn ignores client-supplied `X-Forwarded-For` from outside that subnet —
  spoofing is not possible. The Phase 16 rate limiter (`request.client.host`)
  therefore sees the real client IP.

## 7. Intentionally NOT Implemented in 18B

- Secret-manager integration (Docker secrets / vault / provider secret store) —
  deferred; compose env-file injection is the contract.
- TLS certificates / real domain (Phase 18D).
- Backup automation, rotation, off-host storage, notifications (Phase 18C).
- Deployment automation / CI/CD (Phase 18D).

## 8. Operational Prerequisites for 18C/18D

- A real `deploy/.env.prod` with generated secrets (see example).
- Decision on hosting (Phase 18.0 recommendation: single VPS + Docker Compose).
- Domain + DNS for TLS (18D).
- Backup storage destination decision (18C).
