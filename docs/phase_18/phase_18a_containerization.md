# AttendanceDash Pro — Production Containers (Phase 18A)

Status: Phase 18A foundation — containerization and orchestration configuration.
**Not yet deployed.** No TLS, no domain, no real secrets (Phase 18B+).

## Architecture

```text
Internet
    ↓  :80 (HTTP — TLS in a later phase)
┌─── caddy (reverse proxy) ──────────────── proxy-net ───┐
│    /api/* → backend:8000                              │
│    *      → frontend:3000                             │
└───────────────────────────────────────────────────────┘
              │                              │
      ┌───────▼────────┐            ┌────────▼────────┐
      │ frontend       │            │ backend         │
      │ Next.js 16 SSR │            │ FastAPI+Uvicorn │
      │ + PWA          │            └───────┬─────────┘
      └────────────────┘                    │ data-net (internal: true)
                                    ┌───────▼─────────┐
                                    │ postgres:16     │  ← NO public port
                                    └─────────────────┘
```

## Services

| Service | Image/Build | Port (host) | Network | Role |
|---|---|---|---|---|
| `caddy` | caddy:2-alpine | **80** | proxy-net | Reverse proxy; HTTP routing; TLS later |
| `frontend` | `./frontend/Dockerfile` (node:20-alpine) | none | proxy-net | Next.js SSR + PWA (standalone output) |
| `backend` | `./backend/Dockerfile` (python:3.13-slim) | none | proxy-net + data-net | FastAPI `app.main:app`, uvicorn workers |
| `postgres` | postgres:16 | **none** | data-net (internal) | PostgreSQL, named volume, healthcheck |

- **PostgreSQL is private**: it exists only on the `internal: true` `data-net`;
  no host port is published and it has no external route.
- **Frontend cannot reach PostgreSQL**; only the backend is on both networks.
- Only the reverse proxy port 80 is exposed to the host.

## Reverse Proxy (Caddy)

`deploy/caddy/Caddyfile`:

- `http://{$DOMAIN:app.example.com}` — HTTP-only placeholder (TLS later).
- `handle /api/*` → `backend:8000` (Caddy adds `X-Forwarded-For` automatically).
- `handle *` → `frontend:3000` (Next.js SSR + PWA).

**Proxy-header trust boundary**: the backend runs `uvicorn ... --proxy-headers`
so the Phase 16 rate limiter sees the real client IP. This is safe because the
backend binds only inside the compose network and the Caddy container is the
only client that can reach it. The backend port is never published to the host.

## Environment Variables

Provided via `deploy/.env.prod` (copy from `deploy/.env.prod.example`, gitignored):

| Variable | Used by | Required | Secret |
|---|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | postgres + backend | yes | password yes |
| `JWT_SECRET_KEY` | backend | yes | **yes** |
| `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | backend | no (defaults) | no |
| `APP_ENV` | backend (fixed `production` in compose) | — | no |
| `BACKEND_CORS_ORIGINS` | backend | yes | no |
| `SECURITY_HSTS_ENABLED` | backend | no (default false) | no |
| `UVICORN_WORKERS` | backend | no (default 1) | no |
| `NEXT_PUBLIC_API_URL` | frontend (build arg, inlined) | yes | no (public) |
| `DOMAIN` | caddy | no (default app.example.com) | no |

No real credentials are committed anywhere. `deploy/.env.prod` is gitignored.

## Startup

```bash
# Build + start (no TLS yet)
docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod up -d --build

# Migrations are NOT run automatically. Deployment-time migration (Phase 18D):
# docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

Healthchecks: postgres `pg_isready`; backend `GET /health`; frontend `wget /`;
caddy `wget /`. Restart policy: `unless-stopped` on all services.

## Intentionally NOT implemented in 18A

- No TLS certificates / real domain (Caddy config ready for HTTPS later)
- No secret manager integration (18B)
- No automated backup rotation / off-host storage / notifications (18C)
- No deployment automation / CI/CD (18D)
- No migrations-on-deploy (18D)
- No changes to application behavior, schema, or data

## Development vs Production

| | File |
|---|---|
| Development | `docker-compose.yml` (PostgreSQL only, port 55432, named volume) |
| Production | `docker-compose.prod.yml` (+ `deploy/caddy/Caddyfile`, Dockerfiles) |
