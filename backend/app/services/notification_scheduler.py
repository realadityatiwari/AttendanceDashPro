"""
EVT-005 — CLASS_REMINDER production scheduler.

The deep audit (docs/EVENTS_BACKEND_DEEP_AUDIT_REPORT.md, EVT-005 / H-4d)
established that CLASS_REMINDER generation was unreachable in production: the
only producer was the explicit, callable sweep
(``NotificationService.regenerate_user_notifications``), which had no
production caller — the ``class_reminders`` user preference silently did
nothing.

This module closes that gap with the deployment contract the EVT-005
configuration (``app/core/config.py``) already declared: a background asyncio
task started from the FastAPI lifespan that periodically regenerates the
canonical notification projections for every user opted into class reminders.

Correctness properties (the audit's challenge list):

- Deployment: started in ``app.main``'s lifespan, so it runs inside the
  production web process (Docker CMD / Render service) — it cannot silently
  disappear with a request, and there is no separate worker process to
  deploy.
- Single start: ``start_class_reminder_scheduler`` is idempotent (an already
  running task is returned, never duplicated — e.g. double lifespan events or
  accidental re-imports).
- Overlapping executions are safe AND prevented: the sweep is idempotent by
  construction (``emit`` → ``INSERT … ON CONFLICT DO NOTHING`` keyed on
  (user_id, kind, occurrence_key); existing rows refresh in place and never
  re-push), and an in-process guard makes an overrunning pass skip the next
  tick instead of stacking work.
- Multiple workers: each process runs its own sweep; a concurrent duplicate
  emission loses the ON CONFLICT race and takes the no-push refresh path —
  duplicate reminders remain impossible.
- Timezone: all date semantics come from ``institution_today()``
  (Asia/Kolkata) inside the existing projection builders — unchanged.
- Lead time: the sweep invokes the EXISTING ``_class_reminders`` builder
  (current day → end of the institutional week, unmarked, non-cancelled
  sessions) — identical to the semantics the preference has always
  advertised; no new reminder policy is introduced.
- Exclusions: cancelled (``occurrence_is_cancelled``) and already-marked
  sessions are excluded by the builder; deactivated extras always carry an
  attendance record and are therefore excluded too; past sessions fall
  outside the ``[today, week_end]`` window.
- Isolation: one database session per user, each user swept inside its own
  try/except — one failing user can never abort the pass or crash the task.
  The task itself survives any error (logged, never raised).

The sweep regenerates ALL canonical kinds for opted-in users (not only
CLASS_REMINDER): those projections are keyed identically to what the mutation
triggers already write, so this can only refresh in place what already exists
or materialize the canonical projection — never a duplicate or a re-push.
"""
import asyncio
import logging
from uuid import UUID

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.repositories.preference_repo import PreferenceRepository
from app.services.notification_service import NotificationService

logger = logging.getLogger("app.notification.scheduler")

_scheduler_task: asyncio.Task | None = None
_sweep_in_progress = False


