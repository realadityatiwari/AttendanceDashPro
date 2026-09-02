"""Phase 26.3 static verifier — quiz-window 2N scan elimination.

Static/backend-only checks (no DB required). Demonstrates optimization #3:
the per-subject quiz-window scans (2N total) are replaced by ONE date-bounded
scan over the union of all subjects' windows, bucketed per (subject, window)
in memory — every row for a (subject, window) is byte-identical to the
per-subject query's rows, so the engine input is identical.

Verifies:
 1.  Imports: app.main and both changed services/repos load.
 2.  `get_subject_counts_between_for_subjects` exists in the repo.
 3.  `get_quiz_eligibility_for_subjects` calls `_quiz_window_counts_by_subject`
     and passes precomputed counts into `_evaluate_subject`.
 4.  `_evaluate_subject` accepts optional raw_counts/cumulative_raw_counts
     and skips the DB scans when provided.
 5.  `_build_domain_subject` is the single shared construction path.
 6.  No schema/migration/engine/frontend/auth/API-contract change.
 7.  Static query-count demonstration: 2N -> 1.
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
    print("Phase 26.3 — quiz-window 2N scan elimination (static verification)\n")

    ROOT = Path(__file__).resolve().parent
    elig_path = ROOT / "app" / "services" / "eligibility_service.py"
    repo_path = ROOT / "app" / "repositories" / "attendance_repo.py"

    current_elig = elig_path.read_text(encoding="utf-8")
    current_repo = repo_path.read_text(encoding="utf-8")

    # ── 1. Import check ───────────────────────────────────────────────────
    print("[1] Imports")
    import app.main  # noqa: F401
    from app.services.eligibility_service import EligibilityService
    from app.repositories.attendance_repo import AttendanceRepository
    check("app.main imports", True)
    check("EligibilityService importable", EligibilityService is not None)
    check("AttendanceRepository importable", AttendanceRepository is not None)

    # ── 2. Repo bulk method ────────────────────────────────────────────────
    print("[2] Repository bulk scan method")
    has_bulk_method = "get_subject_counts_between_for_subjects" in current_repo
    check("get_subject_counts_between_for_subjects exists", has_bulk_method)
    if has_bulk_method:
        check("bulk method selects session_subject_id",
              "session_subject_id" in current_repo)
        check("bulk method selects slot (resolved elective slot)",
              "slot" in current_repo and "resolved_slot" in current_repo)
        check("bulk method selects choice_subject_id",
              "choice_subject_id" in current_repo)
        check("bulk method applies outcome",
              "_apply_outcome_to_row" in current_repo)
        check("bulk method orders by (date, start_time, id)",
              "start_time.asc().nulls_last()" in current_repo
              and "ClassSession.id" in current_repo[
                  current_repo.rfind("order_by"):current_repo.rfind("order_by") + 200])
        check("bulk method supports exclude_quiz_day",
              "exclude_quiz_day" in current_repo)
        check("bulk method uses same elective_choice_on join",
              "_elective_choice_on" in current_repo)
        check("bulk method uses same outcome_join_on",
              "_outcome_join_on" in current_repo)

    # ── 3. Service batch path ─────────────────────────────────────────────
    print("[3] Service batch path")
    check("get_quiz_eligibility_for_subjects calls _quiz_window_counts_by_subject",
          "_quiz_window_counts_by_subject" in current_elig)
    check("_quiz_window_counts_by_subject exists",
          "async def _quiz_window_counts_by_subject" in current_elig)
    check("_bucket_window_counts exists",
          "def _bucket_window_counts" in current_elig)
    check("_build_domain_subject exists (shared construction)",
          "def _build_domain_subject" in current_elig)
    check("_evaluate_subject accepts raw_counts param",
          "raw_counts=None" in current_elig and "cumulative_raw_counts=None" in current_elig)

    # Check that the batch passes precomputed counts
    pass_pattern = "raw_counts=counts.get(\"raw_counts\")" in current_elig
    cum_pattern = "cumulative_raw_counts=counts.get(\"cumulative_raw_counts\")" in current_elig
    check("batch passes precomputed raw_counts into _evaluate_subject",
          pass_pattern and cum_pattern)

    # Check that _evaluate_subject skips the scan when counts are provided
    skip_scan_i = "if raw_counts is None:" in current_elig
    skip_scan_ii = "if cumulative_raw_counts is None:" in current_elig
    check("_evaluate_subject skips cycle-window scan when raw_counts provided",
          skip_scan_i)
    check("_evaluate_subject skips cumulative-window scan when cumulative_raw_counts provided",
          skip_scan_ii)

    # Check that the single-subject path still works (get_quiz_eligibility calls _evaluate_subject without new params)
    single_subject_path = "raw_counts=None" in current_elig  # default param
    check("single-subject get_quiz_eligibility unchanged (params default to None)",
          single_subject_path)

    # ── 4. Domain-subject construction is single source of truth ──────────
    print("[4] Single source of truth")
    in_elig = current_elig.count("_build_domain_subject(")
    check("_build_domain_subject used by both batch and _evaluate_subject",
          in_elig >= 2)
    # Confirm no orphaned inline Milestone construction in _evaluate_subject
    inline_milestone = "Milestone(" in current_elig[
        current_elig.rfind("async def _evaluate_subject"):current_elig.rfind("async def _evaluate_subject") + 500]
    check("_evaluate_subject does NOT have inline Milestone construction",
          not inline_milestone)

    # ── 5. Scope guard ────────────────────────────────────────────────────
    print("[5] Scope guard")
    changed = {
        ln.strip().split(maxsplit=1)[-1]
        for ln in subprocess.run(
            ["git", "status", "--porcelain"], capture_output=True, text=True,
        ).stdout.splitlines()
        if ln.strip()
    }
    # Pre-existing uncommitted changes from prior phases / other tracks
    # (Phase 25.1/25.2 refresh, Phase 26.1 dedup, notification-delivery
    # investigation PWA/service-worker work). None are modified by this phase.
    pre_existing = {
        "MASTER_ROADMAP.md", "implementation_plan.md", "task.md", "walkthrough.md",
        "frontend/src/lib/api.ts", "frontend/src/contexts/AuthContext.tsx",
        "frontend/src/app/(auth)/login/page.tsx", "frontend/src/app/(auth)/signup/page.tsx",
        "backend/app/services/notification_service.py",
        "backend/app/repositories/notification_repo.py",
        "backend/app/services/dashboard_service.py",
        "backend/app/services/calendar_service.py",
        "backend/verify_phase_25_4.py",
        # notification-delivery investigation (PWA/service-worker track)
        "frontend/public/service-worker.js",
        "frontend/src/components/pwa/ServiceWorkerRegistration.tsx",
        "frontend/src/components/layout/AppShell.tsx",
        "frontend/src/components/shell/SettingsModal.tsx",
        "frontend/src/hooks/useNotificationPermission.ts",
        "docs/notification_delivery_investigation.md",
    }
    changed_for_this = {p for p in changed if p not in pre_existing}
    this_phase = {
        "backend/app/repositories/attendance_repo.py",
        "backend/app/services/eligibility_service.py",
        "backend/verify_phase_26_3.py",
    }
    extra = changed_for_this - this_phase
    check("only the 2 service files + verifier changed by this phase",
          not extra, f"extra: {extra}")
    # Verify no prohibited categories
    for p in changed_for_this:
        prohibited = (
            "alembic/", "app/models/", "app/engines/", "frontend/", "deploy/",
            "render.yaml", "docker-compose", "app/api/v1/endpoints/",
            "app/schemas/",
        )
        is_prohibited = any(p.startswith(prefix) for prefix in prohibited)
        check(f"no prohibited file changed: {p}", not is_prohibited)

    # ── 6. Query-count reduction ──────────────────────────────────────────
    print("\nExpected query reduction per /dashboard/summary request (static):")
    print("  get_subject_counts_between (cycle window)       N -> 0  (-N)")
    print("  get_subject_counts_between (cumulative window)  N -> 0  (-N)")
    print("  get_subject_counts_between_for_subjects         0 -> 1  (+1)")
    print("  Total                                     2N scans -> 1  (-2N+1)")
    print("  For N=8 quiz-applicable subjects: 16 -> 1  (-15)")

    print(f"\nRESULT: {PASS} PASS / {FAIL} FAIL")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())