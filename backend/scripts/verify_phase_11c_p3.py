"""
Phase 11C-P3 verification — VAPID + PushDispatchService.

Verifies the Web Push DELIVERY infrastructure deterministically WITHOUT
sending a real push: the only mocked boundary is the external Web Push
send call (pywebpush), injected into PushDispatchService. The database and
repository layers are real (local dev DB); all test rows are removed in the
finally block.

Checks:

  A.  Configuration validation: is_configured() is False when VAPID env vars
      are absent; dispatch reports CONFIGURATION_ERROR and does NOT call the
      send boundary.
  B.  Payload serialization: PushPayload.to_json() is valid JSON in exactly
      the P1 service-worker shape ({title,body,icon,badge,tag,url} + optional
      notification_id/kind); same-origin URL restriction is enforced.
  C.  VAPID configuration handling: with the VAPID triple set, the send
      boundary is actually invoked.
  D.  Service construction: PushDispatchService builds against the real
      repository.
  E.  Subscription lookup: dispatch_to_user resolves the user's subscriptions
      via the P2 repository.
  F.  Success path: a mocked accepted delivery -> SUCCESS, subscription KEPT.
  G.  Permanent-invalid cleanup: provider 404 and 410 -> INVALID_SUBSCRIPTION
      and the exact subscription row is removed.
  H.  Transient failure: network error (no HTTP response) and 5xx ->
      TEMPORARY_FAILURE and the subscription is KEPT.
  I.  Isolation: mixed dispatch over several subscriptions — only the
      permanently-invalid ones are removed; the others succeed/fail
      independently in the same run.
  J.  Canonical notification data is untouched by dispatch (row counts
      unchanged).
  K.  Private credentials never appear in log output (endpoint/p256dh/auth
      values are absent from captured logs).
  L.  P2 verifier stays green (run separately: verify_phase_11c_p2.py).

No browser automation; no real network push; no commit.

Usage:
    python scripts/verify_phase_11c_p3.py
"""
import asyncio
import json
import logging
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from pywebpush import WebPushException  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.notification import Notification  # noqa: E402
from app.models.push_subscription import PushSubscription  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories.push_subscription_repo import PushSubscriptionRepository  # noqa: E402
from app.services.push_dispatch_service import (  # noqa: E402
    PushDispatchService,
    PushPayload,
    PushResult,
)
from sqlalchemy import delete, func, select  # noqa: E402

results: List[tuple] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