async def run_class_reminder_sweep_once(
    *,
    push_sink=None,
    session_factory=AsyncSessionLocal,
    user_ids: list[UUID] | None = None,
) -> int:
    """Run ONE sweep pass over every user opted into class reminders.

    Returns the number of users whose projections were regenerated. When a
    pass is already running in this process, the call is skipped (returns 0)
    — the periodic loop's interval guarantees another chance, and skipping
    keeps overlapping executions from stacking on a slow pass.

    ``push_sink`` (optional) receives (user_id, payload) for every Web-Push
    dispatch instead of the real ``PushDispatchService`` (verifier seam; the
    production default dispatches real pushes exactly as the mutation
    triggers do).

    ``session_factory`` (optional) overrides the session factory (verifier
    seam for transactional sandbox tests).

    ``user_ids`` (optional) restricts the pass to these opted-in user ids
    (verifier seam for scoped runs); the default sweeps every opted-in user.

    Per-user failures are logged and swallowed: a failing user neither aborts
    the pass nor affects any other user. This function NEVER commits anything
    outside the per-user sessions it creates.
    """
    global _sweep_in_progress
    if _sweep_in_progress:
        logger.warning(
            "CLASS_REMINDER sweep skipped: the previous pass is still running"
        )
        return 0
    _sweep_in_progress = True
    try:
        async with session_factory() as db:
            opted_in = await PreferenceRepository(db).get_class_reminder_user_ids()
        if user_ids is not None:
            requested = {uid if isinstance(uid, UUID) else UUID(str(uid))
                         for uid in user_ids}
            opted_in = [uid for uid in opted_in if uid in requested]
        if not opted_in:
            return 0

        dispatched = 0
        for user_id in opted_in:
            try:
                async with session_factory() as db:
                    user = await db.get(User, user_id)
                    if user is None or not user.is_active:
                        # Deactivated users keep no working session (H-2 kill
                        # switch) — nothing to remind.
                        continue
                    service = NotificationService(db, push_dispatch=_wrap_sink(push_sink))
                    await service.regenerate_user_notifications(user)
                    dispatched += 1
            except Exception:
                logger.exception(
                    "CLASS_REMINDER sweep failed for user %s (continuing)",
                    user_id,
                )
        logger.info("CLASS_REMINDER sweep completed for %d user(s)", dispatched)
        return dispatched
    finally:
        _sweep_in_progress = False


def _wrap_sink(push_sink):
    """Adapt the verifier push sink to NotificationService's push_dispatch
    callable shape; None keeps the production dispatch path."""
    if push_sink is None:
        return None

    async def _dispatch(user_id: UUID, payload):
        push_sink((user_id, payload))

    return _dispatch


async def _class_reminder_loop() -> None:
    """The periodic sweep loop (one per process). Never raises: errors are
    logged and the loop continues after its interval."""
    startup_delay = max(0, int(settings.CLASS_REMINDER_SWEEP_STARTUP_DELAY_SECONDS))
    if startup_delay:
        await asyncio.sleep(startup_delay)
    interval_seconds = max(1, int(settings.CLASS_REMINDER_SWEEP_INTERVAL_MINUTES)) * 60
    while True:
        try:
            await run_class_reminder_sweep_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Defensive: run_class_reminder_sweep_once is already isolated,
            # but the task must survive anything.
            logger.exception("CLASS_REMINDER scheduler tick failed")
        await asyncio.sleep(interval_seconds)


def start_class_reminder_scheduler() -> asyncio.Task | None:
    """Start the periodic sweep task (idempotent). Returns None when the
    scheduler is disabled by configuration (CLASS_REMINDER_SWEEP_ENABLED)."""
    global _scheduler_task
    if not settings.CLASS_REMINDER_SWEEP_ENABLED:
        logger.info("CLASS_REMINDER scheduler disabled by configuration")
        return None
    if _scheduler_task is not None and not _scheduler_task.done():
        return _scheduler_task  # already running — never started twice
    _scheduler_task = asyncio.create_task(_class_reminder_loop())
    logger.info(
        "CLASS_REMINDER scheduler started (interval=%dm, startup delay=%ds)",
        settings.CLASS_REMINDER_SWEEP_INTERVAL_MINUTES,
        settings.CLASS_REMINDER_SWEEP_STARTUP_DELAY_SECONDS,
    )
    return _scheduler_task


async def stop_class_reminder_scheduler() -> None:
    """Cancel the periodic sweep task (FastAPI shutdown). Safe to call when
    it was never started (disabled configuration / already stopped)."""
    global _scheduler_task
    if _scheduler_task is None:
        return
    _scheduler_task.cancel()
    try:
        await _scheduler_task
    except asyncio.CancelledError:
        pass
    _scheduler_task = None
    logger.info("CLASS_REMINDER scheduler stopped")
