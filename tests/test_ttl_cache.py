"""Tests für services.cache.TTLCache."""

from __future__ import annotations

import threading

import pytest

from services.cache import TTLCache


class FakeClock:
    """Controllable monotonic clock for deterministic tests."""

    def __init__(self, start: float = 0.0) -> None:
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, delta: float) -> None:
        self.t += float(delta)


class TestTTLCacheBasics:
    def test_set_and_get(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10, max_size=4)
        c.set("a", 1)
        assert c.get("a") == 1

    def test_missing_key_returns_none(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10)
        assert c.get("missing") is None

    def test_contains(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10)
        c.set("x", 42)
        assert "x" in c
        assert "y" not in c

    def test_len(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10, max_size=10)
        assert len(c) == 0
        c.set("a", 1)
        c.set("b", 2)
        assert len(c) == 2

    def test_delete(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10)
        c.set("a", 1)
        c.delete("a")
        assert c.get("a") is None

    def test_delete_missing_key_is_noop(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10)
        c.delete("nope")  # should not raise

    def test_clear(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10)
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert len(c) == 0


class TestTTLCacheExpiry:
    def test_expires_after_ttl(self):
        clock = FakeClock()
        c: TTLCache[int] = TTLCache(ttl_seconds=5, clock=clock)
        c.set("k", 1)
        clock.advance(4.9)
        assert c.get("k") == 1
        clock.advance(0.2)
        assert c.get("k") is None

    def test_per_entry_ttl_override(self):
        clock = FakeClock()
        c: TTLCache[int] = TTLCache(ttl_seconds=100, clock=clock)
        c.set("short", 1, ttl=2)
        c.set("long", 2, ttl=50)
        clock.advance(3)
        assert c.get("short") is None
        assert c.get("long") == 2

    def test_zero_ttl_is_ignored(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10)
        c.set("k", 1, ttl=0)
        assert c.get("k") is None


class TestTTLCacheLRU:
    def test_lru_eviction(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=100, max_size=3)
        c.set("a", 1)
        c.set("b", 2)
        c.set("c", 3)
        # Access a, so b becomes LRU
        c.get("a")
        c.set("d", 4)  # should evict b
        assert c.get("b") is None
        assert c.get("a") == 1
        assert c.get("c") == 3
        assert c.get("d") == 4

    def test_set_refreshes_lru_position(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=100, max_size=2)
        c.set("a", 1)
        c.set("b", 2)
        c.set("a", 10)  # a becomes MRU
        c.set("c", 3)  # should evict b
        assert c.get("b") is None
        assert c.get("a") == 10
        assert c.get("c") == 3


class TestTTLCacheGetOrSet:
    def test_get_or_set_runs_producer_once(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10)
        calls = {"n": 0}

        def producer() -> int:
            calls["n"] += 1
            return 99

        assert c.get_or_set("k", producer) == 99
        assert c.get_or_set("k", producer) == 99
        assert calls["n"] == 1

    def test_get_or_set_thundering_herd(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10)
        calls = {"n": 0}
        start = threading.Event()

        def producer() -> int:
            calls["n"] += 1
            return 7

        def worker() -> None:
            start.wait()
            c.get_or_set("shared", producer)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        start.set()
        for t in threads:
            t.join()
        assert calls["n"] == 1


class TestTTLCacheStats:
    def test_hit_miss_counts(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10)
        c.set("a", 1)
        c.get("a")  # hit
        c.get("a")  # hit
        c.get("b")  # miss
        stats = c.stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert 0 < stats["hit_ratio"] <= 1.0

    def test_stats_on_empty_cache(self):
        c: TTLCache[int] = TTLCache(ttl_seconds=10)
        stats = c.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_ratio"] == 0.0


class TestTTLCacheValidation:
    def test_ttl_must_be_positive(self):
        with pytest.raises(ValueError):
            TTLCache(ttl_seconds=0)

    def test_max_size_must_be_positive(self):
        with pytest.raises(ValueError):
            TTLCache(ttl_seconds=10, max_size=0)
