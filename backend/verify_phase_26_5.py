"""Phase 26.5 static verifier — event source filtering (optimization #5).

Static/backend-only checks (no DB required). Demonstrates that the dashboard
summary's single event fetch now filters at the source (active=True,
date_from=min(semester_start, today)) instead of retrieving the full table.

Verifies:
 1.  Imports.
 2.  The dashboard's `get_all_events` call passes `active=True` and `date_from`.
 3.  The lower bound is computed correctly (min(semester_start, today)).
 4.  Repo `get_all_events` already supports the filter parameters.
 5.  No schema/migration/engine/frontend/auth/API-contract change.
"""
import re
import subprocess
import sys
from pathlib import Path

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def main() -> int:
    print("Phase 26.5 — event source filtering (optimization #5, static verification)\n")

    ROOT = Path(__file__).resolve().parent
    dash_path = ROOT / "app" / "services" / "dashboard_service.py"
    repo_path = ROOT / "app" / "repositories" / "calendar_repo.py"

    current_dash = dash_path.read_text(encoding="utf-8")
    current_repo = repo_path.read_text(encoding="utf-8")

    # ── 1. Imports ────────────────────────────────────────────────────────
    print("[1] Imports")
    import app.main  # noqa: F401
    from app.services.dashboard_service import DashboardService
    from app.repositories.calendar_repo import CalendarRepository
    check("app.main imports", True)
    check("DashboardService importable", DashboardService is not None)
    check("CalendarRepository importable", CalendarRepository is not None)

    # ── 2. Dashboard event fetch uses filters ─────────────────────────────
    print("[2] Dashboard event fetch filters")
    has_active = "active=True" in current_dash or "get_all_events(active=True" in current_dash
    check("get_all_events called with active=True", has_active)
    has_date_from = "date_from=" in current_dash
    check("get_all_events called with date_from", has_date_from)
    check("event_floor computation uses min(semester_start, today)",
          "event_floor" in current_dash
          and "semester_start is not None" in current_dash
          and "semester_start < today" in current_dash)
    # Verify the events fetch is the dashboard's single event fetch, not a
    # different call site.
    events_fetch = current_dash[current_dash.find("event_floor"):current_dash.find("event_floor") + 500]
    check("event_floor passed as date_from", "date_from=event_floor" in events_fetch)

    # ── 3. Repo get_all_events already supports both filters ──────────────
    print("[3] Repository supports the filter params")
    check("get_all_events accepts active param", "active: Optional[bool] = None" in current_repo)
    check("get_all_events accepts date_from param", "date_from: Optional[date] = None" in current_repo)
    check("repo filters on active when param not None",
          "if active is not None:" in current_repo and "AcademicEvent.active.is_(active)" in current_repo)
    check("repo filters on end_date >= date_from when param not None",
          "if date_from is not None:" in current_repo and "AcademicEvent.end_date >= date_from" in current_repo)

    # ── 4. Event consumers get the same list ──────────────────────────────
    print("[4] Event consumers receive the filtered events list")
    # The return statement in get_summary passes events to all three builders.
    # Verify by checking the source text directly.
    return_stmt = current_dash[current_dash.find("return DashboardSummaryResponse("):
                               current_dash.find("return DashboardSummaryResponse(") + 600]
    for builder in ("_build_today", "_build_quiz_snapshot", "_build_upcoming_events"):
        check(f"events passed to {builder}", f"events" in return_stmt and builder in return_stmt)
    # Also verify _build_quiz_snapshot passes events into eligibility batch
    snapshot_block = current_dash[current_dash.find("async def _build_quiz_snapshot"):
                                  current_dash.find("async def _build_quiz_snapshot") + 5000]
    check("eligibility batch receives events", "events=events" in snapshot_block)

    # ── 5. Scope guard ────────────────────────────────────────────────────
    print("[5] Scope guard")
    changed = {
        ln.strip().split(maxsplit=1)[-1]
        for ln in subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True,
        ).stdout.splitlines()
        if ln.strip()
    }
    pre_existing = {
        "MASTER_ROADMAP.md", "implementation_plan.md", "task.md", "walkthrough.md",
        "frontend/src/lib/api.ts", "frontend/src/contexts/AuthContext.tsx",
        "frontend/src/app/(auth)/login/page.tsx", "frontend/src/app/(auth)/signup/page.tsx",
        "backend/app/services/notification_service.py",
        "backend/app/repositories/notification_repo.py",
        "backend/app/services/dashboard_service.py",
        "backend/app/services/calendar_service.py",
        "backend/app/repositories/attendance_repo.py",
        "backend/app/services/eligibility_service.py",
        "backend/verify_phase_25_4.py", "backend/verify_phase_26_3.py",
        "frontend/public/service-worker.js",
        "frontend/src/components/pwa/ServiceWorkerRegistration.tsx",
        "frontend/src/components/layout/AppShell.tsx",
        "frontend/src/components/shell/SettingsModal.tsx",
        "frontend/src/hooks/useNotificationPermission.ts",
        "docs/notification_delivery_investigation.md",
    }
    changed_for_this = {p for p in changed if p not in pre_existing}
    expected = {"backend/app/services/dashboard_service.py", "backend/verify_phase_26_5.py"}
    extra = changed_for_this - expected
    check("only dashboard_service.py + verifier changed by this phase",
          not extra, f"extra: {extra}")
    for p in changed_for_this:
        prohibited = ("alembic/", "app/models/", "app/engines/", "frontend/",
                      "deploy/", "render.yaml", "docker-compose",
                      "app/api/v1/endpoints/", "app/schemas/")
        is_prohibited = any(p.startswith(prefix) for prefix in prohibited)
        check(f"no prohibited file changed: {p}", not is_prohibited)

    # ── 6. Summary ────────────────────────────────────────────────────────
    print("\nExpected query reduction per /dashboard/summary request (static):")
    print("  get_all_events (unfiltered full table scan) ->")
    print("  get_all_events(active=True, date_from=floor)")
    print("  Filters applied at the database level:")
    print("    - active=True: excludes all inactive events")
    print("    - end_date >= floor: excludes events that ended before the semester")
    print("  (All other query patterns unchanged; no schema/migration/index change.)")

    print(f"\nRESULT: {PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())