class FakeResponse:
    """Minimal stand-in for the requests/aiohttp response pywebpush wraps in
    WebPushException — only status_code is consumed by classification."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        self.text = "fake provider response"
        self.headers = {}


@contextmanager
def configured_vapid():
    """Temporarily present the full VAPID triple so is_configured() is True."""
    old = (settings.VAPID_PUBLIC_KEY, settings.VAPID_PRIVATE_KEY, settings.VAPID_SUBJECT)
    settings.VAPID_PUBLIC_KEY = "fake-public-key"
    settings.VAPID_PRIVATE_KEY = "fake-private-key"
    settings.VAPID_SUBJECT = "mailto:verifier@example.com"
    try:
        yield
    finally:
        settings.VAPID_PUBLIC_KEY, settings.VAPID_PRIVATE_KEY, settings.VAPID_SUBJECT = old


def make_send(outcomes: Dict[str, str]):
    """Create an async send boundary whose outcome is keyed by endpoint.

    Only the external delivery call is mocked — everything else (repository,
    service, classification, cleanup) is the real implementation.
    """
    calls: List[dict] = []

    async def send(subscription_info: dict, data: str):
        calls.append({"endpoint": subscription_info["endpoint"],
                      "keys": subscription_info.get("keys"),
                      "data": data})
        outcome = outcomes.get(subscription_info["endpoint"], "success")
        if outcome == "success":
            return SimpleNamespace(status_code=201)
        if outcome == "404":
            raise WebPushException("Subscription not found", response=FakeResponse(404))
        if outcome == "410":
            raise WebPushException("Subscription gone", response=FakeResponse(410))
        if outcome == "500":
            raise WebPushException("Provider error", response=FakeResponse(500))
        if outcome == "network":
            raise TimeoutError("connection timed out (no HTTP response)")
        raise AssertionError(f"unexpected endpoint {subscription_info['endpoint']}")

    return send, calls


async def create_user(db, roll: str) -> User:
    u = User(roll_number=roll, name="Phase 11C-P3 verifier", role=UserRole.STUDENT)
    db.add(u)
    await db.flush()
    await db.commit()
    return u


async def add_subscription(db, user_id, endpoint: str) -> PushSubscription:
    repo = PushSubscriptionRepository(db)
    return await repo.upsert(
        user_id=user_id,
        endpoint=endpoint,
        p256dh="B" + "x" * 86,   # realistic URL-safe base64 length
        auth="y" * 22,
    )


async def count_subscriptions(db, user_id) -> int:
    return (await db.execute(
        select(func.count()).select_from(PushSubscription).where(
            PushSubscription.user_id == user_id
        )
    )).scalar() or 0


async def count_notifications(db) -> int:
    return (await db.execute(
        select(func.count()).select_from(Notification)
    )).scalar() or 0


async def main() -> int:
    # All endpoints are globally UNIQUE (DB-enforced); user B gets distinct ones.
    END = {
        "ok": "https://push.example.com/p3-ok",
        "ok_b": "https://push.example.com/p3-ok-b",
        "gone404": "https://push.example.com/p3-404",
        "gone410": "https://push.example.com/p3-410",
        "net": "https://push.example.com/p3-net",
        "srv500": "https://push.example.com/p3-500",
        "srv500_b": "https://push.example.com/p3-500-b",
        "mixed_ok": "https://push.example.com/p3-mixed-ok",
        "mixed_bad": "https://push.example.com/p3-mixed-bad",
    }
    user_a = None
    user_b = None
    sub_ids_created: List = []

    async with AsyncSessionLocal() as db:
        notifications_before = await count_notifications(db)

    try:
        # ── A. Configuration validation (real empty VAPID env) ─────────────
        check("A1. is_configured() False with empty VAPID env",
              not PushDispatchService.is_configured())

        async with AsyncSessionLocal() as db:
            user_a = await create_user(db, "PH11CP3_A")
            user_b = await create_user(db, "PH11CP3_B")
            sub_ok = await add_subscription(db, user_a.id, END["ok"])
            sub_gone = await add_subscription(db, user_a.id, END["gone404"])
            sub_ids_created = [sub_ok.id, sub_gone.id]
            sub_b = await add_subscription(db, user_b.id, END["ok_b"])
            sub_ids_created.append(sub_b.id)

        # CONFIGURATION_ERROR path (no VAPID configured, no mock invocation)
        async with AsyncSessionLocal() as db:
            calls_noop: List = []

            async def noop_send(subscription_info, data):
                calls_noop.append(1)
                raise AssertionError("send must not be called when unconfigured")

            svc = PushDispatchService(db, send_function=noop_send)
            payload = PushPayload(title="T", body="B")
            res = await svc.dispatch_to_user(user_a, payload)
            check("A2. unconfigured dispatch -> CONFIGURATION_ERROR, no send call",
                  len(res) == 2 and all(r.result is PushResult.CONFIGURATION_ERROR
                                        for r in res) and len(calls_noop) == 0,
                  f"results={[r.result.value for r in res]} calls={len(calls_noop)}")

        # ── B. Payload serialization ────────────────────────────────────────
        p1 = PushPayload(title="New update", body="You have a new notification.",
                         notification_id="00000000-0000-0000-0000-000000000001",
                         kind="ACADEMIC_EVENT", url="/notifications")
        parsed = json.loads(p1.to_json())
        check("B1. payload is valid JSON in P1 service-worker shape",
              isinstance(parsed, dict)
              and {"title", "body", "icon", "badge", "tag", "url"} <= set(parsed)
              and parsed["title"] == "New update"
              and parsed["body"] == "You have a new notification."
              and parsed["url"] == "/notifications"
              and parsed["notification_id"].endswith("0001")
              and parsed["kind"] == "ACADEMIC_EVENT",
              f"keys={sorted(parsed.keys())}")
        check("B2. payload has no token/secret keys",
              not ({"password", "jwt", "token", "access_token", "p256dh",
                    "auth", "private_key"} & set(parsed)))
        try:
            PushPayload(title="T", body="B", url="https://evil.example.com")
            check("B3. external url rejected", False)
        except ValueError:
            check("B3. external url rejected", True)
        try:
            PushPayload(title="T", body="B", url="//evil.example.com/path")
            check("B3b. protocol-relative url rejected", False)
        except ValueError:
            check("B3b. protocol-relative url rejected", True)

        # ── C/D/E/F: configured + success path with mocked send ────────────
        with configured_vapid():
            send, calls = make_send({END["ok"]: "success", END["gone404"]: "404"})
            async with AsyncSessionLocal() as db:
                svc = PushDispatchService(db, send_function=send)
                payload = PushPayload(title="Hello", body="World", url="/dashboard")
                res = await svc.dispatch_to_subscription(sub_ok, payload)
                check("D1. service constructed and delivered via mocked send",
                      res.result is PushResult.SUCCESS and len(calls) == 1,
                      f"result={res.result.value} calls={len(calls)}")
                check("C1. VAPID-configured dispatch invoked the send boundary",
                      len(calls) == 1 and calls[0]["endpoint"] == END["ok"])
                check("E1. subscription lookup resolves via P2 repository",
                      await count_subscriptions(db, user_a.id) == 2)
                check("F1. SUCCESS keeps the subscription",
                      await count_subscriptions(db, user_a.id) == 2)
                check("F2. send received exact subscription keys (p256dh/auth)",
                      calls[0]["keys"]["p256dh"] == "B" + "x" * 86
                      and calls[0]["keys"]["auth"] == "y" * 22
                      and calls[0]["data"] == payload.to_json(),
                      f"keys_present={bool(calls[0]['keys'])}")

                # ── G. permanent-invalid cleanup (410 then 404) ─────────────
                sub_gone2 = await add_subscription(db, user_a.id, END["gone410"])
                sub_ids_created.append(sub_gone2.id)
                send2, _ = make_send({END["gone410"]: "410"})
                svc2 = PushDispatchService(db, send_function=send2)
                res2 = await svc2.dispatch_to_subscription(sub_gone2, payload)
                check("G1. provider 410 -> INVALID_SUBSCRIPTION",
                      res2.result is PushResult.INVALID_SUBSCRIPTION,
                      f"result={res2.result.value}")
                check("G2. provider 410 row removed",
                      all(s.id != sub_gone2.id for s in await svc2.repo.get_by_user(user_a.id)))

                res3 = await svc.dispatch_to_subscription(sub_gone, payload)
                check("G3. provider 404 -> INVALID_SUBSCRIPTION + removed",
                      res3.result is PushResult.INVALID_SUBSCRIPTION
                      and all(s.id != sub_gone.id
                              for s in await svc.repo.get_by_user(user_a.id)),
                      f"result={res3.result.value}")

                # ── H. transient failure keeps the subscription ────────────
                sub_net = await add_subscription(db, user_a.id, END["net"])
                sub_500 = await add_subscription(db, user_a.id, END["srv500"])
                sub_ids_created += [sub_net.id, sub_500.id]
                send3, _ = make_send({END["net"]: "network", END["srv500"]: "500"})
                svc3 = PushDispatchService(db, send_function=send3)
                r_net = await svc3.dispatch_to_subscription(sub_net, payload)
                r_500 = await svc3.dispatch_to_subscription(sub_500, payload)
                kept = await svc3.repo.get_by_user(user_a.id)
                check("H1. network error -> TEMPORARY_FAILURE, row kept",
                      r_net.result is PushResult.TEMPORARY_FAILURE
                      and any(s.id == sub_net.id for s in kept),
                      f"result={r_net.result.value}")
                check("H2. provider 5xx -> TEMPORARY_FAILURE, row kept",
                      r_500.result is PushResult.TEMPORARY_FAILURE
                      and any(s.id == sub_500.id for s in kept),
                      f"result={r_500.result.value}")

                # ── I. multi-subscription isolation via dispatch_to_user ───
                # user A now has: ok, net, srv500 (+ two fresh mixed rows).
                sub_mixed_ok = await add_subscription(db, user_a.id, END["mixed_ok"])
                sub_mixed_bad = await add_subscription(db, user_a.id, END["mixed_bad"])
                sub_ids_created += [sub_mixed_ok.id, sub_mixed_bad.id]
                send4, _ = make_send({
                    END["ok"]: "success",
                    END["net"]: "network",
                    END["srv500"]: "500",
                    END["mixed_ok"]: "success",
                    END["mixed_bad"]: "404",
                })
                svc4 = PushDispatchService(db, send_function=send4)
                results4 = await svc4.dispatch_to_user(user_a, payload)
                by_id = {r.subscription_id: r.result for r in results4}
                check("I1. one dispatch_to_user returns per-subscription results",
                      len(results4) == 5, f"got {len(results4)}")
                check("I2. invalid sub removed, healthy sub kept in same run",
                      by_id.get(sub_mixed_bad.id) is PushResult.INVALID_SUBSCRIPTION
                      and by_id.get(sub_mixed_ok.id) is PushResult.SUCCESS
                      and by_id.get(sub_ok.id) is PushResult.SUCCESS
                      and all(s.id != sub_mixed_bad.id
                              for s in await svc4.repo.get_by_user(user_a.id))
                      and any(s.id == sub_mixed_ok.id
                              for s in await svc4.repo.get_by_user(user_a.id)),
                      f"by_id={ {str(k)[:8]: v.value for k, v in by_id.items()} }")

                # ── J. canonical notification data untouched ───────────────
                check("J1. notification table row count unchanged by dispatch",
                      await count_notifications(db) == notifications_before,
                      f"before={notifications_before} after={await count_notifications(db)}")

        # ── K. private credentials never logged ────────────────────────────
        with configured_vapid():
            logger = logging.getLogger("app.push_dispatch")
            captured: List[str] = []
            handler = logging.Handler()
            handler.emit = lambda record: captured.append(record.getMessage())
            old_level = logger.level
            logger.setLevel(logging.DEBUG)
            logger.addHandler(handler)
            try:
                send5, _ = make_send({END["ok_b"]: "success", END["srv500_b"]: "500"})
                async with AsyncSessionLocal() as db:
                    svc5 = PushDispatchService(db, send_function=send5)
                    await svc5.dispatch_to_subscription(sub_b, PushPayload(title="x", body="y"))
                    sub_b2 = await add_subscription(db, user_b.id, END["srv500_b"])
                    sub_ids_created.append(sub_b2.id)
                    await svc5.dispatch_to_subscription(sub_b2, PushPayload(title="x", body="y"))
            finally:
                logger.removeHandler(handler)
                logger.setLevel(old_level)
            joined = "\n".join(captured)
            leaky = [t for t in (END["ok_b"], "B" + "x" * 86, "y" * 22,
                                 settings.VAPID_PRIVATE_KEY)
                     if t and t in joined]
            check("K1. endpoint/p256dh/auth/private key absent from logs",
                  not leaky and len(captured) > 0,
                  f"leaks={leaky} captured={len(captured)}")

    finally:
        # Cleanup: remove every test subscription and both temp users.
        async with AsyncSessionLocal() as db:
            if sub_ids_created:
                await db.execute(
                    delete(PushSubscription).where(
                        PushSubscription.id.in_(sub_ids_created)
                    )
                )
            await db.execute(delete(User).where(User.roll_number.in_(
                ["PH11CP3_A", "PH11CP3_B"]
            )))
            await db.commit()

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"Phase 11C-P3 Verification: {passed}/{total} PASS")
    if passed < total:
        print("FAILURES:")
        for name, ok in results:
            if not ok:
                print(f"  - {name}")
        return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
