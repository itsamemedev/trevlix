"""Shared WebSocket guard helpers.

Currently this module centralizes Socket.IO in-memory rate-limiting so that
`server.py` and migration modules can share one tested implementation.
"""

from __future__ import annotations

import threading
import time


class WsRateLimiter:
    """In-memory event limiter keyed by ``<sid>:<action>``."""

    def __init__(
        self,
        *,
        cleanup_interval_sec: float = 60.0,
        stale_after_sec: float = 300.0,
        max_entries: int = 5000,
    ) -> None:
        self._limits: dict[str, float] = {}
        self._last_cleanup = 0.0
        self._lock = threading.Lock()
        self._cleanup_interval_sec = cleanup_interval_sec
        self._stale_after_sec = stale_after_sec
        self._max_entries = max_entries

    def check(self, sid: str, action: str, *, min_interval_sec: float = 2.0) -> bool:
        """Return ``True`` when event is allowed, ``False`` when rate-limited."""
        key = f"{sid}:{action}"
        now = time.time()
        with self._lock:
            last = self._limits.get(key, 0.0)
            if now - last < min_interval_sec:
                return False
            self._limits[key] = now

            if now - self._last_cleanup > self._cleanup_interval_sec:
                self._last_cleanup = now
                cutoff = now - self._stale_after_sec
                stale_keys = [k for k, ts in self._limits.items() if ts < cutoff]
                for stale in stale_keys:
                    self._limits.pop(stale, None)

            if len(self._limits) > self._max_entries:
                # LRU eviction: remove oldest 20% instead of clearing all
                sorted_keys = sorted(self._limits, key=self._limits.get)
                evict_count = max(1, len(sorted_keys) // 5)
                for old_key in sorted_keys[:evict_count]:
                    self._limits.pop(old_key, None)

        return True

    def size(self) -> int:
        """Expose current table size for diagnostics/tests."""
        with self._lock:
            return len(self._limits)
