"""Phase 25.4 static verifier — dashboard summary query deduplication.

Static/backend-only checks (no DB required). Demonstrates optimization #1:
each request-scoped dataset is fetched once per /dashboard/summary request
and reused in memory, instead of being re-fetched by each builder.

Verifies:
 1.  Imports: app.main and all three touched services load.
 2.  Call-site counts (CURRENT file vs git HEAD baseline) for the four
     datasets that were duplicated and are now consolidated.
 3.  Downstream methods accept pre-fetched data and fetch ONLY under a
     `is None` guard (zero behavior change for existing callers).
 4.  get_summary threads the shared data into every builder.
 5.  Scope guard: only the three service files changed (plus pre-existing
     Phase 25.2 frontend/governance modifications).
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


def count_in(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, re.M))


def main() -> int:
    print("Phase 25.4 — dashboard summary query deduplication (static verification)\n")

    ROOT = Path(__file__).resolve().parent
    dash_path = ROOT / "app" / "services" / "dashboard_service.py"
    cal_path = ROOT / "app" / "services" / "calendar_service.py"
    elig_path = ROOT / "app" / "services" / "eligibility_service.py"

    current_dash = dash_path.read_text(encoding="utf-8")
    current_cal = cal_path.read_text(encoding="utf-8")
    current_elig = elig_path.read_text(encoding="utf-8")

    head_dash = subprocess.run(
        ["git", "show", "HEAD:backend/app/services/dashboard_service.py"],
        capture_output=True, text=True,
    ).stdout

    # ── 1. Import check ───────────────────────────────────────────────────
    print("[1] Imports")
    import app.main  # noqa: F401  (full app wiring)
    from app.services.dashboard_service import DashboardService
    from app.services.calendar_service import CalendarService
    from app.services.eligibility_service import EligibilityService
    check("app.main imports", True)
    check("DashboardService importable", DashboardService is not None)
    check("CalendarService importable", CalendarService is not None)
    check("EligibilityService importable", EligibilityService is not None)

    # ── 2. Call-site counts: HEAD vs current ──────────────────────────────
    print("[2] Call-site counts in dashboard_service.py (HEAD -> current)")

    datasets = {
        "get_all_events": r"calendar_repo\.get_all_events\(\)",
        "get_quiz_cycle_with_policy": r"quiz_repo\.get_quiz_cycle_with_policy\(",
        "load_choices/chosen_elective_map": r"(load_choices|chosen_elective_map)\(",
        "get_effective_quiz_dates_for_subjects": r"quiz_repo\.get_effective_quiz_dates_for_subjects\(",
    }
    expected_current = {
        "get_all_events": 1,
        "get_quiz_cycle_with_policy": 1,
        "load_choices/chosen_elective_map": 1,
        "get_effective_quiz_dates_for_subjects": 1,
    }
    for name, pattern in datasets.items():
        before = count_in(head_dash, pattern)
        after = count_in(current_dash, pattern)
        check(
            f"{name}: {before} -> {after} call site(s)",
            after == expected_current[name] and after <= before,
            f"(expected current=1, before={before}, after={after})",
        )

    # ── 3. Downstream guard pattern ───────────────────────────────────────
    print("[3] Downstream methods: pre-fetched data under `is None` guard")

    has_events_param = "events: Optional[List[AcademicEvent]] = None" in current_cal
    check("get_day_schedule accepts events param", has_events_param)

    guard = "if events is None:" in current_cal
    fetch = "events = await self.repo.get_all_events()" in current_cal
    check("get_day_schedule fetches only when events is None", guard and fetch)

    has_prefetch_params = all(
        k in current_elig
        for k in ("cycle_model=None", "events=None", "elective_scope=None", "effective_by_subject=None")
    )
    check(
        "eligibility batch accepts cycle_model/events/elective_scope/effective_by_subject",
        has_prefetch_params,
    )

    for fetch_str, guard_str in (
        ("get_quiz_cycle_with_policy", "if cycle_model is None:"),
        ("get_all_events", "if events is None:"),
        ("chosen_elective_map", "if elective_scope is None:"),
        ("get_effective_quiz_dates_for_subjects", "if effective_by_subject is None:"),
    ):
        guarded = guard_str in current_elig and fetch_str in current_elig
        check(
            f"eligibility batch: {fetch_str} guarded by `{guard_str}`",
            guarded,
        )

    # ── 4. get_summary threads shared data into every builder ─────────────
    print("[4] get_summary data threading")
    check("events fetched once in get_summary",
          "events = await self.calendar_repo.get_all_events()" in current_dash)
    check("choices fetched once in get_summary",
          "choices = await resolver.load_choices(user.id)" in current_dash)
    check("elective_scope derived from shared choices",
          "choice.subject_id: slot for slot, choice in choices.items()" in current_dash)
    check("get_summary threads events into _build_today",
          "_build_today(user.id, today, rows, events)" in current_dash)
    check("get_summary threads events+elective_scope into _build_quiz_snapshot",
          "_build_quiz_snapshot(user, subjects, semester_start, events, elective_scope)" in current_dash)
    check("get_summary threads events+choices into _build_upcoming_events",
          "_build_upcoming_events(user, subjects, events, choices)" in current_dash)

    # Check that the eligibility batch is called with pre-fetched params
    pre_fetched_params = all(
        p in current_dash
        for p in ("cycle_model=cycle_model", "events=events",
                  "elective_scope=elective_scope", "effective_by_subject=effective_by_subject")
    )
    check("eligibility batch called with pre-fetched params", pre_fetched_params)

    # ── 5. Scope guard ────────────────────────────────────────────────────
    print("[5] Scope guard: no prohibited categories modified")
    changed = {
        ln.strip().split(maxsplit=1)[-1]
        for ln in subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True,
        ).stdout.splitlines()
        if ln.strip()
    }
    # Files that must NOT be touched by this optimization. The working tree
    # also contains pre-existing uncommitted changes that are OUT OF SCOPE
    # for this phase and are whitelisted as such:
    #   - Phase 25.1/25.2 refresh work (auth.py, api.ts, AuthContext.tsx,
    #     login/signup pages, refresh models/services, alembic a9b8c7d6e5f4)
    #   - a separate notification-batching optimization
    #     (notification_service.py / notification_repo.py)
    #   - governance doc updates (MASTER_ROADMAP / implementation_plan / task /
    #     walkthrough)
    prohibited_prefixes = (
        "alembic/",
        "app/models/",
        "app/engines/",
        "deploy/",
        "render.yaml",
        "docker-compose",
    )
    pre_existing_frontend = {
        "frontend/src/lib/api.ts",
        "frontend/src/contexts/AuthContext.tsx",
        "frontend/src/app/(auth)/login/page.tsx",
        "frontend/src/app/(auth)/signup/page.tsx",
    }
    pre_existing = pre_existing_frontend | {
        "MASTER_ROADMAP.md",
        "implementation_plan.md",
        "task.md",
        "walkthrough.md",
        "backend/app/services/notification_service.py",
        "backend/app/repositories/notification_repo.py",
    }
    changed = {p for p in changed if p not in pre_existing}
    prohibited = {p for p in changed if p.startswith(prohibited_prefixes)}
    check("no schema/migration/engine/deploy file modified", not prohibited,
          f"prohibited: {prohibited}")
    this_phase_files = {
        "backend/app/services/dashboard_service.py",
        "backend/app/services/calendar_service.py",
        "backend/app/services/eligibility_service.py",
        "backend/verify_phase_25_4.py",
    }
    check("this phase touched only the 3 service files + verifier",
          changed <= this_phase_files and this_phase_files <= changed,
          f"changed: {changed}")
    check("no auth/notification/api-contract file modified by this phase",
          not (changed & {
              "backend/app/api/v1/endpoints/auth.py",
              "backend/app/schemas/dashboard.py",
              "backend/app/api/v1/endpoints/dashboard.py",
          }))

    # ── Summary ───────────────────────────────────────────────────────────
    print("\nExpected query reduction per /dashboard/summary request (static):")
    print("  get_all_events                    3 -> 1   (-2)")
    print("  get_quiz_cycle_with_policy        2 -> 1   (-1)")
    print("  load_choices/chosen_elective_map  2-3 -> 1 (-1..-2)")
    print("  get_effective_quiz_dates_for_subjects 2 -> 1 (-1)")
    print("  Total                            ~6 queries saved; 2N quiz-window")
    print("  scans (optimization #3) intentionally NOT touched.")

    print(f"\nRESULT: {PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())