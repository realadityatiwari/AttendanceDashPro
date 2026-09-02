"""
Phase 11C-P2 verification — Push Subscription Persistence.

Verifies the Phase 11C-P2 contract end-to-end against the real database
(httpx ASGITransport + real DB + minted JWTs, the established pattern). The
push_subscriptions table is a pure storage registry: no push messages are sent
(P3), no notifications are triggered (P4), and no in-app notification behavior
changes.

Checks:

  1.  Table structure: columns, FK, UNIQUE(endpoint), index exist.
  2.  Unauthenticated POST /api/v1/push-subscriptions → 401.
  3.  Invalid endpoint (not https) → 422.
  4.  Missing keys → 422.
  5.  Client-supplied user_id → 422 (extra="forbid").
  6.  Valid subscription (user A) → 200, returns id + endpoint.
  7.  Same endpoint again (user A) → 200, same id (idempotent).
  8.  Second endpoint (user A) → 200, different id (multi-device).
  9.  Third endpoint (user B) → 200 (ownership isolation).
  10. DELETE user A's subscription (endpoint 1) → 204.
  11. DELETE user A's subscription of user B's endpoint → 404 (ownership).
  12. DELETE with bogus UUID → 404.
  13. DB-level: UNIQUE(endpoint) enforced (raw INSERT duplicate fails).
  14. DB-level: FK enforced (raw INSERT with nonexistent user fails).
  15. Service-level: register idempotency (repeated call → 1 row).
  16. Service-level: unsubscribe ownership (user A delete user B's id → False).
  17. Baseline push_subscriptions count restored (only temp rows removed).

State changes are this script's own artifacts (two temp users + their push
subscription rows) and are removed in the finally block. No frozen system is
touched.

Usage:
    python scripts/verify_phase_11c_p2.py
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import httpx

from app.main import app
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.models.enums import UserRole
from sqlalchemy import select, func, delete, text, Inspector
from sqlalchemy.dialects.postgresql import insert as pg_insert

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


async def main() -> int:
    async with AsyncSessionLocal() as db:
        # Snapshot the baseline push_subscriptions count.
        baseline_count = (await db.execute(
            select(func.count()).select_from(PushSubscription)
        )).scalar() or 0

        # Two temp users for ownership/isolation tests.
        user_a = User(roll_number="PH11CP2_A", name="Phase 11C-P2 User A", role=UserRole.STUDENT)
        user_b = User(roll_number="PH11CP2_B", name="Phase 11C-P2 User B", role=UserRole.STUDENT)
        db.add(user_a)
        db.add(user_b)
        await db.flush()
        user_a_id = user_a.id
        user_b_id = user_b.id
        await db.commit()

    token_a = create_access_token(str(user_a_id), "PH11CP2_A")
    token_b = create_access_token(str(user_b_id), "PH11CP2_B")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Subscription endpoints for testing.
    ENDPOINT_A = "https://fcm.googleapis.com/fcm/send/test-endpoint-a"
    ENDPOINT_B = "https://fcm.googleapis.com/fcm/send/test-endpoint-b"
    ENDPOINT_C = "https://fcm.googleapis.com/fcm/send/test-endpoint-c"
    P256DH = "B" + "x" * 86
    AUTH = "y" * 22
    SUB_A_ID = None
    SUB_A2_ID = None
    SUB_B_ID = None

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            # --- 1. Table structure (via raw SQL) --------------------------------
            async with AsyncSessionLocal() as db:
                check("1. push_subscriptions table exists",
                      bool((await db.execute(text(
                          "SELECT to_regclass('public.push_subscriptions')"
                      ))).scalar()))
                cols = set(
                    row[0] for row in (await db.execute(text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'push_subscriptions'"
                    ))).fetchall()
                )
                check("1b. push_subscriptions columns (id, user_id, endpoint, "
                      "p256dh, auth, created_at, updated_at)",
                      cols >= {"id", "user_id", "endpoint", "p256dh", "auth",
                               "created_at", "updated_at"},
                      f"got {sorted(cols)}")
                unique = set(
                    (row[0], row[1]) for row in (await db.execute(text(
                        "SELECT conname, contype FROM pg_constraint "
                        "WHERE conrelid = 'push_subscriptions'::regclass "
                        "AND contype = 'u'"
                    ))).fetchall()
                )
                check("1c. UNIQUE(endpoint) constraint exists",
                      any("endpoint" in str(n) for n, t in unique),
                      f"unique_constraints={unique}")
                fk = set(
                    (row[0], row[1]) for row in (await db.execute(text(
                        "SELECT conname, contype FROM pg_constraint "
                        "WHERE conrelid = 'push_subscriptions'::regclass "
                        "AND contype = 'f'"
                    ))).fetchall()
                )
                check("1d. FK to users.id exists",
                      len(fk) >= 1, f"fk_constraints={fk}")
                idx = set(
                    row[0] for row in (await db.execute(text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE tablename = 'push_subscriptions'"
                    ))).fetchall()
                )
                check("1e. Index on user_id exists",
                      any("user_id" in str(n) for n in idx), f"indexes={idx}")

            # --- 2. Unauthenticated POST → 401 -----------------------------------
            r = await c.post("/api/v1/push-subscriptions",
                             json={"endpoint": ENDPOINT_A, "keys": {"p256dh": P256DH, "auth": AUTH}})
            check("2. unauthenticated POST → 401", r.status_code == 401,
                  f"got {r.status_code}")

            # --- 3. Invalid endpoint (not https) → 422 ----------------------------
            r = await c.post("/api/v1/push-subscriptions", headers=headers_a,
                             json={"endpoint": "http://example.com/not-https",
                                   "keys": {"p256dh": P256DH, "auth": AUTH}})
            check("3. non-HTTPS endpoint → 422", r.status_code == 422,
                  f"got {r.status_code}")

            # --- 4. Missing keys → 422 --------------------------------------------
            r = await c.post("/api/v1/push-subscriptions", headers=headers_a,
                             json={"endpoint": ENDPOINT_A, "keys": {}})
            check("4. missing keys → 422",
                  r.status_code == 422, f"got {r.status_code} {r.json()}")

            # --- 5. Client-supplied user_id → 422 (extra="forbid") ----------------
            r = await c.post("/api/v1/push-subscriptions", headers=headers_a,
                             json={"endpoint": ENDPOINT_A, "keys": {"p256dh": P256DH, "auth": AUTH},
                                   "user_id": str(user_b_id)})
            check("5. client-supplied user_id → 422 (extra=forbid)",
                  r.status_code == 422, f"got {r.status_code}")

            # --- 6. Valid subscription (user A) → 200 -----------------------------
            r = await c.post("/api/v1/push-subscriptions", headers=headers_a,
                             json={"endpoint": ENDPOINT_A, "keys": {"p256dh": P256DH, "auth": AUTH}})
            body = r.json()
            SUB_A_ID = body.get("id")
            check("6. valid subscription → 200, returns id + endpoint + timestamps",
                  r.status_code == 200
                  and isinstance(body.get("id"), str)
                  and body.get("endpoint") == ENDPOINT_A
                  and "created_at" in body
                  and "updated_at" in body,
                  f"got {r.status_code} {sorted(body.keys())}")

            # --- 7. Same endpoint again → 200, same id (idempotent) ---------------
            r = await c.post("/api/v1/push-subscriptions", headers=headers_a,
                             json={"endpoint": ENDPOINT_A, "keys": {"p256dh": P256DH, "auth": AUTH}})
            body2 = r.json()
            check("7. same endpoint → 200, same id (idempotent)",
                  r.status_code == 200 and body2.get("id") == SUB_A_ID,
                  f"got {r.status_code} id={body2.get('id')} expected={SUB_A_ID}")

            # --- 8. Second endpoint (user A) → 200, different id (multi-device) ---
            r = await c.post("/api/v1/push-subscriptions", headers=headers_a,
                             json={"endpoint": ENDPOINT_B,
                                   "keys": {"p256dh": P256DH, "auth": AUTH}})
            body3 = r.json()
            SUB_A2_ID = body3.get("id")
            check("8. second endpoint (multi-device) → 200, different id",
                  r.status_code == 200 and body3.get("id") != SUB_A_ID
                  and body3.get("endpoint") == ENDPOINT_B,
                  f"id={body3.get('id')}")

            # Count user A's subscriptions.
            async with AsyncSessionLocal() as db:
                count_a = (await db.execute(
                    select(func.count()).select_from(PushSubscription).where(
                        PushSubscription.user_id == user_a_id
                    )
                )).scalar()
            check("8b. user A has exactly 2 subscriptions (multi-device)",
                  count_a == 2, f"got {count_a}")

            # --- 9. Third endpoint (user B) → 200 (ownership isolation) -----------
            r = await c.post("/api/v1/push-subscriptions", headers=headers_b,
                             json={"endpoint": ENDPOINT_C,
                                   "keys": {"p256dh": P256DH, "auth": AUTH}})
            body4 = r.json()
            SUB_B_ID = body4.get("id")
            check("9. user B subscription → 200, different endpoint",
                  r.status_code == 200 and body4.get("endpoint") == ENDPOINT_C,
                  f"got {r.status_code}")

            # --- 10. DELETE user A's subscription (endpoint A) → 204 --------------
            r = await c.delete(f"/api/v1/push-subscriptions/{SUB_A_ID}",
                               headers=headers_a)
            check("10. DELETE own subscription → 204",
                  r.status_code == 204, f"got {r.status_code}")

            # --- 11. DELETE user A's subscription of user B's endpoint → 404 ------
            # User A tries to delete user B's subscription.
            r = await c.delete(f"/api/v1/push-subscriptions/{SUB_B_ID}",
                               headers=headers_a)
            check("11. DELETE another user's subscription → 404 (ownership)",
                  r.status_code == 404, f"got {r.status_code}")

            # --- 12. DELETE with bogus UUID → 404 --------------------------------
            r = await c.delete(
                "/api/v1/push-subscriptions/00000000-0000-0000-0000-000000000000",
                headers=headers_a)
            check("12. DELETE with bogus UUID → 404",
                  r.status_code == 404, f"got {r.status_code}")

            # --- 13. DB-level UNIQUE(endpoint) enforcement ------------------------
            async with AsyncSessionLocal() as db:
                try:
                    stmt = pg_insert(PushSubscription).values(
                        user_id=user_a_id, endpoint=ENDPOINT_B,
                        p256dh=P256DH, auth=AUTH,
                    )
                    await db.execute(stmt)
                    await db.commit()
                    unique_ok = False
                except Exception:
                    await db.rollback()
                    unique_ok = True
            check("13. DB-level UNIQUE(endpoint) enforced",
                  unique_ok, "duplicate endpoint was accepted")

            # --- 14. DB-level FK enforcement ---------------------------------------
            async with AsyncSessionLocal() as db:
                try:
                    bogus_id = "00000000-0000-0000-0000-000000000000"
                    stmt = pg_insert(PushSubscription).values(
                        user_id=bogus_id, endpoint="https://fcm.example.com/fk-test",
                        p256dh=P256DH, auth=AUTH,
                    )
                    await db.execute(stmt)
                    await db.commit()
                    fk_ok = False
                except Exception:
                    await db.rollback()
                    fk_ok = True
            check("14. DB-level FK (nonexistent user) enforced",
                  fk_ok, "invalid FK was accepted")

            # --- 15. Service-level register idempotency ---------------------------
            # Already tested via API (check 7). Confirm via count.
            async with AsyncSessionLocal() as db:
                # Only user A's remaining endpoint B should exist
                count_a_final = (await db.execute(
                    select(func.count()).select_from(PushSubscription).where(
                        PushSubscription.user_id == user_a_id
                    )
                )).scalar() or 0
            check("15. service-level idempotency: user A has 1 remaining row "
                  "(endpoint A deleted, endpoint B exists)",
                  count_a_final == 1, f"got {count_a_final}")

            # --- 16. Service-level ownership (unsubscribe) ------------------------
            from app.services.push_subscription_service import PushSubscriptionService
            async with AsyncSessionLocal() as db:
                svc = PushSubscriptionService(db)
                # user A should NOT be able to delete user B's subscription
                removed = await svc.unsubscribe(user_a, SUB_B_ID)
                # user B should be able to delete own subscription
                removed_own = await svc.unsubscribe(user_b, SUB_B_ID)
            check("16a. user A cannot delete user B's subscription (returns False)",
                  not removed, f"got {removed}")
            check("16b. user B can delete own subscription (returns True)",
                  removed_own, f"got {removed_own}")

            # --- 17. Cleanup: user A deletes remaining endpoint B -----------------
            r = await c.delete(f"/api/v1/push-subscriptions/{SUB_A2_ID}",
                               headers=headers_a)
            check("17. cleanup deletion → 204",
                  r.status_code == 204, f"got {r.status_code}")

        # --- Final baseline check ------------------------------------------------
        async with AsyncSessionLocal() as db:
            final_count = (await db.execute(
                select(func.count()).select_from(PushSubscription)
            )).scalar() or 0
        check("18. push_subscriptions count restored to baseline",
              final_count == baseline_count,
              f"baseline={baseline_count} final={final_count}")

    except Exception:
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Remove temp users and any remaining test rows.
        async with AsyncSessionLocal() as db:
            await db.execute(delete(PushSubscription).where(
                PushSubscription.endpoint.in_([ENDPOINT_A, ENDPOINT_B, ENDPOINT_C])
            ))
            await db.execute(delete(User).where(User.roll_number.in_(
                ["PH11CP2_A", "PH11CP2_B"]
            )))
            await db.commit()

    # Summary
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"Phase 11C-P2 Verification: {passed}/{total} PASS")
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
