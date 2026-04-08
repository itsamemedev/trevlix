"""Redis-backed market cache with in-memory fallback."""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

try:
    import redis
except Exception:  # noqa: BLE001
    redis = None

log = logging.getLogger("trevlix.redis_cache")


class RedisMarketCache:
    def __init__(self, url: str = "redis://localhost:6379/0", enabled: bool = True):
        self.enabled = bool(enabled)
        self._mem: dict[str, tuple[float | None, str]] = {}
        self._lock = threading.Lock()
        self._client = None
        if self.enabled and redis is not None:
            try:
                self._client = redis.from_url(url, decode_responses=True, socket_timeout=1.5)
                self._client.ping()
                log.info("✅ Redis Market Cache verbunden: %s", url)
            except Exception as exc:  # noqa: BLE001
                log.warning("Redis nicht erreichbar (%s) – nutze In-Memory Cache", exc)
                self._client = None

    def _set(self, key: str, payload: dict[str, Any], ttl: int | None = None) -> None:
        encoded = json.dumps(payload, separators=(",", ":"))
        if self._client is not None:
            try:
                if ttl and ttl > 0:
                    self._client.setex(key, ttl, encoded)
                else:
                    self._client.set(key, encoded)
                return
            except Exception:  # noqa: BLE001
                pass
        exp = time.time() + ttl if ttl and ttl > 0 else None
        with self._lock:
            self._mem[key] = (exp, encoded)

    def _get(self, key: str) -> dict[str, Any] | None:
        raw = None
        if self._client is not None:
            try:
                raw = self._client.get(key)
            except Exception:  # noqa: BLE001
                raw = None
        if raw is None:
            with self._lock:
                rec = self._mem.get(key)
                if rec is None:
                    return None
                exp, encoded = rec
                if exp and exp < time.time():
                    self._mem.pop(key, None)
                    return None
                raw = encoded
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return None

    def set_ticker(self, exchange: str, symbol: str, ticker: dict[str, Any], ttl: int = 10) -> None:
        self._set(f"ticker:{exchange}:{symbol}", ticker, ttl)

    def get_ticker(self, exchange: str, symbol: str) -> dict[str, Any] | None:
        return self._get(f"ticker:{exchange}:{symbol}")

    def set_ohlcv(self, exchange: str, symbol: str, tf: str, ohlcv: list[list[float]], ttl: int = 30) -> None:
        self._set(f"ohlcv:{exchange}:{symbol}:{tf}", {"rows": ohlcv}, ttl)

    def get_ohlcv(self, exchange: str, symbol: str, tf: str) -> list[list[float]] | None:
        data = self._get(f"ohlcv:{exchange}:{symbol}:{tf}")
        if not data:
            return None
        rows = data.get("rows")
        return rows if isinstance(rows, list) else None

    def set_snapshot(self, exchange: str, symbol: str, snapshot: dict[str, Any], ttl: int = 20) -> None:
        self._set(f"snapshot:{exchange}:{symbol}", snapshot, ttl)

    def get_snapshot(self, exchange: str, symbol: str) -> dict[str, Any] | None:
        return self._get(f"snapshot:{exchange}:{symbol}")
