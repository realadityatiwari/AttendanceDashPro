# AttendanceDash Pro — Phase 18D: Deployment & Verification

Status: **PARTIAL** — deployment mechanism fully verified via a local rehearsal
deployment; **actual production deployment BLOCKED on missing infrastructure**
(no VPS/cloud host, no domain/DNS/TLS, no production credentials, no off-host
destination exist).

## 1. Phase Status

| Item | Status |
|---|---|
| Deployment mechanism verified (rehearsal) | ✅ COMPLETE |
| Production deployment | ⛔ BLOCKED — no production host/credentials/domain |
| Off-host protection | ⛔ BLOCKED — no destination exists (OFFHOST_TYPE=none) |
| Backup verification | ✅ COMPLETE |
| Restore verification (isolated) | ✅ COMPLETE |
| Health verification | ✅ COMPLETE |

## 2. Deployment Target

- **Intended**: single VPS + Docker Compose (per Phase 18.0 audit).
- **Actual**: NONE — no VPS/cloud host exists. Rehearsal performed on the local
  development machine with disposable volumes.

## 3. Deployment Mechanism

`docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod up -d --build`

The production stack (5 services) was deployed as a **rehearsal** with
placeholder-only env values (temp file, never committed) and disposable
volumes. After verification the stack was torn down; no production deployment
exists.

## 4. Services Deployed (rehearsal)

| Service | Image | Status (rehearsal) |
|---|---|---|
| postgres | postgres:16 | ✅ healthy |
| backend | ./backend Dockerfile | ✅ healthy (after PyJWT fix) |
| frontend | ./frontend Dockerfile | ✅ healthy |
| backup | ./deploy/backup Dockerfile | ✅ healthy |
| caddy | caddy:2-alpine | ✅ healthy |

## 5. Deployment Defects Found & Fixed

1. **PyJWT missing from `backend/requirements.txt`** — the backend container
   crashed at import (`ModuleNotFoundError: No module named 'jwt'`). Added
   `pyjwt>=2.10.0` (installed dev version: 2.13.0). Genuine deployment defect,
   minimal fix.
2. **Caddy route for `/health` missing** — `/health` (backend root endpoint)
   was not routed by the proxy, so external health checks would hit the
   frontend. Added `handle /health { reverse_proxy backend:8000 }` to the
   Caddyfile. Restart required (Caddy does not hot-reload).

## 6. Environment / Configuration

All values supplied at runtime via compose env interpolation from
`deploy/.env.prod` (gitignored). Rehearsal used placeholder values only. The
`${VAR:?}` required syntax (Phase 18B) was exercised: missing required vars
fail fast.

## 7. Secrets Handling

- No real secrets added; placeholder rehearsal values only.
- Backend process argv contains **no password** (PGPASSWORD env only).
- Scheduler logs contain DB identity but **no credentials** (verified).
- Frontend receives only `NEXT_PUBLIC_API_URL` (public, build-time).

## 8. Backup Scheduler Status

- Container healthy, scheduler loop running (`interval=86400s, offhost=none`).
- Lock file prevents overlapping backups (verified).
- First scheduled cycle failed loudly on the empty rehearsal DB (903 bytes <
  1024 minimum) — fail-loudly behavior confirmed correct.

## 9. Backup Execution Result

Executed the **real backup scripts** inside the running backup container:

| Step | Result |
|---|---|
| `backup.sh` (seeded disposable DB) | ✅ PASS — 2972 bytes, pg_restore --list OK, 11 TOC entries, gzip custom format |
| `retention.sh` | ✅ PASS — no prune needed (2 ≤ 14) |
| `offhost.sh` | ✅ PASS — `OFFHOST_TYPE=none — local staging only` |
| Artifact in persistent `backup_data` volume | ✅ confirmed |
| Scheduler lock | ✅ confirmed |

## 10. Off-Host Destination Status

- **Type**: none (contract supports mount/sftp/s3/custom).
- **Destination configured**: NO — no legitimate destination exists.
- **Actual copy**: NO — nothing connected; no disaster-recovery protection
  claimed.

## 11. Restore Verification Result

**Isolated restore PASS**: backup restored into a **disposable** postgres:16
container; `rehearsal_marker` table + data confirmed present; container
removed afterward. The application DB and rehearsal DB were never restored
into destructively.

## 12. Health Checks

| Check | Result |
|---|---|
| postgres healthcheck (pg_isready) | ✅ healthy |
| backend /health (direct, container) | ✅ 200 JSON |
| backend /health (via Caddy proxy) | ✅ 200 JSON |
| frontend / (via Caddy proxy) | ✅ 200 HTML (29KB) |
| API /api/v1/student/me (no token) | ✅ 401 JSON (auth enforced) |
| All 5 containers healthy | ✅ |

## 13. Security Verification

| Check | Result |
|---|---|
| Real secrets added | ZERO |
| Secrets in git diff | NONE |
| Passwords in process args | NONE (verified /proc/1/cmdline) |
| Backup logs expose credentials | NO (verified) |
| PostgreSQL public port | NONE (private data-net) |
| Backend public port | NONE |
| Only proxy port 80 exposed | ✅ |
| proxy-net membership | frontend, backend, caddy |
| data-net membership (internal) | postgres, backup, backend |
| FORWARDED_ALLOW_IPS | 172.28.0.0/24 (pinned subnet) |

## 14. Database Mutation Status

- **Application DB (dev `attendancedashpro_db`)**: INSERT 0 · UPDATE 0 · DELETE 0.
- **Rehearsal DB (disposable)**: one marker table created for backup/restore
  verification — clearly distinguished, destroyed with the rehearsal stack.
- **Restore target (disposable)**: restored backup into it, removed.

## 15. Browser / Manual Testing

**NOT PERFORMED — USER RESPONSIBILITY.** No browser automation.

## 16. Git Status

- Commit: NONE
- Push: NONE

## 17. Cloud / External Resources

**ZERO.** No VPS, no cloud storage, no DNS, no TLS, no external service.

## 18. Known Limitations / Blockers

1. **No production host** — a VPS/cloud compute target must be provisioned
   before a real deployment.
2. **No production credentials** — real `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`,
   `BACKEND_CORS_ORIGINS` must be supplied by the operator.
3. **No domain/DNS/TLS** — HTTPS provisioning deferred; Caddy config ready.
4. **No off-host destination** — set OFFHOST_TYPE + credentials once a
   destination exists; until then, no disaster-recovery protection.
5. **Migrations on deploy** — `alembic upgrade head` must be run as a one-shot
   step against the production DB before the app is used (backend does not
   auto-migrate). No migration was run during 18D.

## 19. Final Deployment State

- Production deployment: **NOT DEPLOYED** (blocked on infrastructure).
- Rehearsal deployment: verified end-to-end, then torn down (disposable
  volumes removed; no residue).
- The repository is **ready** for a real deployment once the operator supplies
  a host, credentials, domain, and optional off-host destination.

## 20. Next Authorized Slice

Phase 19 — CI/CD (per MASTER_ROADMAP) OR a deployment-execution phase once
production infrastructure exists. Phase 19 NOT STARTED.
