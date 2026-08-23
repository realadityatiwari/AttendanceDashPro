"""Phase 17/18B — Production configuration guard verification.

Verifies the production configuration guards without exposing secrets. Runs in
subprocesses so each environment combination is isolated (the Settings
singleton is instantiated at import).

Guards verified:
- development default loads
- production + dev JWT secret -> rejected
- production + short JWT secret -> rejected
- production + valid JWT secret + prod DATABASE_URI + prod CORS -> loads
- production + localhost DATABASE_URI -> rejected (18B)
- production + localhost CORS origin -> rejected (18B)
- errors never print secret values
- empty APP_ENV behaves as development

Usage:
    python scripts/verify_phase_17_jwt_guard.py
"""
import subprocess
import sys
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
GUARD_SCRIPT = (
    "import sys; sys.path.insert(0, '.'); "
    "from app.core.config import settings; "
    "print('OK')"
)

PROD_DB = "postgresql+asyncpg://app:secret@postgres:5432/attendancedash"
PROD_CORS = '["https://app.example.com"]'

results = []
def check(label, ok, detail=""):
    st = "PASS" if ok else "FAIL"
    results.append((st, label, detail))
    print(f"  [{st}] {label}" + (f" -- {detail}" if detail else ""))

def run_with_env(env: dict):
    """Runs the config import in a subprocess with the given env vars."""
    full_env = {**os.environ, "PYTHONIOENCODING": "utf-8", **env}
    return subprocess.run(
        [sys.executable, "-c", GUARD_SCRIPT],
        cwd=str(BACKEND_DIR),
        env=full_env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def main():
    print("=== PRODUCTION CONFIGURATION GUARD (17 + 18B) ===")

    # 1. Development default remains valid
    r = run_with_env({"APP_ENV": "development"})
    check("development (default secret) loads", r.returncode == 0 and "OK" in r.stdout,
          f"rc={r.returncode} out={r.stdout.strip()[:80]} err={r.stderr.strip()[:120]}")

    # 2. Production + missing secret (default) -> fails
    r = run_with_env({"APP_ENV": "production", "DATABASE_URI": PROD_DB, "BACKEND_CORS_ORIGINS": PROD_CORS})
    check("production + dev default -> rejected",
          r.returncode != 0 and "JWT_SECRET_KEY" in r.stderr,
          f"rc={r.returncode}")

    # 3. Production + explicitly unsafe (too short) -> fails
    r = run_with_env({"APP_ENV": "production", "JWT_SECRET_KEY": "shortsecret",
                      "DATABASE_URI": PROD_DB, "BACKEND_CORS_ORIGINS": PROD_CORS})
    check("production + short secret -> rejected",
          r.returncode != 0 and "JWT_SECRET_KEY" in r.stderr,
          f"rc={r.returncode}")

    # 4. Production + explicit valid secret + prod DB + prod CORS -> succeeds
    r = run_with_env({"APP_ENV": "production", "JWT_SECRET_KEY": "a" * 40,
                      "DATABASE_URI": PROD_DB, "BACKEND_CORS_ORIGINS": PROD_CORS})
    check("production + valid config -> loads",
          r.returncode == 0 and "OK" in r.stdout,
          f"rc={r.returncode} err={r.stderr.strip()[:120]}")

    # 5. Error does NOT expose the secret value
    r = run_with_env({"APP_ENV": "production", "JWT_SECRET_KEY": "supersecret_development_key_change_in_production",
                      "DATABASE_URI": PROD_DB, "BACKEND_CORS_ORIGINS": PROD_CORS})
    check("error does not print the secret",
          "supersecret_development_key_change_in_production" not in r.stderr,
          "secret leaked!" if "supersecret_development_key_change_in_production" in r.stderr else "")

    # 6. Empty APP_ENV defaults to development
    r = run_with_env({"APP_ENV": ""})
    check("empty APP_ENV defaults to development", r.returncode == 0 and "OK" in r.stdout,
          f"rc={r.returncode} err={r.stderr.strip()[:120]}")

    # 7. Production + localhost DATABASE_URI -> rejected (18B)
    r = run_with_env({"APP_ENV": "production", "JWT_SECRET_KEY": "a" * 40,
                      "DATABASE_URI": "postgresql+asyncpg://postgres:postgres@localhost:55432/attendancedash",
                      "BACKEND_CORS_ORIGINS": PROD_CORS})
    check("production + localhost DATABASE_URI -> rejected",
          r.returncode != 0 and "DATABASE_URI" in r.stderr,
          f"rc={r.returncode}")

    # 8. Production + localhost CORS origin -> rejected (18B)
    r = run_with_env({"APP_ENV": "production", "JWT_SECRET_KEY": "a" * 40,
                      "DATABASE_URI": PROD_DB,
                      "BACKEND_CORS_ORIGINS": '["http://localhost:3100"]'})
    check("production + localhost CORS -> rejected",
          r.returncode != 0 and "BACKEND_CORS_ORIGINS" in r.stderr,
          f"rc={r.returncode}")

    print("\n" + "=" * 50)
    passed = sum(1 for x in results if x[0] == "PASS")
    failed = sum(1 for x in results if x[0] == "FAIL")
    print(f"  PASS: {passed}, FAIL: {failed}, TOTAL: {len(results)}")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)