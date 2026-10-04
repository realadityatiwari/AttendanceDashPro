"""Bounded concurrency for independent READ queries (Phase 27 Batch 3C).

Production latency is dominated by serialized per-query network round trips
(Render -> Supabase). Within one request every query shares one AsyncSession,
and SQLAlchemy sessions never run concurrent operations — so genuinely
independent reads pay their round trips back to back.

This module provides ONE small, bounded helper: run a group of independent
read callables concurrently, each on its OWN short-lived session created from
the project's existing session factory (`AsyncSessionLocal`). It is not a
session-management architecture — the request session stays authoritative for
anything ordered or written; the helper only exists for independent read
groups that provably do not depend on each other's results.

Safety:
  - A module-level asyncio.Semaphore caps concurrent side sessions globally
    (MAX_CONCURRENT_READ_SESSIONS). Together with each request's own session,
    worst-case connections stay well under the engine pool limit (asyncpg
    defaults: pool_size 5 + max_overflow 10 = 15) even with several
    concurrent requests.
  - Results preserve input order; exceptions propagate after all lanes
    settle (same failure surface as the sequential code: any failing query
    fails the request).
  - Write operations are forbidden here by convention: only read callables
    may be passed (the helper neither commits nor flushes; closing a session
    without commit rolls back nothing that was read).
"""

import asyncio
from typing import Any, Callable, List, Sequence

from app.db.session import AsyncSessionLocal
from sqlalchemy.ext.asyncio import AsyncSession

# Global bound on concurrent side sessions (see module docstring for the
# pool-math). Deliberately conservative: latency win is already large at 4.
MAX_CONCURRENT_READ_SESSIONS = 4

_semaphore = asyncio.Semaphore(MAX_CONCURRENT_READ_SESSIONS)


async def run_independent_reads(
    fns: Sequence[Callable[[AsyncSession], Any]],
) -> List[Any]:
    """Run independent read callables concurrently, one short-lived session
    each, and return their results in input order.

    Each callable receives a fresh AsyncSession and must perform only reads
    that do not depend on another callable in the same group. ORM objects
    returned by a lane are detached but attribute-loaded when the group
    settles (expire_on_commit=False; no expiry on close) — consumers only
    read column attributes, which is the established pattern for these read
    models.
    """
    if not fns:
        return []

    async def _run(fn: Callable[[Any], Any]) -> Any:
        async with _semaphore:
            async with AsyncSessionLocal() as session:
                return await fn(session)

    return list(await asyncio.gather(*(_run(fn) for fn in fns)))
