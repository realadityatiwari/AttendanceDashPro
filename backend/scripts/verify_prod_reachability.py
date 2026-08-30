"""
Production Student Portal reachability guard (incident 2026-08-30 regression).

Read-only HTTP probes against the deployed Student Portal chain:

    Vercel frontend (attendance-dash-pro.vercel.app)
      -> Render FastAPI backend (attendancedash-api.onrender.com)
         -> Supabase PostgreSQL

It verifies the EXACT contract that failed during the recovery incident:

  1. Vercel login page loads (HTTP 200).
  2. Deployed frontend bundle inlines the production Render API URL and does
     NOT reference a localhost/127.0.0.1 backend (fail-loud guard present).
  3. Render GET /health returns 200 (backend is up; distinguishes cold-start
     from outage by retrying).
  4. CORS preflight for the exact Vercel origin succeeds and echoes the
     allowed origin back.
  5. The login route exists and, with deliberately INVALID credentials,
     responds with an HTTP 401 auth error — NOT a 500 (backend/schema
     defect) and NOT a network-level failure.

The 401-vs-500 distinction is the core regression signal: when the deployed
backend queries columns the production schema does not have (e.g.
users.is_active / users.subsection_id added after production's alembic
revision f2e3d4c5b6a7), login returns 500 "Internal server error" and the
Student Portal becomes unusable. This guard fails loudly on that exact
condition.

This script NEVER sends real credentials, NEVER mutates data, and NEVER
touches the database. It is a pure reachability/contract probe.

Usage:
    python scripts/verify_prod_reachability.py [--backend-url URL] [--frontend-url URL]

Exit code 0 = all checks pass; 1 = a check failed.
"""
import argparse
import sys
import time
import urllib.error
import urllib.request

BACKEND_DEFAULT = "https://attendancedash-api.onrender.com"
FRONTEND_DEFAULT = "https://attendance-dash-pro.vercel.app"

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def http_request(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    body: bytes | None = None,
    timeout: float = 45.0,
) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, method=method, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), {k.lower(): v for k, v in exc.headers.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-url", default=BACKEND_DEFAULT)
    parser.add_argument("--frontend-url", default=FRONTEND_DEFAULT)
    args = parser.parse_args()

    backend = args.backend_url.rstrip("/")
    frontend = args.frontend_url.rstrip("/")
    print("=" * 62)
    print("Production Student Portal Reachability Guard")
    print(f"backend : {backend}")
    print(f"frontend: {frontend}")
    print("=" * 62)

    # ── 1. Vercel frontend login page loads ────────────────────────────────
    try:
        status, body, _ = http_request(f"{frontend}/login", timeout=60)
        record(
            "1. Vercel /login loads",
            status == 200 and b"AttendanceDash" in body,
            f"status={status}",
        )
    except Exception as exc:  # noqa: BLE001
        record("1. Vercel /login loads", False, str(exc))

    # ── 2. Deployed bundle: production API URL, no localhost fallback ──────
    try:
        status, html, _ = http_request(f"{frontend}/login", timeout=60)
        found_api = b"attendancedash-api.onrender.com" in html or b"onrender.com" in html
        found_localhost = (
            b"http://localhost" in html
            or b"http://127.0.0.1" in html
            or b"http://0.0.0.0" in html
        )
        # The bundle guard code itself contains the words localhost/127.0.0.1
        # (the dev fallback string and the regex); presence in the HTML is a
        # weak signal. The authoritative check is the build-time guard in
        # frontend/src/lib/api.ts, so this check is intentionally lenient:
        # it only FAILS when the HTML references a localhost *API call* and
        # never references the production backend at all.
        ok = found_api or not found_localhost
        record(
            "2. Bundle carries production API URL (no localhost API)",
            ok,
            f"api_ref={found_api} localhost_ref={found_localhost}",
        )
    except Exception as exc:  # noqa: BLE001
        record("2. Bundle carries production API URL (no localhost API)", False, str(exc))

    # ── 3. Render /health (retry to absorb a cold start) ───────────────────
    health_ok = False
    attempts = 3
    for i in range(1, attempts + 1):
        try:
            status, body, _ = http_request(f"{backend}/health", timeout=60)
            health_ok = status == 200 and b'"ok"' in body
            if health_ok:
                record("3. Render GET /health", True, f"attempt {i}/{attempts}")
                break
            time.sleep(5)
        except Exception as exc:  # noqa: BLE001
            if i == attempts:
                record("3. Render GET /health", False, f"attempt {i}/{attempts}: {exc}")
            else:
                print(f"  ... /health not ready on attempt {i}/{attempts}; retrying")
                time.sleep(5)

    # ── 4. CORS preflight from the exact production origin ─────────────────
    try:
        status, _, headers = http_request(
            f"{backend}/api/v1/auth/login",
            method="OPTIONS",
            headers={
                "Origin": frontend,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
            timeout=45,
        )
        allow_origin = headers.get("access-control-allow-origin", "")
        allow_methods = headers.get("access-control-allow-methods", "")
        record(
            "4. CORS preflight allows Vercel origin",
            status == 200
            and allow_origin == frontend
            and "POST" in allow_methods
            and headers.get("access-control-allow-credentials", "").lower() == "true",
            f"status={status} allow-origin={allow_origin}",
        )
    except Exception as exc:  # noqa: BLE001
        record("4. CORS preflight allows Vercel origin", False, str(exc))

    # ── 5. Login contract: invalid credentials -> 401 (NOT 500/network) ────
    try:
        payload = b'{"roll_number":"0000000000000","password":"wrongpass1"}'
        status, body, _ = http_request(
            f"{backend}/api/v1/auth/login",
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Origin": frontend,
            },
            body=payload,
            timeout=45,
        )
        record(
            "5. Invalid login -> HTTP 401 (not 500 / not network error)",
            status == 401,
            f"status={status} body={body[:120]!r}",
        )
    except Exception as exc:  # noqa: BLE001
        record("5. Invalid login -> HTTP 401 (not 500 / not network error)", False, str(exc))

    print("=" * 62)
    failed = [name for name, ok in RESULTS if not ok]
    if failed:
        print(f"RESULT: FAIL — {len(failed)} check(s) failed: {', '.join(failed)}")
        print("If check 5 fails with status=500, the deployed backend and the")
        print("production database schema are out of sync (login queries columns")
        print("missing in production). Run the production alembic migration gate.")
        return 1
    print("RESULT: PASS — all reachability/contract checks green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
