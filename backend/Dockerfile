# syntax=docker/dockerfile:1

# ────────────────────────────────────────────────────────────────────────
# AttendanceDash Pro — Backend production image (FastAPI + Uvicorn)
#
# - Python 3.13 (matching the development venv)
# - Deterministic install from requirements.txt (pip, no cache)
# - App code + Alembic included so migrations can be run as a separate
#   one-shot step during deployment (Phase 18D) — never at container start.
# - Runs as non-root `appuser`.
# - Healthcheck uses the existing GET /health endpoint (no auth required).
#
# Startup (override workers via UVICORN_WORKERS env, default 1):
#   uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers N --proxy-headers \
#     --forwarded-allow-ips ${FORWARDED_ALLOW_IPS}
#
# NOTE: `--proxy-headers` makes Uvicorn trust X-Forwarded-* headers, but ONLY
# from the IPs/CIDRs in `--forwarded-allow-ips` (default 127.0.0.1). In the
# production compose stack this is set to the pinned proxy-net subnet
# (172.28.0.0/24), so Caddy is the ONLY trusted proxy. Arbitrary client-
# supplied X-Forwarded-For headers from outside that subnet are ignored —
# the Phase 16 rate limiter sees the real client IP, not a spoofed one.
# Do not expose the backend port to the host.
# ────────────────────────────────────────────────────────────────────────

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first (layer caching; deterministic)
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Application + migration files
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Non-root runtime user
RUN adduser --disabled-password --gecos "" appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/health').status==200 else 1)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-1} --proxy-headers --forwarded-allow-ips ${FORWARDED_ALLOW_IPS:-127.0.0.1}"]
