"""Generic token-bucket rate limiter.

Complements ``app/core/websocket_guard.py:WsRateLimiter`` which is
WebSocket-specific. This module provides a generic per-key token bucket
suitable for HTTP endpoints, background job dispatch, outbound API calls or
any other rate-limited path.

Design notes
------------
- Lazy token refill (we only top up on ``acquire``) – no background thread.
- LRU eviction at ``max_keys`` to cap memory (Lesson 30 / 10).
- Thread-safe: all reads/writes of the internal dict are under ``self._lock``.
- Clock is injectable for tests (``clock=lambda: fake_time``).
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable

DEFAULT_MAX_KEYS = 10_000
_EVICT_FRACTION = 0.2


class TokenBucket:
    """Rate-limit state for a single key."""

    __slots__ = ("capacity", "refill_per_sec", "tokens", "last_refill")

    def __init__(self, capacity: float, refill_per_sec: float, tokens: float, last_refill: float):
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.tokens = tokens
        self.last_refill = last_refill


class RateLimiter:
    """Per-key token bucket rate limiter.

    Parameters
    ----------
    capacity:
        Maximum number of tokens a bucket can hold (burst size).
    refill_per_sec:
        How many tokens are added per second.
    max_keys:
        Upper bound on number of tracked keys; LRU eviction drops the oldest
        ``_EVICT_FRACTION`` when exceeded.
    clock:
        Monotonic clock function (defaults to :func:`time.monotonic`).
    """

    def __init__(
        self,
        capacity: float = 10.0,
        refill_per_sec: float = 1.0,
        max_keys: int = DEFAULT_MAX_KEYS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        if refill_per_sec <= 0:
            raise ValueError("refill_per_sec must be > 0")
        if max_keys <= 0:
            raise ValueError("max_keys must be > 0")
        self.capacity = float(capacity)
        self.refill_per_sec = float(refill_per_sec)
        self.max_keys = int(max_keys)
        self._clock = clock
        # OrderedDict gives us O(1) move-to-end for LRU semantics.
        self._buckets: OrderedDict[str, TokenBucket] = OrderedDict()
        self._lock = threading.Lock()

    def _evict_if_needed(self) -> None:
        """Drop oldest ``_EVICT_FRACTION`` of keys when over ``max_keys``."""
        over = len(self._buckets) - self.max_keys
        if over <= 0:
            return
        to_drop = max(over, int(self.max_keys * _EVICT_FRACTION))
        for _ in range(min(to_drop, len(self._buckets))):
            self._buckets.popitem(last=False)

    def _get_bucket(self, key: str) -> TokenBucket:
        bucket = self._buckets.get(key)
        now = self._clock()
        if bucket is None:
            bucket = TokenBucket(
                capacity=self.capacity,
                refill_per_sec=self.refill_per_sec,
                tokens=self.capacity,
                last_refill=now,
            )
            self._buckets[key] = bucket
            self._evict_if_needed()
        else:
            elapsed = max(0.0, now - bucket.last_refill)
            if elapsed > 0:
                bucket.tokens = min(
                    bucket.capacity, bucket.tokens + elapsed * bucket.refill_per_sec
                )
                bucket.last_refill = now
            # Mark as recently used.
            self._buckets.move_to_end(key)
        return bucket

    def acquire(self, key: str, cost: float = 1.0) -> bool:
        """Attempt to consume ``cost`` tokens for ``key``. Returns True on success."""
        if cost <= 0:
            return True
        with self._lock:
            bucket = self._get_bucket(key)
            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return True
            return False

    def retry_after(self, key: str, cost: float = 1.0) -> float:
        """Return the number of seconds until ``cost`` tokens are available."""
        if cost <= 0:
            return 0.0
        with self._lock:
            bucket = self._get_bucket(key)
            if bucket.tokens >= cost:
                return 0.0
            missing = cost - bucket.tokens
            return missing / bucket.refill_per_sec

    def peek(self, key: str) -> float:
        """Return current (refill-adjusted) token count without consuming."""
        with self._lock:
            return self._get_bucket(key).tokens

    def reset(self, key: str | None = None) -> None:
        """Reset a single key or the entire limiter state."""
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)

    def stats(self) -> dict[str, int]:
        """Return summary statistics (useful for health dashboards)."""
        with self._lock:
            return {
                "tracked_keys": len(self._buckets),
                "max_keys": self.max_keys,
            }
