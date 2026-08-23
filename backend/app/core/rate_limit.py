"""In-process sliding-window rate limiter (Phase 16).

Suitable for development/single-process deployment. For production multi-process
deployment, replace with a distributed limiter (Redis).
"""
import asyncio
import time
from typing import Tuple

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """Per-key sliding-window rate limiter using monotonic timestamps.

    Thread-safe via asyncio.Lock; intended for single-process use.
    """

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def _prune(self, key: str, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        hits = self._hits.get(key, [])
        self._hits[key] = [t for t in hits if t > cutoff]

    async def check(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        async with self._lock:
            await self._prune(key, window_seconds)
            hits = self._hits.get(key, [])
            if len(hits) >= limit:
                oldest = hits[0]
                retry = int(window_seconds - (time.monotonic() - oldest) + 1)
                return False, max(retry, 1)
            self._hits.setdefault(key, []).append(time.monotonic())
            return True, 0


# Global limiter instance
_limiter = SlidingWindowRateLimiter()


def rate_limit(limit: int, window_seconds: int, bucket: str):
    """FastAPI dependency factory for rate limiting.

    Usage::
        @router.post("/login")
        async def login(..., _: None = Depends(rate_limit(10, 900, "login"))):
    """
    async def _dep(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"{bucket}:{ip}"
        allowed, retry = await _limiter.check(key, limit, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(retry)},
            )
    return _dep