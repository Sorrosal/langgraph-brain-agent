"""In-process token-bucket rate limiting.

Single-replica only: every process keeps its own buckets, so with N replicas a client can make
up to N times the configured rate. A shared limiter (Redis or the database) is phase 7 work.
Behind a reverse proxy run uvicorn with ``--proxy-headers`` (and a trusted-proxy list) so the
client IP is the real one; ``X-Forwarded-For`` is never read here.
"""

import math
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request

from brain_agent.api.errors import ApiError

DEFAULT_MAX_BUCKETS = 10_000


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated: float
    limit: int
    rate: float

    def refilled(self, now: float) -> bool:
        """Full again, so forgetting the bucket changes nothing."""
        return self.tokens + (now - self.updated) * self.rate >= self.limit


class RateLimiter:
    """Token buckets keyed by an arbitrary string; each bucket starts full.

    Memory is bounded: buckets are kept in least-recently-used order, refilled idle ones are
    dropped from the old end, and at ``max_buckets`` the oldest is evicted (its owner then
    starts over with a full bucket, which is the safe direction for a limiter). All O(1) amortized.
    """

    def __init__(
        self, clock: Callable[[], float] = time.monotonic, max_buckets: int = DEFAULT_MAX_BUCKETS
    ) -> None:
        self._clock = clock
        self._max = max_buckets
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()

    @property
    def size(self) -> int:
        return len(self._buckets)

    def has(self, key: str) -> bool:
        return key in self._buckets

    def hit(self, key: str, limit: int, per_seconds: float) -> float | None:
        """Take one token of ``limit`` per ``per_seconds``; seconds to wait when it is empty."""
        now = self._clock()
        rate = limit / per_seconds
        self._drop_idle(now)
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self._max:
                self._buckets.popitem(last=False)
            bucket = self._buckets[key] = _Bucket(limit, now, limit, rate)
        else:
            self._buckets.move_to_end(key)
        bucket.tokens = min(limit, bucket.tokens + (now - bucket.updated) * rate)
        bucket.updated = now
        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return None
        return (1 - bucket.tokens) / rate

    def _drop_idle(self, now: float) -> None:
        while self._buckets:
            key, oldest = next(iter(self._buckets.items()))
            if not oldest.refilled(now):
                return
            del self._buckets[key]


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
