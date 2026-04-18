"""Unified TTL + LRU cache.

Replaces the three ad-hoc ``_TTLCache`` / ``_cache = {}`` implementations
scattered across ``services/market_data.py``, ``services/cryptopanic.py`` and
``services/knowledge.py`` with a single reusable primitive. Follows the
thread-safety pattern established in Lessons 19 / 24 / 49: all mutations
happen under a lock, read-check-write is atomic.

Highlights
----------
- Per-entry TTL, so a shared cache can mix short-lived (news) and long-lived
  (OHLCV) data.
- Size cap with LRU eviction – prevents unbounded memory growth.
- ``get_or_set`` avoids thundering-herd by holding the per-key lock during
  the producer call so concurrent lookups wait for the first producer.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

V = TypeVar("V")


@dataclass
class _Entry(Generic[V]):
    value: V
    expires_at: float


class TTLCache(Generic[V]):
    """Thread-safe TTL + LRU cache.

    Parameters
    ----------
    ttl_seconds:
        Default time-to-live for entries added without an explicit ttl.
    max_size:
        Upper bound on entries; LRU eviction kicks in on overflow.
    clock:
        Monotonic clock for testability.
    """

    def __init__(
        self,
        ttl_seconds: float = 60.0,
        max_size: int = 1024,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        if max_size <= 0:
            raise ValueError("max_size must be > 0")
        self._ttl = float(ttl_seconds)
        self._max_size = int(max_size)
        self._clock = clock
        self._data: OrderedDict[Any, _Entry[V]] = OrderedDict()
        self._lock = threading.Lock()
        # Per-key lock dict for get_or_set thundering-herd prevention.
        self._producer_locks: dict[Any, threading.Lock] = {}
        self._producer_lock_guard = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: Any) -> V | None:
        """Return cached value or ``None`` on miss/expiry."""
        now = self._clock()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.expires_at <= now:
                del self._data[key]
                self._misses += 1
                return None
            self._data.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: Any, value: V, ttl: float | None = None) -> None:
        """Store ``value`` under ``key`` with ``ttl`` (or default TTL)."""
        effective_ttl = float(ttl if ttl is not None else self._ttl)
        if effective_ttl <= 0:
            return
        expires_at = self._clock() + effective_ttl
        with self._lock:
            self._data[key] = _Entry(value=value, expires_at=expires_at)
            self._data.move_to_end(key)
            self._evict_locked()

    def delete(self, key: Any) -> None:
        """Remove a single key (no-op if absent)."""
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        """Drop all entries."""
        with self._lock:
            self._data.clear()
            self._hits = 0
            self._misses = 0

    def __contains__(self, key: Any) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def get_or_set(
        self,
        key: Any,
        producer: Callable[[], V],
        ttl: float | None = None,
    ) -> V:
        """Return cached value or invoke ``producer`` once and cache its result.

        Concurrent callers for the same missing key wait on a per-key lock so
        the producer runs exactly once (thundering-herd protection).
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        lock = self._get_producer_lock(key)
        with lock:
            cached = self.get(key)
            if cached is not None:
                return cached
            value = producer()
            self.set(key, value, ttl=ttl)
            return value

    def stats(self) -> dict[str, int | float]:
        """Return cache hit/miss stats (useful for dashboards)."""
        with self._lock:
            total = self._hits + self._misses
            ratio = (self._hits / total) if total else 0.0
            return {
                "size": len(self._data),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_ratio": round(ratio, 4),
            }

    def _evict_locked(self) -> None:
        """Caller must hold ``self._lock``."""
        # First drop expired entries so we don't evict live entries prematurely.
        now = self._clock()
        expired = [k for k, e in self._data.items() if e.expires_at <= now]
        for k in expired:
            del self._data[k]
        while len(self._data) > self._max_size:
            self._data.popitem(last=False)

    def _get_producer_lock(self, key: Any) -> threading.Lock:
        with self._producer_lock_guard:
            lock = self._producer_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._producer_locks[key] = lock
            return lock
