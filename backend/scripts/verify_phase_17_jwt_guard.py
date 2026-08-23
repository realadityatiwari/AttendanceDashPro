"""Phase 17 — JWT production-secret guard verification.

Verifies the Phase 16/17 production configuration guard without exposing
secrets. Runs in subprocesses so each environment combination is isolated
(the Settings singleton is instantiated at import).

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
    print("=== PHASE 17 — JWT PRODUCTION-SECRET GUARD ===")

    # 1. Development default remains valid
    r = run_with_env({"APP_ENV": "development"})
    check("development (default secret) loads", r.returncode == 0 and "OK" in r.stdout,
          f"rc={r.returncode} out={r.stdout.strip()[:80]} err={r.stderr.strip()[:120]}")

    # 2. Production + missing secret (default) -> fails
    r = run_with_env({"APP_ENV": "production"})
    check("production + dev default -> rejected",
          r.returncode != 0 and "JWT_SECRET_KEY" in r.stderr,
          f"rc={r.returncode}")

    # 3. Production + explicitly unsafe (too short) -> fails
    r = run_with_env({"APP_ENV": "production", "JWT_SECRET_KEY": "shortsecret"})
    check("production + short secret -> rejected",
          r.returncode != 0 and "JWT_SECRET_KEY" in r.stderr,
          f"rc={r.returncode}")

    # 4. Production + explicit valid secret -> succeeds
    r = run_with_env({"APP_ENV": "production", "JWT_SECRET_KEY": "a" * 40})
    check("production + valid secret -> loads",
          r.returncode == 0 and "OK" in r.stdout,
          f"rc={r.returncode} err={r.stderr.strip()[:120]}")

    # 5. Error does NOT expose the secret value
    r = run_with_env({"APP_ENV": "production", "JWT_SECRET_KEY": "supersecret_development_key_change_in_production"})
    check("error does not print the secret",
          "supersecret_development_key_change_in_production" not in r.stderr,
          "secret leaked!" if "supersecret_development_key_change_in_production" in r.stderr else "")

    # 6. Default APP_ENV (no env var) remains development-compatible
    r = run_with_env({"APP_ENV": ""})
    check("empty APP_ENV defaults to development", r.returncode == 0 and "OK" in r.stdout,
          f"rc={r.returncode} err={r.stderr.strip()[:120]}")

    print("\n" + "=" * 50)
    passed = sum(1 for x in results if x[0] == "PASS")
    failed = sum(1 for x in results if x[0] == "FAIL")
    print(f"  PASS: {passed}, FAIL: {failed}, TOTAL: {len(results)}")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)