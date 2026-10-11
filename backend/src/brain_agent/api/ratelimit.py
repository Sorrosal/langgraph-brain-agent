"""In-process token-bucket rate limiting.

Single-replica only: every process keeps its own buckets, so with N replicas a client can make
up to N times the configured rate. A shared limiter (Redis or the database) is phase 7 work.
Behind a reverse proxy run uvicorn with ``--proxy-headers`` (and a trusted-proxy list) so the
client IP is the real one; ``X-Forwarded-For`` is never read here.
"""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request

from brain_agent.api.errors import ApiError

MAX_BUCKETS = 10_000


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """Token buckets keyed by an arbitrary string; each bucket starts full."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}

    def hit(self, key: str, limit: int, per_seconds: float) -> float | None:
        """Take one token of ``limit`` per ``per_seconds``; seconds to wait when it is empty."""
        now = self._clock()
        rate = limit / per_seconds
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= MAX_BUCKETS:
                self._prune(now)
            bucket = self._buckets[key] = _Bucket(limit, now)
        bucket.tokens = min(limit, bucket.tokens + (now - bucket.updated) * rate)
        bucket.updated = now
        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return None
        return (1 - bucket.tokens) / rate

    def _prune(self, now: float) -> None:
        """Drop buckets idle for over an hour (they have long been full again)."""
        self._buckets = {k: b for k, b in self._buckets.items() if now - b.updated < 3600}


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce(request: Request, group: str, subject: str, limit: int, per_seconds: float) -> None:
    """Raise 429 with ``Retry-After`` when ``subject`` exceeded ``limit`` in ``group``."""
    limiter: RateLimiter = request.app.state.limiter
    wait = limiter.hit(f"{group}:{subject}", limit, per_seconds)
    if wait is not None:
        retry_after = str(max(1, math.ceil(wait)))
        raise ApiError(
            429, "rate_limited", "Too many requests; slow down.", {"Retry-After": retry_after}
        )
