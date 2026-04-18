"""Tests für services.rate_limiter."""

from __future__ import annotations

import threading

import pytest

from services.rate_limiter import RateLimiter


class FakeClock:
    """Controllable monotonic clock for deterministic tests."""

    def __init__(self, start: float = 0.0):
        self.t = float(start)

    def __call__(self) -> float:
        return self.t

    def advance(self, delta: float) -> None:
        self.t += float(delta)


class TestRateLimiter:
    def test_initial_capacity(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=3, refill_per_sec=1, clock=clock)
        assert rl.acquire("k") is True
        assert rl.acquire("k") is True
        assert rl.acquire("k") is True
        assert rl.acquire("k") is False

    def test_refill(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=2, refill_per_sec=1, clock=clock)
        rl.acquire("k")
        rl.acquire("k")
        assert rl.acquire("k") is False
        clock.advance(1.0)
        assert rl.acquire("k") is True
        assert rl.acquire("k") is False

    def test_keys_isolated(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=1, refill_per_sec=1, clock=clock)
        assert rl.acquire("a") is True
        assert rl.acquire("a") is False
        assert rl.acquire("b") is True

    def test_retry_after(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=1, refill_per_sec=2, clock=clock)
        rl.acquire("k")
        assert rl.retry_after("k") == pytest.approx(0.5)

    def test_cost_greater_than_capacity(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=2, refill_per_sec=1, clock=clock)
        assert rl.acquire("k", cost=5) is False  # cannot satisfy
        assert rl.acquire("k", cost=2) is True  # regular path still works

    def test_reset_key(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=1, refill_per_sec=1, clock=clock)
        rl.acquire("k")
        rl.reset("k")
        assert rl.acquire("k") is True

    def test_reset_all(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=1, refill_per_sec=1, clock=clock)
        rl.acquire("k1")
        rl.acquire("k2")
        rl.reset()
        assert rl.stats()["tracked_keys"] == 0

    def test_lru_eviction(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=1, refill_per_sec=1, max_keys=5, clock=clock)
        for i in range(10):
            rl.acquire(f"k{i}")
        stats = rl.stats()
        # max_keys=5 → should not exceed the cap by much.
        assert stats["tracked_keys"] <= 5

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            RateLimiter(capacity=0)
        with pytest.raises(ValueError):
            RateLimiter(refill_per_sec=0)
        with pytest.raises(ValueError):
            RateLimiter(max_keys=0)

    def test_thread_safety(self):
        clock = FakeClock()
        rl = RateLimiter(capacity=100, refill_per_sec=1, clock=clock)
        acquired = [0]
        lock = threading.Lock()

        def worker():
            for _ in range(200):
                if rl.acquire("shared"):
                    with lock:
                        acquired[0] += 1

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Exactly 100 tokens available total (capacity), no refill (clock static).
        assert acquired[0] == 100

    def test_cost_zero_always_succeeds(self):
        rl = RateLimiter(capacity=1, refill_per_sec=1)
        # consume capacity
        rl.acquire("k")
        assert rl.acquire("k", cost=0) is True
